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
        # Interactive login
        page = context.new_page()
        page.goto("https://bytebytego.com/login")
        print("\n=== Please log in to ByteByteGo ===")
        print("Note: Google OAuth may not work. Try email/password login.")
        print("Waiting for login to complete...")
        page.wait_for_url("**/courses**", timeout=300000)
        print("Login successful!")
        page.close()

    # Verify access by navigating to a course page
    page = context.new_page()
    page.goto("https://bytebytego.com/courses", wait_until="networkidle", timeout=15000)

    if "/login" in page.url or "sign-in" in page.url:
        page.close()
        raise RuntimeError(
            "Cookies are invalid or expired. Please re-export cookies from your browser."
        )
    print("Session verified!")
    page.close()

    # Save session for future use
    if session_path:
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


def cleanup(pw: sync_playwright, context: BrowserContext) -> None:
    """Close browser and stop Playwright."""
    context.close()
    pw.stop()
