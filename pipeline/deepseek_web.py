"""DeepSeek-web minimal client (fresh 2026 selectors, token-only)."""
import os
from asyncio import sleep
from pathlib import Path
from time import time
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

LOGIN_URL = "https://chat.deepseek.com/"
TEXTBOX_CSS = 'textarea[placeholder^="Message"]'
DEFAULT_CHROME = Path(__file__).resolve().parent.parent / ".browsers" / "chrome-linux64" / "chrome"


async def launch(headless=True):
    """Start zendriver browser on DeepSeek chat, best-effort CF bypass."""
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


async def login_token(browser, token=None):
    """Login via userToken, wait for chat textbox or raise."""
    token = token or os.environ.get("DEEPSEEK_TOKEN")
    assert token, "export DEEPSEEK_TOKEN first"
    await browser.main_tab.evaluate(
        f"localStorage.setItem('userToken', JSON.stringify({{value: '{token}', __version: '0'}}))",
        await_promise=True, return_by_value=True,
    )
    await browser.main_tab.reload()
    await sleep(3)
    await browser.main_tab.select(TEXTBOX_CSS, timeout=15)


async def _click_send(browser):
    """Click circular send button next to textarea or closest button."""
    await browser.main_tab.evaluate(
        """(() => {
          const btn = document.querySelector('div[role="button"].ds-button--circle');
          if (btn) {
            btn.click();
            return;
          }
          const ta = document.querySelector('textarea[placeholder^="Message"]');
          const btns = [...document.querySelectorAll('[role="button"]')];
          const r = ta.getBoundingClientRect();
          let best = null, bd = 1e12;
          for (const b of btns) {
            const q = b.getBoundingClientRect();
            const d = Math.hypot(q.left - r.right, q.top - r.top);
            if (d < bd) { bd = d; best = b; }
          }
          if (!best) throw new Error('send button not found');
          best.click();
        })()""",
        await_promise=True, return_by_value=True,
    )


def _scrape(html):
    """Extract ds-markdown blocks as text (stable design-system class)."""
    from bs4 import BeautifulSoup
    from inscriptis import get_text
    soup = BeautifulSoup(html, "html.parser")
    blocks = soup.find_all(class_=lambda c: c and "ds-markdown" in c)
    texts = []
    for b in blocks:
        t = get_text(str(b)).strip()
        if t and t not in texts:
            texts.append(t)
    # One-shot browser = single turn; join distinct blocks (dedup identical
    # renders), so multi-block answers aren't truncated.
    return "\n\n".join(texts)


async def send_message(browser, message, timeout=300):
    """Send message, wait for fresh ds-markdown response, return text."""
    box = await browser.main_tab.select(TEXTBOX_CSS, timeout=15)
    await box.send_keys(message)
    await _click_send(browser)
    end, last, stable_since = time() + timeout, "", time()
    while time() < end:
        await sleep(3)
        html = await browser.main_tab.evaluate(
            "document.documentElement.outerHTML", await_promise=True, return_by_value=True,
        )
        text = _scrape(html)
        if text and text != last:
            last, stable_since = text, time()
        if last and time() - stable_since > 6:
            if last.strip().lower() == "the server is busy. please try again later.":
                raise RuntimeError("DeepSeek server busy")
            return last
    raise TimeoutError("no stable response in timeout")


async def ask(message, token=None, timeout=300):
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
