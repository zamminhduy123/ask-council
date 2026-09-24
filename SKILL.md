---
name: ask-council
description: Council over GLM, DeepSeek, Qwen — convene outside Opinions, argue follow-ups across rounds, or synthesize pasted Opinions into a Verdict. Use when the user says council, second opinion, challenge them, or pastes opinions.md.
---

# Ask-Council

Three branches. Take exactly one per run.

## Branch A — Convene a Council

You cannot browse the three chats directly; a local CLI does the fan-out.

1. Convene it yourself if you have shell access, else tell the user to run (setup details in `README.md`):
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

## Branch C — Argue to resolution (autonomous loop)

Fires when you or the user disputes an Opinion, or the round-1 synthesis left open contradictions. The user hears nothing until the loop exits — you run every round yourself.

1. Write the challenge as one direct instruction (quote the claim, state the objection, demand revision-or-rebuttal).
2. Convene the next round yourself:
   `python pipeline/ask_council.py "CHALLENGE" --context opinionsN.md --out opinionsN+1.md`
3. Synthesize per Branch B over the latest round and list remaining disputes.
4. Repeat while disputes remain and rounds < 3. Then verdict, flagging any residual disagreement as unresolved rather than forcing consensus.
Completion criterion: every challenged claim has a final response (revised or defended with reasons), no *new* contradictions in the latest round, or round cap hit — then report once: positions per round, what moved, final Verdict.
