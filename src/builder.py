import logging
import re
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from ebooklib import epub

from src.models import CleanedPage

logger = logging.getLogger(__name__)


def _convert_svg_to_png(svg_data: bytes, ctx=None) -> bytes | None:
    """Render SVG to PNG at 2x device scale factor using Playwright.

    Args:
        svg_data: Raw SVG bytes.
        ctx: Optional existing Playwright BrowserContext (reused across calls).
             If None, a new browser is launched and closed per call.

    Returns PNG bytes, or None if conversion fails.
    """
    from playwright.sync_api import sync_playwright

    own_browser = False
    try:
        svg_text = re.sub(
            r'<image[^>]*xlink:href="https?://[^"]*"[^>]*/?\s*>',
            '',
            svg_data.decode('utf-8'),
        )
        html = f"""<html><body style="margin:0;display:inline-block">
        {svg_text}
        </body></html>"""

        if ctx is None:
            pw = sync_playwright().start()
            browser = pw.chromium.launch()
            ctx = browser.new_context(
                device_scale_factor=2,
                viewport={"width": 800, "height": 600},
            )
            own_browser = True

        page = ctx.new_page()
        try:
            page.set_content(html, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(300)
            box = page.locator("svg").first.bounding_box()
            if box:
                vw = max(int(box["width"]) + 20, 800)
                vh = max(int(box["height"]) + 20, 600)
                page.set_viewport_size({"width": vw, "height": vh})
                box = page.locator("svg").first.bounding_box()
            png_bytes = page.screenshot(clip=box, timeout=10000)
        finally:
            page.close()

        if own_browser:
            ctx.close()
            browser.close()
            pw.stop()

        return png_bytes
    except Exception as e:
        logger.warning(f"SVG→PNG conversion failed: {e}")
        return None


def _convert_image_for_epub(body: bytes, ext: str, ctx=None) -> tuple[bytes | None, str | None]:
    """Convert image bytes to an EPUB-compatible format if needed.

    Args:
        body: Raw image bytes.
        ext: File extension (e.g. ".svg", ".webp", ".png").
        ctx: Optional Playwright BrowserContext for SVG rendering reuse.

    Returns (converted_body, media_type). PNG/JPG/JPEG/GIF pass through
    unchanged. WebP is converted to PNG via Pillow. SVG is rendered to
    PNG via Playwright at 2x DPR.

    Returns (None, None) if conversion fails and fallback is not possible.
    """
    if ext in (".png", ".jpg", ".jpeg", ".gif"):
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
        }[ext]
        return body, mime

    if ext == ".webp":
        try:
            from PIL import Image
            img = Image.open(BytesIO(body))
            png_buf = BytesIO()
            img.save(png_buf, format="PNG")
            return png_buf.getvalue(), "image/png"
        except Exception as e:
            logger.warning(f"WebP→PNG conversion failed: {e}")
            return body, "image/webp"

    if ext == ".svg":
        png_bytes = _convert_svg_to_png(body, ctx=ctx)
        if png_bytes:
            return png_bytes, "image/png"
        return None, None

    # Unknown format — try to pass through as PNG
    return body, "image/png"


# Used by cli.py for saving intermediate HTML files
EPUB_CSS = """\
body { font-family: sans-serif; line-height: 1.6; }
h5 { font-size: 1.1em; }
h6 { font-size: 1em; }
table { border-collapse: collapse; margin: 1em 0; width: 100%; }
th, td { border: 1px solid #999; padding: 0.4em 0.6em; text-align: left; }
th { background-color: #f0f0f0; font-weight: bold; }
img { max-width: 100%; height: auto; }
ol { list-style-type: none; }
.info-box {
    border-left: 4px solid #35cea0;
    background-color: #f5f5f5;
    padding: 0.8em 1em;
    margin: 1em 0;
}
.sample-dialogue {
    border: 1px solid #bbb;
    background-color: #f5f5f5;
    padding: 0.8em 1em;
    margin: 1em 0;
}
.sample-dialogue p {
    margin: 0.3em 0;
}
pre {
    background-color: #f5f5f5;
    border: 1px solid #ddd;
    padding: 0.8em 1em;
    margin: 1em 0;
    overflow-x: auto;
    font-family: monospace;
    font-size: 0.9em;
    line-height: 1.4;
    white-space: pre;
}
code {
    font-family: monospace;
    font-size: 0.9em;
}
pre code {
    background: none;
    border: none;
    padding: 0;
}
.hljs-keyword, .hljs-built_in {
    font-weight: bold;
    color: #1a3a6b;
}
.hljs-comment {
    color: #888;
    font-style: italic;
}
.hljs-string {
    color: #2a6a2a;
}
.hljs-type {
    color: #5a2a7a;
}
.hljs-title {
    color: #6b4a1a;
}
.hljs-meta {
    color: #888;
}
.hljs-params {
    color: inherit;
}
"""


