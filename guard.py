"""Guarded Incident Assistant: the execution boundary between an untrusted planner and tenant data.

Trust model
- Untrusted: every proposal (tool name, args, extra keys) and every alert/asset body.
- Trusted: the session -> principal lookup in the fixture store (a MOCK identity provider,
  not real authentication) and the state held in this object.
- approve() and execute_approved() are human-interface calls. They are deliberately absent
  from the model-callable tool table, so no proposal can reach them.
"""
import json
import time
import uuid
from pathlib import Path

FIXTURES = Path(__file__).with_name("fixtures.json")

MAX_ATTEMPTS = 3  # per execute_plan call, denied attempts included
MAX_ID, MAX_TITLE, MAX_SUMMARY = 64, 120, 1000

# One public category for "does not exist" and "belongs to someone else",
# so a denial never confirms that another tenant's object exists.
NOT_FOUND = "not_found_or_forbidden"

# Model-callable allowlist: tool -> {argument: max length}. Keys must match exactly.
SCHEMAS = {
    "get_alert": {"alert_id": MAX_ID},
    "get_asset": {"asset_id": MAX_ID},
    "propose_ticket": {"alert_id": MAX_ID, "title": MAX_TITLE, "summary": MAX_SUMMARY},
}


class Denied(Exception):
    """Raised inside the boundary. Only its category string crosses it."""


def _validate(proposal):
    """Shape check only. Returns (tool, args) or raises Denied. Authority is checked later."""
    if not isinstance(proposal, dict) or set(proposal) != {"tool", "args"}:
        raise Denied("malformed_proposal")
    tool, args = proposal["tool"], proposal["args"]
    if not isinstance(tool, str) or tool not in SCHEMAS:
        raise Denied("unknown_tool")
    schema = SCHEMAS[tool]
    if not isinstance(args, dict) or set(args) != set(schema):
        raise Denied("invalid_arguments")  # includes spoofed tenant_id / role / approved keys
    for key, limit in schema.items():
        value = args[key]
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise Denied("invalid_arguments")
    return tool, args


