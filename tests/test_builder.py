import zipfile
from pathlib import Path
from ebooklib import epub

from src.builder import build_epub
from src.models import CleanedPage, Chapter, Asset


def _make_cleaned_page(
    index: int = 1,
    title: str = "Chapter One",
    html: str = "<h1>Chapter One</h1><p>Hello world.</p>",
    images: list[Asset] | None = None,
) -> CleanedPage:
    return CleanedPage(
        chapter=Chapter(index=index, title=title, url=f"https://example.com/ch{index}", slug=f"ch{index}"),
        html=html,
        images=images or [],
    )


def test_build_epub_creates_file(tmp_path):
    pages = [_make_cleaned_page(1, "Intro", "<h1>Intro</h1><p>Text.</p>")]
    output = tmp_path / "test.epub"
    build_epub("Test Book", pages, output)
    assert output.exists()
    assert output.stat().st_size > 0


def test_build_epub_is_valid_zip(tmp_path):
    pages = [_make_cleaned_page(1)]
    output = tmp_path / "test.epub"
    build_epub("Test Book", pages, output)
    assert zipfile.is_zipfile(output)


def test_build_epub_has_multiple_chapters(tmp_path):
    pages = [
        _make_cleaned_page(1, "Chapter 1", "<h1>Chapter 1</h1>"),
        _make_cleaned_page(2, "Chapter 2", "<h1>Chapter 2</h1>"),
        _make_cleaned_page(3, "Chapter 3", "<h1>Chapter 3</h1>"),
    ]
    output = tmp_path / "test.epub"
    build_epub("Test Book", pages, output)
    book = epub.read_epub(str(output))
    titles = [item.title for item in book.toc if hasattr(item, "title")]
    assert len(titles) == 3


def test_build_epub_with_images(tmp_path):
    png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # minimal PNG-like bytes
    # Asset filenames are prefixes without extension; actual file has extension
    img_path = tmp_path / "ch01-001.png"
    img_path.write_bytes(png_data)

    images = [Asset(filename="ch01-001", original_url="https://example.com/img.png", media_type="")]
    pages = [_make_cleaned_page(1, "With Image", '<h1>With Image</h1><img src="images/ch01-001"/>', images)]
    output = tmp_path / "test.epub"
    build_epub("Test Book", pages, output, assets_dir=tmp_path)
    book = epub.read_epub(str(output))
    image_items = [i for i in book.get_items() if isinstance(i, epub.EpubImage)]
    assert len(image_items) == 1


import pytest


def test_convert_svg_to_png_returns_png_bytes(tmp_path):
    """SVG bytes are converted to PNG bytes."""
    from src.builder import _convert_svg_to_png

    svg_data = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
        b'<rect width="100" height="50" fill="blue"/></svg>'
    )
    result = _convert_svg_to_png(svg_data)
    assert result is not None
    assert result[:4] == b'\x89PNG'


def test_convert_svg_to_png_returns_none_on_failure():
    """Invalid SVG returns None instead of raising."""
    from src.builder import _convert_svg_to_png

    result = _convert_svg_to_png(b'\xff\xfe invalid utf-8 bytes')
    assert result is None


def test_convert_image_for_epub_passes_png_through():
    """PNG bytes pass through unchanged."""
    from src.builder import _convert_image_for_epub

    png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
    result_body, result_type = _convert_image_for_epub(png_data, ".png")
    assert result_body == png_data
    assert result_type == "image/png"


def test_convert_image_for_epub_passes_jpg_through():
    """JPG bytes pass through unchanged."""
    from src.builder import _convert_image_for_epub

    jpg_data = b'\xff\xd8\xff\xe0' + b'\x00' * 100
    result_body, result_type = _convert_image_for_epub(jpg_data, ".jpg")
    assert result_body == jpg_data
    assert result_type == "image/jpeg"


def test_convert_image_for_epub_converts_webp():
    """WebP bytes are converted to PNG."""
    from src.builder import _convert_image_for_epub
    from PIL import Image
    from io import BytesIO

    # Create a real WebP image
    img = Image.new("RGB", (10, 10), "red")
    buf = BytesIO()
    img.save(buf, format="WEBP")
    webp_data = buf.getvalue()

    result_body, result_type = _convert_image_for_epub(webp_data, ".webp")
    assert result_type == "image/png"
    assert result_body[:4] == b'\x89PNG'


