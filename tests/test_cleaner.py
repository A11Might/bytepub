from pathlib import Path
from src.cleaner import clean_page
from src.models import ScrapedPage, Chapter

FIXTURE = Path(__file__).parent / "fixtures" / "sample_page.html"

def _make_scraped(html: str | None = None) -> ScrapedPage:
    raw = html or FIXTURE.read_text()
    return ScrapedPage(
        chapter=Chapter(index=1, title="Introduction and Overview", url="https://example.com/ch1", slug="introduction-and-overview"),
        raw_html=raw,
    )


def test_removes_non_content_elements():
    page = _make_scraped()
    result = clean_page(page)
    assert "Navigation links" not in result.html
    assert "Site header" not in result.html
    assert "Footer content" not in result.html
    assert "Buy now" not in result.html
    assert "console.log" not in result.html
    assert "Enable JS" not in result.html


def test_preserves_content():
    page = _make_scraped()
    result = clean_page(page)
    assert "Introduction and Overview" in result.html
    assert "system design" in result.html
    assert "<table>" in result.html
    assert "Cell 1" in result.html
    assert "print" in result.html


def test_counts_words():
    page = _make_scraped()
    result = clean_page(page)
    assert result.word_count > 0
    assert "system design" in result.html


def test_rewrites_image_paths():
    page = _make_scraped()
    result = clean_page(page)
    assert len(result.images) == 2
    assert result.images[0].filename.startswith("ch01-")
    assert result.images[0].media_type == "image/png"
    assert result.images[1].media_type == "image/svg+xml"
    # Original URLs no longer in HTML
    assert "bytebytego.com/images/diagram1.png" not in result.html
    # Local filenames are in HTML
    assert result.images[0].filename in result.html


def test_counts_formulas():
    page = _make_scraped()
    result = clean_page(page)
    assert result.formula_count >= 1


def test_handles_no_content_selector_match():
    html = "<html><body><div>No article tag here</div></body></html>"
    page = _make_scraped(html)
    result = clean_page(page)
    assert "No article tag here" in result.html
