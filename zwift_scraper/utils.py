"""Utility functions for Zwift Workout Scraper."""

import os
import logging
from pathlib import Path
from typing import Optional

from .workout import Workout, TrainingProgram
from .xml_generator import workout_to_xml_string
from .validator import validate_workout, validate_xml_string

logger = logging.getLogger(__name__)


def write_workout_file(
    workout: Workout,
    output_dir: Path,
    organize_by_week: bool = False,
    overwrite: bool = False,
    validate: bool = True
) -> Optional[Path]:
    """Write a workout to a .zwo file.

    Args:
        workout: The Workout to write
        output_dir: Base output directory
        organize_by_week: If True, create week subdirectories
        overwrite: If True, overwrite existing files
        validate: If True, validate before writing

    Returns:
        Path to the written file, or None if failed
    """
    # Determine output path
    if organize_by_week:
        week_dir = output_dir / f"week_{workout.week_number:02d}"
        week_dir.mkdir(parents=True, exist_ok=True)
        output_path = week_dir / workout.filename
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / workout.filename

    # Check if file exists
    if output_path.exists() and not overwrite:
        logger.info(f"Skipping existing file: {output_path}")
        return None

    # Validate workout
    if validate:
        result = validate_workout(workout)
        if not result.is_valid:
            logger.error(f"Workout validation failed for {workout.filename}:")
            for error in result.errors:
                logger.error(f"  {error.message}")
            return None

        for warning in result.warnings:
            logger.warning(f"  {warning.message}")

    # Generate XML
    try:
        xml_string = workout_to_xml_string(workout)
    except Exception as e:
        logger.error(f"Failed to generate XML for {workout.filename}: {e}")
        return None

    # Validate XML
    if validate:
        xml_result = validate_xml_string(xml_string)
        if not xml_result.is_valid:
            logger.error(f"XML validation failed for {workout.filename}:")
            for error in xml_result.errors:
                logger.error(f"  {error.message}")
            return None

    # Write file
    try:
        with open(output_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(xml_string)
        logger.info(f"Wrote: {output_path}")
        return output_path
    except IOError as e:
        logger.error(f"Failed to write {output_path}: {e}")
        return None


def write_all_workouts(
    program: TrainingProgram,
    output_dir: Path,
    organize_by_week: bool = False,
    overwrite: bool = False,
    validate: bool = True,
    progress_callback=None
) -> dict:
    """Write all workouts from a training program to .zwo files.

    Args:
        program: The TrainingProgram containing workouts
        output_dir: Base output directory
        organize_by_week: If True, create week subdirectories
        overwrite: If True, overwrite existing files
        validate: If True, validate before writing
        progress_callback: Optional callback for progress updates

    Returns:
        Dict with 'success', 'failed', 'skipped' counts
    """
    callback = progress_callback or (lambda x: None)

    results = {
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'files': []
    }

    callback(f"Writing {program.total_workouts} workout files...")

    for workout in program.workouts:
        path = write_workout_file(
            workout,
            output_dir,
            organize_by_week=organize_by_week,
            overwrite=overwrite,
            validate=validate
        )

        if path:
            results['success'] += 1
            results['files'].append(str(path))
        elif path is None and (output_dir / workout.filename).exists():
            results['skipped'] += 1
        else:
            results['failed'] += 1

    callback(f"Complete! {results['success']} files written, {results['skipped']} skipped, {results['failed']} failed")

    return results


def format_duration(minutes: int) -> str:
    """Format duration in minutes as human-readable string.

    Args:
        minutes: Duration in minutes

    Returns:
        Formatted string like "1h 30m" or "45m"
    """
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}m"


def sanitize_filename(name: str, max_length: int = 50) -> str:
    """Sanitize a string for use as a filename.

    Args:
        name: The string to sanitize
        max_length: Maximum length for the result

    Returns:
        Sanitized filename string
    """
    import re
    from .config import FILENAME_INVALID_CHARS

    # Remove invalid characters
    result = re.sub(FILENAME_INVALID_CHARS, '', name)

    # Replace spaces with underscores
    result = result.replace(' ', '_')

    # Remove multiple underscores
    result = re.sub(r'_+', '_', result)

    # Strip leading/trailing underscores
    result = result.strip('_')

    # Truncate if necessary
    if len(result) > max_length:
        result = result[:max_length]

    return result
