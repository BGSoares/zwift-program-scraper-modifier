"""Report generation for workout modifications."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from .models import Workout, ModificationResult, WeekSummary

logger = logging.getLogger(__name__)


def generate_modification_report(
    results: List[ModificationResult],
    weeks: Dict[int, List[Workout]]
) -> str:
    """Generate a markdown report of all modifications.

    Args:
        results: List of modification results
        weeks: Dict of week number to workouts

    Returns:
        Markdown report string
    """
    # Calculate summary statistics
    total_workouts = len(results)
    modified_count = sum(1 for r in results if r.status == 'modified')
    skipped_count = sum(1 for r in results if r.status == 'skipped')
    unchanged_count = sum(1 for r in results if r.status == 'unchanged')
    total_time_saved = sum(r.time_saved for r in results)

    # Group results by week
    results_by_week: Dict[int, List[ModificationResult]] = {}
    for result in results:
        week = result.week_number
        if week not in results_by_week:
            results_by_week[week] = []
        results_by_week[week].append(result)

    # Build report
    lines = [
        "# Zwift Workout Modification Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        f"- **Total workouts processed:** {total_workouts}",
        f"- **Workouts modified:** {modified_count}",
        f"- **Workouts skipped:** {skipped_count}",
        f"- **Workouts unchanged:** {unchanged_count}",
        f"- **Total time saved:** {total_time_saved // 3600}h {(total_time_saved % 3600) // 60}m",
        "",
        "## Week-by-Week Details",
        ""
    ]

    for week_num in sorted(results_by_week.keys()):
        week_results = results_by_week[week_num]
        week_results.sort(key=lambda r: r.day_number)

        week_original = sum(r.original_duration for r in week_results if r.status != 'skipped')
        week_new = sum(r.new_duration for r in week_results if r.status != 'skipped')
        week_saved = sum(r.time_saved for r in week_results)

        lines.append(f"### Week {week_num}")
        lines.append("")

        for result in week_results:
            if result.status == 'skipped':
                lines.append(
                    f"- **Day {result.day_number} - {result.workout_name}**: "
                    f"SKIPPED ({result.reason})"
                )
            elif result.status == 'unchanged':
                duration_min = result.original_duration // 60
                reason = f" - {result.reason}" if result.reason else ""
                lines.append(
                    f"- **Day {result.day_number} - {result.workout_name}**: "
                    f"Unchanged ({duration_min}min){reason}"
                )
            elif result.status == 'modified':
                orig_min = result.original_duration // 60
                new_min = result.new_duration // 60
                cut_min = result.time_saved // 60

                # Build cut details
                cut_details = []
                for seg_type, seconds in result.segments_cut.items():
                    if seconds > 0:
                        cut_details.append(f"{seconds // 60}min from {seg_type}")
                cut_str = ", ".join(cut_details) if cut_details else f"{cut_min}min"

                warning = f" **{result.warning}**" if result.warning else ""

                lines.append(
                    f"- **Day {result.day_number} - {result.workout_name}**: "
                    f"{orig_min}min -> {new_min}min (cut {cut_str}){warning}"
                )

        lines.append("")
        lines.append(
            f"**Week {week_num} total**: "
            f"{format_duration(week_original)} -> {format_duration(week_new)} "
            f"(saved {format_duration(week_saved)})"
        )
        lines.append("")

    # Add overall program summary
    total_original = sum(r.original_duration for r in results if r.status != 'skipped')
    total_new = sum(r.new_duration for r in results if r.status != 'skipped')

    lines.extend([
        "## Program Summary",
        "",
        f"- **Original total duration:** {format_duration(total_original)}",
        f"- **New total duration:** {format_duration(total_new)}",
        f"- **Total time saved:** {format_duration(total_time_saved)}",
        f"- **Average weekly time (new):** {format_duration(total_new // len(weeks) if weeks else 0)}",
        ""
    ])

    return '\n'.join(lines)


def format_duration(seconds: int) -> str:
    """Format duration in seconds as human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string like "1h 30m"
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours > 0:
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"
    return f"{minutes}m"


def write_report(report: str, output_path: Path) -> bool:
    """Write report to file.

    Args:
        report: Report content
        output_path: Output file path

    Returns:
        True if successful
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        logger.info(f"Report written to: {output_path}")
        return True
    except IOError as e:
        logger.error(f"Failed to write report: {e}")
        return False


def print_progress_summary(results: List[ModificationResult], week_num: int) -> None:
    """Print progress summary for a week.

    Args:
        results: Results for the week
        week_num: Week number
    """
    modified = sum(1 for r in results if r.status == 'modified')
    skipped = sum(1 for r in results if r.status == 'skipped')
    unchanged = sum(1 for r in results if r.status == 'unchanged')

    print(f"\nWeek {week_num}: {len(results)} workouts")
    for result in sorted(results, key=lambda r: r.day_number):
        if result.status == 'skipped':
            print(f"  [SKIP] Day {result.day_number} - {result.workout_name}")
        elif result.status == 'unchanged':
            dur = result.original_duration // 60
            print(f"  [KEEP] Day {result.day_number} - {result.workout_name} ({dur}min)")
        else:
            orig = result.original_duration // 60
            new = result.new_duration // 60
            print(f"  [CUT]  Day {result.day_number} - {result.workout_name}: {orig}min -> {new}min")