def rewrite_image_paths(html: str, pages: list[CleanedPage], assets_dir: Path, prefix: str = "images/") -> str:
    """Rewrite img src from bare prefix to actual filename with extension."""
    prefix_to_actual: dict[str, str] = {}
    if assets_dir.exists():
        for f in assets_dir.iterdir():
            if f.is_file():
                prefix_to_actual[f.stem] = f.name

    for page in pages:
        for img in page.images:
            bare = img.filename
            actual_name = prefix_to_actual.get(bare)
            if actual_name:
                html = html.replace(f"{prefix}{bare}\"", f"{prefix}{actual_name}\"")
                html = html.replace(f"{prefix}{bare}<", f"{prefix}{actual_name}<")
    return html


def _extract_course_slug(pages: list[CleanedPage]) -> str | None:
    """Extract course slug from chapter URLs."""
    for page in pages:
        parts = urlparse(page.chapter.url).path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "courses":
            return parts[1]
    return None


def _build_slug_map(pages: list[CleanedPage]) -> dict[str, str]:
    """Map chapter slugs to EPUB filenames (slug → chapter_N.xhtml)."""
    return {page.chapter.slug: f"chapter_{i + 1}.xhtml" for i, page in enumerate(pages)}


def _rewrite_internal_links(html: str, course_slug: str, slug_map: dict[str, str]) -> str:
    """Rewrite /courses/{course}/{slug}#{anchor} links to chapter_N.xhtml#{anchor}."""
    def _replace(m):
        slug = m.group(1)
        anchor = m.group(2) or ""
        target = slug_map.get(slug)
        if target:
            return f'href="{target}{anchor}"'
        return m.group(0)

    return re.sub(
        rf'href="/courses/{re.escape(course_slug)}/([^"#]+)(#[^"]*)?"',
        _replace,
        html,
    )


def _render_html(title: str, content: str) -> str:
    """Wrap content in XHTML 1.1 template."""
    return f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{title}</title>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>
</head>
<body>
<h1>{title}</h1>

