import argparse
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


def no_auth_session():
    """Launch browser without any authentication."""
    from src.auth import no_auth as _no_auth
    return _no_auth()


def cmd_test(args: argparse.Namespace) -> None:
    """Single page test mode: scrape + clean one page, output summary."""
    from src.auth import create_session, load_session, cleanup
    from src.scraper import parse_course_url, fetch_page
    from src.cleaner import clean_page
    from src.models import Chapter

    url = args.url
    course_slug = parse_course_url(url)
    chapter_slug = url.rstrip("/").split("/")[-1]

    output_dir = Path(args.output) / "test"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Auth
    session_path = Path(args.session) if args.session else None
    cookie_file = Path(args.cookies) if args.cookies else None
    if args.no_auth:
        pw, context = no_auth_session()
    elif session_path and session_path.exists():
        pw, context = load_session(session_path)
    elif cookie_file:
        pw, context = create_session(cookie_file=cookie_file)
    else:
        pw, context = create_session()

    try:
        chapter = Chapter(index=1, title="Test Page", url=url, slug=chapter_slug)
        scraped = fetch_page(context, chapter, output_dir)

        # Save raw HTML
        raw_path = output_dir / "raw.html"
        raw_path.write_text(scraped.raw_html, encoding="utf-8")

        # Clean
        cleaned = clean_page(scraped)

        # Save cleaned HTML
        cleaned_path = output_dir / "cleaned.html"
        cleaned_path.write_text(cleaned.html, encoding="utf-8")

        # Print summary
        print("\n=== Page Test Results ===")
        print(f"Title:     {cleaned.chapter.title}")
        print(f"Course:    {course_slug}")
        print(f"Word count: {cleaned.word_count}")
        print(f"Images:    {len(cleaned.images)} ({', '.join(f'{a.media_type}' for a in cleaned.images) or 'none'})")
        print(f"Formulas:  {cleaned.formula_count}")
        print(f"HTML size: {len(cleaned.html):,} chars")
        print(f"Raw saved: {raw_path}")
        print(f"Clean saved: {cleaned_path}")
        text_preview = cleaned.html[:200].replace("\n", " ")
        print(f"\nPreview: {text_preview}...")
        print("\n=== Done ===")

    finally:
        cleanup(pw, context)


def cmd_scrape(args: argparse.Namespace) -> None:
    """Full course scrape: discover -> fetch -> clean -> build EPUB."""
    from src.auth import create_session, load_session, cleanup
    from src.scraper import parse_course_url, discover_chapters, fetch_all
    from src.cleaner import clean_page
    from src.builder import build_epub

    url = args.url
    course_slug = parse_course_url(url)

    output_dir = Path(args.output) / course_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    # Auth
    session_path = Path(args.session) if args.session else None
    cookie_file = Path(args.cookies) if args.cookies else None
    if args.no_auth:
        pw, context = no_auth_session()
    elif session_path and session_path.exists():
        pw, context = load_session(session_path)
    elif cookie_file:
        pw, context = create_session(cookie_file=cookie_file)
    else:
        pw, context = create_session()

    try:
        # Discover chapters
        print(f"\nDiscovering chapters for: {course_slug}")
        chapters = discover_chapters(context, url)
        if not chapters:
            print("No chapters found. Check the URL and your access.")
            return

        print(f"\nFound {len(chapters)} chapters:")
        for ch in chapters:
            print(f"  {ch.index}. {ch.title}")

        confirm = input("\nContinue? [Y/n] ").strip().lower()
        if confirm in ("n", "no"):
            print("Aborted.")
            return

        # Parse refresh list
        refresh_set: set[int] | None = None
        if args.refresh is not None:
            if len(args.refresh) == 0:
                refresh_set = set()  # empty = refresh all
            else:
                refresh_set = set(args.refresh)

        # Fetch all chapters
        delay_min = args.delay_min
        delay_max = args.delay_max
        scraped_pages = fetch_all(
            context, chapters, output_dir,
            refresh_chapters=refresh_set,
            delay_min=delay_min,
            delay_max=delay_max,
        )

        print(f"\nScraped {len(scraped_pages)}/{len(chapters)} chapters successfully.")

        # Clean all pages
        cleaned_pages = []
        for scraped in scraped_pages:
            cleaned = clean_page(scraped)
            cleaned_pages.append(cleaned)

        # Update chapter titles from H1 in cleaned HTML
        from bs4 import BeautifulSoup
        for cleaned in cleaned_pages:
            soup = BeautifulSoup(cleaned.html, "lxml")
            h1 = soup.find("h1")
            if h1:
                cleaned.chapter.title = h1.get_text().strip()

        # Build EPUB
        epub_filename = args.output_file or f"{course_slug}.epub"
        epub_path = output_dir / epub_filename
        assets_dir = output_dir / "assets"

        cover_path = Path(args.cover) if args.cover else None
        build_epub(course_slug.replace("-", " ").title(), cleaned_pages, epub_path, assets_dir, cover_path)

        print(f"\nEPUB saved to: {epub_path}")

        # Final report
        cached = sum(1 for p in scraped_pages if p.cached)
        print(f"\n=== Final Report ===")
        print(f"Total chapters:  {len(chapters)}")
        print(f"Scraped:         {len(scraped_pages) - cached}")
        print(f"From cache:      {cached}")
        print(f"Failed/Skipped:  {len(chapters) - len(scraped_pages)}")

    finally:
        cleanup(pw, context)


def main():
    parser = argparse.ArgumentParser(
        description="Scrape ByteByteGo courses into EPUB ebooks",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Test mode
    test_parser = subparsers.add_parser("test", help="Test single page scraping")
    test_parser.add_argument("url", help="Chapter page URL to test")
    test_parser.add_argument("--output", "-o", default="output", help="Output directory")
    test_parser.add_argument("--session", "-s", help="Session file path")
    test_parser.add_argument("--cookies", "-c", help="Cookie string file (exported from browser)")
    test_parser.add_argument("--no-auth", action="store_true", help="Skip authentication")

    # Scrape mode
    scrape_parser = subparsers.add_parser("scrape", help="Scrape full course")
    scrape_parser.add_argument("url", help="Course index or chapter page URL")
    scrape_parser.add_argument("--output", "-o", default="output", help="Output directory")
    scrape_parser.add_argument("--session", "-s", help="Session file path")
    scrape_parser.add_argument("--cookies", "-c", help="Cookie string file (exported from browser)")
    scrape_parser.add_argument("--no-auth", action="store_true", help="Skip authentication")
    scrape_parser.add_argument("--output-file", help="EPUB filename (default: {course-slug}.epub)")
    scrape_parser.add_argument("--cover", help="Custom cover image path")
    scrape_parser.add_argument("--refresh", nargs="*", type=int, default=None,
                               help="Refresh specific chapter numbers (no args = refresh all)")
    scrape_parser.add_argument("--delay-min", type=float, default=3.0, help="Min delay between pages (seconds)")
    scrape_parser.add_argument("--delay-max", type=float, default=8.0, help="Max delay between pages (seconds)")

    args = parser.parse_args()
    if args.command == "test":
        cmd_test(args)
    elif args.command == "scrape":
        cmd_scrape(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
