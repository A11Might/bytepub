from dataclasses import dataclass, field


@dataclass
class Chapter:
    index: int
    title: str
    url: str
    slug: str


@dataclass
class Asset:
    filename: str
    original_url: str
    media_type: str


@dataclass
class ScrapedPage:
    chapter: Chapter
    raw_html: str
    assets: list[Asset] = field(default_factory=list)
    cached: bool = False


@dataclass
class CleanedPage:
    chapter: Chapter
    html: str
    images: list[Asset] = field(default_factory=list)
    formula_count: int = 0
    word_count: int = 0