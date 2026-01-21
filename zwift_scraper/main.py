"""CLI entry point for Zwift Workout Scraper."""

import argparse
import logging
import sys
import time
from pathlib import Path

from .config import DEFAULT_DELAY, DEFAULT_TIMEOUT, BASE_URL, PROGRAM_PATH
from .scraper import ZwiftWorkoutScraper, ScraperError
from .validator import validate_program
from .utils import write_all_workouts


def setup_logging(verbose: bool = False) -> None:
    """Configure logging based on verbosity setting."""
    level = logging.DEBUG if verbose else logging.INFO

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # Format
    if verbose:
        formatter = logging.Formatter(
            '[%(levelname)s] %(name)s: %(message)s'
        )
    else:
        formatter = logging.Formatter('%(message)s')

    console_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)


def print_progress(message: str) -> None:
    """Print a progress message to stdout."""
    print(message)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog='zwift_scraper',
        description='Scrape Zwift workouts from whatsonzwift.com and generate .zwo files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s https://whatsonzwift.com/workouts/active-offseason --output-dir ./workouts
  %(prog)s --output-dir ./workouts --organize-by-week --verbose
  %(prog)s --dry-run
        """
    )

    parser.add_argument(
        'url',
        nargs='?',
        default=BASE_URL + PROGRAM_PATH,
        help=f'URL to Active Offseason page (default: {BASE_URL + PROGRAM_PATH})'
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('./workouts'),
        help='Output directory for .zwo files (default: ./workouts)'
    )

    parser.add_argument(
        '--delay',
        type=float,
        default=DEFAULT_DELAY,
        help=f'Delay between requests in seconds (default: {DEFAULT_DELAY})'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f'Request timeout in seconds (default: {DEFAULT_TIMEOUT})'
    )

    parser.add_argument(
        '--organize-by-week',
        action='store_true',
        help='Create week subdirectories'
    )

    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing files'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Validate generated XML without writing files'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be scraped without actually scraping'
    )

    return parser


def main(argv=None) -> int:
    """Main entry point.

    Args:
        argv: Command line arguments (defaults to sys.argv[1:])

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = create_parser()
    args = parser.parse_args(argv)

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Print banner
    print("=" * 60)
    print("Zwift Workout Scraper")
    print("Extract workouts from whatsonzwift.com")
    print("=" * 60)
    print()

    # Validate URL
    url = args.url
    if not url.startswith('http'):
        logger.error(f"Invalid URL: {url}")
        return 1

    # Create scraper
    scraper = ZwiftWorkoutScraper(
        delay=args.delay,
        timeout=args.timeout,
        progress_callback=print_progress
    )

    # Track timing
    start_time = time.time()

    try:
        # Dry run mode
        if args.dry_run:
            scraper.dry_run(url)
            return 0

        # Scrape program
        print(f"Scraping workouts from: {url}")
        print(f"Output directory: {args.output_dir}")
        print()

        program = scraper.scrape_program(url)

        if program.total_workouts == 0:
            logger.error("No workouts were scraped")
            return 1

        print()
        print(f"Scraped {program.total_workouts} workouts across {program.weeks} weeks")
        print()

        # Validate program
        validation_result = validate_program(program)

        if validation_result.warnings:
            print("Warnings:")
            for warning in validation_result.warnings:
                print(f"  {warning.context}: {warning.message}")
            print()

        if validation_result.errors:
            print("Errors:")
            for error in validation_result.errors:
                print(f"  {error.context}: {error.message}")
            print()

        # Validate only mode
        if args.validate_only:
            if validation_result.is_valid:
                print("Validation passed!")
                return 0
            else:
                print("Validation failed!")
                return 1

        # Write files
        results = write_all_workouts(
            program,
            args.output_dir,
            organize_by_week=args.organize_by_week,
            overwrite=args.overwrite,
            validate=True,
            progress_callback=print_progress
        )

        # Print summary
        elapsed = time.time() - start_time
        print()
        print("=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"  Files written: {results['success']}")
        print(f"  Files skipped: {results['skipped']}")
        print(f"  Files failed:  {results['failed']}")
        print(f"  Output:        {args.output_dir}")
        print(f"  Total time:    {elapsed:.1f} seconds")
        print()

        if results['failed'] > 0:
            return 1

        return 0

    except ScraperError as e:
        logger.error(f"Scraping failed: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
