"""
AML Investigation Copilot — API server

Serves:
  - GET  /api/alerts                 list all alerts
  - GET  /api/alerts/{alert_id}      alert detail
  - POST /api/investigate/{alert_id} run the agent, return draft summary + audit trail
  - GET  /api/network/{customer_id}  graph data (nodes/edges) for the related-party network
  - POST /api/decision               analyst approves/edits/rejects a draft -> logs feedback
  - GET  /api/feedback                full feedback log (for a "history" view)
  - GET  /                            the review UI
"""

import sys
import json
from pathlib import Path

from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent))  # allow importing sibling modules

from tools import _load  # reuse the same data loader
import orchestrator
import feedback as feedback_module

app = FastAPI(title="AML Investigation Copilot")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class DecisionPayload(BaseModel):
    alert_id: str
    decision: str  # "approved" | "edited" | "rejected"
    agent_risk_score: Optional[int] = None
    agent_recommendation: Optional[str] = None
    agent_narrative: Optional[str] = None
    final_narrative: Optional[str] = None
    analyst_notes: Optional[str] = None
    tool_call_count: Optional[int] = None


@app.get("/")
def serve_ui():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/alerts")
def list_alerts():
    alerts = _load("alerts")
    customers = {c["customer_id"]: c for c in _load("customers")}
    for a in alerts:
        cust = customers.get(a["customer_id"], {})
        a["customer_name"] = cust.get("full_name", "Unknown")
    return alerts


@app.get("/api/alerts/{alert_id}")
def get_alert_detail(alert_id: str):
    alerts = {a["alert_id"]: a for a in _load("alerts")}
    if alert_id not in alerts:
        raise HTTPException(404, f"Alert {alert_id} not found")
    return alerts[alert_id]


@app.post("/api/investigate/{alert_id}")
def investigate(alert_id: str):
    alerts = {a["alert_id"]: a for a in _load("alerts")}
    if alert_id not in alerts:
        raise HTTPException(404, f"Alert {alert_id} not found")
    try:
        result = orchestrator.run_investigation(alert_id, verbose=False, use_feedback=True)
    except Exception as e:
        raise HTTPException(500, f"Investigation failed: {e}")
    return result


@app.get("/api/network/{customer_id}")
def network_graph(customer_id: str):
    customers = {c["customer_id"]: c for c in _load("customers")}
    related = _load("related_parties")

    if customer_id not in customers:
        raise HTTPException(404, f"Customer {customer_id} not found")

    node_ids = {customer_id}
    edges = []
    for r in related:
        if r["primary_customer_id"] == customer_id or r["related_customer_id"] == customer_id:
            node_ids.add(r["primary_customer_id"])
            node_ids.add(r["related_customer_id"])
            edges.append({
                "source": r["primary_customer_id"],
                "target": r["related_customer_id"],
                "relationship_type": r["relationship_type"],
                "strength": r["relationship_strength"],
            })

    nodes = []
    for nid in node_ids:
        c = customers.get(nid, {})
        nodes.append({
            "id": nid,
            "label": c.get("full_name", nid),
            "risk_rating": c.get("kyc_risk_rating", "Unknown"),
            "is_business_entity": c.get("is_business_entity", False),
            "is_center": nid == customer_id,
        })

    return {"nodes": nodes, "edges": edges}


@app.post("/api/decision")
def submit_decision(payload: DecisionPayload):
    if payload.decision not in ("approved", "edited", "rejected"):
        raise HTTPException(400, "decision must be one of: approved, edited, rejected")

    entry = feedback_module.log_feedback(
        alert_id=payload.alert_id,
        agent_risk_score=payload.agent_risk_score or 0,
        agent_recommendation=payload.agent_recommendation or "",
        agent_narrative=payload.agent_narrative or "",
        decision=payload.decision,
        final_narrative=payload.final_narrative,
        analyst_notes=payload.analyst_notes,
        audit_trail=[{} for _ in range(payload.tool_call_count or 0)],
    )
    return entry


@app.get("/api/feedback")
def list_feedback():
    return feedback_module.get_all_feedback()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)