"""Qwen-web minimal client (chat.qwen.ai, stable semantic hooks, token-only)."""
import os
from asyncio import sleep
from pathlib import Path
from time import time
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

LOGIN_URL = "https://chat.qwen.ai/"
TEXTBOX_CSS = "textarea.message-input-textarea"
TEXTBOX_FALLBACKS = [
    "textarea.message-input-textarea",
    "textarea",
    '[role="textbox"][contenteditable="true"]',
]
SEND_CSS = ".message-input-right-button-send"
DEFAULT_CHROME = Path(__file__).resolve().parent.parent / ".browsers" / "chrome-linux64" / "chrome"
PROFILE_DIR = Path.home() / ".ask-council" / "profiles" / "qwen"


async def launch(headless=True, user_data_dir=None):
    """Start zendriver browser on Qwen chat, best-effort CF bypass."""
    import zendriver
    kwargs = {"headless": headless, "sandbox": False}
    if user_data_dir:
        kwargs["user_data_dir"] = str(user_data_dir)
    browser_bin = os.environ.get("BROWSER_PATH")
    if (not browser_bin or "chrome-headless-shell" in browser_bin) and DEFAULT_CHROME.is_file():
        browser_bin = str(DEFAULT_CHROME)
    if not browser_bin:
        for mac_path in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ):
            if Path(mac_path).is_file():
                browser_bin = mac_path
                break
    if browser_bin:
        kwargs["browser_executable_path"] = browser_bin

    browser = await zendriver.start(**kwargs)
    await browser.get(LOGIN_URL)
    try:
        cf_box = await browser.main_tab.query_selector("#cf-turnstile")
        if cf_box:
            await browser.main_tab.verify_cf(timeout=5)
    except Exception:
        pass  # no challenge presented
    return browser


async def _is_logged_out(browser):
    """True if header shows a *visible* Log in button."""
    return await browser.main_tab.evaluate(
        """(() => {
          return [...document.querySelectorAll('button')]
            .some(b => b.offsetParent && (b.innerText || '').includes('Log in'));
        })()""",
        await_promise=True, return_by_value=True,
    )


async def login_token(browser, token=None):
    """Login via saved profile or localStorage token; raise if logged out."""
    # Saved profile (from --login) may already hold a live session.
    if not await _is_logged_out(browser):
        return
    token = token or os.environ.get("QWEN_TOKEN")
    assert token, "export QWEN_TOKEN first (or run: python pipeline/ask_council.py --login qwen)"
    # Qwen stores raw JWT in localStorage `token` (DevTools: localStorage.getItem("token"))
    await browser.main_tab.evaluate(
        f"localStorage.setItem('token', '{token}')",
        await_promise=True, return_by_value=True,
    )
    await browser.main_tab.reload()
    await sleep(4)
    last_err = None
    for sel in TEXTBOX_FALLBACKS:
        try:
            await browser.main_tab.select(sel, timeout=5)
            break
        except Exception as e:
            last_err = e
    else:
        raise RuntimeError(f"Qwen login failed: composer not found ({last_err})")
    if await _is_logged_out(browser):
        raise RuntimeError("Qwen token rejected (page shows Log in). Try: python pipeline/ask_council.py --login qwen")


async def _click_send(browser):
    """Click Qwen send button or fallback to closest button / Enter."""
    await browser.main_tab.evaluate(
        """(() => {
          const sels = [
            '.message-input-right-button-send button',
            '.message-input-right-button-send',
            'button[aria-label="\\u53d1\\u9001\\u6d88\\u606f"]',
            'button[aria-label="Send"]'
          ];
          for (const s of sels) {
            const btn = document.querySelector(s);
            if (btn && !btn.disabled) { btn.click(); return; }
          }
          const ta = document.querySelector('textarea.message-input-textarea')
            || document.querySelector('textarea');
          const btns = [...document.querySelectorAll('button')];
          if (ta) {
            const r = ta.getBoundingClientRect();
            let best = null, bd = 1e12;
            for (const b of btns) {
              const q = b.getBoundingClientRect();
              const d = Math.hypot(q.left - r.right, q.top - r.top);
              if (d < bd) { bd = d; best = b; }
            }
            if (best && !best.disabled) { best.click(); return; }
          }
          if (btns.length) { btns[btns.length - 1].click(); return; }
          throw new Error('send button not found');
        })()""",
        await_promise=True, return_by_value=True,
    )


