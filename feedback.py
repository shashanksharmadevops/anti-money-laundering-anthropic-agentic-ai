"""
Feedback loop for the AML Investigation Copilot.

Every time a human analyst Approves, Edits, or Rejects a draft investigation,
that decision is logged here. Recent feedback (especially edits and rejections,
where the agent's draft differed from the analyst's judgment) is surfaced back
to the orchestrator as few-shot context, so the agent's future drafts trend
toward how this team's analysts actually decide.

This is a lightweight file-backed store for demo purposes. Swap FEEDBACK_PATH
for a real DB table in production.
"""

import json
from datetime import datetime
from pathlib import Path
from threading import Lock

FEEDBACK_PATH = Path(__file__).parent / "data" / "feedback_log.json"
_lock = Lock()


def _read_all() -> list:
    if not FEEDBACK_PATH.exists():
        return []
    with open(FEEDBACK_PATH) as f:
        return json.load(f)


def _write_all(records: list):
    with open(FEEDBACK_PATH, "w") as f:
        json.dump(records, f, indent=2)


def log_feedback(alert_id: str, agent_risk_score: int, agent_recommendation: str,
                  agent_narrative: str, decision: str, final_narrative: str = None,
                  analyst_notes: str = None, audit_trail: list = None) -> dict:
    """
    decision must be one of: "approved", "edited", "rejected"
    """
    with _lock:
        records = _read_all()
        entry = {
            "feedback_id": f"FB-{len(records) + 1:04d}",
            "alert_id": alert_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent_risk_score": agent_risk_score,
            "agent_recommendation": agent_recommendation,
            "agent_narrative": agent_narrative,
            "decision": decision,  # approved | edited | rejected
            "final_narrative": final_narrative or agent_narrative,
            "analyst_notes": analyst_notes or "",
            "tool_calls_made": len(audit_trail) if audit_trail else None,
        }
        records.append(entry)
        _write_all(records)
        return entry


def get_all_feedback() -> list:
    return _read_all()


def get_feedback_examples(limit: int = 3) -> str:
    """
    Returns recent 'edited' or 'rejected' feedback formatted as few-shot context
    to inject into the orchestrator's system prompt. These are the cases where the
    agent's draft and the analyst's judgment diverged — the most useful signal for
    steering future drafts.
    """
    records = _read_all()
    corrective = [r for r in records if r["decision"] in ("edited", "rejected")]
    corrective = corrective[-limit:]

    if not corrective:
        return ""

    blocks = []
    for r in corrective:
        blocks.append(
            f"--- Past case {r['alert_id']} (analyst {r['decision']} this draft) ---\n"
            f"Agent's original recommendation: {r['agent_recommendation']} "
            f"(risk score {r['agent_risk_score']})\n"
            f"Analyst notes: {r['analyst_notes'] or '(none provided)'}\n"
            f"Analyst's final narrative differed as follows: "
            f"{'see final_narrative in feedback log' if r['decision'] == 'edited' else 'draft was rejected outright'}"
        )

    return (
        "\n\nLEARNING FROM PAST ANALYST FEEDBACK:\n"
        "The following are recent cases where a human analyst edited or rejected your "
        "team's draft investigation. Use these to calibrate your risk scoring and "
        "recommendations — do not repeat the same misjudgment:\n\n"
        + "\n\n".join(blocks)
    )
