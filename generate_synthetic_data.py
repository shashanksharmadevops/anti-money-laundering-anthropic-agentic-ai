"""
Synthetic Data Generator for AML Investigation Copilot Demo
=============================================================
Generates realistic (but entirely fake) datasets:
  - customers.json        : KYC profiles
  - transactions.json     : transaction history, with embedded suspicious patterns
  - related_parties.json  : account network / linked entities
  - watchlist.json        : sanctions / PEP list
  - typologies.json       : reference library of ML typologies
  - alerts.json           : pre-built alerts that reference the above data

Run: python3 generate_synthetic_data.py
Outputs land in ./data/
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)  # reproducible demo data

OUT_DIR = Path(__file__).parent / "data"
OUT_DIR.mkdir(exist_ok=True)

FIRST_NAMES = ["James", "Maria", "Wei", "Fatima", "Carlos", "Anna", "Raj", "Elena",
               "Michael", "Priya", "David", "Sofia", "Ahmed", "Linda", "Kenji", "Olga"]
LAST_NAMES = ["Smith", "Garcia", "Chen", "Khan", "Rossi", "Kowalski", "Patel", "Novak",
              "Johnson", "Silva", "Muller", "Ivanov", "Tanaka", "Diallo", "Nguyen", "Brown"]
CITIES = ["Toronto", "New York", "London", "Dubai", "Singapore", "Miami", "Hong Kong", "Zurich"]
COUNTRIES_LOW_RISK = ["Canada", "United States", "United Kingdom", "Germany", "Australia"]
COUNTRIES_HIGH_RISK = ["Country_A_HighRisk", "Country_B_Sanctioned", "Country_C_TaxHaven"]
BUSINESS_TYPES = ["Retail Trading Co", "Import/Export LLC", "Consulting Services",
                   "Real Estate Holdings", "Restaurant Group", "Shell Corp Ventures"]

def rand_date(days_back_start, days_back_end):
    days = random.randint(days_back_end, days_back_start)
    return (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

def gen_customer(customer_id, risk_profile="normal"):
    """risk_profile: 'normal' | 'structuring' | 'layering' | 'pep' | 'shell'"""
    name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
    country = random.choice(COUNTRIES_HIGH_RISK if risk_profile in ("layering", "shell") else COUNTRIES_LOW_RISK)
    customer = {
        "customer_id": customer_id,
        "full_name": name,
        "date_of_birth": rand_date(25000, 18000),
        "nationality": country,
        "residence_city": random.choice(CITIES),
        "account_open_date": rand_date(3000, 400),
        "account_type": random.choice(["Personal Checking", "Business Checking", "Savings"]),
        "occupation": random.choice(["Business Owner", "Consultant", "Import/Export Trader",
                                      "Real Estate Agent", "Government Official", "Retail Manager"]),
        "declared_annual_income_usd": random.choice([45000, 65000, 90000, 120000, 250000]),
        "kyc_risk_rating": {"normal": "Low", "structuring": "Medium",
                             "layering": "High", "pep": "High", "shell": "High"}[risk_profile],
        "is_business_entity": risk_profile == "shell",
    }
    if risk_profile == "shell":
        customer["business_name"] = f"{random.choice(BUSINESS_TYPES)} #{random.randint(100,999)}"
        customer["incorporation_country"] = random.choice(COUNTRIES_HIGH_RISK)
    return customer

def gen_structuring_transactions(customer_id, account_id, n_days=6):
    """Multiple sub-$10K cash deposits over consecutive days — classic structuring pattern."""
    txns = []
    start = datetime.now() - timedelta(days=n_days + 1)
    for i in range(n_days):
        amt = round(random.uniform(8500, 9800), 2)
        txns.append({
            "transaction_id": str(uuid.uuid4())[:8],
            "customer_id": customer_id,
            "account_id": account_id,
            "date": (start + timedelta(days=i)).strftime("%Y-%m-%d"),
            "type": "Cash Deposit",
            "amount_usd": amt,
            "channel": "Branch Teller",
            "counterparty": None,
            "location": random.choice(CITIES),
        })
    return txns

def gen_layering_transactions(customer_id, account_id, related_accounts, n=5):
    """Rapid transfers through multiple accounts to obscure origin — layering pattern."""
    txns = []
    start = datetime.now() - timedelta(days=10)
    amount = round(random.uniform(40000, 95000), 2)
    for i in range(n):
        dest = random.choice(related_accounts)
        txns.append({
            "transaction_id": str(uuid.uuid4())[:8],
            "customer_id": customer_id,
            "account_id": account_id,
            "date": (start + timedelta(days=i)).strftime("%Y-%m-%d"),
            "type": "Wire Transfer Out",
            "amount_usd": round(amount * random.uniform(0.85, 0.98), 2),
            "channel": "Online Banking",
            "counterparty": dest,
            "location": "N/A - Digital",
        })
        amount *= 0.9  # amount shrinks slightly at each hop, typical of layering
    return txns

def gen_normal_transactions(customer_id, account_id, n=8):
    txns = []
    for i in range(n):
        txns.append({
            "transaction_id": str(uuid.uuid4())[:8],
            "customer_id": customer_id,
            "account_id": account_id,
            "date": rand_date(180, 1),
            "type": random.choice(["Debit Purchase", "Direct Deposit", "Bill Payment", "ATM Withdrawal"]),
            "amount_usd": round(random.uniform(20, 3000), 2),
            "channel": random.choice(["POS", "Online Banking", "ATM"]),
            "counterparty": random.choice(["Grocery Store", "Employer Payroll", "Utility Co", None]),
            "location": random.choice(CITIES),
        })
    return txns

def build_dataset():
    customers = []
    transactions = []
    related_parties = []
    watchlist = []
    alerts = []

    # --- Case 1: Structuring ---
    cust_1 = gen_customer("CUST-1001", "structuring")
    customers.append(cust_1)
    acct_1 = "ACCT-1001-A"
    transactions += gen_structuring_transactions(cust_1["customer_id"], acct_1)
    transactions += gen_normal_transactions(cust_1["customer_id"], acct_1, n=4)

    # --- Case 2: Layering (with shell company network) ---
    cust_2 = gen_customer("CUST-2002", "layering")
    customers.append(cust_2)
    shell_1 = gen_customer("CUST-2003", "shell")
    shell_2 = gen_customer("CUST-2004", "shell")
    customers += [shell_1, shell_2]
    acct_2 = "ACCT-2002-A"
    related_accts = ["ACCT-2003-A", "ACCT-2004-A"]
    transactions += gen_layering_transactions(cust_2["customer_id"], acct_2, related_accts)
    transactions += gen_normal_transactions(cust_2["customer_id"], acct_2, n=3)

    related_parties.append({
        "primary_customer_id": cust_2["customer_id"],
        "related_customer_id": shell_1["customer_id"],
        "relationship_type": "Frequent Wire Recipient",
        "relationship_strength": "High",
    })
    related_parties.append({
        "primary_customer_id": cust_2["customer_id"],
        "related_customer_id": shell_2["customer_id"],
        "relationship_type": "Frequent Wire Recipient",
        "relationship_strength": "Medium",
    })

    # --- Case 3: PEP with adverse media risk ---
    cust_3 = gen_customer("CUST-3005", "pep")
    cust_3["occupation"] = "Government Official"
    customers.append(cust_3)
    acct_3 = "ACCT-3005-A"
    transactions += gen_normal_transactions(cust_3["customer_id"], acct_3, n=5)
    transactions.append({
        "transaction_id": str(uuid.uuid4())[:8],
        "customer_id": cust_3["customer_id"],
        "account_id": acct_3,
        "date": rand_date(15, 5),
        "type": "Wire Transfer In",
        "amount_usd": 185000.00,
        "channel": "SWIFT",
        "counterparty": "Offshore Consulting Ltd",
        "location": "N/A - Digital",
    })
    # Primary PEP entry — exact match case for cust_3 (CUST-3005)
    watchlist.append({
        "watchlist_id": "WL-001",
        "full_name": cust_3["full_name"],
        "aliases": [],
        "date_of_birth": cust_3["date_of_birth"],
        "list_type": "PEP",
        "list_source": "World-Check (simulated)",
        "notes": "Senior government official, foreign ministry — simulated PEP designation for demo purposes",
    })

    # Name-only collision — a DIFFERENT "David Johnson" (different DOB/nationality) than
    # cust_5. Tests that the agent uses DOB to correctly clear a false positive rather
    # than flagging on name match alone.
    watchlist.append({
        "watchlist_id": "WL-002",
        "full_name": "David Johnson",
        "aliases": [],
        "date_of_birth": "1965-08-22",
        "list_type": "Sanctions",
        "list_source": "OFAC SDN List (simulated)",
        "notes": "Simulated sanctions entry — unrelated individual, born 1965, last known "
                 "residence Country_B_Sanctioned. Name-only collision risk for screening demo.",
    })

    # Alias-based true positive — listed under a formal/full name, with an alias that
    # matches cust_6's spelling variant. Tests whether the agent's screening checks
    # aliases, not just the primary listed name.
    watchlist.append({
        "watchlist_id": "WL-003",
        "full_name": "Mohammad al-Rashid",
        "aliases": ["Mohammed Al Rashid", "M. Al-Rashid", "Mohammed Rashid"],
        "date_of_birth": "1968-11-02",
        "list_type": "Sanctions",
        "list_source": "UN Consolidated List (simulated)",
        "notes": "Simulated sanctions entry — listed for alleged involvement in trade-based "
                 "money laundering network. Multiple spelling variants on file.",
    })

    # Standalone sanctions entry with no matching customer — included so the watchlist
    # isn't trivially "every entry matches someone," and to show the screening tool
    # correctly returning no match for the majority of customers.
    watchlist.append({
        "watchlist_id": "WL-004",
        "full_name": "Elena Petrov",
        "aliases": ["Elena Petrova"],
        "date_of_birth": "1980-01-30",
        "list_type": "PEP",
        "list_source": "World-Check (simulated)",
        "notes": "Simulated PEP entry — foreign state-owned enterprise executive. No matching "
                 "customer in this demo dataset (true negative case).",
    })

    # --- Case 4: Clean customer (control case — should NOT trigger high risk) ---
    cust_4 = gen_customer("CUST-4006", "normal")
    customers.append(cust_4)
    acct_4 = "ACCT-4006-A"
    transactions += gen_normal_transactions(cust_4["customer_id"], acct_4, n=10)

    # --- Case 5: Common-name FALSE POSITIVE — shares a name with a sanctioned individual,
    #             but different DOB/nationality. Tests whether the agent correctly clears
    #             a name-only hit instead of over-flagging. ---
    cust_5 = gen_customer("CUST-5007", "normal")
    cust_5["full_name"] = "David Johnson"
    cust_5["date_of_birth"] = "1990-03-14"
    cust_5["nationality"] = "Canada"
    customers.append(cust_5)
    acct_5 = "ACCT-5007-A"
    transactions += gen_normal_transactions(cust_5["customer_id"], acct_5, n=6)

    # --- Case 6: Alias / near-miss TRUE POSITIVE — customer's name is a minor spelling
    #             variant of a sanctioned entity's listed alias. Tests whether the agent
    #             catches a match that a naive exact-string check would miss. ---
    cust_6 = gen_customer("CUST-6008", "layering")
    cust_6["full_name"] = "Mohammed Al Rashid"
    cust_6["date_of_birth"] = "1968-11-02"
    customers.append(cust_6)
    acct_6 = "ACCT-6008-A"
    transactions.append({
        "transaction_id": str(uuid.uuid4())[:8],
        "customer_id": cust_6["customer_id"],
        "account_id": acct_6,
        "date": rand_date(10, 3),
        "type": "Wire Transfer In",
        "amount_usd": 240000.00,
        "channel": "SWIFT",
        "counterparty": "Overseas Trading Partner",
        "location": "N/A - Digital",
    })
    transactions += gen_normal_transactions(cust_6["customer_id"], acct_6, n=3)

    # --- Typology reference library ---
    typologies = [
        {
            "typology_id": "TYP-STRUCTURING",
            "name": "Structuring / Smurfing",
            "description": "Breaking up large cash transactions into smaller amounts, "
                            "each below the $10,000 CTR reporting threshold, to avoid detection.",
            "red_flags": [
                "Multiple cash deposits just under $10,000 within a short period",
                "Deposits made at different branches or by different individuals",
                "No clear business rationale for cash-intensive activity",
            ],
        },
        {
            "typology_id": "TYP-LAYERING",
            "name": "Layering",
            "description": "Moving funds through multiple accounts, entities, or jurisdictions "
                            "in rapid succession to obscure the original source of funds.",
            "red_flags": [
                "Rapid transfers through multiple related accounts",
                "Transfers to shell companies or high-risk jurisdictions",
                "Transaction amounts shrink slightly at each hop (fee absorption pattern)",
                "No apparent business purpose for the fund movement",
            ],
        },
        {
            "typology_id": "TYP-PEP-RISK",
            "name": "PEP / Adverse Media Risk",
            "description": "Transactions involving politically exposed persons (PEPs) or entities "
                            "with adverse media, warranting enhanced due diligence.",
            "red_flags": [
                "Customer or counterparty matches a PEP or sanctions watchlist",
                "Large wire transfers inconsistent with declared income",
                "Counterparty is an offshore or consulting entity with limited transparency",
            ],
        },
        {
            "typology_id": "TYP-SHELL-COMPANY",
            "name": "Shell Company Activity",
            "description": "Use of entities with no genuine business operations to move "
                            "or disguise funds.",
            "red_flags": [
                "Entity incorporated in high-risk or secrecy jurisdiction",
                "No clear operating business behind the account",
                "Account used primarily as a pass-through for transfers",
            ],
        },
        {
            "typology_id": "TYP-WATCHLIST-SCREENING",
            "name": "Sanctions / Watchlist Name Match",
            "description": "Customer name (or a known alias) matches an entry on a "
                            "sanctions or PEP watchlist. Requires careful verification — "
                            "name-only matches are frequently false positives and must be "
                            "corroborated with date of birth, nationality, or other identifiers "
                            "before escalation.",
            "red_flags": [
                "Exact name AND date-of-birth match to a watchlist entry (high confidence)",
                "Name matches only, DOB differs or is unavailable (possible false positive — verify further)",
                "Name matches a listed alias rather than the primary name (requires alias-aware screening)",
            ],
        },
    ]

    # --- Pre-built alerts ---
    alerts = [
        {
            "alert_id": "ALERT-9001",
            "customer_id": cust_1["customer_id"],
            "alert_type": "Structuring Pattern Detected",
            "triggering_rule": "RULE-CTR-AVOIDANCE-01",
            "date_raised": rand_date(2, 0),
            "summary": "6 cash deposits between $8,500-$9,800 over 6 consecutive days, "
                       "total exceeding $54,000, all just under CTR threshold.",
            "priority": "High",
        },
        {
            "alert_id": "ALERT-9002",
            "customer_id": cust_2["customer_id"],
            "alert_type": "Rapid Fund Layering",
            "triggering_rule": "RULE-VELOCITY-02",
            "date_raised": rand_date(1, 0),
            "summary": "5 wire transfers totaling ~$300K moved through 2 related accounts "
                       "within a 5-day window, both flagged as shell-type entities.",
            "priority": "Critical",
        },
        {
            "alert_id": "ALERT-9003",
            "customer_id": cust_3["customer_id"],
            "alert_type": "PEP Large Wire Received",
            "triggering_rule": "RULE-PEP-THRESHOLD-01",
            "date_raised": rand_date(3, 0),
            "summary": "$185,000 wire received from an offshore consulting entity by a customer "
                       "flagged as a Politically Exposed Person.",
            "priority": "High",
        },
        {
            "alert_id": "ALERT-9004",
            "customer_id": cust_4["customer_id"],
            "alert_type": "Routine Threshold Alert (Low Risk)",
            "triggering_rule": "RULE-GENERIC-VOLUME-05",
            "date_raised": rand_date(4, 0),
            "summary": "Customer crossed a routine monthly transaction volume threshold. "
                       "Included as a control case — expected outcome is dismissal.",
            "priority": "Low",
        },
        {
            "alert_id": "ALERT-9005",
            "customer_id": cust_5["customer_id"],
            "alert_type": "Sanctions Screening Name Match (Unverified)",
            "triggering_rule": "RULE-WATCHLIST-NAME-01",
            "date_raised": rand_date(2, 0),
            "summary": "Customer name matched an entry on the sanctions watchlist. "
                       "Included as a demo case testing false-positive resolution via DOB check.",
            "priority": "Medium",
        },
        {
            "alert_id": "ALERT-9006",
            "customer_id": cust_6["customer_id"],
            "alert_type": "Large Wire + Possible Sanctions Alias Match",
            "triggering_rule": "RULE-WATCHLIST-ALIAS-01",
            "date_raised": rand_date(1, 0),
            "summary": "$240,000 wire received; customer's name is a spelling variant of a "
                       "listed sanctions alias. Included as a demo case testing alias/fuzzy "
                       "matching that a naive exact-string screen would miss.",
            "priority": "Critical",
        },
    ]

    return {
        "customers": customers,
        "transactions": transactions,
        "related_parties": related_parties,
        "watchlist": watchlist,
        "typologies": typologies,
        "alerts": alerts,
    }

def main():
    data = build_dataset()
    for key, records in data.items():
        path = OUT_DIR / f"{key}.json"
        with open(path, "w") as f:
            json.dump(records, f, indent=2)
        print(f"Wrote {len(records):>3} records -> {path}")

    print("\nSummary:")
    print(f"  Customers: {len(data['customers'])}")
    print(f"  Transactions: {len(data['transactions'])}")
    print(f"  Related party links: {len(data['related_parties'])}")
    print(f"  Watchlist entries: {len(data['watchlist'])}")
    print(f"  Typologies: {len(data['typologies'])}")
    print(f"  Pre-built alerts: {len(data['alerts'])}")
    print("\nDemo cases included:")
    print("  ALERT-9001 -> Structuring (should trigger HIGH risk)")
    print("  ALERT-9002 -> Layering via shell companies (should trigger CRITICAL risk)")
    print("  ALERT-9003 -> PEP + large wire (should trigger HIGH risk)")
    print("  ALERT-9004 -> Clean/control case (should trigger LOW risk / dismiss)")
    print("  ALERT-9005 -> Name-only watchlist match, DOB differs (should DISMISS as false positive)")
    print("  ALERT-9006 -> Alias/fuzzy watchlist match + large wire (should trigger CRITICAL risk)")

if __name__ == "__main__":
    main()