class Assistant:
    # ponytail: in-memory, single-threaded state. Restart loses proposals/tickets and
    # concurrent execute_approved calls could double-create. Upgrade path: a transactional
    # store with a unique constraint on ticket.proposal_id.
    def __init__(self, fixtures=None):
        fx = fixtures if fixtures is not None else json.loads(FIXTURES.read_text())
        self.sessions = fx["sessions"]
        self.alerts = {a["id"]: a for a in fx["alerts"]}
        self.assets = {a["id"]: a for a in fx["assets"]}
        self.proposals = {}  # proposal_id -> stored action, owner, tenant, state
        self.tickets = {}    # ticket_id -> ticket (the side effect)
        self.audit = []      # one record per real side effect
        self._tools = {
            "get_alert": self._get_alert,
            "get_asset": self._get_asset,
            "propose_ticket": self._propose_ticket,
        }

    # --- authority -------------------------------------------------------

    def _principal(self, session_id):
        principal = self.sessions.get(session_id) if isinstance(session_id, str) else None
        if principal is None:
            raise Denied("unknown_session")
        return principal

    def _owned(self, table, obj_id, principal):
        obj = table.get(obj_id)
        if obj is None or obj["tenant_id"] != principal["tenant_id"]:
            raise Denied(NOT_FOUND)
        return obj

    # --- model-callable tools (args already shape-validated) --------------

    def _get_alert(self, principal, run_id, args):
        return "ok", dict(self._owned(self.alerts, args["alert_id"], principal))

    def _get_asset(self, principal, run_id, args):
        return "ok", dict(self._owned(self.assets, args["asset_id"], principal))

    def _propose_ticket(self, principal, run_id, args):
        self._owned(self.alerts, args["alert_id"], principal)
        proposal_id = "P-" + uuid.uuid4().hex[:12]
        self.proposals[proposal_id] = {
            "id": proposal_id,
            "owner": principal["user_id"],
            "tenant_id": principal["tenant_id"],
            "run_id": run_id,
            "payload": dict(args),  # the complete action, frozen here
            "state": "pending",
            "ticket_id": None,
        }
        # The payload is echoed so the human sees exactly what they would approve.
        return "pending_approval", {"proposal_id": proposal_id, "state": "pending", "payload": dict(args)}

    # --- public interface -------------------------------------------------

    def execute_plan(self, session_id, run_id, proposals):
        try:
            principal = self._principal(session_id)
            if not isinstance(run_id, str) or not run_id or len(run_id) > MAX_ID or not isinstance(proposals, list):
                raise Denied("invalid_request")
        except Denied as denied:
            return {"status": "denied", "category": str(denied)}

        results, trace, pending = [], [], []
        for step, proposal in enumerate(proposals[:MAX_ATTEMPTS], 1):  # attempt 4+ is never dispatched
            start = time.perf_counter()
            # Only allowlisted names reach the trace; an unknown tool name is model-controlled text.
            named = proposal.get("tool") if isinstance(proposal, dict) else None
            tool = named if isinstance(named, str) and named in SCHEMAS else "unknown"
            data = None
            try:
                _, args = _validate(proposal)
                category, data = self._tools[tool](principal, run_id, args)
                decision = "allow"
                if category == "pending_approval":
                    pending.append(data["proposal_id"])
            except Denied as denied:
                decision, category = "deny", str(denied)
            result = {"step": step, "tool": tool, "decision": decision, "category": category}
            if data is not None:
                result["data"] = data
            results.append(result)
            trace.append({
                "run_id": run_id,
                "user_id": principal["user_id"],
                "tenant_id": principal["tenant_id"],
                "step": step,
                "tool": tool,
                "decision": decision,
                "category": category,
                "duration_ms": round((time.perf_counter() - start) * 1000, 3),
            })
        return {
            "run_id": run_id,
            # Honest state: a pending proposal is not a ticket. This call never creates one.
            "status": "awaiting_approval" if pending else "finished_nothing_pending",
            "pending_proposal_ids": pending,
            "tickets_created": 0,
            "attempts": len(trace),
            "skipped_over_budget": max(0, len(proposals) - MAX_ATTEMPTS),
            "results": results,
            "trace": trace,
        }

    def _owned_proposal(self, session_id, proposal_id):
        """Every check runs on every approve AND execute call: owner, permission, alert tenant."""
        principal = self._principal(session_id)
        proposal = self.proposals.get(proposal_id) if isinstance(proposal_id, str) else None
        if proposal is None or (proposal["owner"], proposal["tenant_id"]) != (principal["user_id"], principal["tenant_id"]):
            raise Denied(NOT_FOUND)
        if principal.get("can_create_ticket") is not True:
            raise Denied("permission_denied")
        self._owned(self.alerts, proposal["payload"]["alert_id"], principal)
        return principal, proposal

    def approve(self, session_id, proposal_id):
        """Trusted human-interface call. Not in SCHEMAS, so the model cannot invoke it."""
        try:
            _, proposal = self._owned_proposal(session_id, proposal_id)
        except Denied as denied:
            return {"status": "denied", "category": str(denied)}
        if proposal["state"] == "pending":
            proposal["state"] = "approved"
        return {"status": proposal["state"], "proposal_id": proposal["id"], "payload": dict(proposal["payload"])}

    def execute_approved(self, session_id, proposal_id):
        """Takes no payload: the ticket is built only from what was stored at proposal time."""
        try:
            principal, proposal = self._owned_proposal(session_id, proposal_id)
            if proposal["state"] == "pending":
                raise Denied("not_approved")
        except Denied as denied:
            return {"status": "denied", "category": str(denied)}
        replayed = proposal["state"] == "executed"
        if not replayed:
            ticket_id = "T-" + uuid.uuid4().hex[:12]
            self.tickets[ticket_id] = {
                "id": ticket_id,
                "tenant_id": proposal["tenant_id"],
                "created_by": principal["user_id"],
                "proposal_id": proposal["id"],
                **proposal["payload"],
            }
            self.audit.append({
                "event": "ticket_created",
                "ticket_id": ticket_id,
                "proposal_id": proposal["id"],
                "user_id": principal["user_id"],
                "tenant_id": proposal["tenant_id"],
                "alert_id": proposal["payload"]["alert_id"],
            })
            proposal["state"], proposal["ticket_id"] = "executed", ticket_id
        return {
            "status": "executed",
            "ticket_id": proposal["ticket_id"],
            "replayed": replayed,
            "ticket": dict(self.tickets[proposal["ticket_id"]]),
        }
