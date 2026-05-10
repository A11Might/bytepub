from src.scraper import parse_course_url, build_cache_filename


def test_parse_course_url_from_chapter():
    slug = parse_course_url("https://bytebytego.com/courses/genai-system-design-interview/introduction-and-overview")
    assert slug == "genai-system-design-interview"


def test_parse_course_url_from_index():
    slug = parse_course_url("https://bytebytego.com/courses/genai-system-design-interview")
    assert slug == "genai-system-design-interview"


def test_parse_course_url_trailing_slash():
    slug = parse_course_url("https://bytebytego.com/courses/genai-system-design-interview/")
    assert slug == "genai-system-design-interview"


def test_build_cache_filename():
    name = build_cache_filename(1, "introduction-and-overview")
    assert name == "01-introduction-and-overview.html"

    name2 = build_cache_filename(12, "text-to-video-generation")
    assert name2 == "12-text-to-video-generation.html"


def test_parse_course_url_rejects_non_course():
    import pytest
    with pytest.raises(ValueError):
        parse_course_url("https://bytebytego.com/pricing")


from src.scraper import _detect_image_format


def test_detect_image_format_svg():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
    ext, mime = _detect_image_format(svg)
    assert ext == ".svg"
    assert mime == "image/svg+xml"


def test_detect_image_format_webp():
    webp = b'RIFF\x00\x00\x00\x00WEBP'
    ext, mime = _detect_image_format(webp)
    assert ext == ".webp"
    assert mime == "image/webp"


def test_detect_image_format_png():
    png = b'\x89PNG\r\n\x1a\n'
    ext, mime = _detect_image_format(png)
    assert ext == ".png"
    assert mime == "image/png"
