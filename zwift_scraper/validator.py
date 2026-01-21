"""Validation logic for Zwift workouts and .zwo files."""

import logging
import xml.etree.ElementTree as ET
from typing import List, Tuple, Optional
from dataclasses import dataclass

from .workout import Workout, WorkoutSegment, TrainingProgram
from .config import (
    MIN_WORKOUT_DURATION, MAX_WORKOUT_DURATION,
    MIN_POWER, MAX_POWER,
    EXPECTED_WEEKS, EXPECTED_MIN_WORKOUTS, EXPECTED_MAX_WORKOUTS
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Represents a validation error."""
    level: str  # 'error', 'warning'
    message: str
    context: str = ""


@dataclass
class ValidationResult:
    """Result of validation check."""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]

    @property
    def all_issues(self) -> List[ValidationError]:
        return self.errors + self.warnings


def validate_workout(workout: Workout) -> ValidationResult:
    """Validate a single workout.

    Args:
        workout: The Workout to validate

    Returns:
        ValidationResult with any errors/warnings
    """
    errors = []
    warnings = []

    context = f"Week {workout.week_number} Day {workout.day_number}"

    # Check workout has segments
    if not workout.segments:
        errors.append(ValidationError(
            level='error',
            message="Workout has no segments",
            context=context
        ))
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # Calculate total duration from segments
    total_duration_seconds = 0
    for segment in workout.segments:
        segment_duration = get_segment_duration(segment)
        total_duration_seconds += segment_duration

    # Validate total duration
    if total_duration_seconds < MIN_WORKOUT_DURATION:
        warnings.append(ValidationError(
            level='warning',
            message=f"Workout duration ({total_duration_seconds}s) is very short (< {MIN_WORKOUT_DURATION}s)",
            context=context
        ))

    if total_duration_seconds > MAX_WORKOUT_DURATION:
        warnings.append(ValidationError(
            level='warning',
            message=f"Workout duration ({total_duration_seconds}s) is very long (> {MAX_WORKOUT_DURATION}s)",
            context=context
        ))

    # Validate each segment
    for i, segment in enumerate(workout.segments):
        segment_errors, segment_warnings = validate_segment(segment, i, context)
        errors.extend(segment_errors)
        warnings.extend(segment_warnings)

    # Check segment order (warmup first, cooldown last)
    if workout.segments[0].type not in ['warmup', 'steady', 'freeride']:
        warnings.append(ValidationError(
            level='warning',
            message="First segment is not a warmup",
            context=context
        ))

    if len(workout.segments) > 1 and workout.segments[-1].type not in ['cooldown', 'steady', 'freeride']:
        warnings.append(ValidationError(
            level='warning',
            message="Last segment is not a cooldown",
            context=context
        ))

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)


def get_segment_duration(segment: WorkoutSegment) -> int:
    """Get the total duration of a segment in seconds."""
    if segment.type == 'intervals' and segment.repeat:
        return (segment.on_duration or 0) * segment.repeat + (segment.off_duration or 0) * segment.repeat
    return segment.duration_seconds


def validate_segment(
    segment: WorkoutSegment,
    index: int,
    workout_context: str
) -> Tuple[List[ValidationError], List[ValidationError]]:
    """Validate a single segment.

    Args:
        segment: The WorkoutSegment to validate
        index: The segment index in the workout
        workout_context: Context string for error messages

    Returns:
        Tuple of (errors, warnings)
    """
    errors = []
    warnings = []
    context = f"{workout_context}, Segment {index + 1}"

    # Validate duration
    if segment.duration_seconds <= 0:
        errors.append(ValidationError(
            level='error',
            message="Segment duration must be positive",
            context=context
        ))

    # Validate power values
    if segment.power is not None:
        if segment.power < MIN_POWER:
            errors.append(ValidationError(
                level='error',
                message=f"Power ({segment.power}) is below minimum ({MIN_POWER})",
                context=context
            ))
        if segment.power > MAX_POWER:
            errors.append(ValidationError(
                level='error',
                message=f"Power ({segment.power}) exceeds maximum ({MAX_POWER})",
                context=context
            ))

    # Validate power range for warmup/cooldown
    if segment.type in ['warmup', 'cooldown']:
        if segment.power_low is None or segment.power_high is None:
            errors.append(ValidationError(
                level='error',
                message=f"{segment.type.capitalize()} must have power_low and power_high",
                context=context
            ))
        else:
            if segment.power_low < MIN_POWER or segment.power_high < MIN_POWER:
                errors.append(ValidationError(
                    level='error',
                    message="Power values must be non-negative",
                    context=context
                ))
            if segment.power_low > MAX_POWER or segment.power_high > MAX_POWER:
                errors.append(ValidationError(
                    level='error',
                    message=f"Power values exceed maximum ({MAX_POWER})",
                    context=context
                ))

    # Validate intervals
    if segment.type == 'intervals':
        if not segment.repeat or segment.repeat < 1:
            errors.append(ValidationError(
                level='error',
                message="Intervals must have repeat count >= 1",
                context=context
            ))
        if not segment.on_duration or segment.on_duration <= 0:
            errors.append(ValidationError(
                level='error',
                message="Intervals must have positive on_duration",
                context=context
            ))
        if not segment.off_duration or segment.off_duration <= 0:
            errors.append(ValidationError(
                level='error',
                message="Intervals must have positive off_duration",
                context=context
            ))
        if segment.on_power is None:
            errors.append(ValidationError(
                level='error',
                message="Intervals must have on_power",
                context=context
            ))
        if segment.off_power is None:
            errors.append(ValidationError(
                level='error',
                message="Intervals must have off_power",
                context=context
            ))

    return errors, warnings


def validate_xml_string(xml_string: str) -> ValidationResult:
    """Validate that an XML string is well-formed and has required elements.

    Args:
        xml_string: The XML string to validate

    Returns:
        ValidationResult
    """
    errors = []
    warnings = []

    # Check well-formedness
    try:
        root = ET.fromstring(xml_string)
    except ET.ParseError as e:
        errors.append(ValidationError(
            level='error',
            message=f"XML is not well-formed: {e}"
        ))
        return ValidationResult(is_valid=False, errors=errors, warnings=warnings)

    # Check root element
    if root.tag != 'workout_file':
        errors.append(ValidationError(
            level='error',
            message=f"Root element must be 'workout_file', got '{root.tag}'"
        ))

    # Check required elements
    required_elements = ['author', 'name', 'sportType', 'workout']
    for elem_name in required_elements:
        elem = root.find(elem_name)
        if elem is None:
            errors.append(ValidationError(
                level='error',
                message=f"Missing required element: {elem_name}"
            ))

    # Check workout has segments
    workout = root.find('workout')
    if workout is not None:
        if len(workout) == 0:
            errors.append(ValidationError(
                level='error',
                message="Workout element has no segments"
            ))

        # Validate segment elements
        valid_segment_types = {'Warmup', 'Cooldown', 'SteadyState', 'IntervalsT', 'FreeRide', 'Ramp'}
        for segment in workout:
            if segment.tag not in valid_segment_types:
                warnings.append(ValidationError(
                    level='warning',
                    message=f"Unknown segment type: {segment.tag}"
                ))

            # Check Duration attribute
            if 'Duration' not in segment.attrib and segment.tag != 'IntervalsT':
                errors.append(ValidationError(
                    level='error',
                    message=f"Segment {segment.tag} missing Duration attribute"
                ))

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)


def validate_program(program: TrainingProgram) -> ValidationResult:
    """Validate an entire training program.

    Args:
        program: The TrainingProgram to validate

    Returns:
        ValidationResult
    """
    errors = []
    warnings = []

    # Check number of weeks
    if program.weeks != EXPECTED_WEEKS:
        warnings.append(ValidationError(
            level='warning',
            message=f"Expected {EXPECTED_WEEKS} weeks, found {program.weeks}"
        ))

    # Check number of workouts
    if program.total_workouts < EXPECTED_MIN_WORKOUTS:
        warnings.append(ValidationError(
            level='warning',
            message=f"Expected at least {EXPECTED_MIN_WORKOUTS} workouts, found {program.total_workouts}"
        ))

    if program.total_workouts > EXPECTED_MAX_WORKOUTS:
        warnings.append(ValidationError(
            level='warning',
            message=f"Expected at most {EXPECTED_MAX_WORKOUTS} workouts, found {program.total_workouts}"
        ))

    # Validate each workout
    for workout in program.workouts:
        result = validate_workout(workout)
        errors.extend(result.errors)
        warnings.extend(result.warnings)

    # Check for missing weeks
    week_numbers = set(w.week_number for w in program.workouts)
    for week_num in range(1, program.weeks + 1):
        if week_num not in week_numbers:
            warnings.append(ValidationError(
                level='warning',
                message=f"Week {week_num} has no workouts"
            ))

    # Check for duplicate filenames
    filenames = [w.filename for w in program.workouts]
    duplicates = set(f for f in filenames if filenames.count(f) > 1)
    for dup in duplicates:
        errors.append(ValidationError(
            level='error',
            message=f"Duplicate filename: {dup}"
        ))

    is_valid = len(errors) == 0
    return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
