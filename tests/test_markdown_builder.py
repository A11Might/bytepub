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
