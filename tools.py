"""
Tool layer for the AML Investigation Copilot.
These are the functions exposed to the orchestrator agent as "tools" it can call
via Claude's tool-use / function-calling interface.

Each function returns plain dicts/lists so they can be dropped straight into a
tool_result block.
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

def _load(name):
    with open(DATA_DIR / f"{name}.json") as f:
        return json.load(f)

_customers = {c["customer_id"]: c for c in _load("customers")}
_transactions = _load("transactions")
_related_parties = _load("related_parties")
_watchlist = _load("watchlist")
_typologies = _load("typologies")
_alerts = {a["alert_id"]: a for a in _load("alerts")}


def get_alert(alert_id: str) -> dict:
    """Fetch the original alert that triggered the investigation."""
    return _alerts.get(alert_id, {"error": f"Alert {alert_id} not found"})


def get_customer_profile(customer_id: str) -> dict:
    """Fetch KYC profile for a customer."""
    return _customers.get(customer_id, {"error": f"Customer {customer_id} not found"})


def get_transaction_history(customer_id: str) -> list:
    """Fetch all transactions for a given customer."""
    return [t for t in _transactions if t["customer_id"] == customer_id]


def get_related_parties(customer_id: str) -> list:
    """Fetch related/linked accounts for a customer (network view)."""
    return [r for r in _related_parties
            if r["primary_customer_id"] == customer_id or r["related_customer_id"] == customer_id]


def _normalize(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum() or ch.isspace()).strip()


def check_sanctions_pep(full_name: str, date_of_birth: str = None) -> dict:
    """
    Screen a name (and optionally DOB) against the sanctions/PEP watchlist.

    Returns tiered results so the agent can reason about match confidence rather than
    treating every name hit as equally suspicious:
      - CONFIRMED  : name matches (primary or alias) AND date of birth matches
      - NAME_ONLY  : name matches but DOB differs or is unavailable -> likely false positive,
                     needs further verification
      - ALIAS_FUZZY: name is a close spelling variant of a listed alias (not exact) -> flagged
                     for manual review, common in real-world alias/transliteration cases
      - NONE       : no meaningful match
    """
    import difflib

    query_norm = _normalize(full_name)
    results = []

    for entry in _watchlist:
        candidates = [entry["full_name"]] + entry.get("aliases", [])
        best_ratio = 0.0
        best_candidate = None
        exact_hit = False

        for cand in candidates:
            cand_norm = _normalize(cand)
            if cand_norm == query_norm:
                exact_hit = True
                best_candidate = cand
                best_ratio = 1.0
                break
            ratio = difflib.SequenceMatcher(None, query_norm, cand_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_candidate = cand

        if exact_hit:
            dob_match = date_of_birth is not None and date_of_birth == entry.get("date_of_birth")
            results.append({
                "watchlist_id": entry["watchlist_id"],
                "matched_on": best_candidate,
                "match_type": "CONFIRMED" if dob_match else "NAME_ONLY",
                "confidence": "High" if dob_match else "Medium",
                "list_type": entry["list_type"],
                "list_source": entry["list_source"],
                "notes": entry["notes"],
                "watchlist_dob": entry.get("date_of_birth"),
                "dob_provided_matches": dob_match,
            })
        elif best_ratio >= 0.82:  # close spelling variant, not exact
            results.append({
                "watchlist_id": entry["watchlist_id"],
                "matched_on": best_candidate,
                "match_type": "ALIAS_FUZZY",
                "confidence": "Medium",
                "similarity_score": round(best_ratio, 2),
                "list_type": entry["list_type"],
                "list_source": entry["list_source"],
                "notes": entry["notes"],
                "watchlist_dob": entry.get("date_of_birth"),
                "dob_provided_matches": date_of_birth is not None and date_of_birth == entry.get("date_of_birth"),
            })

    return {
        "match_found": len(results) > 0,
        "match_count": len(results),
        "matches": results,
        "guidance": (
            "CONFIRMED matches should be escalated immediately. NAME_ONLY and ALIAS_FUZZY "
            "matches require further verification (DOB, nationality, other identifiers) "
            "before concluding — do not auto-escalate on name similarity alone."
        ),
    }


def search_adverse_media(full_name: str) -> dict:
    """
    Simulated adverse media search. In production this would hit a news/media API.
    For demo purposes, returns a canned hit only for the PEP test case.
    """
    if "government official" in str(_customers.get(
            next((cid for cid, c in _customers.items() if c["full_name"] == full_name), ""), {}
    ).get("occupation", "")).lower():
        return {
            "hits_found": 1,
            "articles": [{
                "headline": "[SIMULATED] Local official under review for undisclosed offshore consulting income",
                "source": "Simulated Wire Service",
                "date": "2026-06-15",
                "relevance": "Medium",
            }]
        }
    return {"hits_found": 0, "articles": []}


def get_typology_library() -> list:
    """Fetch the reference library of AML typologies and their red flags."""
    return _typologies


TOOL_REGISTRY = {
    "get_alert": get_alert,
    "get_customer_profile": get_customer_profile,
    "get_transaction_history": get_transaction_history,
    "get_related_parties": get_related_parties,
    "check_sanctions_pep": check_sanctions_pep,
    "search_adverse_media": search_adverse_media,
    "get_typology_library": get_typology_library,
}

# Anthropic tool-use schema definitions — pass these in the `tools` param of the API call
TOOL_SCHEMAS = [
    {
        "name": "get_alert",
        "description": "Fetch the original transaction-monitoring alert that triggered this investigation.",
        "input_schema": {"type": "object", "properties": {
            "alert_id": {"type": "string", "description": "e.g. ALERT-9001"}
        }, "required": ["alert_id"]},
    },
    {
        "name": "get_customer_profile",
        "description": "Fetch the KYC profile for a customer, including risk rating, occupation, and income.",
        "input_schema": {"type": "object", "properties": {
            "customer_id": {"type": "string"}
        }, "required": ["customer_id"]},
    },
    {
        "name": "get_transaction_history",
        "description": "Fetch all transactions for a customer.",
        "input_schema": {"type": "object", "properties": {
            "customer_id": {"type": "string"}
        }, "required": ["customer_id"]},
    },
    {
        "name": "get_related_parties",
        "description": "Fetch related/linked accounts and entities for a customer (network view).",
        "input_schema": {"type": "object", "properties": {
            "customer_id": {"type": "string"}
        }, "required": ["customer_id"]},
    },
    {
        "name": "check_sanctions_pep",
        "description": "Screen a person's name and date of birth against sanctions and PEP watchlists.",
        "input_schema": {"type": "object", "properties": {
            "full_name": {"type": "string"},
            "date_of_birth": {"type": "string"}
        }, "required": ["full_name"]},
    },
    {
        "name": "search_adverse_media",
        "description": "Search for adverse media / negative news associated with a person's name.",
        "input_schema": {"type": "object", "properties": {
            "full_name": {"type": "string"}
        }, "required": ["full_name"]},
    },
    {
        "name": "get_typology_library",
        "description": "Fetch the reference library of money-laundering typologies and their known red flags, "
                        "to match against gathered evidence.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]
