import argparse
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.cli import cmd_test
from src.models import ScrapedPage, Chapter


def _make_args(**overrides) -> argparse.Namespace:
    defaults = {
        "url": "https://example.com/courses/test-course/intro",
        "output": "output",
        "no_auth": True,
        "format": "markdown",
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _scraped_page() -> ScrapedPage:
    chapter = Chapter(
        index=1,
        title="Test",
        url="https://example.com/courses/test-course/intro",
        slug="intro",
    )
    return ScrapedPage(
        chapter=chapter,
        raw_html="<html><body><article><h1>Test</h1><p>Content.</p></article></body></html>",
    )


def test_cmd_test_markdown_format(tmp_path):
    """cmd_test with --format markdown should call build_markdown, not build_epub."""
    args = _make_args(output=str(tmp_path), format="markdown")

    with patch("src.auth.no_auth") as mock_auth, \
         patch("src.scraper.parse_course_url", return_value="test-course"), \
         patch("src.scraper.fetch_page", return_value=_scraped_page()) as mock_fetch, \
         patch("src.auth.cleanup"):
        mock_pw, mock_ctx = MagicMock(), MagicMock()
        mock_auth.return_value = (mock_pw, mock_ctx)

        cmd_test(args)

    # Markdown directory should exist
    md_dir = tmp_path / "test" / "markdown"
    assert md_dir.exists()
    assert (md_dir / "ch01.md").exists()
    assert (md_dir / "full.md").exists()
    # EPUB should NOT exist
    assert not (tmp_path / "test" / "test.epub").exists()


def test_cmd_test_all_format(tmp_path):
    """cmd_test with --format all should produce both EPUB and Markdown."""
    args = _make_args(output=str(tmp_path), format="all")

    with patch("src.auth.no_auth") as mock_auth, \
         patch("src.scraper.parse_course_url", return_value="test-course"), \
         patch("src.scraper.fetch_page", return_value=_scraped_page()), \
         patch("src.auth.cleanup"):
        mock_pw, mock_ctx = MagicMock(), MagicMock()
        mock_auth.return_value = (mock_pw, mock_ctx)

        cmd_test(args)

    # Both outputs should exist
    assert (tmp_path / "test" / "test.epub").exists()
    assert (tmp_path / "test" / "markdown" / "ch01.md").exists()
    assert (tmp_path / "test" / "markdown" / "full.md").exists()


def test_cmd_test_epub_format_no_markdown(tmp_path):
    """cmd_test with --format epub (default) should NOT create markdown dir."""
    args = _make_args(output=str(tmp_path), format="epub")

    with patch("src.auth.no_auth") as mock_auth, \
         patch("src.scraper.parse_course_url", return_value="test-course"), \
         patch("src.scraper.fetch_page", return_value=_scraped_page()), \
         patch("src.auth.cleanup"):
        mock_pw, mock_ctx = MagicMock(), MagicMock()
        mock_auth.return_value = (mock_pw, mock_ctx)

        cmd_test(args)

    # EPUB should exist, markdown dir should NOT
    assert (tmp_path / "test" / "test.epub").exists()
    assert not (tmp_path / "test" / "markdown").exists()
