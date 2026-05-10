import os
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

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
    _process_styles(content)
    word_count = len(content.get_text().split())

    return CleanedPage(
        chapter=scraped.chapter,
        html=str(content),
        images=images,
        formula_count=formula_count,
        word_count=word_count,
    )


def _remove_unwanted(content: Tag) -> None:
    # Preserve h1 inside <header> before removing it
    for header in content.find_all("header"):
        h1 = header.find("h1")
        if h1:
            h1 = h1.extract()
            header.insert_before(h1)
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

    # KaTeX: keep only the MathML part (EPUB supports MathML),
    # remove the katex-html part (relies on complex CSS not available in EPUB)
    for katex in content.find_all(class_="katex"):
        count += 1
        mathml_span = katex.find(class_="katex-mathml")
        html_span = katex.find(class_="katex-html")
        if mathml_span:
            # Extract the <math> element from the MathML span
            math_tag = mathml_span.find("math")
            if math_tag:
                math_tag = math_tag.extract()
                katex.replace_with(math_tag)
            else:
                # No <math> found, just remove katex-html
                if html_span:
                    html_span.decompose()
        elif html_span:
            html_span.decompose()

    return count


def _process_images(content: Tag, chapter_index: int) -> list[Asset]:
    images = []
    counter = 0
    for img in content.find_all("img"):
        src = img.get("src")
        if not src:
            continue
        counter += 1
        # Use prefix without extension — actual extension determined by scraper
        prefix = f"ch{chapter_index:02d}-{counter:03d}"
        # Use placeholder prefix — rewritten by builder/cli to actual path later
        img["src"] = f"images/{prefix}"
        # Remove srcset to avoid external URL references
        if img.has_attr("srcset"):
            del img["srcset"]
        # Remove lazy loading attrs that break EPUB rendering
        if img.has_attr("loading"):
            del img["loading"]
        if img.has_attr("data-nimg"):
            del img["data-nimg"]
        # Remove Next.js transparent style
        if img.has_attr("style") and "transparent" in img.get("style", ""):
            del img["style"]
        images.append(Asset(
            filename=prefix,
            original_url=src,
            media_type="",
        ))
    return images


def _process_styles(content: Tag) -> None:
    """Replace problematic Unicode characters with EPUB-safe alternatives."""
    for text_node in content.find_all(string=True):
        if isinstance(text_node, NavigableString) and "✅" in text_node:
            text_node.replace_with(text_node.replace("✅", "[√]"))
