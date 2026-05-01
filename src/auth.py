import json
from pathlib import Path

from playwright.sync_api import sync_playwright, Browser, BrowserContext


def create_session(session_path: Path | None = None) -> tuple[sync_playwright, Browser, BrowserContext]:
    """Launch browser, let user log in, save session."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )
    page = context.new_page()
    page.goto("https://bytebytego.com/login")

    print("\n=== Please log in to ByteByteGo ===")
    print("Waiting for login to complete...")

    # Wait until we can access a course page (indicates successful login)
    page.wait_for_url("**/courses/**", timeout=300000)
    print("Login successful!")

    # Save session
    if session_path:
        storage = context.storage_state()
        session_path.write_text(json.dumps(storage, indent=2))
        print(f"Session saved to {session_path}")

    return pw, browser, context


def load_session(session_path: Path) -> tuple[sync_playwright, Browser, BrowserContext]:
    """Load a previously saved session."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=False)
    storage = json.loads(session_path.read_text())
    context = browser.new_context(storage_state=storage)
    print(f"Session loaded from {session_path}")
    return pw, browser, context


def cleanup(pw: sync_playwright, browser: Browser) -> None:
    """Close browser and stop Playwright."""
    browser.close()
    pw.stop()