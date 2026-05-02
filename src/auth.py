import json
from pathlib import Path

from playwright.sync_api import sync_playwright, BrowserContext

USER_DATA_DIR = Path("output/.browser-data")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


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


def _launch_context(pw, user_data_dir: Path | None = None):
    """Create a persistent browser context that survives across sessions.

    Uses launch_persistent_context so IndexedDB (Firebase refresh tokens),
    cookies, and localStorage are all persisted to disk automatically.
    """
    if user_data_dir is None:
        user_data_dir = USER_DATA_DIR
    user_data_dir.mkdir(parents=True, exist_ok=True)
    return pw.chromium.launch_persistent_context(
        str(user_data_dir),
        headless=False,
        viewport={"width": 1280, "height": 900},
        user_agent=UA,
    )


def _interactive_login(context) -> None:
    """Open login page and wait for user to complete login."""
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
    page.close()


def create_session(
    session_path: Path | None = None,
    cookie_string: str | None = None,
    cookie_file: Path | None = None,
) -> tuple[sync_playwright, BrowserContext]:
    """Launch browser and authenticate.

    Priority: cookie_string > cookie_file > interactive login
    """
    pw = sync_playwright().start()
    context = _launch_context(pw)

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
        _interactive_login(context)

    return pw, context


def load_session(session_path: Path) -> tuple[sync_playwright, BrowserContext]:
    """Load a previously saved browser session.

    Uses persistent context (output/.browser-data/) so IndexedDB is included.
    Firebase refresh tokens survive, enabling auto-renewal of the 1-hour JWT.
    """
    pw = sync_playwright().start()
    context = _launch_context(pw)
    print(f"Session loaded from persistent browser data")
    return pw, context


def no_auth() -> tuple[sync_playwright, BrowserContext]:
    """Launch browser without any authentication. For pages that don't require login."""
    pw = sync_playwright().start()
    context = _launch_context(pw)
    print("Launched browser (no auth)")
    return pw, context


def cleanup(pw: sync_playwright, context: BrowserContext) -> None:
    """Close browser and stop Playwright."""
    try:
        context.close()
    except Exception:
        pass
    pw.stop()