def _scrape(html):
    """Extract final answer text; "" while only the thinking card is present."""
    from bs4 import BeautifulSoup
    from inscriptis import get_text
    soup = BeautifulSoup(html, "html.parser")
    # Answer body first: present only once streaming finishes.
    nodes = soup.select(".response-message-content.phase-answer")
    if not nodes:
        nodes = soup.select(".custom-qwen-markdown")
    if not nodes:
        nodes = soup.select("[data-chat-answers-wrap]")
    if not nodes:
        nodes = soup.select("#qk-markdown-react")
    if nodes:
        return get_text(str(nodes[-1])).strip()
    # No answer body yet. If the thinking card (.qwen-chat-status-card + Skip)
    # is live its text churns — report "" so the stability loop keeps waiting
    # instead of tracking thinking text forever.
    if soup.select(".qwen-chat-status-card"):
        return ""
    # Thinking gone but no body class (render variant): use wrapper text.
    wrap = soup.select(".qwen-chat-message-assistant, .chat-response-message")
    if not wrap:
        return ""
    text = get_text(str(wrap[-1])).strip()
    lines = [ln for ln in text.splitlines() if ln.strip().lower() not in ("skip",)]
    return "\n".join(lines).strip()


async def _select_composer(browser, timeout=15):
    """Return composer element, trying stable selector then fallbacks."""
    last_err = None
    for sel in TEXTBOX_FALLBACKS:
        try:
            return await browser.main_tab.select(sel, timeout=5)
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Qwen composer not found ({last_err})")


async def send_message(browser, message, timeout=300):
    """Send message, wait for stable response text, return it."""
    box = await _select_composer(browser)
    # send_keys fires real keystrokes so the send button arms
    # (programmatic fill leaves it inert on Qwen Studio).
    try:
        await box.send_keys(message)
    except Exception:
        # contenteditable fallback: focus + execCommand insert
        import json
        msg_json = json.dumps(message)
        await browser.main_tab.evaluate(
            f"""(() => {{
              const ed = document.querySelector('[role="textbox"][contenteditable="true"]');
              if (ed) {{
                ed.focus();
                document.execCommand('selectAll', false, null);
                document.execCommand('insertText', false, {msg_json});
                return;
              }}
              const ta = document.querySelector('textarea.message-input-textarea')
                || document.querySelector('textarea');
              if (!ta) throw new Error('composer not found');
              ta.focus();
              ta.value = {msg_json};
              ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
              ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }})()""",
            await_promise=True, return_by_value=True,
        )
    await sleep(0.6)
    await _click_send(browser)
    end, last, stable_since = time() + timeout, "", time()
    while time() < end:
        await sleep(3)
        html = await browser.main_tab.evaluate(
            "document.documentElement.outerHTML", await_promise=True, return_by_value=True,
        )
        text = _scrape(html)
        if not text or _is_transient(text):
            continue  # still streaming / researching, not an answer yet
        if text != last:
            last, stable_since = text, time()
        if time() - stable_since > 6:
            # Completion signal mirrors DeepSeek/GLM: 6s DOM stability.
            # Qwen also mounts .copy-response-button on done; stability covers both.
            return last
    raise TimeoutError("no stable response in timeout")


def _is_transient(text):
    """True for short research/status labels (e.g. "Reading sources…"), not answers."""
    import re
    t = text.strip()
    return bool(re.fullmatch(r"(Reading sources…?|Thinking…?|Reasoning…?|Searching…?|Analyzing…?)", t))


def _saved_profile():
    """Return persistent profile dir if user completed --login once, else None."""
    return str(PROFILE_DIR) if PROFILE_DIR.joinpath("Default").is_dir() else None


async def ask(message, token=None, timeout=300):
    """One-shot: launch (saved profile if present), login, ask, close, return text."""
    browser = await launch(user_data_dir=_saved_profile())
    try:
        await login_token(browser, token)
        return await send_message(browser, message, timeout)
    finally:
        try:
            await browser.stop()
        except Exception:
            pass
