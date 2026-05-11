from pathlib import Path

from playwright.sync_api import sync_playwright, BrowserContext

USER_DATA_DIR = Path("output/.browser-data")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"


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
    print("Log in with your credentials, then press Enter here...")
    try:
        input()
    except EOFError:
        # Fallback: wait for URL change
        page.wait_for_url("**/courses**", timeout=300000)
    print("Login successful!")
    page.close()


def authenticated_session() -> tuple[sync_playwright, BrowserContext]:
    """Launch persistent context, reusing existing session or prompting for first-time login.

    Checks for the Default/ subdir in the browser data directory as a reliable
    indicator that browser data has been stored from a previous session.
    Firebase refresh tokens in IndexedDB auto-refresh the JWT on navigation.
    """
    has_session = (USER_DATA_DIR / "Default").exists()

    pw = sync_playwright().start()
    context = _launch_context(pw)

    if has_session:
        print("Reusing existing browser session")
    else:
        _interactive_login(context)

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
