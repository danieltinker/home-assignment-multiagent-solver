# Guarded Incident Assistant (practice exercise)

**This is an invented practice take-home, not an employer assignment.** All data is synthetic.
No model, network, credential or paid service is used.

A model plans an alert investigation and proposes a ticket. The model may be wrong or hostile.
This project is the execution boundary: allowed work succeeds, unsafe proposed actions do not run.

## Run

Needs Python 3.10+ and nothing else.

```bash
python3 -m unittest -v
```

```bash
python3 demo.py
```

The demo shows one successful investigation (read alert, read asset, propose, approve, execute),
one rejected cross-tenant plan, and the evaluation counts.

## Files

| File | Role |
|---|---|
| `guard.py` | The boundary: validation, tenant policy, proposal/approval/execution state, trace |
| `planner.py` | Deterministic fake planner. Its output is untrusted |
| `fixtures.json` | Synthetic sessions, alerts, assets |
| `demo.py` | Demo and evaluation report |
| `test_guard.py` | The 12 required tests plus 6 extras |

## Trust boundary

```
 UNTRUSTED                         |  TRUSTED (guard.Assistant)
                                   |
 fake planner / model              |  1. session_id -> principal   (fixture lookup, mock IdP)
   proposals: tool, args  -------->|  2. shape check: allowlist, exact keys, types, lengths
                                   |  3. tenant check on every referenced alert/asset
 alert and asset bodies            |  4. dispatch, at most 3 attempts per call
   (returned as data only)  <------|     get_alert / get_asset  -> data
                                   |     propose_ticket         -> PENDING proposal, stored
 ----------------------------------|
 HUMAN INTERFACE (not a tool)      |
   approve(session, proposal_id) ->|  owner + permission + tenant rechecked
   execute_approved(...)  -------->|  same checks again; ticket built from STORED payload
                                   |  ticket + one audit record, once
```

Authority comes from one place: the session-to-principal lookup. Nothing in a proposal can add to it.

## Design decisions

- **Exact-key schemas.** A proposal must be `{"tool", "args"}` and `args` must match the tool's
  keys exactly. A spoofed `tenant_id`, `role` or `approved` is rejected as `invalid_arguments`.
  It is never read, so it cannot be honoured by accident.
- **One denial category for missing and foreign objects** (`not_found_or_forbidden`). A denial does
  not confirm that another tenant's alert, asset or proposal exists.
- **Approval is not a tool.** `approve` and `execute_approved` are methods outside the model-callable
  table. A proposal naming them is an unknown tool.
- **Execution takes no payload.** `execute_approved(session_id, proposal_id)` builds the ticket from
  what was stored at proposal time. Later model output cannot change it.
- **Checks repeat.** Owner, `can_create_ticket` and alert tenant are checked at approval and again at
  execution. A permission revoked after approval blocks execution.
- **Owner is the principal** (`user_id` + `tenant_id`), not the session string. A same-tenant colleague
  cannot run someone else's proposal.
- **Idempotency lives on the proposal.** The proposal stores its `ticket_id`. A replay returns the same
  ticket with `replayed: true` and writes no second audit record.
- **Budget counts attempts, not successes.** Only the first 3 proposals of a call are looked at.
  Denied ones count. The rest are reported as `skipped_over_budget`.
- **A denied step does not abort the plan.** Each attempt is judged alone, so the trace shows every
  decision. Stopping at the first denial would also be defensible.
- **Honest states.** `execute_plan` returns `awaiting_approval` or `finished_nothing_pending`, and
  `tickets_created` is always 0 there. Only `execute_approved` reports `executed`.
- **Trace holds categories, not content.** Run ID, principal, tenant, step, tool, allow/deny, category,
  duration. An unknown tool name is logged as `unknown` because the model chose that text.
- **A read-only user cannot propose.** `propose_ticket` is denied with `permission_denied` when the
  principal lacks `can_create_ticket`. Otherwise the call would report `awaiting_approval` for a
  proposal nobody could ever approve. (Changed after review finding G1.)
- **Random proposal and ticket IDs.** They avoid leaking counts across tenants. Access control does not
  depend on them being secret.

## Evaluation report

Output of `python3 demo.py` on this suite:

```
Allowed-task completion:   3/3
Forbidden execution:       0/12 (target 0)
Unauthorized disclosure:   0 of 17 outputs contain the beta canary (target 0)
Replay correctness:        PASS (same ticket ID, 1 ticket, 1 audit record)
Budget enforcement:        PASS (max 3 attempts per call)
```

The 12 forbidden attempts: cross-tenant read, unknown tool, forged tenant argument, execute before
approval, other tenant approves, other tenant executes, read-only proposes, read-only approves,
read-only executes, a fourth proposal, oversized title, wrong argument type.

These are counts over a small fixed synthetic suite. They show the demonstrated cases hold. They are
not a security guarantee, and they are not precision or recall: nothing here classifies anything.
The adversarial proposals are fed straight to the boundary, so this says nothing about whether a real
model resists prompt injection.

## Known limitations

- **Mock identity.** A session ID is a caller-supplied string mapped to a fixture principal. Anyone who
  knows `session-a` is Alice. Real use needs vetted authentication.
- **In-memory state.** A restart loses proposals, tickets and audit records, and with them idempotency.
- **Not concurrency-safe.** Two simultaneous `execute_approved` calls could both create a ticket.
  Not implemented and not tested. The fix is a transactional store with a unique constraint on
  `ticket.proposal_id`.
- **Budget is per call.** A caller can call `execute_plan` again. There is no per-tenant rate or spend
  limit, and pending proposals are never expired.
- **Returned alert text is still hostile.** The boundary returns A-2's body as data. A real model that
  reads it may be steered. What it then proposes is still checked, which is all this project claims.
- **Audit covers ticket creation only.** Denials appear in the per-call trace, not in a durable log.
- **Approval shows the payload but nothing renders it.** There is no UI. The stored payload is returned
  by `propose_ticket` and `approve` for a human to read.

For production: real authentication, durable transactional state, scoped service identities,
per-tenant rate and budget accounting, timeouts and cancellation, deployment health checks, protected
audit retention.

## AI-use disclosure

Written with Claude Code (Anthropic) as the implementing assistant, from the practice brief, directed
by Daniel Baruch. The code and tests were AI-drafted. The tests and demo were run locally and the
results above are from that run. A second AI assistant (Grok) reviewed commit `ccb5dae` read-only and
reported three findings, relayed by Daniel; all three are fixed here and listed in `WORKLOG.md`.
The reviewer had not re-verified this revision when it was committed.
