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