{content}
</body>
</html>"""


def build_epub(
    title: str,
    pages: list[CleanedPage],
    output_path: Path,
    assets_dir: Path | None = None,
    cover_image_path: Path | None = None,
    cache_dir: Path | None = None,
    pw=None,
) -> Path:
    """Build EPUB from saved HTML chapter files.

    Reads from cache_dir/chXX.html files (with assets/ paths and extensions),
    matching the same approach as geektime_dl.
    """
    book = epub.EpubBook()
    book.set_title(title)
    book.set_language("en")
    book.add_author("ByteByteGo")
    book.set_identifier(f"bytebytego-{title}")

    # Cover
    if cover_image_path and cover_image_path.exists():
        book.set_cover(
            f"cover{cover_image_path.suffix}",
            cover_image_path.read_bytes(),
        )

    # CSS stylesheet for tables, headings, images
    nav_css = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content=EPUB_CSS,
    )
    book.add_item(nav_css)

    # Build mapping for internal link rewriting
    course_slug = _extract_course_slug(pages)
    slug_map = _build_slug_map(pages) if course_slug else {}

    # Launch a shared browser context for SVG conversions (reused across all images)
    svg_ctx = None
    _own_browser = False
    if assets_dir and assets_dir.exists():
        has_svgs = any(f.suffix.lower() == ".svg" for f in assets_dir.iterdir() if f.is_file())
        if has_svgs:
            if pw:
                # Reuse existing Playwright instance (from scraper) with 2x scale
                _browser = pw.chromium.launch()
                svg_ctx = _browser.new_context(
                    device_scale_factor=2,
                    viewport={"width": 800, "height": 600},
                )
                _own_browser = True
            else:
                from playwright.sync_api import sync_playwright
                _pw = sync_playwright().start()
                _browser = _pw.chromium.launch()
                svg_ctx = _browser.new_context(
                    device_scale_factor=2,
                    viewport={"width": 800, "height": 600},
                )
                _own_browser = True

    chapters = []
    toc = []
    for page in pages:
        ch_num = page.chapter.index

        # Read from saved HTML file (assets/xxx.png paths) if available
        if cache_dir:
            html_file = cache_dir / f"ch{ch_num:02d}.html"
            if html_file.exists():
                raw = html_file.read_text()
            else:
                raw = page.html
        else:
            raw = page.html

        # Extract body content
        m = re.search(r"<body[^>]*>(.*)</body>", raw, re.DOTALL)
        content = m.group(1).strip() if m else raw

        # Remove style attributes from img tags (geektime_dl approach)
        for style in re.findall(r'img (.{1,15}=".*?") src=".*?"', content):
            content = content.replace(style, "")

        # Remove empty img tags
        for empty in re.findall(r"</?img>", content):
            content = content.replace(empty, "")

        # Replace assets/ image paths and embed in EPUB
        if assets_dir and assets_dir.exists():
            for match in re.finditer(r'img\s+src="assets/([^"]*)"', content):
                filename = match.group(1)
                local_path = assets_dir / filename
                if local_path.exists():
                    raw_body = local_path.read_bytes()
                    ext = local_path.suffix.lower()
                    converted_body, media_type = _convert_image_for_epub(raw_body, ext, ctx=svg_ctx)
                    if converted_body is None:
                        logger.warning(f"  Skipping image {filename}: conversion failed")
                        continue
                    # Use .png extension if format was converted
                    epub_filename = filename if ext in (".png", ".jpg", ".jpeg", ".gif") else f"{local_path.stem}.png"
                    img_item = epub.EpubImage()
                    img_item.file_name = f"images/{epub_filename}"
                    img_item.content = converted_body
                    book.add_item(img_item)
                    content = content.replace(f"assets/{filename}", f"images/{epub_filename}")

        # Also handle images/ paths (from cleaner direct output)
        if assets_dir and assets_dir.exists():
            stem_to_actual = {f.stem: f.name for f in assets_dir.iterdir() if f.is_file()}

            def _replace_img(m):
                bare = m.group(1)
                actual = stem_to_actual.get(bare)
                if not actual:
                    return m.group(0)
                local_path = assets_dir / actual
                epub_filename = actual  # default
                if local_path.exists():
                    raw_body = local_path.read_bytes()
                    ext = local_path.suffix.lower()
                    converted_body, media_type = _convert_image_for_epub(raw_body, ext, ctx=svg_ctx)
                    if converted_body is None:
                        logger.warning(f"  Skipping image {actual}: conversion failed")
                        return m.group(0)
                    epub_filename = actual if ext in (".png", ".jpg", ".jpeg", ".gif") else f"{local_path.stem}.png"
                    img_item = epub.EpubImage()
                    img_item.file_name = f"images/{epub_filename}"
                    img_item.content = converted_body
                    book.add_item(img_item)
                return f'src="images/{epub_filename}"'

            content = re.sub(r'\bsrc="images/([^"]*)"', _replace_img, content)

        # Extract title from h1
        m_title = re.search(r"<h1[^>]*>(.*?)</h1>", content)
        raw_title = re.sub(r"<[^>]+>", "", m_title.group(1)).strip() if m_title else page.chapter.title

        # Remove original h1 from content (template adds one with chapter number)
        content = re.sub(r"<h1[^>]*>.*?</h1>", "", content, count=1, flags=re.DOTALL)

        chapter_title = f"{ch_num}. {raw_title}"
        html = _render_html(chapter_title, content)
        file_name = f"chapter_{len(chapters) + 1}.xhtml"

        # Add section anchors and build sub-section TOC (preserve original IDs)
        # Use h2 if present, otherwise fall back to h3
        sub_items = []
        sec_counter = [0]
        has_h2 = bool(re.search(r"<h2(\s[^>]*)?>(.*?)</h2>", html))

        def _replace_section(match):
            sec_counter[0] += 1
            attrs = match.group(1) or ""
            sec_content = match.group(2)
            # Keep the original ID if present, otherwise generate one
            id_match = re.search(r'id="([^"]*)"', attrs)
            anchor_id = id_match.group(1) if id_match else f"sec{sec_counter[0]:02d}"
            text = re.sub(r"<[^>]+>", "", sec_content).strip()
            uid = f"chapter_{len(chapters) + 1}-s{sec_counter[0]:02d}"
            sub_items.append(epub.Link(f"{file_name}#{anchor_id}", text, uid))
            return f'<h2 id="{anchor_id}">{sec_content}</h2>'

        tag = "h2" if has_h2 else "h3"
        html = re.sub(rf"<{tag}(\s[^>]*)?>(.*?)</{tag}>", _replace_section, html)

        # Rewrite internal cross-chapter links
        if course_slug:
            html = _rewrite_internal_links(html, course_slug, slug_map)

        chapter = epub.EpubHtml(
            title=chapter_title,
            file_name=file_name,
            lang="en",
        )
        chapter.content = html
        chapter.add_item(nav_css)
        book.add_item(chapter)
        chapters.append(chapter)

        if sub_items:
            toc.append((chapter, sub_items))
        else:
            toc.append(chapter)

    book.toc = toc
    book.add_item(epub.EpubNcx())
    nav = epub.EpubNav()
    nav.add_item(nav_css)
    book.add_item(nav)
    book.spine = ["nav"] + chapters

    # Clean up shared browser context (only if we launched it)
    if _own_browser and svg_ctx:
        svg_ctx.close()
        _browser.close()
        _pw.stop()

    epub.write_epub(str(output_path), book, {})
    return output_path
