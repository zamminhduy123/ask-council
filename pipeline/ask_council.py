"""ask-council CLI: parallel fan-out to free web LLMs, markdown for Host verdict."""
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

REGISTRY = {
    "glm": ("glm_web", "GLM_TOKEN"),
    "deepseek": ("deepseek_web", "DEEPSEEK_TOKEN"),
    "qwen": ("qwen_web", "QWEN_TOKEN"),
}

JUDGE_PROMPT = (
    "You are the Chairman of an AI Council. Review the individual opinions below.\n"
    "Highlight: 1) Points of consensus, 2) Contradictions or blind spots, "
    "3) Final synthesized best recommendation.\n"
)


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    except Exception:
        pass


FIX_HINTS = {
    "glm": 'chat.z.ai DevTools Console → localStorage.getItem("token") → GLM_TOKEN',
    "deepseek": "chat.deepseek.com DevTools → localStorage userToken → value → DEEPSEEK_TOKEN",
    "qwen": 'chat.qwen.ai DevTools Console → localStorage.getItem("token") → QWEN_TOKEN',
}


async def _check_one(model, timeout=60):
    mod_name, env_key = REGISTRY[model]
    if not os.environ.get(env_key):
        return model, False, f"Missing {env_key}. Fix: {FIX_HINTS[model]}"
    try:
        mod = __import__(mod_name)

        async def _login():
            browser = await mod.launch()
            try:
                await mod.login_token(browser)
                return True
            finally:
                try:
                    await browser.stop()
                except Exception:
                    pass

        await asyncio.wait_for(_login(), timeout)
        return model, True, "OK (browser + token)"
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        if "Failed to connect to browser" in msg:
            msg += " | Fix: quit/reopen Chrome (auto-update skew), retry"
        elif "token rejected" in msg or "Log in" in msg:
            msg += f" | Fix: refresh token: {FIX_HINTS[model]}"
        elif "Missing" in msg or "export" in msg:
            msg += f" | Fix: {FIX_HINTS[model]}"
        return model, False, msg


def _doctor(models):
    print("Ask-Council doctor: browser + token check (no council run)\n")
    all_ok = True
    for m in models:
        _, env_key = REGISTRY[m]
        has = bool(os.environ.get(env_key))
        print(f"[{m}] token {env_key}: {'present' if has else 'MISSING'}")
        try:
            _, ok, msg = asyncio.run(_check_one(m))
        except Exception as e:
            ok, msg = False, f"{type(e).__name__}: {e}"
        print(f"[{m}] {'OK' if ok else 'FAIL'}: {msg}\n")
        all_ok = all_ok and ok
    if all_ok:
        print("All models ready. Run: python pipeline/ask_council.py \"Your question\" --out opinions.md")
    else:
        print("Some models failed. Fix hints above, then re-run --check.")
    return 0 if all_ok else 1


async def _run_one(model, prompt, timeout):
    mod_name, env_key = REGISTRY[model]
    if not os.environ.get(env_key):
        return model, None, f"Missing {env_key} (disabled)"
    try:
        mod = __import__(mod_name)
        text = await asyncio.wait_for(mod.ask(prompt, timeout=timeout), timeout + 30)
        return model, text, None
    except Exception as e:
        return model, None, f"{type(e).__name__}: {e}"


async def _gather(prompt, models, timeout):
    tasks = [_run_one(m, prompt, timeout) for m in models]
    return await asyncio.gather(*tasks)


def _to_markdown(prompt, results):
    lines = [f"USER QUERY: {prompt}", "---"]
    for model, text, err in results:
        lines.append(f"## OPINION [{model}]")
        lines.append(text.strip() if text else f"_FAILED: {err}_")
        lines.append("---")
    ok = sum(1 for _, t, _ in results if t)
    if ok == 0:
        lines.append("_WARNING: all models failed. No verdict possible._")
    elif ok == 1:
        lines.append("_WARNING: only 1 model succeeded. Skipping synthesis; treat its Opinion as provisional._")
    return "\n".join(lines) + "\n"


async def _judge(prompt, results, judge_model, timeout):
    ok = [(m, t) for m, t, _ in results if t]
    if len(ok) < 2:
        return None
    payload = f"USER QUERY: {prompt}\n---\n" + "\n---\n".join(
        f"OPINION [{m}]:\n{t}" for m, t in ok
    )
    mod_name, env_key = REGISTRY[judge_model]
    if not os.environ.get(env_key):
        return f"_Judge {judge_model} disabled (missing {env_key})._"
    mod = __import__(mod_name)
    try:
        verdict = await asyncio.wait_for(
            mod.ask(JUDGE_PROMPT + "\n" + payload, timeout=timeout), timeout + 30
        )
        return verdict.strip()
    except Exception as e:
        return f"_Judge failed: {type(e).__name__}: {e}_"


def main():
    _load_env()
    ap = argparse.ArgumentParser(description="Convene a council of free web LLMs")
    ap.add_argument("prompt", nargs="?", help="User query (or omit to read stdin)")
    ap.add_argument("--models", default="glm,deepseek,qwen",
                    help="Comma list from glm,deepseek,qwen (default: all)")
    ap.add_argument("--timeout", type=int, default=180, help="Per-model timeout seconds")
    ap.add_argument("--out", default="", help="Write opinions markdown to file")
    ap.add_argument("--judge", default="", help="Optional standalone judge model")
    ap.add_argument("--check", action="store_true", help="Doctor: validate browser + tokens, no council run")
    args = ap.parse_args()

    models = [m.strip().lower() for m in args.models.split(",") if m.strip().lower() in REGISTRY]
    if not models:
        ap.error(f"--models must be subset of {list(REGISTRY)}")

    if args.check:
        sys.exit(_doctor(models))

    if args.prompt:
        prompt = args.prompt
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read().strip()
    else:
        prompt = ""
    if not prompt:
        ap.error("empty prompt")

    results = asyncio.run(_gather(prompt, models, args.timeout))
    md = _to_markdown(prompt, results)

    verdict = None
    if args.judge:
        jm = args.judge.strip().lower()
        if jm not in REGISTRY:
            ap.error(f"--judge must be one of {list(REGISTRY)}")
        verdict = asyncio.run(_judge(prompt, results, jm, args.timeout))
        md += f"\n## VERDICT (judge={jm})\n{verdict}\n"

    if args.out:
        Path(args.out).write_text(md)
        print(f"wrote {args.out} ({sum(1 for _,t,_ in results if t)}/{len(results)} succeeded)")
    print(md)
    if verdict:
        print(f"\n## VERDICT (judge={args.judge})\n{verdict}")


if __name__ == "__main__":
    main()
