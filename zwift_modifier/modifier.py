"""Workout modification logic - proportional cutting algorithm."""

import logging
from typing import List, Tuple, Dict, Optional

from .models import Workout, WorkoutSegment, ModificationResult
from .config import (
    TARGET_WEEKDAY_DURATION, MIN_WARMUP_DURATION, MIN_COOLDOWN_DURATION,
    MIN_SEGMENT_DURATION
)
from .classifier import classify_segment

logger = logging.getLogger(__name__)


def identify_cuttable_segments(workout: Workout) -> Tuple[List[WorkoutSegment], List[WorkoutSegment]]:
    """Identify which segments can be cut and which must be preserved.

    Args:
        workout: The Workout to analyze

    Returns:
        Tuple of (cuttable_segments, preserve_segments)
    """
    cuttable = []
    preserve = []

    for segment in workout.segments:
        seg_type = classify_segment(segment)

        # PRESERVE: All IntervalsT elements (structured intervals)
        if segment.xml_type == 'IntervalsT':
            preserve.append(segment)

        # PRESERVE: High-intensity steady state (Z4+)
        elif seg_type == 'interval':
            preserve.append(segment)

        # CUTTABLE: Endurance segments (Z2-Z3)
        elif seg_type == 'endurance':
            cuttable.append(segment)

        # CUTTABLE: Warmup (but enforce minimum)
        elif seg_type == 'warmup':
            cuttable.append(segment)

        # CUTTABLE: Cooldown (but enforce minimum)
        elif seg_type == 'cooldown':
            cuttable.append(segment)

        # PRESERVE: Recovery and unknown segments by default
        else:
            preserve.append(segment)

    return cuttable, preserve


def calculate_cut_requirements(
    workout: Workout,
    target_duration: int = TARGET_WEEKDAY_DURATION
) -> Dict:
    """Calculate how much time needs to be cut.

    Args:
        workout: The Workout to analyze
        target_duration: Target duration in seconds

    Returns:
        Dict with cut requirements and feasibility info
    """
    current_duration = workout.total_duration
    time_to_cut = current_duration - target_duration

    if time_to_cut <= 0:
        return {
            'current_duration': current_duration,
            'target_duration': target_duration,
            'time_to_cut': 0,
            'cuttable_duration': 0,
            'max_cuttable': 0,
            'is_feasible': True
        }

    cuttable_segments, preserve_segments = identify_cuttable_segments(workout)
    cuttable_duration = sum(seg.duration for seg in cuttable_segments)

    # Calculate minimum required for warmup/cooldown
    warmup_segments = [s for s in cuttable_segments if classify_segment(s) == 'warmup']
    cooldown_segments = [s for s in cuttable_segments if classify_segment(s) == 'cooldown']

    warmup_duration = sum(s.duration for s in warmup_segments)
    cooldown_duration = sum(s.duration for s in cooldown_segments)

    min_warmup = min(MIN_WARMUP_DURATION, warmup_duration)
    min_cooldown = min(MIN_COOLDOWN_DURATION, cooldown_duration)

    max_cuttable = cuttable_duration - min_warmup - min_cooldown

    return {
        'current_duration': current_duration,
        'target_duration': target_duration,
        'time_to_cut': time_to_cut,
        'cuttable_duration': cuttable_duration,
        'max_cuttable': max(0, max_cuttable),
        'is_feasible': time_to_cut <= max_cuttable
    }


