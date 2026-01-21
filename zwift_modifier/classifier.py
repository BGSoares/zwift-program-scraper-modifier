"""Workout classification logic."""

import logging
from typing import List

from .models import Workout, WorkoutSegment
from .config import (
    FILENAME_KEYWORDS, ZONE_1_MAX, ZONE_2_MAX, ZONE_3_MAX,
    ZONE_4_MAX, ZONE_5_MAX
)

logger = logging.getLogger(__name__)


def classify_workout(workout: Workout) -> str:
    """Classify a workout into categories.

    Args:
        workout: The Workout to classify

    Returns:
        Classification: 'recovery', 'endurance', 'interval', or 'mixed'
    """
    # First try filename classification
    filename_class = classify_from_filename(workout.filename)

    # Then try segment analysis
    segment_class = classify_from_segments(workout.segments, workout.total_duration)

    # If filename gives a clear result, use it
    if filename_class in ['recovery', 'interval']:
        workout.classification = filename_class
        return filename_class

    # If filename says endurance but segments say interval, trust segments
    if filename_class == 'endurance' and segment_class == 'interval':
        workout.classification = 'interval'
        return 'interval'

    # If segment analysis is clear, use it
    if segment_class != 'mixed':
        workout.classification = segment_class
        return segment_class

    # Default to filename classification or mixed
    workout.classification = filename_class if filename_class != 'mixed' else 'mixed'
    return workout.classification


def classify_from_filename(filename: str) -> str:
    """Classify workout based on filename keywords.

    Args:
        filename: The workout filename

    Returns:
        Classification string
    """
    filename_lower = filename.lower()

    for workout_type, keywords in FILENAME_KEYWORDS.items():
        if any(keyword in filename_lower for keyword in keywords):
            return workout_type

    return 'mixed'


def classify_from_segments(segments: List[WorkoutSegment], total_duration: int) -> str:
    """Classify workout based on segment analysis.

    Args:
        segments: List of workout segments
        total_duration: Total workout duration in seconds

    Returns:
        Classification string
    """
    if not segments or total_duration == 0:
        return 'mixed'

    # Calculate high-intensity duration (Z4+, >= 90% FTP)
    high_intensity_duration = 0
    low_intensity_duration = 0
    has_intervals = False

    for seg in segments:
        power = seg.get_effective_power()

        if seg.xml_type == 'IntervalsT':
            has_intervals = True
            # Count interval work
            if seg.on_power and seg.on_power >= ZONE_3_MAX:
                high_intensity_duration += (seg.on_duration or 0) * (seg.repeat or 1)

        elif power >= ZONE_3_MAX:
            high_intensity_duration += seg.duration

        elif power < ZONE_2_MAX:
            low_intensity_duration += seg.duration

    # Calculate ratios
    intensity_ratio = high_intensity_duration / total_duration if total_duration > 0 else 0
    low_ratio = low_intensity_duration / total_duration if total_duration > 0 else 0

    # Classification logic
    if has_intervals or intensity_ratio > 0.15:
        return 'interval'

    if total_duration > 5400 and low_ratio > 0.8:  # >90min and mostly low intensity
        return 'endurance'

    if total_duration < 3600 and low_ratio > 0.9:  # <60min and very low intensity
        return 'recovery'

    # Calculate average power
    avg_power = calculate_average_power(segments)
    if avg_power < ZONE_1_MAX:
        return 'recovery'
    elif avg_power < ZONE_2_MAX:
        return 'endurance'

    return 'mixed'


def calculate_average_power(segments: List[WorkoutSegment]) -> float:
    """Calculate the weighted average power across all segments.

    Args:
        segments: List of workout segments

    Returns:
        Weighted average power (decimal)
    """
    total_power_time = 0.0
    total_duration = 0

    for seg in segments:
        power = seg.get_effective_power()
        duration = seg.duration

        if seg.xml_type == 'IntervalsT' and seg.repeat:
            # For intervals, weight by both on and off periods
            if seg.on_power and seg.on_duration:
                total_power_time += seg.on_power * seg.on_duration * seg.repeat
                total_duration += seg.on_duration * seg.repeat
            if seg.off_power and seg.off_duration:
                total_power_time += seg.off_power * seg.off_duration * seg.repeat
                total_duration += seg.off_duration * seg.repeat
        elif power > 0:
            total_power_time += power * duration
            total_duration += duration

    if total_duration == 0:
        return 0.0

    return total_power_time / total_duration


def calculate_difficulty_score(workout: Workout) -> float:
    """Calculate a difficulty score for the workout.

    Lower score = lighter/easier workout.

    Args:
        workout: The Workout to score

    Returns:
        Difficulty score (lower = easier)
    """
    duration_minutes = workout.total_duration / 60
    avg_power = calculate_average_power(workout.segments)

    # Count interval segments (they add difficulty)
    interval_count = sum(1 for s in workout.segments if s.xml_type == 'IntervalsT')

    # Calculate intensity factor weighted by duration
    intensity_factor = 0.0
    for seg in workout.segments:
        power = seg.get_effective_power()
        intensity_factor += power * seg.duration

    if workout.total_duration > 0:
        intensity_factor /= workout.total_duration

    # Difficulty score: combines duration, intensity, and interval presence
    difficulty = (intensity_factor * duration_minutes) / 100
    difficulty += interval_count * 0.1  # Bonus for having intervals

    workout.difficulty_score = difficulty
    return difficulty


def classify_segment(segment: WorkoutSegment) -> str:
    """Classify a single segment.

    Args:
        segment: The WorkoutSegment to classify

    Returns:
        Segment type: 'warmup', 'cooldown', 'endurance', 'interval', 'recovery', 'unknown'
    """
    # Based on XML element type
    if segment.xml_type == 'Warmup':
        return 'warmup'
    if segment.xml_type == 'Cooldown':
        return 'cooldown'
    if segment.xml_type == 'IntervalsT':
        return 'interval'
    if segment.xml_type == 'FreeRide':
        return 'recovery'
    if segment.xml_type == 'Ramp':
        # Determine if it's warmup or cooldown based on power direction
        if segment.power_low and segment.power_high:
            if segment.power_low < segment.power_high:
                return 'warmup'
            else:
                return 'cooldown'
        return 'unknown'

    # For SteadyState, classify by power
    if segment.xml_type == 'SteadyState':
        power = segment.power or 0

        if power < ZONE_1_MAX:
            return 'recovery'
        elif power < ZONE_3_MAX:
            return 'endurance'  # Z2-Z3
        else:
            return 'interval'  # Z4+

    return 'unknown'
