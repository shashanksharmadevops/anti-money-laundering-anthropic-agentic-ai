"""
AML Investigation Orchestrator Agent
======================================
This is the agentic core: given an alert ID, the agent decides which tools to call,
gathers evidence, matches it against known typologies, and produces a structured
investigation output for human review.

Requires: pip install anthropic
Set ANTHROPIC_API_KEY in your environment before running.

Usage:
    python3 orchestrator.py ALERT-9001
"""

import re
import sys
import json
import anthropic

from tools import TOOL_REGISTRY, TOOL_SCHEMAS
from feedback import get_feedback_examples

MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = """You are an AML (Anti-Money Laundering) investigation copilot.

Given a transaction-monitoring alert, your job is to investigate it thoroughly by:
1. Pulling the alert details
2. Pulling the customer's KYC profile
3. Pulling their transaction history
4. Checking related parties / network connections if relevant
5. Screening the customer against sanctions/PEP watchlists
6. Searching for adverse media
7. Comparing the evidence against the known typology library

Use the tools available to you to gather ALL relevant evidence before drawing conclusions.
Be thorough — do not skip steps, and do not assume facts you have not retrieved via a tool call.

Once you have gathered sufficient evidence, produce a FINAL INVESTIGATION SUMMARY in this
exact structure:

## Investigation Summary: <alert_id>

**Customer:** <name> (<customer_id>)
**Risk Score:** <0-100>
**Recommended Action:** <File SAR / Escalate for Senior Review / Dismiss - No Further Action>

### Red Flags Identified
- <bullet list, each citing the specific evidence>

### Typology Match
<which typology/typologies this matches, and why>

### Draft SAR Narrative
<a 1-2 paragraph narrative in the style of a Suspicious Activity Report: who, what, when,
where, why suspicious — written in formal, factual, third-person compliance language>

### Analyst Note
<one sentence flagging anything uncertain that a human reviewer should double check>

IMPORTANT: This is a DRAFT for human review only. You are not filing anything. A human
analyst must approve, edit, or reject this before any action is taken. Make this clear
in your output.
"""


def parse_summary(text: str) -> dict:
    """Best-effort extraction of structured fields from the agent's markdown summary,
    so the API/UI layer doesn't have to re-parse free text on every request."""
    def _find(pattern, default=None):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else default

    risk_score_raw = _find(r"\*\*Risk Score:\*\*\s*(\d+)")
    return {
        "customer_line": _find(r"\*\*Customer:\*\*\s*(.+)"),
        "risk_score": int(risk_score_raw) if risk_score_raw else None,
        "recommended_action": _find(r"\*\*Recommended Action:\*\*\s*(.+)"),
        "raw_text": text,
    }


def run_investigation(alert_id: str, verbose: bool = True, use_feedback: bool = True):
    client = anthropic.Anthropic()

    system_prompt = SYSTEM_PROMPT
    if use_feedback:
        feedback_context = get_feedback_examples(limit=3)
        if feedback_context:
            system_prompt = SYSTEM_PROMPT + feedback_context

    messages = [{
        "role": "user",
        "content": f"Investigate alert {alert_id}. Gather all relevant evidence using the "
                   f"tools available, then produce the final investigation summary."
    }]

    audit_trail = []

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=system_prompt,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        # Log any text reasoning the agent produced this turn
        for block in response.content:
            if block.type == "text" and verbose:
                print(f"\n[AGENT REASONING]\n{block.text}\n")

        if response.stop_reason != "tool_use":
            # Agent is done — final answer is in the last text block
            final_text = "\n".join(b.text for b in response.content if b.type == "text")
            structured = parse_summary(final_text)
            structured["audit_trail"] = audit_trail
            structured["alert_id"] = alert_id
            return structured

        # Handle tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input
                if verbose:
                    print(f"[TOOL CALL] {tool_name}({tool_input})")

                fn = TOOL_REGISTRY.get(tool_name)
                result = fn(**tool_input) if fn else {"error": f"Unknown tool {tool_name}"}

                audit_trail.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "output": result,
                })

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                })

        messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    alert_id = sys.argv[1] if len(sys.argv) > 1 else "ALERT-9001"
    print(f"Running investigation for {alert_id}...\n" + "=" * 60)

    result = run_investigation(alert_id)

    print("\n" + "=" * 60)
    print("FINAL OUTPUT (for human review)")
    print("=" * 60)
    print(result["raw_text"])

    trail = result["audit_trail"]
    print("\n" + "=" * 60)
    print(f"AUDIT TRAIL: {len(trail)} tool calls made")
    print("=" * 60)
    for i, step in enumerate(trail, 1):
        print(f"{i}. {step['tool']}({step['input']})")