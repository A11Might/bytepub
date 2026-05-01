from pathlib import Path

from ebooklib import epub

from src.models import CleanedPage

MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


def convert_svgs_to_png(assets_dir: Path) -> None:
    """Convert all SVG files in assets_dir to PNG using Playwright for accurate rendering."""
    svg_files = list(assets_dir.glob("*.svg"))
    if not svg_files:
        return

    from playwright.sync_api import sync_playwright

    print(f"Converting {len(svg_files)} SVGs to PNG...")
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page()

    converted = 0
    for svg_file in svg_files:
        png_file = svg_file.with_suffix(".png")
        if png_file.exists():
            svg_file.unlink()
            converted += 1
            continue
        try:
            page.goto(f"file://{svg_file.resolve()}")
            # Get SVG dimensions for proper rendering
            dimensions = page.evaluate("""() => {
                const svg = document.querySelector('svg');
                if (!svg) return { w: 800, h: 600 };
                const vb = svg.getAttribute('viewBox');
                if (vb) {
                    const parts = vb.split(/[\\s,]+/);
                    return { w: parseFloat(parts[2]) || 800, h: parseFloat(parts[3]) || 600 };
                }
                return {
                    w: parseFloat(svg.getAttribute('width')) || 800,
                    h: parseFloat(svg.getAttribute('height')) || 600
                };
            }""")
            page.set_viewport_size({"width": int(dimensions["w"]), "height": int(dimensions["h"])})
            page.screenshot(path=str(png_file), full_page=True)
            svg_file.unlink()
            converted += 1
        except Exception as e:
            print(f"  Warning: failed to convert {svg_file.name}: {e}")

    browser.close()
    pw.stop()
    print(f"Converted {converted}/{len(svg_files)} SVGs to PNG")

EPUB_CSS = """\
body { font-family: sans-serif; line-height: 1.6; }
h5 { font-size: 1.1em; }
h6 { font-size: 1em; }
table { border-collapse: collapse; margin: 1em 0; width: 100%; }
th, td { border: 1px solid #999; padding: 0.4em 0.6em; text-align: left; }
th { background-color: #f0f0f0; font-weight: bold; }
img { max-width: 100%; height: auto; }
"""


def rewrite_image_paths(html: str, pages: list[CleanedPage], assets_dir: Path, prefix: str = "images/") -> str:
    """Rewrite img src from bare prefix to actual filename with extension.

    Args:
        html: The HTML content to rewrite.
        pages: List of CleanedPage with image info.
        assets_dir: Directory containing actual asset files.
        prefix: Path prefix used in img src (e.g. "images/" for EPUB, "assets/" for HTML).
    """
    # Build prefix -> actual filename mapping
    prefix_to_actual: dict[str, str] = {}
    if assets_dir.exists():
        for f in assets_dir.iterdir():
            if f.is_file():
                prefix_to_actual[f.stem] = f.name

    for page in pages:
        for img in page.images:
            bare = img.filename  # e.g. "ch01-001"
            actual_name = prefix_to_actual.get(bare)
            if actual_name:
                html = html.replace(f"{prefix}{bare}\"", f"{prefix}{actual_name}\"")
                html = html.replace(f"{prefix}{bare}<", f"{prefix}{actual_name}<")
    return html


def build_epub(
    title: str,
    pages: list[CleanedPage],
    output_path: Path,
    assets_dir: Path | None = None,
    cover_image_path: Path | None = None,
) -> Path:
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

    # Chapters
    nav_css = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content=EPUB_CSS,
    )
    book.add_item(nav_css)

    chapters = []
    toc = []
    for page in pages:
        chapter_file = f"ch{page.chapter.index:02d}.xhtml"
        chapter = epub.EpubHtml(
            title=page.chapter.title,
            file_name=chapter_file,
            lang="en",
        )
        html = page.html
        if assets_dir:
            html = rewrite_image_paths(html, [page], assets_dir, "images/")

        # Add id anchors to h2 tags and extract sub-sections for TOC
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        sub_items = []
        h2_counter = 0
        for h2 in soup.find_all("h2"):
            h2_counter += 1
            anchor_id = f"sec{h2_counter:02d}"
            h2["id"] = anchor_id
            sub_items.append(epub.Link(
                f"{chapter_file}#{anchor_id}",
                h2.get_text().strip(),
                f"ch{page.chapter.index:02d}-s{h2_counter:02d}",
            ))
        html = str(soup)

        chapter.content = html
        chapter.add_item(nav_css)
        book.add_item(chapter)
        chapters.append(chapter)

        # Build nested TOC: chapter with h2 sub-sections
        if sub_items:
            toc.append((chapter, sub_items))
        else:
            toc.append(chapter)

    # Embed images — match prefix to actual file in assets_dir
    if assets_dir and assets_dir.exists():
        for page in pages:
            for img in page.images:
                # img.filename is a prefix like "ch01-001" (no extension)
                # Find actual file with any extension
                matches = list(assets_dir.glob(f"{img.filename}.*"))
                if not matches:
                    continue
                actual = matches[0]
                ext = actual.suffix.lower()
                media_type = MIME_MAP.get(ext, "image/png")
                epub_image = epub.EpubImage()
                epub_image.file_name = f"images/{actual.name}"
                epub_image.media_type = media_type
                epub_image.content = actual.read_bytes()
                book.add_item(epub_image)

    # TOC and navigation
    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Spine: cover + all chapters
    book.spine = ["nav"] + chapters

    epub.write_epub(str(output_path), book, {})
    return output_path