def apply_proportional_cuts(
    workout: Workout,
    target_duration: int = TARGET_WEEKDAY_DURATION
) -> ModificationResult:
    """Apply proportional cuts to a workout.

    Preserves all interval work, cuts from endurance segments proportionally,
    and maintains minimum warmup/cooldown durations.

    Args:
        workout: The Workout to modify (will be modified in place)
        target_duration: Target duration in seconds

    Returns:
        ModificationResult with details of what was changed
    """
    original_duration = workout.original_duration
    cut_info = calculate_cut_requirements(workout, target_duration)

    result = ModificationResult(
        workout_name=workout.name,
        filename=workout.filename,
        week_number=workout.week_number,
        day_number=workout.day_number,
        status='unchanged',
        original_duration=original_duration,
        new_duration=workout.total_duration,
        time_saved=0,
        segments_cut={}
    )

    if cut_info['time_to_cut'] <= 0:
        result.status = 'unchanged'
        return result

    if not cut_info['is_feasible']:
        logger.warning(
            f"Cannot fully cut {workout.name} to {target_duration}s. "
            f"Cutting as much as possible ({cut_info['max_cuttable']}s max)."
        )
        result.warning = f"Could not reach target; cut maximum possible"

    time_to_cut = cut_info['time_to_cut']
    remaining_cut = time_to_cut

    # Categorize cuttable segments
    cuttable_segments, _ = identify_cuttable_segments(workout)

    warmup_segments = [s for s in cuttable_segments if classify_segment(s) == 'warmup']
    cooldown_segments = [s for s in cuttable_segments if classify_segment(s) == 'cooldown']
    endurance_segments = [s for s in cuttable_segments if classify_segment(s) == 'endurance']

    warmup_duration = sum(s.duration for s in warmup_segments)
    cooldown_duration = sum(s.duration for s in cooldown_segments)
    endurance_duration = sum(s.duration for s in endurance_segments)

    # Step 1: Cut from endurance segments first (proportionally)
    if endurance_duration > 0 and remaining_cut > 0:
        endurance_cut = min(remaining_cut, endurance_duration)
        cut_ratio = endurance_cut / endurance_duration

        actual_cut = 0
        for segment in endurance_segments:
            reduction = int(segment.duration * cut_ratio)
            new_duration = segment.duration - reduction

            # Remove segment if too short
            if new_duration < MIN_SEGMENT_DURATION:
                actual_cut += segment.duration
                segment.duration = 0
            else:
                actual_cut += reduction
                segment.duration = new_duration

        remaining_cut -= actual_cut
        result.segments_cut['endurance'] = actual_cut

    # Step 2: Cut from warmup if needed (maintain minimum)
    if remaining_cut > 0 and warmup_duration > MIN_WARMUP_DURATION:
        available_warmup_cut = warmup_duration - MIN_WARMUP_DURATION
        warmup_cut = min(remaining_cut, available_warmup_cut)

        if warmup_cut > 0:
            cut_ratio = warmup_cut / warmup_duration

            actual_cut = 0
            for segment in warmup_segments:
                reduction = int(segment.duration * cut_ratio)
                new_duration = max(MIN_WARMUP_DURATION, segment.duration - reduction)
                actual_cut += segment.duration - new_duration
                segment.duration = new_duration

            remaining_cut -= actual_cut
            result.segments_cut['warmup'] = actual_cut

    # Step 3: Cut from cooldown if still needed (maintain minimum)
    if remaining_cut > 0 and cooldown_duration > MIN_COOLDOWN_DURATION:
        available_cooldown_cut = cooldown_duration - MIN_COOLDOWN_DURATION
        cooldown_cut = min(remaining_cut, available_cooldown_cut)

        if cooldown_cut > 0:
            cut_ratio = cooldown_cut / cooldown_duration

            actual_cut = 0
            for segment in cooldown_segments:
                reduction = int(segment.duration * cut_ratio)
                new_duration = max(MIN_COOLDOWN_DURATION, segment.duration - reduction)
                actual_cut += segment.duration - new_duration
                segment.duration = new_duration

            remaining_cut -= actual_cut
            result.segments_cut['cooldown'] = actual_cut

    # Remove zero-duration segments
    workout.segments = [s for s in workout.segments if s.duration > 0]

    # Recalculate total duration
    workout.calculate_total_duration()

    # Update result
    result.new_duration = workout.total_duration
    result.time_saved = original_duration - workout.total_duration
    result.status = 'modified'

    # Log if target not achieved
    if workout.total_duration > target_duration:
        logger.warning(
            f"{workout.name}: Could not reach target. "
            f"Final duration: {workout.total_duration}s (target: {target_duration}s)"
        )
        if not result.warning:
            result.warning = f"Final duration {workout.total_duration // 60}min exceeds target"

    workout.modification_status = 'modified'

    return result


