import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag, NavigableString

from src.models import CleanedPage


def html_to_markdown(html: str) -> str:
    """Convert an HTML fragment to Markdown text."""
    soup = BeautifulSoup(html, "lxml")
    root = soup.body or soup
    parts = []
    for child in root.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                parts.append(text)
        elif isinstance(child, Tag):
            parts.append(_tag_to_md(child))
    return "\n\n".join(p for p in parts if p)


def _tag_to_md(tag: Tag) -> str:
    """Recursively convert a single HTML tag to Markdown."""
    name = tag.name

    if name in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(name[1])
        text = _inline_content(tag)
        return f"{'#' * level} {text}"

    if name == "p":
        return _inline_content(tag)

    if name in ("strong", "b"):
        return f"**{_inline_content(tag)}**"

    if name in ("em", "i"):
        return f"*{_inline_content(tag)}*"

    if name == "a":
        href = tag.get("href", "")
        text = _inline_content(tag)
        return f"[{text}]({href})"

    if name == "code" and tag.parent and tag.parent.name != "pre":
        return f"`{_inline_content(tag)}`"

    if name == "pre":
        code_tag = tag.find("code")
        code_text = code_tag.get_text() if code_tag else tag.get_text()
        return f"```\n{code_text}\n```"

    if name == "img":
        alt = tag.get("alt", "")
        src = tag.get("src", "")
        return f"![{alt}]({src})"

    if name == "ul":
        items = []
        for li in tag.find_all("li", recursive=False):
            items.append(f"- {_inline_content(li)}")
        return "\n".join(items)

    if name == "ol":
        items = []
        for i, li in enumerate(tag.find_all("li", recursive=False), 1):
            items.append(f"{i}. {_inline_content(li)}")
        return "\n".join(items)

    if name == "table":
        return _table_to_md(tag)

    if "MathJax" in tag.get("class", []):
        return _mathjax_to_md(tag)

    if "katex" in tag.get("class", []):
        return _katex_to_md(tag)

    if name == "math":
        return _mathml_to_md(tag)

    # Block-level containers: recurse and join
    if name in (
        "div",
        "section",
        "article",
        "main",
        "header",
        "footer",
        "aside",
        "figure",
        "figcaption",
        "blockquote",
        "details",
        "summary",
        "span",
    ):
        inner = []
        for child in tag.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    inner.append(text)
            elif isinstance(child, Tag):
                inner.append(_tag_to_md(child))
        return "\n\n".join(p for p in inner if p)

    # Fallback: just extract text
    return tag.get_text().strip()


def _inline_content(tag: Tag) -> str:
    """Convert inline children of a tag to Markdown."""
    parts = []
    for child in tag.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            parts.append(_tag_to_md(child))
    return "".join(parts).strip()


def _table_to_md(table: Tag) -> str:
    """Convert HTML table to GFM Markdown table."""
    rows = table.find_all("tr")
    if not rows:
        return ""
    lines = []
    for i, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        cell_texts = [c.get_text().strip().replace("|", "\\|") for c in cells]
        line = "| " + " | ".join(cell_texts) + " |"
        lines.append(line)
        if i == 0 and cells and cells[0].name == "th":
            sep = "| " + " | ".join("---" for _ in cells) + " |"
            lines.append(sep)
    return "\n".join(lines)


def _mathjax_to_md(tag: Tag) -> str:
    expr = tag.get("data-expr")
    if expr:
        return f"$${expr}$$"
    script = tag.find_previous_sibling("script", type="math/tex")
    if script:
        return f"${script.get_text().strip()}$"
    svg = tag.find("svg")
    if svg:
        text = svg.get_text().strip()
        if text:
            return f"`{text}`"
    return "[formula]"


def _katex_to_md(tag: Tag) -> str:
    mathml = tag.find(class_="katex-mathml")
    if mathml:
        annotation = mathml.find("annotation")
        if annotation:
            latex = annotation.get_text().strip()
            return f"${latex}$"
        math_tag = mathml.find("math")
        if math_tag:
            return _mathml_to_md(math_tag)
    return "[formula]"


def _mathml_to_md(tag: Tag) -> str:
    annotation = tag.find("annotation")
    if annotation:
        return f"${annotation.get_text().strip()}$"
    text = tag.get_text().strip()
    if text:
        return f"${text}$"
    return "[formula]"
