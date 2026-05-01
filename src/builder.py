from datetime import date
from pathlib import Path

from ebooklib import epub

from src.models import CleanedPage


def generate_cover_svg(title: str, subtitle: str = "") -> str:
    escaped_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    escaped_sub = subtitle.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    today = date.today().isoformat()
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800">
  <rect width="600" height="800" fill="#1a1a2e"/>
  <rect x="40" y="40" width="520" height="720" fill="none" stroke="#e94560" stroke-width="2"/>
  <text x="300" y="350" text-anchor="middle" fill="#eee" font-size="32" font-family="sans-serif">{escaped_title}</text>
  <text x="300" y="410" text-anchor="middle" fill="#aaa" font-size="18" font-family="sans-serif">{escaped_sub}</text>
  <text x="300" y="700" text-anchor="middle" fill="#666" font-size="14" font-family="sans-serif">{today}</text>
</svg>"""


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
    else:
        cover_svg = generate_cover_svg(title)
        cover_path = output_path.parent / "cover.svg"
        cover_path.write_text(cover_svg)
        book.set_cover("cover.svg", cover_svg.encode())

    # Chapters
    chapters = []
    for page in pages:
        chapter_file = f"ch{page.chapter.index:02d}.xhtml"
        chapter = epub.EpubHtml(
            title=page.chapter.title,
            file_name=chapter_file,
            lang="en",
        )
        chapter.content = page.html
        book.add_item(chapter)
        chapters.append(chapter)

    # Embed images
    if assets_dir and assets_dir.exists():
        for page in pages:
            for img in page.images:
                img_path = assets_dir / img.filename
                if img_path.exists():
                    epub_image = epub.EpubImage()
                    epub_image.file_name = f"images/{img.filename}"
                    epub_image.media_type = img.media_type
                    epub_image.content = img_path.read_bytes()
                    book.add_item(epub_image)

    # TOC and navigation
    book.toc = chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Spine: cover + all chapters
    book.spine = ["nav"] + chapters

    epub.write_epub(str(output_path), book, {})
    return output_path
