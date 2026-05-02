import re
from pathlib import Path

from ebooklib import epub

from src.models import CleanedPage

# Used by cli.py for saving intermediate HTML files
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
                    img_item = epub.EpubImage()
                    img_item.file_name = f"images/{filename}"
                    img_item.content = local_path.read_bytes()
                    book.add_item(img_item)
                    content = content.replace(f"assets/{filename}", f"images/{filename}")

        # Also handle images/ paths (from cleaner direct output)
        if assets_dir and assets_dir.exists():
            stem_to_actual = {f.stem: f.name for f in assets_dir.iterdir() if f.is_file()}

            def _replace_img(m):
                bare = m.group(1)
                actual = stem_to_actual.get(bare)
                if not actual:
                    return m.group(0)
                local_path = assets_dir / actual
                if local_path.exists():
                    img_item = epub.EpubImage()
                    img_item.file_name = f"images/{actual}"
                    img_item.content = local_path.read_bytes()
                    book.add_item(img_item)
                return f'src="images/{actual}"'

            content = re.sub(r'\bsrc="images/([^"]*)"', _replace_img, content)

        # Extract title from h1
        m_title = re.search(r"<h1[^>]*>(.*?)</h1>", content)
        raw_title = re.sub(r"<[^>]+>", "", m_title.group(1)).strip() if m_title else page.chapter.title

        # Remove original h1 from content (template adds one with chapter number)
        content = re.sub(r"<h1[^>]*>.*?</h1>", "", content, count=1, flags=re.DOTALL)

        chapter_title = f"{ch_num}. {raw_title}"
        html = _render_html(chapter_title, content)
        file_name = f"chapter_{len(chapters) + 1}.xhtml"

        # Add h2 anchors and build sub-section TOC
        sub_items = []
        h2_counter = [0]

        def _replace_h2(match):
            h2_counter[0] += 1
            anchor_id = f"sec{h2_counter[0]:02d}"
            h2_content = match.group(1)
            text = re.sub(r"<[^>]+>", "", h2_content).strip()
            uid = f"chapter_{len(chapters) + 1}-s{h2_counter[0]:02d}"
            sub_items.append(epub.Link(f"{file_name}#{anchor_id}", text, uid))
            return f'<h2 id="{anchor_id}">{h2_content}</h2>'

        html = re.sub(r"<h2(?:\s[^>]*)?>(.*?)</h2>", _replace_h2, html)

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
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + chapters

    epub.write_epub(str(output_path), book, {})
    return output_path
