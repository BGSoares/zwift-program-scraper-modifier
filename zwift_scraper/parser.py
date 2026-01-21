"""HTML and text parsing for Zwift Workout Scraper."""

import re
import logging
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, Tag

from .workout import WorkoutSegment, Workout
from .config import ZONE_2_MAX

logger = logging.getLogger(__name__)

# Regular expression patterns for parsing segment text
PATTERNS = {
    # "10min from 50 to 75% FTP" or "10min from 50% to 75% FTP"
    'duration_range': re.compile(
        r'(\d+)\s*(?:min(?:ute)?s?|hr|hour)\s*(?:(\d+)\s*min)?\s*from\s*(\d+)%?\s*to\s*(\d+)%?\s*(?:FTP)?',
        re.IGNORECASE
    ),
    # "2hr @ 73% FTP" or "1hr 30min @ 73% FTP" or "90min @ 73% FTP"
    'duration_steady': re.compile(
        r'(\d+)\s*(hr|hour|min(?:ute)?s?)\s*(?:(\d+)\s*min)?\s*@\s*(?:(\d+)\s*rpm\s*,?\s*)?(\d+)%?\s*(?:FTP)?',
        re.IGNORECASE
    ),
    # "10min @ 73% FTP" - simpler version
    'simple_steady': re.compile(
        r'(\d+)\s*min(?:ute)?s?\s*@\s*(\d+)%?\s*(?:FTP)?',
        re.IGNORECASE
    ),
    # "10 x 1-minute" or "10x1min"
    'interval_count': re.compile(
        r'(\d+)\s*x\s*(\d+)[- ]?(?:min(?:ute)?s?|sec(?:ond)?s?)',
        re.IGNORECASE
    ),
    # Power range "50 to 75% FTP"
    'power_range': re.compile(r'(\d+)%?\s*to\s*(\d+)%?\s*(?:FTP)?', re.IGNORECASE),
    # Single power "@ 73% FTP" or just "73% FTP"
    'single_power': re.compile(r'@?\s*(\d+)%\s*(?:FTP)?', re.IGNORECASE),
    # Cadence "95rpm"
    'cadence': re.compile(r'(\d+)\s*rpm', re.IGNORECASE),
    # Duration extraction
    'duration_hours': re.compile(r'(\d+)\s*(?:hr|hour|h)(?:s)?(?:\s|$|[^a-z])', re.IGNORECASE),
    'duration_minutes': re.compile(r'(\d+)\s*(?:min|m)(?:ute)?(?:s)?(?:\s|$|[^a-z])', re.IGNORECASE),
    'duration_seconds': re.compile(r'(\d+)\s*sec(?:ond)?s?', re.IGNORECASE),
}


def parse_duration_to_seconds(text: str) -> int:
    """Parse duration text to seconds.

    Examples:
        "10min" -> 600
        "1hr 30min" -> 5400
        "2hr" -> 7200
        "90sec" -> 90
    """
    total_seconds = 0

    # Check for hours
    hours_match = PATTERNS['duration_hours'].search(text)
    if hours_match:
        total_seconds += int(hours_match.group(1)) * 3600

    # Check for minutes
    minutes_match = PATTERNS['duration_minutes'].search(text)
    if minutes_match:
        total_seconds += int(minutes_match.group(1)) * 60

    # Check for seconds
    seconds_match = PATTERNS['duration_seconds'].search(text)
    if seconds_match:
        total_seconds += int(seconds_match.group(1))

    return total_seconds


def parse_duration_text(text: str) -> int:
    """Parse human-readable duration to minutes.

    Examples:
        "1h50m" -> 110
        "1hr 30min" -> 90
        "45min" -> 45
    """
    total_minutes = 0

    # Match hours (various formats)
    hour_match = re.search(r'(\d+)\s*h(?:r|our)?s?(?:\s|$|[^a-z])', text, re.IGNORECASE)
    if hour_match:
        total_minutes += int(hour_match.group(1)) * 60

    # Match minutes (various formats)
    min_match = re.search(r'(\d+)\s*m(?:in(?:ute)?s?)?(?:\s|$|[^a-z])', text, re.IGNORECASE)
    if min_match:
        total_minutes += int(min_match.group(1))

    return total_minutes