def test_convert_image_for_epub_converts_svg():
    """SVG bytes are converted to PNG."""
    from src.builder import _convert_image_for_epub

    svg_data = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
        b'<rect width="100" height="50" fill="blue"/></svg>'
    )
    result_body, result_type = _convert_image_for_epub(svg_data, ".svg")
    assert result_type == "image/png"
    assert result_body[:4] == b'\x89PNG'


def test_convert_image_for_epub_svg_failure_falls_back():
    """Broken SVG returns (None, None) so caller can skip it."""
    from src.builder import _convert_image_for_epub

    result_body, result_type = _convert_image_for_epub(b'\xff\xfe invalid', ".svg")
    assert result_body is None
    assert result_type is None


def test_build_epub_converts_svg_assets(tmp_path):
    """SVG files in assets_dir are converted to PNG when embedded in EPUB."""
    svg_data = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="100" height="50">'
        b'<rect width="100" height="50" fill="blue"/></svg>'
    )
    img_path = tmp_path / "assets" / "ch01-001.svg"
    img_path.parent.mkdir()
    img_path.write_bytes(svg_data)

    images = [Asset(filename="ch01-001", original_url="https://example.com/img.svg", media_type="")]
    pages = [_make_cleaned_page(1, "SVG Test", '<h1>SVG Test</h1><img src="assets/ch01-001.svg"/>', images)]
    output = tmp_path / "test.epub"
    build_epub("Test Book", pages, output, assets_dir=tmp_path / "assets")
    book = epub.read_epub(str(output))
    image_items = [i for i in book.get_items() if isinstance(i, epub.EpubImage)]
    assert len(image_items) == 1
    # Content should be PNG bytes (starts with PNG magic number)
    assert image_items[0].content[:4] == b'\x89PNG'
    # File name in EPUB should use .png extension
    assert image_items[0].file_name.endswith(".png")


def test_build_epub_skips_failed_svg_conversion(tmp_path):
    """Broken SVG images are skipped (not embedded) in the EPUB."""
    img_path = tmp_path / "assets" / "ch01-001.svg"
    img_path.parent.mkdir()
    img_path.write_bytes(b'\xff\xfe invalid')

    images = [Asset(filename="ch01-001", original_url="https://example.com/img.svg", media_type="")]
    pages = [_make_cleaned_page(1, "Broken SVG", '<h1>Broken SVG</h1><img src="assets/ch01-001.svg"/>', images)]
    output = tmp_path / "test.epub"
    build_epub("Test Book", pages, output, assets_dir=tmp_path / "assets")
    book = epub.read_epub(str(output))
    image_items = [i for i in book.get_items() if isinstance(i, epub.EpubImage)]
    assert len(image_items) == 0


def test_build_epub_with_existing_png_still_works(tmp_path):
    """Legacy cached PNG files still work without conversion."""
    png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
    img_path = tmp_path / "assets" / "ch01-001.png"
    img_path.parent.mkdir()
    img_path.write_bytes(png_data)

    images = [Asset(filename="ch01-001", original_url="https://example.com/img.png", media_type="")]
    pages = [_make_cleaned_page(1, "PNG Test", '<h1>PNG Test</h1><img src="assets/ch01-001.png"/>', images)]
    output = tmp_path / "test.epub"
    build_epub("Test Book", pages, output, assets_dir=tmp_path / "assets")
    book = epub.read_epub(str(output))
    image_items = [i for i in book.get_items() if isinstance(i, epub.EpubImage)]
    assert len(image_items) == 1
    assert image_items[0].content == png_data


def test_epub_css_contains_special_styles(tmp_path):
    """EPUB stylesheet includes rules for info-box, sample-dialogue, and hljs."""
    from src.builder import EPUB_CSS
    assert ".info-box" in EPUB_CSS
    assert ".sample-dialogue" in EPUB_CSS
    assert "pre" in EPUB_CSS
    assert ".hljs-keyword" in EPUB_CSS
    assert ".hljs-comment" in EPUB_CSS
    assert ".hljs-string" in EPUB_CSS


def test_epub_embeds_css_in_chapters(tmp_path):
    """Built EPUB chapters reference the stylesheet with special styles."""
    pages = [_make_cleaned_page(1, "Styled", '<h1>Styled</h1><div class="info-box"><p>Tip</p></div>')]
    output = tmp_path / "test.epub"
    build_epub("Test Book", pages, output)
    book = epub.read_epub(str(output))
    # Find the CSS item
    css_items = [i for i in book.get_items() if hasattr(i, 'file_name') and i.file_name == "style.css"]
    assert len(css_items) == 1
    css_content = css_items[0].content.decode("utf-8")
    assert ".info-box" in css_content
    assert ".sample-dialogue" in css_content

