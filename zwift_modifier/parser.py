"""Parser for .zwo XML files."""

import re
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional, Tuple

from .models import Workout, WorkoutSegment
from .config import WEEK_PATTERNS, DAY_PATTERNS

logger = logging.getLogger(__name__)


def parse_zwo_file(filepath: Path) -> Optional[Workout]:
    """Parse a .zwo file and return a Workout object.

    Args:
        filepath: Path to the .zwo file

    Returns:
        Workout object or None if parsing fails
    """
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error(f"Invalid XML in {filepath}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        return None

    # Extract week and day from filename
    week_number, day_number = extract_week_day(filepath.stem)

    # Extract metadata
    author = get_element_text(root, 'author', 'Unknown')
    name = get_element_text(root, 'name', filepath.stem)
    description = get_element_text(root, 'description', '')
    sport_type = get_element_text(root, 'sportType', 'bike')

    # Extract tags
    tags = []
    tags_elem = root.find('tags')
    if tags_elem is not None:
        for tag in tags_elem.findall('tag'):
            tag_name = tag.get('name')
            if tag_name:
                tags.append(tag_name)

    # Extract segments
    workout_elem = root.find('workout')
    if workout_elem is None:
        logger.error(f"No <workout> element in {filepath}")
        return None

    segments = parse_segments(workout_elem)
    if not segments:
        logger.warning(f"No segments found in {filepath}")

    return Workout(
        filename=filepath.name,
        week_number=week_number,
        day_number=day_number,
        author=author,
        name=name,
        description=description,
        sport_type=sport_type,
        tags=tags,
        segments=segments,
        original_xml=root
    )


def extract_week_day(filename: str) -> Tuple[int, int]:
    """Extract week and day numbers from filename.

    Args:
        filename: The filename without extension

    Returns:
        Tuple of (week_number, day_number)
    """
    week_number = 0
    day_number = 0

    # Try week patterns
    for pattern in WEEK_PATTERNS:
        match = re.search(pattern, filename)
        if match:
            week_number = int(match.group(1))
            break

    # Try day patterns
    for pattern in DAY_PATTERNS:
        match = re.search(pattern, filename)
        if match:
            day_number = int(match.group(1))
            break

    if week_number == 0:
        logger.warning(f"Could not extract week number from: {filename}")
    if day_number == 0:
        logger.warning(f"Could not extract day number from: {filename}")

    return week_number, day_number


def get_element_text(root: ET.Element, tag: str, default: str = '') -> str:
    """Get text content of an XML element."""
    elem = root.find(tag)
    if elem is not None and elem.text:
        return elem.text.strip()
    return default


def parse_segments(workout_elem: ET.Element) -> List[WorkoutSegment]:
    """Parse all segments from a workout element.

    Args:
        workout_elem: The <workout> XML element

    Returns:
        List of WorkoutSegment objects
    """
    segments = []

    for elem in workout_elem:
        segment = parse_segment_element(elem)
        if segment:
            segments.append(segment)

    return segments


def parse_segment_element(elem: ET.Element) -> Optional[WorkoutSegment]:
    """Parse a single segment XML element.

    Args:
        elem: XML element (Warmup, Cooldown, SteadyState, IntervalsT, FreeRide)

    Returns:
        WorkoutSegment or None
    """
    xml_type = elem.tag

    # Get duration
    duration = int(elem.get('Duration', 0))

    segment = WorkoutSegment(
        xml_type=xml_type,
        duration=duration,
        original_element=elem
    )

    # Parse type-specific attributes
    if xml_type in ['Warmup', 'Cooldown']:
        segment.power_low = parse_float(elem.get('PowerLow'))
        segment.power_high = parse_float(elem.get('PowerHigh'))

    elif xml_type == 'SteadyState':
        segment.power = parse_float(elem.get('Power'))
        segment.cadence = parse_int(elem.get('Cadence'))

    elif xml_type == 'IntervalsT':
        segment.repeat = parse_int(elem.get('Repeat'))
        segment.on_duration = parse_int(elem.get('OnDuration'))
        segment.off_duration = parse_int(elem.get('OffDuration'))
        segment.on_power = parse_float(elem.get('OnPower'))
        segment.off_power = parse_float(elem.get('OffPower'))
        segment.cadence = parse_int(elem.get('Cadence'))

        # For intervals, the Duration attribute might not be set
        # Calculate from repeat * (on + off)
        if duration == 0 and segment.repeat:
            on_dur = segment.on_duration or 0
            off_dur = segment.off_duration or 0
            segment.duration = segment.repeat * (on_dur + off_dur)

    elif xml_type == 'FreeRide':
        # FreeRide has no power target
        pass

    elif xml_type == 'Ramp':
        # Ramp is similar to Warmup/Cooldown
        segment.power_low = parse_float(elem.get('PowerLow'))
        segment.power_high = parse_float(elem.get('PowerHigh'))

    else:
        logger.debug(f"Unknown segment type: {xml_type}")

    return segment


def parse_float(value: Optional[str]) -> Optional[float]:
    """Parse a float value from string."""
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_int(value: Optional[str]) -> Optional[int]:
    """Parse an integer value from string."""
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def scan_directory(directory: Path) -> List[Workout]:
    """Scan a directory for .zwo files and parse them.

    Args:
        directory: Path to directory containing .zwo files

    Returns:
        List of parsed Workout objects, sorted by week and day
    """
    workouts = []

    if not directory.exists():
        logger.error(f"Directory not found: {directory}")
        return workouts

    # Find all .zwo files
    zwo_files = list(directory.glob('**/*.zwo'))

    if not zwo_files:
        logger.warning(f"No .zwo files found in {directory}")
        return workouts

    logger.info(f"Found {len(zwo_files)} .zwo files")

    for filepath in zwo_files:
        workout = parse_zwo_file(filepath)
        if workout:
            workouts.append(workout)
        else:
            logger.warning(f"Failed to parse: {filepath}")

    # Sort by week and day
    workouts.sort(key=lambda w: (w.week_number, w.day_number))

    return workouts
