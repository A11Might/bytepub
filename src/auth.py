import json
from pathlib import Path

from playwright.sync_api import sync_playwright, BrowserContext


def _parse_cookie_string(cookie_str: str) -> list[dict]:
    """Parse a cookie header string like 'name1=val1; name2=val2' into Playwright cookie format."""
    cookies = []
    for part in cookie_str.strip().split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, value = part.partition("=")
        cookies.append({
            "name": name.strip(),
            "value": value.strip(),
            "domain": ".bytebytego.com",
            "path": "/",
        })
    return cookies


def create_session(
    session_path: Path | None = None,
    cookie_string: str | None = None,
    cookie_file: Path | None = None,
) -> tuple[sync_playwright, BrowserContext]:
    """Launch browser and authenticate.

    Priority: cookie_string > cookie_file > interactive login
    """
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )

    if cookie_string:
        cookies = _parse_cookie_string(cookie_string)
        context.add_cookies(cookies)
        print(f"Loaded {len(cookies)} cookies from string")
    elif cookie_file and cookie_file.exists():
        raw = cookie_file.read_text().strip()
        cookies = _parse_cookie_string(raw)
        context.add_cookies(cookies)
        print(f"Loaded {len(cookies)} cookies from {cookie_file}")
    else:
        # Interactive login: open the login page, let user log in
        page = context.new_page()
        page.goto("https://bytebytego.com/login")
        print("\n=== Please log in to ByteByteGo in the browser ===")
        print("After login, navigate to any course page, then press Enter here...")
        try:
            input()
        except EOFError:
            # Fallback: wait for URL change
            page.wait_for_url("**/courses**", timeout=300000)
        print("Login successful!")
        # Don't close the page — keep the logged-in session alive
        page.close()

    # Save session for future use (auto-save if no explicit path)
    if not session_path:
        session_path = Path("output/.session.json")
    session_path.parent.mkdir(parents=True, exist_ok=True)
    storage = context.storage_state()
    session_path.write_text(json.dumps(storage, indent=2))
    print(f"Session saved to {session_path}")

    return pw, context


def load_session(session_path: Path) -> tuple[sync_playwright, BrowserContext]:
    """Load a previously saved session."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=False)
    storage = json.loads(session_path.read_text())
    context = browser.new_context(
        storage_state=storage,
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    print(f"Session loaded from {session_path}")
    return pw, context


def no_auth() -> tuple[sync_playwright, BrowserContext]:
    """Launch browser without any authentication. For pages that don't require login."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    print("Launched browser (no auth)")
    return pw, context


def cleanup(pw: sync_playwright, context: BrowserContext) -> None:
    """Close browser and stop Playwright."""
    try:
        context.close()
    except Exception:
        pass
    pw.stop()
