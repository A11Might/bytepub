from src.markdown_builder import html_to_markdown


def test_headings():
    html = "<h1>Title</h1><h2>Section</h2><h3>Sub</h3>"
    md = html_to_markdown(html)
    assert "# Title" in md
    assert "## Section" in md
    assert "### Sub" in md


def test_paragraphs():
    html = "<p>First paragraph.</p><p>Second paragraph.</p>"
    md = html_to_markdown(html)
    assert "First paragraph." in md
    assert "Second paragraph." in md


def test_bold_and_italic():
    html = "<p>This is <strong>bold</strong> and <em>italic</em> text.</p>"
    md = html_to_markdown(html)
    assert "**bold**" in md
    assert "*italic*" in md


def test_links():
    html = '<p><a href="https://example.com">Link text</a></p>'
    md = html_to_markdown(html)
    assert "[Link text](https://example.com)" in md


def test_unordered_list():
    html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
    md = html_to_markdown(html)
    assert "- Item 1" in md
    assert "- Item 2" in md


def test_ordered_list():
    html = "<ol><li>First</li><li>Second</li></ol>"
    md = html_to_markdown(html)
    assert "1. First" in md
    assert "2. Second" in md


def test_code_block():
    html = "<pre><code>def hello():\n    print('hi')</code></pre>"
    md = html_to_markdown(html)
    assert "```" in md
    assert "def hello():" in md


def test_inline_code():
    html = "<p>Use <code>pip install</code> to install.</p>"
    md = html_to_markdown(html)
    assert "`pip install`" in md


def test_image():
    html = '<img src="assets/ch01-001.png" alt="Architecture diagram"/>'
    md = html_to_markdown(html)
    assert "![Architecture diagram](assets/ch01-001.png)" in md


def test_image_no_alt():
    html = '<img src="assets/ch01-002.png"/>'
    md = html_to_markdown(html)
    assert "![](assets/ch01-002.png)" in md


def test_table():
    html = """<table>
<tr><th>Header 1</th><th>Header 2</th></tr>
<tr><td>Cell 1</td><td>Cell 2</td></tr>
<tr><td>Cell 3</td><td>Cell 4</td></tr>
</table>"""
    md = html_to_markdown(html)
    assert "| Header 1 | Header 2 |" in md
    assert "| --- | --- |" in md
    assert "| Cell 1 | Cell 2 |" in md


def test_mathjax_formula():
    html = '<span class="MathJax"><svg xmlns="http://www.w3.org/2000/svg"><text>x^2 + y^2 = r^2</text></svg></span>'
    md = html_to_markdown(html)
    assert "x^2" in md or "[formula]" in md


def test_formula_placeholder_when_no_latex():
    html = '<span class="katex"><span class="katex-mathml"><math><mrow><mi>x</mi></mrow></math></span></span>'
    md = html_to_markdown(html)
    assert "$x$" in md or "[formula]" in md


def test_strips_unwanted_html():
    html = "<article><h1>Title</h1><p>Content.</p></article>"
    md = html_to_markdown(html)
    assert "<article>" not in md
    assert "<h1>" not in md


from pathlib import Path
from src.models import CleanedPage, Chapter, Asset


def _make_cleaned_page(
    index: int = 1,
    title: str = "Chapter One",
    html: str = "<h1>Chapter One</h1><p>Hello world.</p>",
    images: list[Asset] | None = None,
    slug: str | None = None,
) -> CleanedPage:
    return CleanedPage(
        chapter=Chapter(index=index, title=title, url=f"https://example.com/courses/my-course/ch{index}", slug=slug or f"ch{index}"),
        html=html,
        images=images or [],
    )


def test_build_markdown_creates_chapter_files(tmp_path):
    from src.markdown_builder import build_markdown
    pages = [
        _make_cleaned_page(1, "Intro", "<h1>Intro</h1><p>Welcome.</p>"),
        _make_cleaned_page(2, "Basics", "<h1>Basics</h1><p>Let's start.</p>"),
    ]
    build_markdown("My Course", pages, tmp_path)
    assert (tmp_path / "ch01.md").exists()
    assert (tmp_path / "ch02.md").exists()


