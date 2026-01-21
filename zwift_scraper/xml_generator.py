"""XML generation for Zwift .zwo workout files."""

import xml.etree.ElementTree as ET
from xml.dom import minidom
import logging
from typing import Optional

from .workout import Workout, WorkoutSegment

logger = logging.getLogger(__name__)


def generate_zwo(workout: Workout) -> ET.Element:
    """Generate .zwo XML from a Workout object.

    Args:
        workout: The Workout object to convert

    Returns:
        XML Element tree for the workout
    """
    # Create root element
    root = ET.Element('workout_file')

    # Add metadata
    author = ET.SubElement(root, 'author')
    author.text = 'WhatsOnZwift'

    name = ET.SubElement(root, 'name')
    name.text = workout.full_name

    description = ET.SubElement(root, 'description')
    description.text = workout.description or f"Week {workout.week_number} Day {workout.day_number} workout"

    sport_type = ET.SubElement(root, 'sportType')
    sport_type.text = 'bike'

    # Add tags
    tags = ET.SubElement(root, 'tags')
    tag = ET.SubElement(tags, 'tag')
    tag.set('name', 'ACTIVE OFFSEASON')

    # Add workout segments
    workout_elem = ET.SubElement(root, 'workout')

    for segment in workout.segments:
        add_segment_to_workout(workout_elem, segment)

    return root


def add_segment_to_workout(workout_elem: ET.Element, segment: WorkoutSegment) -> None:
    """Add a segment element to the workout.

    Args:
        workout_elem: The workout XML element
        segment: The WorkoutSegment to add
    """
    if segment.type == 'warmup':
        elem = ET.SubElement(workout_elem, 'Warmup')
        elem.set('Duration', str(segment.duration_seconds))
        elem.set('PowerLow', f"{segment.power_low:.2f}")
        elem.set('PowerHigh', f"{segment.power_high:.2f}")
        elem.set('pace', '0')

    elif segment.type == 'cooldown':
        elem = ET.SubElement(workout_elem, 'Cooldown')
        elem.set('Duration', str(segment.duration_seconds))
        elem.set('PowerLow', f"{segment.power_low:.2f}")
        elem.set('PowerHigh', f"{segment.power_high:.2f}")
        elem.set('pace', '0')

    elif segment.type == 'steady':
        elem = ET.SubElement(workout_elem, 'SteadyState')
        elem.set('Duration', str(segment.duration_seconds))
        elem.set('Power', f"{segment.power:.2f}")
        elem.set('pace', '0')

        if segment.cadence:
            elem.set('Cadence', str(segment.cadence))

    elif segment.type == 'intervals':
        elem = ET.SubElement(workout_elem, 'IntervalsT')
        elem.set('Repeat', str(segment.repeat or 1))
        elem.set('OnDuration', str(segment.on_duration or 0))
        elem.set('OffDuration', str(segment.off_duration or 0))
        elem.set('OnPower', f"{segment.on_power:.2f}" if segment.on_power else "0.90")
        elem.set('OffPower', f"{segment.off_power:.2f}" if segment.off_power else "0.50")
        elem.set('pace', '0')

        if segment.cadence:
            elem.set('Cadence', str(segment.cadence))

    elif segment.type == 'freeride':
        elem = ET.SubElement(workout_elem, 'FreeRide')
        elem.set('Duration', str(segment.duration_seconds))
        elem.set('FlatRoad', '1')

    else:
        logger.warning(f"Unknown segment type: {segment.type}")
        # Default to steady state if we have power
        if segment.power:
            elem = ET.SubElement(workout_elem, 'SteadyState')
            elem.set('Duration', str(segment.duration_seconds))
            elem.set('Power', f"{segment.power:.2f}")
            elem.set('pace', '0')
        else:
            elem = ET.SubElement(workout_elem, 'FreeRide')
            elem.set('Duration', str(segment.duration_seconds))
            elem.set('FlatRoad', '1')


def format_xml(root: ET.Element) -> str:
    """Format XML element tree as a pretty-printed string.

    Args:
        root: The root XML element

    Returns:
        Formatted XML string with declaration and proper indentation
    """
    # Convert to string
    rough_string = ET.tostring(root, encoding='unicode')

    # Parse with minidom for pretty printing
    parsed = minidom.parseString(rough_string)

    # Get pretty printed string
    pretty = parsed.toprettyxml(indent='    ', encoding=None)

    # Clean up the output
    lines = pretty.split('\n')
    # Remove extra blank lines and the default XML declaration
    cleaned_lines = []
    for line in lines:
        # Skip empty lines and replace the declaration
        if line.strip():
            cleaned_lines.append(line)

    # Add proper XML declaration at the start
    result = '<?xml version="1.0" encoding="UTF-8"?>\n'
    # Skip the minidom XML declaration line if present
    start_idx = 0
    if cleaned_lines and cleaned_lines[0].startswith('<?xml'):
        start_idx = 1

    result += '\n'.join(cleaned_lines[start_idx:])

    return result


def workout_to_xml_string(workout: Workout) -> str:
    """Convert a Workout to a formatted XML string.

    Args:
        workout: The Workout object to convert

    Returns:
        Formatted .zwo XML string
    """
    root = generate_zwo(workout)
    return format_xml(root)


def workout_to_xml_bytes(workout: Workout) -> bytes:
    """Convert a Workout to XML bytes (UTF-8 encoded).

    Args:
        workout: The Workout object to convert

    Returns:
        UTF-8 encoded .zwo XML bytes
    """
    xml_string = workout_to_xml_string(workout)
    return xml_string.encode('utf-8')
