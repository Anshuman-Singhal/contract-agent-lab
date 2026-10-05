#!/usr/bin/env python3
"""
contract-agent-lab: a minimal agentic NDA redlining loop.

Three ideas, kept small on purpose:
  1. Agent loop: draft a redline, critique it against the client playbook, revise.
  2. Playbook retrieval: per-clause rules the agent must satisfy (a toy version of
     client preference memory that accrues over time).
  3. Eval harness: every run scores each output against a rubric, so regressions
     across runs are visible immediately.

The default model is MockClient, a deterministic, clearly-labeled stand-in, so the
whole loop runs with zero API keys. Set ANTHROPIC_API_KEY and ANTHROPIC_MODEL to
route the same loop through a real model (requires `pip install anthropic`).

All fixtures are synthetic and labeled as such. Nothing here is legal advice.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_json(rel):
    with open(os.path.join(HERE, rel)) as f:
        return json.load(f)


# ---------------------------------------------------------------- model clients

class MockClient:
    """Deterministic stand-in for an LLM. Every output is labeled mock.

    The mock draft is deliberately imperfect: it fixes the obvious issues but
    misses the subtler non-solicitation rule, so the critique and revise steps
    have real work to do. That is the point of the loop.
    """

    name = "mock"

    def complete(self, system, user):
        low = user.lower()
        # NOTE: check "revise" before "critique" because the revise prompt
        # mentions the critique.
        if "draft a redline" in low:
            return self._draft(user)
        if low.startswith("revise"):
            return self._revise(user)
        if "critique" in low:
            return self._critique(user)
        return "[mock] unrecognized step"

    def _draft(self, user):
        text = self._field(user, "CLAUSE")
        text = re.sub(r"in perpetuity|perpetual|indefinite",
                      "for a period of two (2) years", text, flags=re.I)
        text = re.sub(r"shall be unlimited in all cases",
                      "shall be capped at the amounts paid in the twelve months preceding the claim",
                      text, flags=re.I)
        text = re.sub(r"within 90 days of receipt \(net-90\)|net-90",
                      "within 30 days of receipt (net-30)", text, flags=re.I)
        # NOTE: deliberately does NOT narrow the non-solicitation clause.
        return "[mock draft] " + text

    def _critique(self, user):
        draft = self._field(user, "DRAFT").lower()
        findings = []
        if ("perpetuity" in draft or "perpetual" in draft) and "two (2) years" not in draft:
            findings.append("CONF-TERM violated: confidentiality term still open-ended.")
        if "unlimited" in draft:
            findings.append("LIAB-CAP violated: liability still uncapped.")
        if "net-90" in draft or "90 days" in draft:
            findings.append("PAY-TERMS violated: payment term still net-90.")
        if "shall solicit or hire any employee" in draft:
            findings.append("NON-SOLICIT violated: non-solicit still overly broad.")
        if not findings:
            findings.append("No playbook violations found.")
        return "[mock critique] " + " | ".join(findings)

    def _revise(self, user):
        draft = self._field(user, "DRAFT").replace("[mock draft] ", "")
        critique = self._field(user, "CRITIQUE")
        text = draft
        if "CONF-TERM violated" in critique:
            text = re.sub(r"in perpetuity|perpetual|indefinite",
                          "for a period of two (2) years", text, flags=re.I)
        if "LIAB-CAP violated" in critique:
            text = re.sub(r"unlimited[^.]*",
                          "capped at the amounts paid in the twelve months preceding the claim",
                          text, flags=re.I)
        if "PAY-TERMS violated" in critique:
            text = re.sub(r"net-90|90 days", "net-30", text, flags=re.I)
        if "NON-SOLICIT violated" in critique:
            text = re.sub(r"shall solicit or hire any employee[^.]*",
                          "shall solicit any employee of the other party with whom it had material contact",
                          text, flags=re.I)
        return "[mock revision] " + text

    @staticmethod
    def _field(user, name):
        m = re.search(name + r":\s*(.*?)(?:\n[A-Z-]+:|\Z)", user, re.S)
        return m.group(1).strip() if m else ""


class AnthropicClient:
    """Optional real-model adapter. Same loop, real model."""

    name = "anthropic"

    def __init__(self):
        import anthropic  # pip install anthropic
        self.client = anthropic.Anthropic()
        self.model = os.environ.get("ANTHROPIC_MODEL", "")
        if not self.model:
            raise SystemExit("Set ANTHROPIC_MODEL to use the real-model adapter.")

    def complete(self, system, user):
        msg = self.client.messages.create(
            model=self.model, max_tokens=600, system=system,
            messages=[{"role": "user", "content": user}])
        return msg.content[0].text


# ---------------------------------------------------------------- agent loop

def run_clause(client, clause, rules):
    system = ("You are a contract redlining assistant for the client described in "
              "the playbook. Satisfy every applicable rule.")
    rules_text = "\n".join(
        "- {id}: {principle} Guidance: {guidance}".format(**r) for r in rules)
    draft = client.complete(
        system,
        "Draft a redline for the clause below, applying the playbook.\n\n"
        "PLAYBOOK:\n{rules}\n\nCLAUSE:\n{clause}".format(
            rules=rules_text, clause=clause["text"]))
    critique = client.complete(
        system,
        "Critique the draft against the playbook. List violations by rule id.\n\n"
        "PLAYBOOK:\n{rules}\n\nDRAFT:\n{draft}".format(
            rules=rules_text, draft=draft))
    final = client.complete(
        system,
        "Revise the draft to fix every violation named in the critique. "
        "If the critique finds no violations, return the draft unchanged.\n\n"
        "CRITIQUE:\n{critique}\n\nDRAFT:\n{draft}".format(
            critique=critique, draft=draft))
    return draft, critique, final


# ---------------------------------------------------------------- eval harness

def clean(text):
    return re.sub(r"^\[mock (draft|revision)\] ", "", text).strip()


def score_clause(clause, final_text):
    """Rubric: did the final redline resolve the known issue (or, for the clean
    control clause, did the agent correctly leave it alone)?"""
    text = clean(final_text)
    if clause["id"] == "C5":
        ok = ("State of New York" in text
              and "two (2) years" not in text
              and "net-30" not in text)
        return ok
    return any(kw.lower() in text.lower()
               for kw in clause["expected_fix_keywords"])


def main():
    playbook = load_json("playbook.json")
    fixtures = load_json(os.path.join("fixtures", "nda_sample.json"))
    rules = playbook["rules"]

    if os.environ.get("ANTHROPIC_API_KEY"):
        client = AnthropicClient()
    else:
        client = MockClient()

    print("contract-agent-lab | model={} | fixtures={}".format(
        client.name, fixtures["document"]))
    print("=" * 72)

    rows = []
    for clause in fixtures["clauses"]:
        draft, critique, final = run_clause(client, clause, rules)
        draft_ok = score_clause(clause, draft)
        final_ok = score_clause(clause, final)
        rows.append((clause["id"], clause["title"], draft_ok, final_ok))
        print("\n[{}] {}".format(clause["id"], clause["title"]))
        print("  known issue : {}".format(clause["known_issue"]))
        print("  draft       : {}".format(clean(draft)))
        print("  critique    : {}".format(clean(critique).replace("[mock critique] ", "")))
        print("  final       : {}".format(clean(final)))
        print("  draft_ok={} final_ok={}".format(int(draft_ok), int(final_ok)))

    print("\n" + "=" * 72)
    print("{:<6}{:<28}{:<10}{:<10}".format("clause", "title", "draft_ok", "final_ok"))
    for cid, title, dok, fok in rows:
        print("{:<6}{:<28}{:<10}{:<10}".format(cid, title[:27], int(dok), int(fok)))
    resolved = sum(1 for _, _, _, fok in rows if fok)
    print("\nmodel={} | {}/{} clauses resolved after revision".format(
        client.name, resolved, len(rows)))
    if client.name == "mock":
        print("NOTE: mock run. Swap in a real model via ANTHROPIC_API_KEY "
              "to measure the loop for real.")


if __name__ == "__main__":
    sys.exit(main())
