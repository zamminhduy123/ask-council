# Ask-Council — get a second opinion from free AI models (GLM, DeepSeek, Qwen) inside ChatGPT, Claude, or Gemini

No API keys. A local Python CLI asks free web LLMs in parallel via headless browser automation; your current model synthesizes the Verdict. Works as a drop-in Claude skill, ChatGPT workflow, or Gemini routine.

- **Who it's for:** anyone who wants a cross-model check — architecture calls, debugging second opinions, writing reviews — without paying per-token.
- **How it works:** fan-out (one headless Chrome per model, `asyncio.gather`) → `opinions.md` → Host debate (consensus, contradictions, Verdict).
- **Cost:** free web chats only (`chat.z.ai`, `chat.deepseek.com`, `chat.qwen.ai`). Bring your own logged-in session tokens.

## Quickstart

```bash
git clone https://github.com/zamminhduy123/ask-council.git && cd ask-council
./setup.sh  # venv + deps + Chrome detect + .env scaffold
source .venv/bin/activate
# fill .env (token table below), then:
python pipeline/ask_council.py --check
python pipeline/ask_council.py "Should I use Postgres or SQLite for 10k rows?" --out opinions.md
```

Paste `opinions.md` back into your host chat. It follows `SKILL.md`: 1. Consensus, 2. Contradictions/blind spots, 3. Final Verdict.

Disagree with an Opinion? Argue a round (repeat up to 3x, then verdict):

```bash
python pipeline/ask_council.py "Your objection as one direct instruction" --context opinions.md --out opinions2.md
```

| Model    | Page                | Token source (logged-in DevTools Console)   | Env var          |
|----------|---------------------|---------------------------------------------|------------------|
| GLM      | `chat.z.ai`         | `localStorage.getItem("token")`             | `GLM_TOKEN`      |
| DeepSeek | `chat.deepseek.com` | `localStorage` `userToken` → `value`        | `DEEPSEEK_TOKEN` |
| Qwen     | `chat.qwen.ai`      | one-time `python pipeline/ask_council.py --login qwen` (manual login, persists profile). Fallback: `QWEN_TOKEN` from `localStorage.getItem("token")` | `QWEN_TOKEN` (optional if profile saved) |

macOS: system Chrome auto-detected. Linux: set `BROWSER_PATH` or use `.browsers/chrome-linux64/chrome`.

## FAQ

**Do I need paid API keys?**
No. Ask-Council drives the free web chats you already use. Tokens are session cookies from your own logins, never billed.

**Which models are supported?**
GLM (Zhipu `chat.z.ai`), DeepSeek (`chat.deepseek.com`), Qwen (`chat.qwen.ai`). Filter per run: `--models glm,qwen`. Registry is fixed for v1.

**How is this different from calling three APIs?**
There are no APIs — it automates the web UIs with `zendriver`, waits for each answer to stabilize, and hands raw Opinions to your host model, which acts as Chairman. No middleman service, everything runs locally.

**What if only one model answers?**
You still get its Opinion with a warning; synthesis is skipped. No fake consensus, ever.

**Does it work with my assistant?**
Yes — ChatGPT, Claude, Gemini, or any host that can read `SKILL.md`. Drop in `SKILL.md` + `pipeline/` and that assistant becomes Chairman.

## Layout

```
.
├── SKILL.md               # host instructions (lean, agent-facing)
├── pipeline/
│   ├── ask_council.py     # CLI fan-out + --check doctor + markdown output
│   ├── glm_web.py         # chat.z.ai driver
│   ├── deepseek_web.py    # chat.deepseek.com driver
│   └── qwen_web.py        # chat.qwen.ai driver
├── setup.sh               # one-command installer
├── .env.example
└── requirements.txt
```

## Notes

- One-shot browser per model per run (per-model `--timeout`, default 300s — models often think for minutes; `0` = wait indefinitely). `--judge glm` gives a standalone verdict without a Host.
- Qwen rejects bare-JWT injection in sterile profiles (bot cookies don't transfer) — run `--login qwen` once; the persistent profile (`~/.ask-council/profiles/qwen`) is reused after.
- `Failed to connect to browser` system-wide → quit/reopen Chrome (auto-update skew) and re-run `--check`.