def parse_power_percentage(text: str) -> Optional[float]:
    """Parse power percentage from text to decimal.

    Examples:
        "73% FTP" -> 0.73
        "@ 88%" -> 0.88
        "@ MAX" -> 2.00 (200% FTP for sprints)
    """
    # Check for MAX power (sprint/maximal effort)
    if re.search(r'\bMAX\b', text, re.IGNORECASE):
        return 2.00  # Represent MAX as 200% FTP

    # Look for percentage
    match = re.search(r'(\d+)\s*%', text)
    if match:
        return int(match.group(1)) / 100.0

    return None


def parse_power_range(text: str) -> Optional[Tuple[float, float]]:
    """Parse power range from text.

    Examples:
        "from 50 to 75% FTP" -> (0.50, 0.75)
        "50 to 75%" -> (0.50, 0.75)
    """
    match = PATTERNS['power_range'].search(text)
    if match:
        low = int(match.group(1)) / 100.0
        high = int(match.group(2)) / 100.0
        return (low, high)
    return None


def parse_cadence(text: str) -> Optional[int]:
    """Parse cadence from text.

    Examples:
        "95rpm" -> 95
        "@ 90 rpm" -> 90
    """
    match = PATTERNS['cadence'].search(text)
    if match:
        return int(match.group(1))
    return None


def parse_segment_text(text: str, position: str = 'middle') -> Optional[WorkoutSegment]:
    """Parse a segment text description into a WorkoutSegment.

    Args:
        text: The segment text description
        position: 'first', 'middle', or 'last' - helps determine segment type

    Returns:
        WorkoutSegment or None if parsing fails
    """
    text = text.strip()
    if not text:
        return None

    duration_seconds = parse_duration_to_seconds(text)
    if duration_seconds == 0:
        logger.warning(f"Could not parse duration from: {text}")
        return None

    cadence = parse_cadence(text)

    # Check for power range (warmup/cooldown pattern)
    power_range = parse_power_range(text)
    if power_range:
        low, high = power_range
        # Determine if warmup or cooldown based on position and power direction
        if position == 'first' or (low < high and position != 'last'):
            seg_type = 'warmup'
        elif position == 'last' or low > high:
            seg_type = 'cooldown'
        else:
            seg_type = 'warmup'  # Default to warmup for ranges

        return WorkoutSegment(
            type=seg_type,
            duration_seconds=duration_seconds,
            power_low=low,
            power_high=high,
            cadence=cadence
        )

    # Check for steady state power
    power = parse_power_percentage(text)
    if power:
        return WorkoutSegment(
            type='steady',
            duration_seconds=duration_seconds,
            power=power,
            cadence=cadence
        )

    # Check for rest/recovery/freeride
    if any(keyword in text.lower() for keyword in ['rest', 'recovery', 'free']):
        return WorkoutSegment(
            type='freeride',
            duration_seconds=duration_seconds
        )

    logger.warning(f"Could not fully parse segment: {text}")
    return None


def detect_intervals(segments: List[WorkoutSegment]) -> List[WorkoutSegment]:
    """Detect and consolidate interval patterns in segment list.

    Looks for alternating power levels and consolidates them into IntervalsT elements.
    """
    if len(segments) < 4:
        return segments

    result = []
    i = 0

    while i < len(segments):
        # Check if we can detect an interval pattern starting at i
        interval = try_detect_interval_pattern(segments, i)
        if interval:
            result.append(interval[0])
            i = interval[1]  # Skip to end of detected pattern
        else:
            result.append(segments[i])
            i += 1

    return result


