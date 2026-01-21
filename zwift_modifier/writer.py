"""Write modified workouts to .zwo files."""

import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
from typing import Optional

from .models import Workout, WorkoutSegment
from .classifier import classify_segment

logger = logging.getLogger(__name__)


def generate_modified_xml(workout: Workout) -> ET.Element:
    """Generate XML from a modified workout.

    Args:
        workout: The modified Workout

    Returns:
        XML Element tree
    """
    root = ET.Element('workout_file')

    # Add metadata
    author = ET.SubElement(root, 'author')
    author.text = workout.author or 'WhatsOnZwift'

    name = ET.SubElement(root, 'name')
    name.text = workout.name

    # Add modification note to description
    description = ET.SubElement(root, 'description')
    original_desc = workout.description or ""

    if workout.modification_status == 'modified':
        modification_note = (
            f"\n\n[MODIFIED: Duration reduced from "
            f"{workout.original_duration // 60}min to "
            f"{workout.total_duration // 60}min. "
            f"Interval work preserved.]"
        )
        description.text = original_desc + modification_note
    else:
        description.text = original_desc

    sport_type = ET.SubElement(root, 'sportType')
    sport_type.text = workout.sport_type or 'bike'

    # Add tags
    if workout.tags:
        tags = ET.SubElement(root, 'tags')
        for tag_name in workout.tags:
            tag = ET.SubElement(tags, 'tag')
            tag.set('name', tag_name)

    # Add workout segments
    workout_elem = ET.SubElement(root, 'workout')

    for segment in workout.segments:
        if segment.duration <= 0:
            continue  # Skip zero-duration segments

        seg_elem = create_segment_element(segment)
        workout_elem.append(seg_elem)

    return root


def create_segment_element(segment: WorkoutSegment) -> ET.Element:
    """Create XML element for a segment.

    Args:
        segment: The WorkoutSegment

    Returns:
        XML Element
    """
    elem = ET.Element(segment.xml_type)

    if segment.xml_type in ['Warmup', 'Cooldown', 'Ramp']:
        elem.set('Duration', str(segment.duration))
        if segment.power_low is not None:
            elem.set('PowerLow', f"{segment.power_low:.2f}")
        if segment.power_high is not None:
            elem.set('PowerHigh', f"{segment.power_high:.2f}")
        elem.set('pace', '0')

    elif segment.xml_type == 'SteadyState':
        elem.set('Duration', str(segment.duration))
        if segment.power is not None:
            elem.set('Power', f"{segment.power:.2f}")
        if segment.cadence:
            elem.set('Cadence', str(segment.cadence))
        elem.set('pace', '0')

    elif segment.xml_type == 'IntervalsT':
        if segment.repeat:
            elem.set('Repeat', str(segment.repeat))
        if segment.on_duration:
            elem.set('OnDuration', str(segment.on_duration))
        if segment.off_duration:
            elem.set('OffDuration', str(segment.off_duration))
        if segment.on_power is not None:
            elem.set('OnPower', f"{segment.on_power:.2f}")
        if segment.off_power is not None:
            elem.set('OffPower', f"{segment.off_power:.2f}")
        if segment.cadence:
            elem.set('Cadence', str(segment.cadence))
        elem.set('pace', '0')

    elif segment.xml_type == 'FreeRide':
        elem.set('Duration', str(segment.duration))
        elem.set('FlatRoad', '1')

    else:
        # Generic segment - just set duration
        elem.set('Duration', str(segment.duration))
        elem.set('pace', '0')

    return elem


def format_xml(root: ET.Element) -> str:
    """Format XML element tree as a pretty-printed string.

    Args:
        root: The root XML element

    Returns:
        Formatted XML string
    """
    rough_string = ET.tostring(root, encoding='unicode')
    parsed = minidom.parseString(rough_string)
    pretty = parsed.toprettyxml(indent='    ')

    # Clean up the output
    lines = pretty.split('\n')
    cleaned_lines = []
    for line in lines:
        if line.strip():
            cleaned_lines.append(line)

    # Add proper XML declaration
    result = '<?xml version="1.0" encoding="UTF-8"?>\n'
    start_idx = 0
    if cleaned_lines and cleaned_lines[0].startswith('<?xml'):
        start_idx = 1

    result += '\n'.join(cleaned_lines[start_idx:])

    return result


def write_workout_file(
    workout: Workout,
    output_path: Path,
    append_suffix: bool = True
) -> Optional[Path]:
    """Write a workout to a .zwo file.

    Args:
        workout: The Workout to write
        output_path: Output directory or file path
        append_suffix: Whether to append _MODIFIED suffix

    Returns:
        Path to written file, or None if failed
    """
    # Determine output filename
    if output_path.is_dir():
        if append_suffix and workout.modification_status == 'modified':
            filename = workout.filename.replace('.zwo', '_MODIFIED.zwo')
        else:
            filename = workout.filename
        file_path = output_path / filename
    else:
        file_path = output_path

    # Generate XML
    try:
        root = generate_modified_xml(workout)
        xml_string = format_xml(root)
    except Exception as e:
        logger.error(f"Failed to generate XML for {workout.filename}: {e}")
        return None

    # Write file
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(xml_string)
        logger.debug(f"Wrote: {file_path}")
        return file_path
    except IOError as e:
        logger.error(f"Failed to write {file_path}: {e}")
        return None


def generate_output_filename(workout: Workout, original_filename: str) -> str:
    """Generate output filename for a modified workout.

    Args:
        workout: The Workout
        original_filename: Original filename

    Returns:
        New filename
    """
    if workout.modification_status == 'modified':
        base_name = original_filename.replace('.zwo', '')
        return f"{base_name}_MODIFIED.zwo"
    return original_filename
