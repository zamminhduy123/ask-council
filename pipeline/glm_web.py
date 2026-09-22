"""GLM-web minimal client (chat.z.ai, stable semantic hooks, token-only)."""
import json
import os
import re
from asyncio import sleep
from pathlib import Path
from time import time
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

LOGIN_URL = "https://chat.z.ai/"
DEFAULT_CHROME = Path(__file__).resolve().parent.parent / ".browsers" / "chrome-linux64" / "chrome"


async def launch(headless=True):
    """Start zendriver browser on Z.ai chat, best-effort CF bypass."""
    import zendriver
    kwargs = {"headless": headless, "sandbox": False}
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


async def _dismiss_modal(browser):
    """Dismiss promotional modal dialogs if present."""
    await browser.main_tab.evaluate(
        """(() => {
          const btns = Array.from(document.querySelectorAll('button'));
          const maybeLater = btns.find(b => b.innerText && b.innerText.includes('Maybe Later'));
          if (maybeLater) maybeLater.click();
        })()""",
        await_promise=True, return_by_value=True,
    )


async def login_token(browser, token=None):
    """Login via localStorage token, wait for chat box or raise."""
    token = token or os.environ.get("GLM_TOKEN")
    assert token, "export GLM_TOKEN first"
    await browser.main_tab.evaluate(
        f"localStorage.setItem('token', '{token}')",
        await_promise=True, return_by_value=True,
    )
    await browser.main_tab.reload()
    await sleep(4)
    await _dismiss_modal(browser)
    await browser.main_tab.select("textarea", timeout=15)


def _scrape(html):
    """Extract assistant response text from HTML."""
    from bs4 import BeautifulSoup
    from inscriptis import get_text
    soup = BeautifulSoup(html, "html.parser")
    assts = soup.find_all(class_=lambda c: c and "chat-assistant" in c)
    if not assts:
        return ""
    latest = assts[-1]
    # Remove thinking chain block if final answer exists
    cleaned = BeautifulSoup(str(latest), "html.parser")
    for tc in cleaned.find_all(class_=lambda c: c and "thinking-chain-container" in c):
        tc.decompose()
    text = get_text(str(cleaned)).strip()
    return text if text else get_text(str(latest)).strip()


async def send_message(browser, message, timeout=180):
    """Send message, wait for stable response text, return it."""
    await _dismiss_modal(browser)
    msg_json = json.dumps(message)
    await browser.main_tab.evaluate(
        f"""(() => {{
          const ta = document.querySelector('textarea');
          if (!ta) throw new Error('textarea not found');
          ta.focus();
          ta.value = {msg_json};
          ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
          ta.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }})()""",
        await_promise=True, return_by_value=True,
    )
    await sleep(1)
    await browser.main_tab.evaluate(
        """(() => {
          const sendBtn = document.querySelector('.sendMessageButton');
          if (sendBtn && !sendBtn.disabled) {
            sendBtn.click();
            return;
          }
          const ta = document.querySelector('textarea');
          if (ta) {
            const ev = new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true });
            ta.dispatchEvent(ev);
          }
        })()""",
        await_promise=True, return_by_value=True,
    )
    end, last, stable_since = time() + timeout, "", time()
    while time() < end:
        await sleep(3)
        html = await browser.main_tab.evaluate(
            "document.documentElement.outerHTML", await_promise=True, return_by_value=True,
        )
        text = _scrape(html)
        if not text or re.fullmatch(r"(Thinking\.{0,3}|\.{3})", text.strip(), re.I):
            continue  # still reasoning, not an answer yet
        if text != last:
            last, stable_since = text, time()
        if time() - stable_since > 6:
            return last
    raise TimeoutError("no stable response in timeout")


async def ask(message, token=None, timeout=180):
    """One-shot: launch, login, ask, close, return text."""
    browser = await launch()
    try:
        await login_token(browser, token)
        return await send_message(browser, message, timeout)
    finally:
        try:
            await browser.stop()
        except Exception:
            pass
