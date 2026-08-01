# AML Investigation Copilot — Agentic AI Demo

An agentic AI system that investigates AML (Anti-Money Laundering) alerts autonomously,
gathering evidence across multiple data sources, matching it against known typologies,
and producing a draft SAR (Suspicious Activity Report) for human review — with a full
human-in-the-loop web UI, network graph visualization, and a feedback loop that steers
future drafts based on analyst decisions.

**All data in this repo is 100% synthetic.** No real customers, transactions, or
individuals are represented.

## Architecture

```
Alert (JSON) --> Orchestrator Agent (Claude + tool use)
                     |
                     +--> get_customer_profile()
                     +--> get_transaction_history()
                     +--> get_related_parties()
                     +--> check_sanctions_pep()   [tiered: CONFIRMED / NAME_ONLY / ALIAS_FUZZY]
                     +--> search_adverse_media()
                     +--> get_typology_library()
                     |
                     v
              Evidence synthesis + typology matching
                     |
                     v
        Draft output: risk score, red flags, SAR narrative
                     |
                     v
    ===========================================
    |        FastAPI + Web UI (app/)          |
    |  - Case queue (alert list)              |
    |  - Evidence trail (every tool call)      |
    |  - Network graph (D3, related parties)   |
    |  - Draft SAR: editable, Approve/Edit/    |
    |    Reject buttons                        |
    ===========================================
                     |
                     v
     Analyst decision --> feedback.py logs it
                     |
                     v
     Next investigation's system prompt includes
     recent analyst corrections (few-shot feedback loop)
```

The agent is genuinely agentic (not a scripted pipeline) — it decides which tools to
call and in what order based on the alert content, reasoning step by step through the
investigation the way a human analyst would.

## Files

| File | Purpose |
|---|---|
| `generate_synthetic_data.py` | Generates all synthetic data, including watchlist edge cases |
| `data/` | JSON data files + `feedback_log.json` (created at runtime) |
| `tools.py` | Tool layer — functions the agent can call, incl. tiered sanctions/PEP matching |
| `orchestrator.py` | The agentic loop — runs an investigation end-to-end, injects feedback context |
| `feedback.py` | Feedback loop — logs analyst decisions, surfaces corrections as few-shot examples |
| `app/main.py` | FastAPI backend — alerts, investigate, network graph, decision endpoints |
| `app/static/index.html` | Human-in-the-loop review UI (case queue, evidence trail, network graph, draft SAR) |
| `Dockerfile` | Containerization |

## Demo cases included

| Alert | Pattern | Expected outcome |
|---|---|---|
| `ALERT-9001` | Structuring — 6 cash deposits just under $10K over 6 days | High risk, File SAR |
| `ALERT-9002` | Layering — rapid transfers through shell company network | Critical risk, File SAR |
| `ALERT-9003` | PEP receiving large offshore wire + adverse media hit | High risk, Escalate |
| `ALERT-9004` | Routine volume alert, no real red flags | Low risk, Dismiss (control case) |
| `ALERT-9005` | Name-only sanctions match, DOB differs from watchlist entry | Should DISMISS as false positive |
| `ALERT-9006` | Customer name is a spelling variant of a listed sanctions alias, large wire | Critical risk, File SAR |

The last two cases specifically test the agent's judgment on watchlist screening — a
naive exact-string match would either miss the real hit (9006) or over-flag the false
positive (9005). The `check_sanctions_pep` tool returns tiered confidence
(`CONFIRMED` / `NAME_ONLY` / `ALIAS_FUZZY`) so the agent has to reason about which
evidence actually warrants escalation, not just pattern-match on a name string.

## Running with Docker (Recommended and Straight Forward)

```bash
export ANTHROPIC_API_KEY=your_key_here
docker run -e ANTHROPIC_API_KEY -p 8000:8000 -d shankysharma86/anti-money-laundering-agentic-ai-anthropic:v1.1
```

Then open `http://127.0.0.1:8000`— you'll see the case queue. Click a case, click
**Run Investigation**, and watch the agent's tool calls populate the Evidence Trail tab
in real time, followed by a draft SAR you can approve, edit, or reject.

The `data/` folder is NOT bind-mounted into the container so the synthetic dataset that
ships with this repo is generated in the image directly, and any analyst decisions (`feedback_log.json`)
will not persist across container restarts. 

## Running locally (without Docker)

**Use a virtual environment.** This isolates the project's dependencies from whatever
else is installed system-wide, and avoids Python-version mismatches (this project
needs **Python 3.9+** — FastAPI + Pydantic 2.x won't run on older versions).

```bash
python3 --version          # confirm it's 3.9+; if not, install a newer Python first

python3 -m venv venv
source venv/bin/activate   # on Windows: venv\Scripts\activate

pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_key_here

python3 generate_synthetic_data.py     # generate the dataset
cd app
uvicorn main:app --reload --port 8000
```

Every time you come back to work on this project in a new terminal session, reactivate
the venv first: `source venv/bin/activate` (run from the project root, since `venv/`
lives there).

Open `http://127.0.0.1:8000` — you'll see the case queue. Click a case, click
**Run Investigation**, and watch the agent's tool calls populate the Evidence Trail tab
in real time, followed by a draft SAR you can approve, edit, or reject.

You can also run a single investigation from the CLI:
```bash
python3 orchestrator.py ALERT-9001
```

### Troubleshooting: `got an unexpected keyword argument 'proxies'`

If `/api/investigate` returns a 500 with this error, it's a known compatibility break
between the `anthropic` SDK and `httpx` 0.28+ (which removed the `proxies` argument the
SDK used to pass internally — this can happen even on recent `anthropic` versions if an
`HTTP_PROXY`/`HTTPS_PROXY` environment variable is set). `requirements.txt` already pins
`httpx<0.28` to prevent this — if you still hit it, you likely have a stale environment;
reinstall inside a fresh venv:
```bash
deactivate
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## The human-in-the-loop review flow

1. Analyst picks a case from the queue.
2. Clicks **Run Investigation** — the agent calls tools live, each call and its result
   appears in the **Evidence Trail** tab as it happens (this is the actual audit trail,
   not a simulation).
3. **Network** tab shows a force-directed graph of related accounts/entities for the
   customer — useful for spotting shell-company clusters at a glance.
4. **Draft SAR & Decision** tab shows the risk score, recommended action, and a fully
   editable draft SAR narrative.
5. Analyst clicks **Approve**, **Save Edit** (after editing the narrative), or
   **Reject** — optionally with a note explaining why.
6. That decision is logged via `feedback.py`. The *next* investigation the agent runs
   will include recent edited/rejected cases as few-shot context in its system prompt,
   nudging its risk scoring and recommendations toward how this team's analysts
   actually decide.

## Extending further

- **Persist feedback to a real DB** (Postgres/BigQuery) instead of the JSON file for
  production use, and add richer feedback signals (e.g. structured diffs between
  agent and analyst narratives, not just free-text notes).
- **Deploy to Cloud Run**: the Dockerfile is already Cloud Run-compatible — `gcloud run
  deploy` with the `ANTHROPIC_API_KEY` set as a secret gets you a live, shareable demo URL.
- **Expand the network graph** to multi-hop traversal (accounts connected to accounts
  connected to accounts) for more realistic shell-company detection.
- **Add authentication** if this ever needs to hold real analyst identities.

## Disclaimer

This is a portfolio/demo project. It does not implement real AML compliance requirements,
is not connected to real sanctions/PEP databases, and should not be used for actual
compliance decisions. It's built to demonstrate agentic AI architecture patterns.