def test_build_markdown_creates_full_merged_file(tmp_path):
    from src.markdown_builder import build_markdown
    pages = [
        _make_cleaned_page(1, "Intro", "<h1>Intro</h1><p>Welcome.</p>"),
        _make_cleaned_page(2, "Basics", "<h1>Basics</h1><p>Let's start.</p>"),
    ]
    build_markdown("My Course", pages, tmp_path)
    full = (tmp_path / "full.md")
    assert full.exists()
    content = full.read_text()
    assert "# Intro" in content
    assert "# Basics" in content
    assert "---" in content  # separator between chapters


def test_build_markdown_full_has_toc_with_anchors(tmp_path):
    from src.markdown_builder import build_markdown
    pages = [
        _make_cleaned_page(1, "Introduction", "<h1>Introduction</h1><p>First.</p>"),
        _make_cleaned_page(2, "Architecture", "<h1>Architecture</h1><p>Second.</p>"),
    ]
    build_markdown("My Course", pages, tmp_path)
    content = (tmp_path / "full.md").read_text()
    # TOC should link to internal anchors, not external files
    assert "[Introduction](#chapter-1)" in content
    assert "[Architecture](#chapter-2)" in content
    # Chapter anchors should exist
    assert '<a id="chapter-1"></a>' in content
    assert '<a id="chapter-2"></a>' in content


def test_build_markdown_chapter_content(tmp_path):
    from src.markdown_builder import build_markdown
    pages = [_make_cleaned_page(1, "Test", "<h1>Test</h1><p>Some content.</p>")]
    build_markdown("My Course", pages, tmp_path)
    ch1 = (tmp_path / "ch01.md").read_text()
    assert "# Test" in ch1
    assert "Some content." in ch1


def test_build_markdown_rewrites_image_paths(tmp_path):
    from src.markdown_builder import build_markdown
    # Create a fake assets dir with a real image
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "ch01-001.png").write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 10)

    pages = [_make_cleaned_page(1, "Test", '<h1>Test</h1><p><img src="images/ch01-001" alt="Diagram"/></p>')]
    build_markdown("My Course", pages, tmp_path, assets_dir=assets_dir)
    ch1 = (tmp_path / "ch01.md").read_text()
    # Image path should be rewritten to ../assets/ch01-001.png
    assert "![Diagram](../assets/ch01-001.png)" in ch1


def test_build_markdown_rewrites_cross_chapter_links(tmp_path):
    from src.markdown_builder import build_markdown
    pages = [
        _make_cleaned_page(1, "Intro", '<h1>Intro</h1><p>See <a href="/courses/my-course/ch2#section">Chapter 2</a></p>', slug="ch1"),
        _make_cleaned_page(2, "Basics", "<h1>Basics</h1><p>Content.</p>", slug="ch2"),
    ]
    build_markdown("My Course", pages, tmp_path)
    ch1 = (tmp_path / "ch01.md").read_text()
    # Cross-chapter link should be rewritten to ch02.md#section
    assert "[Chapter 2](ch02.md#section)" in ch1


def test_build_markdown_full_rewrites_links_to_anchors(tmp_path):
    from src.markdown_builder import build_markdown
    pages = [
        _make_cleaned_page(1, "Intro", '<h1>Intro</h1><p>See <a href="/courses/my-course/ch2#section">Chapter 2</a></p>', slug="ch1"),
        _make_cleaned_page(2, "Basics", "<h1>Basics</h1><p>Content.</p>", slug="ch2"),
    ]
    build_markdown("My Course", pages, tmp_path)
    full = (tmp_path / "full.md").read_text()
    # In full.md, links should point to internal anchors
    assert "[Chapter 2](#chapter-2#section)" in full