def try_detect_interval_pattern(segments: List[WorkoutSegment], start: int) -> Optional[Tuple[WorkoutSegment, int]]:
    """Try to detect an interval pattern starting at given index.

    Returns (WorkoutSegment, end_index) if pattern found, None otherwise.
    """
    if start + 3 >= len(segments):
        return None

    # Need at least 2 repetitions to confirm a pattern
    seg1 = segments[start]
    seg2 = segments[start + 1]

    # Both must be steady state
    if seg1.type != 'steady' or seg2.type != 'steady':
        return None

    # They must have different power levels
    if seg1.power == seg2.power:
        return None

    # Look for repetitions
    repeat = 1
    idx = start + 2

    while idx + 1 < len(segments):
        next1 = segments[idx]
        next2 = segments[idx + 1]

        # Check if pattern repeats
        if (next1.type == 'steady' and next2.type == 'steady' and
            next1.duration_seconds == seg1.duration_seconds and
            next2.duration_seconds == seg2.duration_seconds and
            abs(next1.power - seg1.power) < 0.01 and
            abs(next2.power - seg2.power) < 0.01):
            repeat += 1
            idx += 2
        else:
            break

    # Need at least 2 repetitions
    if repeat < 2:
        return None

    # Determine which is "on" (higher intensity) and which is "off"
    if seg1.power > seg2.power:
        on_power, on_duration = seg1.power, seg1.duration_seconds
        off_power, off_duration = seg2.power, seg2.duration_seconds
    else:
        on_power, on_duration = seg2.power, seg2.duration_seconds
        off_power, off_duration = seg1.power, seg1.duration_seconds

    total_duration = (on_duration + off_duration) * repeat

    interval_segment = WorkoutSegment(
        type='intervals',
        duration_seconds=total_duration,
        repeat=repeat,
        on_duration=on_duration,
        off_duration=off_duration,
        on_power=on_power,
        off_power=off_power
    )

    return (interval_segment, idx)


def parse_workout_from_article(article: Tag, week_number: int, base_url: str) -> Optional[Workout]:
    """Parse a workout from an article element on whatsonzwift.com.

    Args:
        article: BeautifulSoup article Tag element
        week_number: The week number
        base_url: Base URL for the page

    Returns:
        Workout object or None if parsing fails
    """
    # Extract day number and name from article ID or h3
    article_id = article.get('id', '')
    day_match = re.search(r'day-(\d+)', article_id)
    day_number = int(day_match.group(1)) if day_match else 1

    # Get workout name from h3
    h3 = article.select_one('h3')
    name = h3.get_text(strip=True) if h3 else f"Day {day_number}"
    # Clean up name - remove "Day X - " prefix
    name = re.sub(r'^Day\s*\d+\s*[-:]\s*', '', name)

    # Extract segments from div.textbar elements
    segments = []
    textbars = article.select('div.textbar')
    for i, textbar in enumerate(textbars):
        text = textbar.get_text(strip=True)
        position = 'first' if i == 0 else ('last' if i == len(textbars) - 1 else 'middle')
        segment = parse_segment_text(text, position)
        if segment:
            segments.append(segment)

    if not segments:
        logger.warning(f"No segments found for {name}")
        return None

    # Detect and consolidate interval patterns
    segments = detect_intervals(segments)

    # Extract duration and TSS from text
    article_text = article.get_text()
    duration_minutes = 0
    tss = 0

    duration_match = re.search(r'Duration\s*:\s*(\d+h\s*\d*m|\d+m)', article_text)
    if duration_match:
        duration_minutes = parse_duration_text(duration_match.group(1))

    tss_match = re.search(r'(?:Stress points|TSS)\s*:\s*(\d+)', article_text)
    if tss_match:
        tss = int(tss_match.group(1))

    # Extract description - look for longer text paragraphs
    description = ""
    for p in article.select('p'):
        text = p.get_text(strip=True)
        # Skip short texts and navigation
        if len(text) > 50 and 'Available in Zwift' not in text:
            description = text
            break

    # If no paragraph description, look for text after zone distribution
    if not description:
        # Find text content that looks like a description
        desc_match = re.search(r'Z6\s*:\s*[-\d%hmZone\s:]+([A-Z][^✓]+)', article_text)
        if desc_match:
            description = desc_match.group(1).strip()

    url = f"{base_url}#{article_id}" if article_id else base_url

    return Workout(
        week_number=week_number,
        day_number=day_number,
        name=name,
        description=description,
        duration_minutes=duration_minutes,
        tss=tss,
        segments=segments,
        url=url
    )


