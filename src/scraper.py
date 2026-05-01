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


def discover_chapters(context: BrowserContext, course_url: str) -> list[Chapter]:
    """Load course index page and extract all chapter links."""
    course_slug = parse_course_url(course_url)
    index_url = build_course_index_url(course_url, course_slug)

    page = context.new_page()
    try:
        page.goto(index_url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        # Find all links under this course
        links = page.query_selector_all(f'a[href*="/courses/{course_slug}/"]')
        chapters = []
        seen_slugs = set()

        for link in links:
            href = link.get_attribute("href") or ""
            text = link.inner_text().strip()
            if not text:
                continue

            # Extract the chapter slug from href
            link_path = urlparse(href).path.rstrip("/")
            parts = link_path.split("/")
            if len(parts) < 3:
                continue
            chapter_slug = parts[-1]
            if chapter_slug == course_slug or chapter_slug in seen_slugs:
                continue

            full_url = href if href.startswith("http") else urljoin(index_url, href)
            seen_slugs.add(chapter_slug)
            chapters.append(Chapter(
                index=len(chapters) + 1,
                title=text,
                url=full_url,
                slug=chapter_slug,
            ))
    finally:
        page.close()

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
        page.goto(chapter.url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(1500)

        # Extract the main content area
        content = page.query_selector("article") or page.query_selector("[role='main']") or page.query_selector("main")
        if content:
            raw_html = content.inner_html()
        else:
            raw_html = page.content()

        cache_file.write_text(raw_html, encoding="utf-8")

        # Download assets
        assets = _download_assets(page, chapter.index, assets_dir)

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

        # Rate limit between pages (not after last page)
        if i < len(chapters) - 1:
            delay = random.uniform(delay_min, delay_max)
            logger.info(f"Waiting {delay:.1f}s before next page...")
            time.sleep(delay)

    return results


def _download_assets(
    page,
    chapter_index: int,
    assets_dir: Path,
) -> list[Asset]:
    """Download all images from the current page."""
    assets = []
    counter = 0

    # Get base URL for resolving relative paths
    base_url = page.url

    images = page.query_selector_all("img")
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

        # Strip query params for extension detection
        path_without_query = urlparse(full_url).path
        ext = os.path.splitext(path_without_query)[1].lower() or ".png"
        media_type = MIME_MAP.get(ext, "image/png")

        counter += 1
        filename = f"ch{chapter_index:02d}-{counter:03d}{ext}"
        local_path = assets_dir / filename

        if not local_path.exists():
            try:
                response = page.request.get(full_url)
                if response.ok:
                    local_path.write_bytes(response.body())
                    logger.info(f"  Downloaded: {filename}")
                else:
                    logger.warning(f"  Failed to download {full_url}: HTTP {response.status}")
            except Exception as e:
                logger.warning(f"  Failed to download {full_url}: {e}")

        assets.append(Asset(
            filename=filename,
            original_url=full_url,
            media_type=media_type,
        ))

    return assets
