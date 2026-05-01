import os
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

from src.models import Asset, CleanedPage, ScrapedPage

REMOVE_TAGS = {"script", "noscript", "iframe", "nav", "footer", "header"}
REMOVE_ROLES = {"navigation", "banner", "contentinfo", "complementary"}
CONTENT_SELECTORS = [
    "article",
    "[role='main']",
    "main",
    ".course-content",
    ".post-content",
    ".article-content",
]

MIME_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}


def guess_mime(url: str) -> str:
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    return MIME_MAP.get(ext, "image/png")


def clean_page(
    scraped: ScrapedPage,
    content_selectors: list[str] | None = None,
) -> CleanedPage:
    selectors = content_selectors or CONTENT_SELECTORS
    soup = BeautifulSoup(scraped.raw_html, "lxml")

    # Find content area
    content = None
    for selector in selectors:
        content = soup.select_one(selector)
        if content:
            break
    if content is None:
        content = soup.body or soup

    _remove_unwanted(content)
    formula_count = _process_formulas(content)
    images = _process_images(content, scraped.chapter.index)
    word_count = len(content.get_text().split())

    return CleanedPage(
        chapter=scraped.chapter,
        html=str(content),
        images=images,
        formula_count=formula_count,
        word_count=word_count,
    )


def _remove_unwanted(content: Tag) -> None:
    for tag_name in REMOVE_TAGS:
        for tag in content.find_all(tag_name):
            tag.decompose()
    for role in REMOVE_ROLES:
        for tag in content.find_all(attrs={"role": role}):
            tag.decompose()
    for tag in content.find_all("style"):
        tag.decompose()
    for tag in content.find_all(class_=re.compile(r"popup|ad|advertisement|cookie-banner|modal", re.I)):
        tag.decompose()


def _process_formulas(content: Tag) -> int:
    count = 0

    # MathJax: extract SVG from container, remove the wrapper
    for mjx in content.find_all(class_=re.compile(r"MathJax")):
        svg = mjx.find("svg")
        if svg:
            count += 1
            svg = svg.extract()
            mjx.replace_with(svg)
        else:
            count += 1

    # KaTeX: preserve the rendered output
    for katex in content.find_all(class_="katex"):
        count += 1

    return count


def _process_images(content: Tag, chapter_index: int) -> list[Asset]:
    images = []
    counter = 0
    for img in content.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        counter += 1
        # Strip query params for extension detection
        path_without_query = urlparse(src).path
        ext = os.path.splitext(path_without_query)[1].lower() or ".png"
        filename = f"ch{chapter_index:02d}-{counter:03d}{ext}"
        # Use images/ prefix to match EPUB internal structure
        img["src"] = f"images/{filename}"
        images.append(Asset(
            filename=filename,
            original_url=src,
            media_type=guess_mime(src),
        ))
    return images