def parse_landing_page(html: str, base_url: str) -> List[Dict]:
    """Parse the whatsonzwift.com landing page to extract week information.

    Returns list of dicts with week info:
    [
        {
            'week_number': 1,
            'url': 'https://...',
            'total_duration': '8h41m',
            'workout_count': 4,
            'tss': 465
        },
        ...
    ]
    """
    soup = BeautifulSoup(html, 'lxml')
    weeks = []

    # Find week sections using the actual whatsonzwift.com structure
    week_sections = soup.select('section[id^="week-"]')

    for section in week_sections:
        section_id = section.get('id', '')
        week_match = re.search(r'week-(\d+)', section_id)
        if not week_match:
            continue

        week_number = int(week_match.group(1))

        week_info = {
            'week_number': week_number,
            'url': f"{base_url}#{section_id}",
            'total_duration': '',
            'workout_count': 0,
            'tss': 0
        }

        # Extract stats from <p> elements
        for p in section.select('p'):
            text = p.get_text(strip=True)

            if 'Workouts:' in text:
                match = re.search(r'Workouts:\s*(\d+)', text)
                if match:
                    week_info['workout_count'] = int(match.group(1))

            elif 'Total duration:' in text:
                match = re.search(r'Total duration:\s*(\S+)', text)
                if match:
                    week_info['total_duration'] = match.group(1)

            elif 'stress points:' in text.lower():
                match = re.search(r'stress points:\s*(\d+)', text, re.IGNORECASE)
                if match:
                    week_info['tss'] = int(match.group(1))

        weeks.append(week_info)

    # Sort by week number
    weeks.sort(key=lambda x: x['week_number'])

    return weeks


def parse_all_workouts_from_page(html: str, base_url: str) -> List[Workout]:
    """Parse all workouts from the whatsonzwift.com landing page.

    The Active Offseason page has all workouts on a single page, organized by week.

    Returns:
        List of all Workout objects
    """
    soup = BeautifulSoup(html, 'lxml')
    workouts = []

    # Find all week sections
    week_sections = soup.select('section[id^="week-"]')

    for section in week_sections:
        section_id = section.get('id', '')
        week_match = re.search(r'week-(\d+)', section_id)
        if not week_match:
            continue

        week_number = int(week_match.group(1))

        # Find all workout articles within this week
        articles = section.select('article')

        for article in articles:
            workout = parse_workout_from_article(article, week_number, base_url)
            if workout:
                workouts.append(workout)

    return workouts


# Legacy functions for compatibility
def parse_week_page(html: str, base_url: str) -> List[Dict]:
    """Parse a week page to extract workout links and metadata.

    Note: On whatsonzwift.com, all workouts are on the landing page.
    This function is kept for compatibility.
    """
    return []


def parse_workout_page(html: str, week_number: int, day_number: int, url: str) -> Optional[Workout]:
    """Parse a workout detail page HTML into a Workout object.

    Note: On whatsonzwift.com, workout details are inline on the landing page.
    This function is kept for compatibility.
    """
    soup = BeautifulSoup(html, 'lxml')

    # Try to find the specific article
    articles = soup.select('article')
    for article in articles:
        article_id = article.get('id', '')
        if f'week-{week_number}' in article_id and f'day-{day_number}' in article_id:
            return parse_workout_from_article(article, week_number, url)

    return None


def extract_workout_name(soup: BeautifulSoup) -> Optional[str]:
    """Extract workout name from page."""
    h3 = soup.select_one('h3')
    if h3:
        name = h3.get_text(strip=True)
        name = re.sub(r'^Day\s*\d+\s*[-:]\s*', '', name)
        return name.strip()
    return None


def extract_workout_description(soup: BeautifulSoup) -> str:
    """Extract workout description from page."""
    for p in soup.select('p'):
        text = p.get_text(strip=True)
        if len(text) > 50 and 'Available in Zwift' not in text:
            return text
    return ""


def extract_workout_duration(soup: BeautifulSoup) -> int:
    """Extract workout duration in minutes from page."""
    text = soup.get_text()
    duration_match = re.search(r'Duration\s*:\s*(\d+h\s*\d*m|\d+m)', text)
    if duration_match:
        return parse_duration_text(duration_match.group(1))
    return 0


def extract_workout_tss(soup: BeautifulSoup) -> int:
    """Extract workout TSS from page."""
    text = soup.get_text()
    tss_match = re.search(r'(?:Stress points|TSS)\s*:\s*(\d+)', text)
    if tss_match:
        return int(tss_match.group(1))
    return 0


def extract_workout_segments(soup: BeautifulSoup) -> List[WorkoutSegment]:
    """Extract workout segments from page."""
    segments = []
    textbars = soup.select('div.textbar')

    for i, textbar in enumerate(textbars):
        text = textbar.get_text(strip=True)
        position = 'first' if i == 0 else ('last' if i == len(textbars) - 1 else 'middle')
        segment = parse_segment_text(text, position)
        if segment:
            segments.append(segment)

    return segments
