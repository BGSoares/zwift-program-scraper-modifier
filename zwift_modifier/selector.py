"""Workout selection logic - skip and weekend ride identification."""

import logging
from typing import List, Dict, Optional

from .models import Workout
from .config import SKIP_THRESHOLD_WORKOUTS, TARGET_WEEKDAY_DURATION
from .classifier import classify_workout, calculate_difficulty_score

logger = logging.getLogger(__name__)


def group_by_week(workouts: List[Workout]) -> Dict[int, List[Workout]]:
    """Group workouts by week number.

    Args:
        workouts: List of all workouts

    Returns:
        Dict mapping week number to list of workouts
    """
    weeks = {}

    for workout in workouts:
        week_num = workout.week_number
        if week_num not in weeks:
            weeks[week_num] = []
        weeks[week_num].append(workout)

    # Sort workouts within each week by day number
    for week_num in weeks:
        weeks[week_num].sort(key=lambda w: w.day_number)

    return weeks


def identify_weekend_ride(week_workouts: List[Workout]) -> Optional[Workout]:
    """Identify the weekend long ride for a week.

    The weekend ride is typically the last workout of the week
    and is usually the longest endurance ride.

    Args:
        week_workouts: List of workouts for a single week (sorted by day)

    Returns:
        The weekend ride workout, or None
    """
    if not week_workouts:
        return None

    # Get the last workout (highest day number)
    week_workouts_sorted = sorted(week_workouts, key=lambda w: w.day_number)
    last_workout = week_workouts_sorted[-1]

    # Verify it's a reasonably long ride (>90 min)
    if last_workout.total_duration >= 5400:  # 90 minutes
        last_workout.is_weekend_ride = True
        return last_workout

    # If last workout is short, find the longest workout in the week
    longest_workout = max(week_workouts, key=lambda w: w.total_duration)

    # Only mark as weekend ride if it's significantly longer than target
    if longest_workout.total_duration > TARGET_WEEKDAY_DURATION:
        longest_workout.is_weekend_ride = True
        return longest_workout

    # If no workout qualifies as a long weekend ride, pick the last one anyway
    last_workout.is_weekend_ride = True
    return last_workout


def identify_workouts_to_skip(week_workouts: List[Workout]) -> List[Workout]:
    """Identify which workouts should be skipped in a high-volume week.

    Skip workouts if the week has >= SKIP_THRESHOLD_WORKOUTS workouts.
    Priority: skip the lightest recovery workout.

    Args:
        week_workouts: List of workouts for a single week

    Returns:
        List of workouts to skip
    """
    if len(week_workouts) < SKIP_THRESHOLD_WORKOUTS:
        return []  # Don't skip anything

    # Classify and score all workouts
    for workout in week_workouts:
        classify_workout(workout)
        calculate_difficulty_score(workout)

    # First, try to identify active recovery workouts
    recovery_workouts = [
        w for w in week_workouts
        if w.classification == 'recovery' and not w.is_weekend_ride
    ]

    if recovery_workouts:
        # Skip the lightest recovery workout
        recovery_workouts.sort(key=lambda w: w.difficulty_score)
        to_skip = recovery_workouts[0]
        to_skip.should_skip = True
        to_skip.skip_reason = "Recovery workout in high-volume week"
        return [to_skip]

    # If no recovery workouts, skip the lightest non-weekend, non-interval workout
    candidates = [
        w for w in week_workouts
        if not w.is_weekend_ride and w.classification != 'interval'
    ]

    if candidates:
        candidates.sort(key=lambda w: w.difficulty_score)
        to_skip = candidates[0]
        to_skip.should_skip = True
        to_skip.skip_reason = "Lightest workout in high-volume week"
        return [to_skip]

    # As last resort, don't skip anything if all workouts are important
    logger.warning(f"Week has {len(week_workouts)} workouts but no good candidates to skip")
    return []


def determine_modification_action(
    workout: Workout,
    target_duration: int = TARGET_WEEKDAY_DURATION
) -> str:
    """Determine what action to take for a workout.

    Args:
        workout: The Workout to evaluate
        target_duration: Target maximum duration in seconds

    Returns:
        Action: 'skip', 'keep_unchanged', or 'shorten'
    """
    # Skip if marked for skipping
    if workout.should_skip:
        return 'skip'

    # Keep weekend ride unchanged
    if workout.is_weekend_ride:
        return 'keep_unchanged'

    # Keep if already at or under target duration
    if workout.total_duration <= target_duration:
        return 'keep_unchanged'

    # Otherwise, shorten
    return 'shorten'


def process_week_selection(
    week_workouts: List[Workout],
    target_duration: int = TARGET_WEEKDAY_DURATION
) -> None:
    """Process workout selection for a single week.

    This classifies workouts, identifies weekend rides, and marks
    workouts to skip.

    Args:
        week_workouts: List of workouts for the week
        target_duration: Target weekday duration
    """
    if not week_workouts:
        return

    # Classify all workouts
    for workout in week_workouts:
        classify_workout(workout)
        calculate_difficulty_score(workout)

    # Identify weekend ride
    identify_weekend_ride(week_workouts)

    # Identify workouts to skip
    identify_workouts_to_skip(week_workouts)


def process_all_weeks(
    workouts: List[Workout],
    target_duration: int = TARGET_WEEKDAY_DURATION
) -> Dict[int, List[Workout]]:
    """Process workout selection for all weeks.

    Args:
        workouts: All workouts
        target_duration: Target weekday duration

    Returns:
        Dict mapping week number to processed workouts
    """
    weeks = group_by_week(workouts)

    for week_num in sorted(weeks.keys()):
        week_workouts = weeks[week_num]
        process_week_selection(week_workouts, target_duration)

    return weeks
