# contract-agent-lab

A weekend-scale demo of an **agentic contract redlining loop**: draft a redline,
critique it against a client playbook, revise, and score every run against a
rubric so regressions are visible.

## Why this exists

Crosby's public writing (intelligence.crosby.ai, the New Ontologies field study)
names three hard problems in AI-native legal work:

1. **Custom eval systems** that catch regressions on every generated edit.
2. **Client preference playbooks**: living corpora of rules, accrued over time,
   that both humans and agents retrieve.
3. **Agents in non-verifiable domains**: law has no answer key, so quality has to
   be constructed, not just measured.

This repo is a toy model of all three: an agent loop (`agent.py`), a playbook
(`playbook.json`), synthetic fixtures (`fixtures/nda_sample.json`), and an eval
harness that scores draft vs. final output per clause.

## What is real and what is a stand-in

- **Real:** the loop architecture (draft -> critique -> revise), the playbook
  retrieval pattern, the eval harness with a draft-vs-final comparison, and the
  control-clause test (C5) that checks the agent leaves clean text alone.
- **Stand-in:** `MockClient` is deterministic and rule-based, so the demo runs
  with zero API keys. It is deliberately imperfect: the mock draft fixes obvious
  issues but misses the subtler non-solicitation rule, so the critique and
  revise steps do real work (see C4 below).
- **Synthetic:** all NDA clauses were written for this demo. Nothing here is a
  real agreement, and nothing here is legal advice.

## Sample run (mock model)

```
clause title                       draft_ok  final_ok
C1     Confidentiality period      1         1
C2     Limitation of liability     1         1
C3     Payment terms               1         1
C4     Non-solicitation            0         1
C5     Governing law (clean)       1         1

model=mock | 5/5 clauses resolved after revision
```

C4 is the interesting row: the draft left the non-solicit overly broad, the
critique flagged `NON-SOLICIT violated`, and the revision narrowed it to
employees with whom the party had material contact. C5 confirms the agent does
not invent work where none is needed.

## Run it

```bash
python3 agent.py
```

No dependencies, no keys. To route the same loop through a real model:

```bash
pip install anthropic
export ANTHROPIC_API_KEY=... ANTHROPIC_MODEL=<model-id>
python3 agent.py
```

## What this does not claim

No real contracts, no real model judgments, no precision/recall numbers that
mean anything beyond this fixture set. It is a structure demo: the loop,
the playbook, and the eval harness are the point.

I built this 4th October 2026, as a weekend project.
