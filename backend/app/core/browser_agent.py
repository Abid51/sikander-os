"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IGRIS BROWSER AUTOMATION AGENT
  Real web automation: browse, click, fill forms, extract data
  Uses Playwright (async) — no fake stubs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import logging

logger = logging.getLogger(__name__)

# ── Try importing Playwright ──────────────────────────────────────────────────
try:
    from playwright.async_api import async_playwright, Browser, Page, Playwright
    _PLAYWRIGHT = True
except ImportError:
    _PLAYWRIGHT = False
    logger.warning("[BROWSER] Playwright not installed. Run: pip install playwright && playwright install chromium")


# ─────────────────────────────────────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BrowseResult:
    url: str
    title: str
    text: str
    html: str
    screenshot_b64: Optional[str]
    links: List[Dict[str, str]]
    timestamp: float = field(default_factory=time.time)
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # Don't return huge html/screenshot in normal responses
        d.pop("html", None)
        if self.screenshot_b64:
            d["has_screenshot"] = True
            d.pop("screenshot_b64", None)
        return d


@dataclass
class ActionResult:
    action: str
    target: str
    success: bool
    message: str
    timestamp: float = field(default_factory=time.time)
    data: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────────────────────
#  BROWSER AGENT
# ─────────────────────────────────────────────────────────────────────────────

