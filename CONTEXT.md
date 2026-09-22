# Ask-Council

Portable skill for consulting free web LLMs from any host model, with the host delivering the final verdict.

## Language

**Council**:
One user query run across N selected web models.
_Avoid_: debate run, session

**Opinion**:
Raw cleaned text from one web model for a Council.
_Avoid_: response, answer

**Verdict**:
Final synthesized recommendation produced by the Host from Opinions.
_Avoid_: consensus, final answer

**Debate**:
The synthesis step over Opinions, not the whole run.
_Avoid_: discussion

**Driver**:
Per-model zendriver automation exposing launch, login, send, scrape.
_Avoid_: client, wrapper

**Host**:
The user's current model (GPT, Claude, Gemini) that invokes the skill and writes the Verdict.
_Avoid_: judge, chairman

**Skill**:
Local CLI plus SKILL.md drop-in, not a hosted web app.
_Avoid_: app, platform
