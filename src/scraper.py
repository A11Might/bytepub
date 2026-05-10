import json
import logging
import os
import random
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.sync_api import BrowserContext

from src.models import Asset, Chapter, ScrapedPage

logger = logging.getLogger(__name__)

MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


def parse_course_url(url: str) -> str:
    """Extract course slug from a ByteByteGo URL."""
    path = urlparse(url).path.rstrip("/")
    parts = path.split("/")
    try:
        courses_idx = parts.index("courses")
    except ValueError:
        raise ValueError(f"URL does not contain a course path: {url}")
    if courses_idx + 1 >= len(parts):
        raise ValueError(f"URL does not contain a course slug: {url}")
    return parts[courses_idx + 1]


def build_cache_filename(index: int, slug: str) -> str:
    return f"{index:02d}-{slug}.html"


def build_course_index_url(url: str, course_slug: str) -> str:
    """Build the course index page URL from any URL within the course."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}/courses/{course_slug}"


def discover_chapters(context: BrowserContext, course_url: str, output_dir: Path | None = None) -> list[Chapter]:
    """Load a chapter page and extract all chapters from the sidebar menu."""
    course_slug = parse_course_url(course_url)

    # Check cache
    if output_dir:
        cache_file = output_dir / "cache" / "chapters.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("course_slug") == course_slug:
                logger.info(f"[cache hit] Chapter list for {course_slug}")
                return [Chapter(**ch) for ch in data["chapters"]]

    page = context.new_page()
    try:
        page.goto(course_url, wait_until="domcontentloaded", timeout=30000)
        # Wait for sidebar to render
        page.wait_for_selector("li.ant-menu-item", timeout=15000)
        page.wait_for_timeout(1000)

        # Chapters are in aside > ant-menu-item with data-menu-id containing the course path
        items = page.query_selector_all("li.ant-menu-item")
        chapters = []

        for item in items:
            menu_id = item.get_attribute("data-menu-id") or ""
            # data-menu-id format: "rc-menu-uuid-XXXXX-1-/courses/{slug}/{chapter}"
            if f"/courses/{course_slug}/" not in menu_id:
                continue

            # Extract path from data-menu-id (after the last course slug segment)
            path = menu_id.split(f"/courses/{course_slug}/")[-1]
            chapter_slug = path.strip("/")

            # Get title from <strong> inside the menu item
            strong = item.query_selector("strong")
            title = strong.inner_text().strip() if strong else ""
            if not title:
                continue

            full_url = f"https://bytebytego.com/courses/{course_slug}/{chapter_slug}"
            chapters.append(Chapter(
                index=len(chapters) + 1,
                title=title,
                url=full_url,
                slug=chapter_slug,
            ))
    finally:
        page.close()

    # Save cache
    if output_dir:
        cache_file = output_dir / "cache" / "chapters.json"
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({
            "course_slug": course_slug,
            "chapters": [{"index": ch.index, "title": ch.title, "url": ch.url, "slug": ch.slug} for ch in chapters],
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    return chapters


def fetch_page(
    context: BrowserContext,
    chapter: Chapter,
    output_dir: Path,
    force_refresh: bool = False,
) -> ScrapedPage:
    """Fetch a single chapter page. Uses cache if available."""
    cache_dir = output_dir / "cache"
    assets_dir = output_dir / "assets"
    cache_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    cache_file = cache_dir / build_cache_filename(chapter.index, chapter.slug)

    if not force_refresh and cache_file.exists():
        logger.info(f"[cache hit] Chapter {chapter.index}: {chapter.title}")
        return ScrapedPage(
            chapter=chapter,
            raw_html=cache_file.read_text(encoding="utf-8"),
            cached=True,
        )

    logger.info(f"[fetching] Chapter {chapter.index}: {chapter.title}")
    page = context.new_page()
    try:
        page.goto(chapter.url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector("article, [role='main'], main", timeout=15000)
        page.wait_for_timeout(1500)

        # Extract the main content area
        content = page.query_selector("article") or page.query_selector("[role='main']") or page.query_selector("main")
        if content:
            raw_html = content.inner_html()
        else:
            raw_html = page.content()

        cache_file.write_text(raw_html, encoding="utf-8")

        # Download assets (scope to content area so numbering matches cleaner)
        scope = content or page
        assets = _download_assets(scope, page, chapter.index, assets_dir)

        return ScrapedPage(
            chapter=chapter,
            raw_html=raw_html,
            assets=assets,
        )
    except Exception as e:
        logger.warning(f"[failed] Chapter {chapter.index}: {chapter.title} — {e}")
        raise
    finally:
        page.close()


def fetch_all(
    context: BrowserContext,
    chapters: list[Chapter],
    output_dir: Path,
    refresh_chapters: set[int] | None = None,
    delay_min: float = 3.0,
    delay_max: float = 8.0,
) -> list[ScrapedPage]:
    """Fetch all chapters with rate limiting."""
    results = []
    for i, chapter in enumerate(chapters):
        force_refresh = refresh_chapters is not None and (
            len(refresh_chapters) == 0 or chapter.index in refresh_chapters
        )
        try:
            scraped = fetch_page(context, chapter, output_dir, force_refresh)
            results.append(scraped)
        except Exception as e:
            logger.warning(f"Skipping chapter {chapter.index}: {e}")
            continue

        # Rate limit between pages (only after actual fetch, not cache hits)
        if i < len(chapters) - 1 and not scraped.cached:
            delay = random.uniform(delay_min, delay_max)
            logger.info(f"Waiting {delay:.1f}s before next page...")
            time.sleep(delay)

    return results


def _detect_image_format(data: bytes) -> tuple[str, str]:
    """Detect actual image format from bytes. Returns (ext, media_type)."""
    if data[:4] == b'\x89PNG':
        return ".png", "image/png"
    if data[:3] == b'\xff\xd8\xff':
        return ".jpg", "image/jpeg"
    if data[:4] == b'RIFF' and b'WEBP' in data[:12]:
        return ".webp", "image/webp"
    if data[:4] == b'GIF8':
        return ".gif", "image/gif"
    if b'<svg' in data[:200]:
        return ".svg", "image/svg+xml"
    return ".png", "image/png"


def _download_assets(
    scope,
    page,
    chapter_index: int,
    assets_dir: Path,
) -> list[Asset]:
    """Download all images from the content scope (not the full page).

    Args:
        scope: The Playwright element to search for img tags (content area).
        page: The Playwright page (used for base URL and HTTP requests).
    """
    assets = []
    counter = 0

    # Get base URL for resolving relative paths
    base_url = page.url

    images = scope.query_selector_all("img")
    for img in images:
        src = img.get_attribute("src")
        if not src:
            continue
        if src.startswith("data:"):
            continue

        # Resolve relative URLs to absolute
        if src.startswith("/"):
            parsed = urlparse(base_url)
            full_url = f"{parsed.scheme}://{parsed.netloc}{src}"
        elif not src.startswith("http"):
            full_url = urljoin(base_url, src)
        else:
            full_url = src

        counter += 1

        # Download first, then detect actual format
        body = None
        try:
            response = page.request.get(full_url)
            if response.ok:
                body = response.body()
        except Exception as e:
            logger.warning(f"  Failed to download {full_url}: {e}")

        if body is None:
            # Use URL extension as fallback
            path_without_query = urlparse(full_url).path
            ext = os.path.splitext(path_without_query)[1].lower() or ".png"
            media_type = MIME_MAP.get(ext, "image/png")
        else:
            ext, media_type = _detect_image_format(body)

        filename = f"ch{chapter_index:02d}-{counter:03d}{ext}"
        local_path = assets_dir / filename

        if body and not local_path.exists():
            local_path.write_bytes(body)
            logger.info(f"  Downloaded: {filename} ({len(body):,} bytes, {media_type})")

        if body:
            assets.append(Asset(
                filename=filename,
                original_url=full_url,
                media_type=media_type,
            ))

    return assets
