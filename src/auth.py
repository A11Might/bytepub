import json
import shutil
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright, BrowserContext

CHROME_USER_DATA = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
CHROME_CHANNEL = "chromium"  # Use chromium channel which is separate from running Chrome


def create_session(session_path: Path | None = None) -> tuple[sync_playwright, BrowserContext, BrowserContext]:
    """Launch browser using a copy of Chrome's profile to reuse login state.

    Copies Chrome's profile to a temp directory so we don't lock or modify
    the real Chrome profile. The user's existing cookies and login state are
    preserved.
    """
    pw = sync_playwright().start()

    # Copy Chrome Default profile to temp dir to avoid locking the real one
    temp_dir = Path(tempfile.mkdtemp(prefix="web-to-epub-"))
    profile_dir = temp_dir / "chrome-profile"
    default_profile = CHROME_USER_DATA / "Default"

    if default_profile.exists():
        # Copy only the files needed for cookies/auth, not the entire profile
        profile_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(default_profile), str(profile_dir / "Default"), dirs_exist_ok=True)
        # Copy Local State which contains encryption keys for cookies
        local_state = CHROME_USER_DATA / "Local State"
        if local_state.exists():
            shutil.copy2(str(local_state), str(profile_dir / "Local State"))
        print(f"Copied Chrome profile to {profile_dir}")
    else:
        print("No Chrome profile found, starting with fresh profile")
        profile_dir.mkdir(parents=True, exist_ok=True)

    context = pw.chromium.launch_persistent_context(
        str(profile_dir),
        headless=False,
        viewport={"width": 1280, "height": 900},
        channel=CHROME_CHANNEL,
        accept_downloads=True,
    )

    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://bytebytego.com/courses")

    # Check if already logged in (page loads course content)
    page.wait_for_load_state("networkidle")
    current_url = page.url

    if "/login" in current_url or "sign-in" in current_url:
        print("\n=== Please log in to ByteByteGo ===")
        print("Waiting for login to complete...")
        page.wait_for_url("**/courses**", timeout=300000)
        print("Login successful!")
    else:
        print("Already logged in via Chrome profile!")

    # Save session for future use
    if session_path:
        storage = context.storage_state()
        session_path.write_text(json.dumps(storage, indent=2))
        print(f"Session saved to {session_path}")

    return pw, context, profile_dir


def load_session(session_path: Path) -> tuple[sync_playwright, BrowserContext, Path]:
    """Load a previously saved session."""
    pw = sync_playwright().start()
    temp_dir = Path(tempfile.mkdtemp(prefix="web-to-epub-"))
    profile_dir = temp_dir / "chrome-profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    context = pw.chromium.launch_persistent_context(
        str(profile_dir),
        headless=False,
        viewport={"width": 1280, "height": 900},
        channel=CHROME_CHANNEL,
    )

    # Add saved cookies
    storage = json.loads(session_path.read_text())
    context.add_cookies(storage.get("cookies", []))
    print(f"Session loaded from {session_path}")

    return pw, context, profile_dir


def cleanup(pw: sync_playwright, context: BrowserContext, profile_dir: Path | None = None) -> None:
    """Close browser and stop Playwright. Cleans up temp profile."""
    context.close()
    pw.stop()
    # Clean up temp profile directory
    if profile_dir and profile_dir.exists():
        try:
            shutil.rmtree(profile_dir.parent)
        except Exception:
            pass