def validate_interval_preservation(original: Workout, modified: Workout) -> bool:
    """Verify that all interval segments remain unchanged.

    Args:
        original: The original workout
        modified: The modified workout

    Returns:
        True if intervals are preserved, False otherwise
    """
    def get_intervals(workout: Workout) -> List[WorkoutSegment]:
        return [
            s for s in workout.segments
            if s.xml_type == 'IntervalsT' or classify_segment(s) == 'interval'
        ]

    original_intervals = get_intervals(original)
    modified_intervals = get_intervals(modified)

    if len(original_intervals) != len(modified_intervals):
        logger.error(
            f"Interval count mismatch in {modified.name}: "
            f"{len(original_intervals)} -> {len(modified_intervals)}"
        )
        return False

    for orig, mod in zip(original_intervals, modified_intervals):
        # For IntervalsT, check all interval-specific attributes
        if orig.xml_type == 'IntervalsT':
            if (orig.repeat != mod.repeat or
                orig.on_duration != mod.on_duration or
                orig.off_duration != mod.off_duration or
                orig.on_power != mod.on_power or
                orig.off_power != mod.off_power):
                logger.error(
                    f"Interval attributes changed in {modified.name}"
                )
                return False
        else:
            # For SteadyState intervals, check duration and power
            if orig.duration != mod.duration:
                logger.error(
                    f"Interval duration changed in {modified.name}: "
                    f"{orig.duration}s -> {mod.duration}s"
                )
                return False

            if orig.power != mod.power:
                logger.error(
                    f"Interval power changed in {modified.name}: "
                    f"{orig.power} -> {mod.power}"
                )
                return False

    return True


def modify_workout(
    workout: Workout,
    target_duration: int = TARGET_WEEKDAY_DURATION,
    validate: bool = True
) -> Tuple[Workout, ModificationResult]:
    """Modify a single workout if needed.

    Args:
        workout: The Workout to modify
        target_duration: Target duration in seconds
        validate: Whether to validate interval preservation

    Returns:
        Tuple of (modified_workout, modification_result)
    """
    # Make a copy to preserve original
    original = workout.copy()
    modified = workout.copy()

    # Determine action
    from .selector import determine_modification_action
    action = determine_modification_action(modified, target_duration)

    if action == 'skip':
        result = ModificationResult(
            workout_name=modified.name,
            filename=modified.filename,
            week_number=modified.week_number,
            day_number=modified.day_number,
            status='skipped',
            original_duration=modified.original_duration,
            new_duration=0,
            time_saved=modified.original_duration,
            reason=modified.skip_reason or "Skipped"
        )
        modified.modification_status = 'skipped'
        return modified, result

    if action == 'keep_unchanged':
        result = ModificationResult(
            workout_name=modified.name,
            filename=modified.filename,
            week_number=modified.week_number,
            day_number=modified.day_number,
            status='unchanged',
            original_duration=modified.original_duration,
            new_duration=modified.total_duration,
            time_saved=0,
            reason="Weekend ride" if modified.is_weekend_ride else "Under target duration"
        )
        modified.modification_status = 'unchanged'
        return modified, result

    # Apply cuts
    result = apply_proportional_cuts(modified, target_duration)

    # Validate interval preservation
    if validate and result.status == 'modified':
        if not validate_interval_preservation(original, modified):
            logger.error(f"Interval preservation failed for {modified.name}")
            result.warning = "VALIDATION FAILED: Intervals may have been modified"

    return modified, result
