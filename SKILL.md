---
name: ask-council
description: Council over GLM, DeepSeek, Qwen — convene outside Opinions, argue follow-ups across rounds, or synthesize pasted Opinions into a Verdict. Use when the user says council, second opinion, challenge them, or pastes opinions.md.
---

# Ask-Council

Three branches. Take exactly one per run.

## Branch A — Convene a Council

You cannot browse the three chats directly; a local CLI does the fan-out.

1. Tell the user to run (details in `README.md` if they hit setup issues):
   `python pipeline/ask_council.py "QUESTION" --out opinions.md`
2. Completion criterion: `opinions.md` holds one `## OPINION [model]` block per healthy model, each raw text or explicit `_FAILED:_`. No Verdict yet.

Token/Chrome problems belong to `README.md` + `pipeline/ask_council.py --check` — point there, don't debug inline.

## Branch B — Synthesize a Verdict

Fires when the user pastes `opinions.md` (USER QUERY + OPINION blocks).

As Chairman, output exactly:

1. **Consensus** — what ≥2 Opinions agree on.
2. **Contradictions / blind spots** — where they disagree, hedge, or miss.
3. **Verdict** — best synthesized recommendation, citing which Opinion(s) each point draws from.

Completion criterion: all three headings present; every Verdict claim traces to a quoted Opinion; zero invented Opinions. If only 1 Opinion succeeded, say so with a warning instead of a fake consensus.

## Branch C — Argue (follow-up round)

Fires when you or the user disputes an Opinion and wants the Council to respond.

1. Write the challenge as one direct instruction (quote the claim, state the objection, demand revision-or-rebuttal).
2. Tell the user to run:
   `python pipeline/ask_council.py "CHALLENGE" --context opinions.md --out opinions2.md`
   Each model gets the prior round plus the challenge and answers it directly.
3. Synthesize per Branch B over the latest round. Cap at 3 rounds, then verdict.
Completion criterion: every challenged claim has a round-2 response (revised or defended); verdict cites final positions only.
