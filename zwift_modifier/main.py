"""CLI entry point for Zwift Workout Modifier."""

import argparse
import logging
import sys
import shutil
from pathlib import Path
from typing import List, Dict

from .config import (
    TARGET_WEEKDAY_DURATION, MIN_WARMUP_DURATION, MIN_COOLDOWN_DURATION,
    SKIP_THRESHOLD_WORKOUTS
)
from .parser import scan_directory
from .classifier import classify_workout, calculate_difficulty_score
from .selector import process_all_weeks, group_by_week
from .modifier import modify_workout
from .writer import write_workout_file
from .reporter import generate_modification_report, write_report, print_progress_summary
from .models import Workout, ModificationResult


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    if verbose:
        formatter = logging.Formatter('[%(levelname)s] %(name)s: %(message)s')
    else:
        formatter = logging.Formatter('%(message)s')

    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(console_handler)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser."""
    parser = argparse.ArgumentParser(
        prog='zwift_modifier',
        description='Modify Zwift workout durations while preserving interval work',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./original_workouts --output-dir ./modified_workouts
  %(prog)s ./original_workouts --dry-run
  %(prog)s ./original_workouts --target-duration 60 --verbose
        """
    )

    parser.add_argument(
        'input_dir',
        type=Path,
        help='Directory containing .zwo files to modify'
    )

    parser.add_argument(
        '--output-dir', '-o',
        type=Path,
        default=Path('./modified_workouts'),
        help='Output directory for modified files (default: ./modified_workouts)'
    )

    parser.add_argument(
        '--target-duration',
        type=int,
        default=75,
        help='Target weekday workout duration in minutes (default: 75)'
    )

    parser.add_argument(
        '--min-warmup',
        type=int,
        default=5,
        help='Minimum warmup duration in minutes (default: 5)'
    )

    parser.add_argument(
        '--min-cooldown',
        type=int,
        default=5,
        help='Minimum cooldown duration in minutes (default: 5)'
    )

    parser.add_argument(
        '--skip-threshold',
        type=int,
        default=5,
        help='Skip recovery if week has >= N workouts (default: 5)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without writing files'
    )

    parser.add_argument(
        '--backup',
        action='store_true',
        help='Create backup of original files'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    parser.add_argument(
        '--report',
        type=Path,
        default=Path('./modification_report.md'),
        help='Output path for modification report (default: ./modification_report.md)'
    )

    parser.add_argument(
        '--no-suffix',
        action='store_true',
        help='Do not append _MODIFIED suffix to filenames'
    )

    return parser


def main(argv=None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Print banner
    print("=" * 60)
    print("Zwift Workout Modifier")
    print("Reduce workout durations while preserving interval work")
    print("=" * 60)
    print()

    # Validate input
    if not args.input_dir.exists():
        logger.error(f"Input directory not found: {args.input_dir}")
        return 1

    # Convert duration to seconds
    target_duration = args.target_duration * 60

    # Update config values
    from . import config
    config.TARGET_WEEKDAY_DURATION = target_duration
    config.MIN_WARMUP_DURATION = args.min_warmup * 60
    config.MIN_COOLDOWN_DURATION = args.min_cooldown * 60
    config.SKIP_THRESHOLD_WORKOUTS = args.skip_threshold

    # Scan for workout files
    print(f"Scanning for .zwo files in {args.input_dir}...")
    workouts = scan_directory(args.input_dir)

    if not workouts:
        logger.error("No workout files found")
        return 1

    print(f"Found {len(workouts)} workout files")
    print()

    # Process workout selection (classify, identify weekend rides, mark skips)
    print("Analyzing workouts...")
    weeks = process_all_weeks(workouts, target_duration)
    print(f"Organized into {len(weeks)} weeks")
    print()

    # Backup if requested
    if args.backup and not args.dry_run:
        backup_dir = args.output_dir.parent / f"{args.output_dir.name}_backup"
        if backup_dir.exists():
            shutil.rmtree(backup_dir)
        shutil.copytree(args.input_dir, backup_dir)
        print(f"Backup created at: {backup_dir}")
        print()

    # Process modifications
    if args.dry_run:
        print("DRY RUN - No files will be written")
        print()

    print("Processing workouts...")
    print()

    all_results: List[ModificationResult] = []

    for week_num in sorted(weeks.keys()):
        week_workouts = weeks[week_num]
        week_results: List[ModificationResult] = []

        for workout in week_workouts:
            modified, result = modify_workout(workout, target_duration)
            week_results.append(result)
            all_results.append(result)

            # Write modified file (unless dry run or skipped)
            if not args.dry_run and result.status != 'skipped':
                args.output_dir.mkdir(parents=True, exist_ok=True)
                write_workout_file(
                    modified,
                    args.output_dir,
                    append_suffix=not args.no_suffix
                )

        # Print week summary
        print_progress_summary(week_results, week_num)

    # Generate and write report
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)

    modified_count = sum(1 for r in all_results if r.status == 'modified')
    skipped_count = sum(1 for r in all_results if r.status == 'skipped')
    unchanged_count = sum(1 for r in all_results if r.status == 'unchanged')
    total_saved = sum(r.time_saved for r in all_results)

    print(f"  Workouts modified:  {modified_count}")
    print(f"  Workouts skipped:   {skipped_count}")
    print(f"  Workouts unchanged: {unchanged_count}")
    print(f"  Total time saved:   {total_saved // 3600}h {(total_saved % 3600) // 60}m")
    print()

    if not args.dry_run:
        print(f"  Output directory:   {args.output_dir}")

        # Write report
        report = generate_modification_report(all_results, weeks)
        if write_report(report, args.report):
            print(f"  Report:             {args.report}")
    else:
        print("  (Dry run - no files written)")

    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
