# Ask-Council — plug-and-play skill

Consult free web LLMs (GLM, DeepSeek, Qwen) in parallel from any host model.
Local CLI does fan-out; your current model (Host) writes the Verdict.

## Setup (once)

```bash
cd multi-agent-council
./setup.sh  # venv + deps + Chrome detect + .env scaffold
# or manually: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cp .env.example .env
```

Then validate before first council:

```bash
source .venv/bin/activate
python pipeline/ask_council.py --check
```

Tokens (browser DevTools on each chat page, logged in):

| Model    | Page                 | DevTools Console                        | Env var         |
|----------|----------------------|-----------------------------------------|-----------------|
| GLM      | `chat.z.ai`          | `localStorage.getItem("token")`         | `GLM_TOKEN`     |
| DeepSeek | `chat.deepseek.com`  | `localStorage` `userToken` → `value`    | `DEEPSEEK_TOKEN`|
| Qwen     | `chat.qwen.ai`       | `localStorage.getItem("token")`         | `QWEN_TOKEN`    |

macOS: system Chrome auto-detected. Linux: set `BROWSER_PATH` or place chrome at `.browsers/chrome-linux64/chrome`. `sandbox=False` is already set for zendriver.

## Use

```bash
source .venv/bin/activate
python pipeline/ask_council.py "Your question" --models glm,deepseek,qwen --out opinions.md
# subset: --models glm,deepseek
# standalone judge (no Host): --judge glm
```

Paste `opinions.md` back into your host chat (GPT/Claude/Gemini). Host follows `SKILL.md`:
1. Consensus, 2. Contradictions/blind spots, 3. Final Verdict.

Drop `SKILL.md` + `pipeline/` into any assistant as a skill — that assistant becomes Chairman.

## Layout

```
.
├── SKILL.md               # host instructions + verdict template
├── pipeline/
│   ├── ask_council.py     # CLI fan-out, markdown output
│   ├── glm_web.py         # chat.z.ai driver
│   ├── deepseek_web.py    # chat.deepseek.com driver
│   └── qwen_web.py        # chat.qwen.ai driver
├── .env.example
└── requirements.txt
```

## Notes

- One-shot browser per model per run (`asyncio.gather`, per-model `--timeout`, default 180s). No persistent pool in v1.
- Graceful degradation: 1/3 succeeding still returns with warning; 0/3 reports failure, no fake consensus.
- Qwen rejects expired tokens with `Qwen token rejected (page shows Log in)` — refresh via DevTools.
- If `Failed to connect to browser` appears system-wide, quit/reopen Chrome (auto-update skew) and retry.