class IgrisBrowserAgent:
    """
    Igris ki aankhein aur haath — web automation engine.

    Capabilities
    ─────────────
    • Navigate to any URL and extract clean text
    • Take screenshots (base64 encoded)
    • Click elements by selector, text, or aria-label
    • Fill forms with text
    • Extract all links from a page
    • Search Google/Bing and return results
    • Multi-step task execution
    • Headless or visible browser mode
    """

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._history: List[Dict[str, Any]] = []
        self._active = False
        self._available = _PLAYWRIGHT

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> bool:
        """Start browser session."""
        if not _PLAYWRIGHT:
            logger.error("[BROWSER] Playwright not installed.")
            return False
        if self._active:
            return True
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            self._page = await self._browser.new_page()
            # Set realistic user agent
            await self._page.set_extra_http_headers({
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                )
            })
            self._active = True
            logger.info("[BROWSER] ⚡ Browser session started.")
            return True
        except Exception as e:
            logger.error(f"[BROWSER] Start failed: {e}")
            return False

    async def stop(self) -> None:
        """Close browser session."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass
        self._active = False
        self._browser = None
        self._playwright = None
        self._page = None
        logger.info("[BROWSER] Session closed.")

    async def _ensure_started(self) -> bool:
        if not self._active:
            return await self.start()
        return True

    # ── Core Navigation ───────────────────────────────────────────────────────

    async def browse(self, url: str, take_screenshot: bool = False) -> BrowseResult:
        """Navigate to URL and extract content."""
        if not await self._ensure_started():
            return BrowseResult(
                url=url, title="", text="", html="", screenshot_b64=None, links=[],
                success=False, error="Playwright not available. Run: pip install playwright && playwright install chromium"
            )
        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1)  # Let JS render

            title = await self._page.title()

            # Extract readable text (remove scripts/styles)
            text = await self._page.evaluate("""() => {
                const scripts = document.querySelectorAll('script, style, nav, footer, aside');
                scripts.forEach(el => el.remove());
                return document.body?.innerText?.slice(0, 5000) || '';
            }""")

            # Extract links
            links_raw = await self._page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .slice(0, 30)
                    .map(a => ({ text: a.innerText.trim().slice(0, 100), href: a.href }))
                    .filter(l => l.href.startsWith('http'));
            }""")

            # Screenshot
            screenshot_b64 = None
            if take_screenshot:
                ss_bytes = await self._page.screenshot(type="png", full_page=False)
                screenshot_b64 = base64.b64encode(ss_bytes).decode("utf-8")

            html = await self._page.content()

            result = BrowseResult(
                url=self._page.url,
                title=title,
                text=text.strip(),
                html=html[:10000],
                screenshot_b64=screenshot_b64,
                links=links_raw,
            )
            self._history.append({"action": "browse", "url": url, "title": title, "ts": time.time()})
            return result

        except Exception as e:
            logger.error(f"[BROWSER] Browse error: {e}")
            return BrowseResult(url=url, title="", text="", html="", screenshot_b64=None,
                                links=[], success=False, error=str(e))

    # ── Actions ───────────────────────────────────────────────────────────────

    async def click(self, selector: str) -> ActionResult:
        """Click an element by CSS selector."""
        if not await self._ensure_started():
            return ActionResult("click", selector, False, "Browser not started")
        try:
            await self._page.click(selector, timeout=10000)
            await asyncio.sleep(0.5)
            self._history.append({"action": "click", "selector": selector, "ts": time.time()})
            return ActionResult("click", selector, True, f"Clicked: {selector}")
        except Exception as e:
            return ActionResult("click", selector, False, str(e))

    async def click_text(self, text: str) -> ActionResult:
        """Click element containing specific text."""
        if not await self._ensure_started():
            return ActionResult("click_text", text, False, "Browser not started")
        try:
            await self._page.get_by_text(text).first.click(timeout=10000)
            await asyncio.sleep(0.5)
            self._history.append({"action": "click_text", "text": text, "ts": time.time()})
            return ActionResult("click_text", text, True, f"Clicked text: {text}")
        except Exception as e:
            return ActionResult("click_text", text, False, str(e))

    async def fill_input(self, selector: str, value: str) -> ActionResult:
        """Fill an input field."""
        if not await self._ensure_started():
            return ActionResult("fill", selector, False, "Browser not started")
        try:
            await self._page.fill(selector, value, timeout=10000)
            self._history.append({"action": "fill", "selector": selector, "ts": time.time()})
            return ActionResult("fill", selector, True, f"Filled '{selector}' with value")
        except Exception as e:
            return ActionResult("fill", selector, False, str(e))

    async def press_key(self, key: str) -> ActionResult:
        """Press a keyboard key (e.g., 'Enter', 'Tab', 'Escape')."""
        if not await self._ensure_started():
            return ActionResult("press", key, False, "Browser not started")
        try:
            await self._page.keyboard.press(key)
            return ActionResult("press", key, True, f"Pressed: {key}")
        except Exception as e:
            return ActionResult("press", key, False, str(e))

    async def screenshot(self) -> Optional[str]:
        """Take screenshot, return base64 string."""
        if not await self._ensure_started():
            return None
        try:
            ss_bytes = await self._page.screenshot(type="png", full_page=False)
            return base64.b64encode(ss_bytes).decode("utf-8")
        except Exception:
            return None

    async def extract_table(self, selector: str = "table") -> List[List[str]]:
        """Extract data from an HTML table."""
        if not await self._ensure_started():
            return []
        try:
            rows = await self._page.evaluate(f"""(sel) => {{
                const table = document.querySelector(sel);
                if (!table) return [];
                return Array.from(table.querySelectorAll('tr')).map(row =>
                    Array.from(row.querySelectorAll('td, th')).map(cell => cell.innerText.trim())
                );
            }}""", selector)
            return rows
        except Exception:
            return []

    async def get_current_url(self) -> str:
        if not self._page:
            return ""
        return self._page.url

    async def get_page_text(self) -> str:
        """Get clean text from current page."""
        if not await self._ensure_started():
            return ""
        try:
            return await self._page.evaluate("""() =>
                document.body?.innerText?.slice(0, 8000) || ''
            """)
        except Exception:
            return ""

    # ── High-Level Tasks ──────────────────────────────────────────────────────

    async def google_search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """Search Google and return structured results."""
        result = await self.browse(f"https://www.google.com/search?q={query.replace(' ', '+')}")
        if not result.success:
            return []
        try:
            results = await self._page.evaluate(f"""() => {{
                const items = document.querySelectorAll('.g');
                return Array.from(items).slice(0, {max_results}).map(item => ({{
                    title: item.querySelector('h3')?.innerText || '',
                    url: item.querySelector('a')?.href || '',
                    snippet: item.querySelector('.VwiC3b, .s3v9rd, .st')?.innerText?.slice(0, 200) || ''
                }})).filter(r => r.title && r.url);
            }}""")
            self._history.append({"action": "google_search", "query": query, "ts": time.time()})
            return results
        except Exception:
            return []

    async def multi_step_task(self, steps: List[Dict[str, Any]]) -> List[ActionResult]:
        """
        Execute a sequence of browser actions.
        Steps format: [{"action": "navigate", "url": "..."}, {"action": "click", "selector": "..."}, ...]
        Supported actions: navigate, click, click_text, fill, press, screenshot, extract_table
        """
        results = []
        for step in steps:
            action = step.get("action", "")
            try:
                if action == "navigate":
                    r = await self.browse(step.get("url", ""))
                    results.append(ActionResult(action, step.get("url", ""), r.success, r.title or r.error or ""))
                elif action == "click":
                    results.append(await self.click(step.get("selector", "")))
                elif action == "click_text":
                    results.append(await self.click_text(step.get("text", "")))
                elif action == "fill":
                    results.append(await self.fill_input(step.get("selector", ""), step.get("value", "")))
                elif action == "press":
                    results.append(await self.press_key(step.get("key", "Enter")))
                elif action == "wait":
                    await asyncio.sleep(step.get("seconds", 1))
                    results.append(ActionResult("wait", "", True, f"Waited {step.get('seconds', 1)}s"))
                else:
                    results.append(ActionResult(action, "", False, f"Unknown action: {action}"))
            except Exception as e:
                results.append(ActionResult(action, str(step), False, str(e)))
                if step.get("stop_on_error", False):
                    break
        return results

    # ── History & Status ──────────────────────────────────────────────────────

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._history[-limit:]

    def get_status(self) -> Dict[str, Any]:
        return {
            "playwright_available": _PLAYWRIGHT,
            "session_active": self._active,
            "headless": self._headless,
            "current_url": self._page.url if self._page and self._active else None,
            "history_count": len(self._history),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  SINGLETON
# ─────────────────────────────────────────────────────────────────────────────

_instance: Optional[IgrisBrowserAgent] = None


def get_browser_agent(headless: bool = True) -> IgrisBrowserAgent:
    global _instance
    if _instance is None:
        _instance = IgrisBrowserAgent(headless=headless)
    return _instance
