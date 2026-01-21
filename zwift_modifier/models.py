"""Data structures for Zwift Workout Modifier."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import xml.etree.ElementTree as ET
import copy


@dataclass
class WorkoutSegment:
    """Single segment within a workout."""
    xml_type: str  # 'Warmup', 'Cooldown', 'SteadyState', 'IntervalsT', 'FreeRide'
    duration: int  # seconds

    # SteadyState attributes
    power: Optional[float] = None
    cadence: Optional[int] = None

    # Warmup/Cooldown attributes
    power_low: Optional[float] = None
    power_high: Optional[float] = None

    # IntervalsT attributes
    repeat: Optional[int] = None
    on_duration: Optional[int] = None
    off_duration: Optional[int] = None
    on_power: Optional[float] = None
    off_power: Optional[float] = None

    # Original XML element for preservation
    original_element: Optional[ET.Element] = None

    def copy(self) -> 'WorkoutSegment':
        """Create a deep copy of this segment."""
        new_seg = WorkoutSegment(
            xml_type=self.xml_type,
            duration=self.duration,
            power=self.power,
            cadence=self.cadence,
            power_low=self.power_low,
            power_high=self.power_high,
            repeat=self.repeat,
            on_duration=self.on_duration,
            off_duration=self.off_duration,
            on_power=self.on_power,
            off_power=self.off_power,
            original_element=copy.deepcopy(self.original_element) if self.original_element is not None else None
        )
        return new_seg

    def get_effective_power(self) -> float:
        """Get the effective/average power for this segment."""
        if self.power is not None:
            return self.power
        if self.power_low is not None and self.power_high is not None:
            return (self.power_low + self.power_high) / 2
        if self.on_power is not None and self.off_power is not None:
            # Weighted average for intervals
            if self.on_duration and self.off_duration:
                total = self.on_duration + self.off_duration
                return (self.on_power * self.on_duration + self.off_power * self.off_duration) / total
            return (self.on_power + self.off_power) / 2
        return 0.0


@dataclass
class Workout:
    """Complete workout definition."""
    filename: str
    week_number: int
    day_number: int

    # XML content
    author: str
    name: str
    description: str
    sport_type: str
    tags: List[str]
    segments: List[WorkoutSegment]

    # Calculated properties
    total_duration: int = 0  # seconds
    original_duration: int = 0  # for tracking modifications
    classification: str = 'mixed'  # 'recovery', 'endurance', 'interval', 'mixed'
    difficulty_score: float = 0.0

    # Processing flags
    is_weekend_ride: bool = False
    should_skip: bool = False
    modification_status: str = 'pending'  # 'pending', 'skipped', 'unchanged', 'modified'
    skip_reason: Optional[str] = None

    # Original XML tree
    original_xml: Optional[ET.Element] = None

    def __post_init__(self):
        """Calculate derived properties after initialization."""
        self.calculate_total_duration()
        if self.original_duration == 0:
            self.original_duration = self.total_duration

    def calculate_total_duration(self) -> None:
        """Calculate total workout duration from segments."""
        total = 0
        for seg in self.segments:
            if seg.xml_type == 'IntervalsT' and seg.repeat:
                # For intervals, total duration is repeat * (on + off)
                on_dur = seg.on_duration or 0
                off_dur = seg.off_duration or 0
                total += seg.repeat * (on_dur + off_dur)
            else:
                total += seg.duration
        self.total_duration = total

    def copy(self) -> 'Workout':
        """Create a deep copy of this workout."""
        return Workout(
            filename=self.filename,
            week_number=self.week_number,
            day_number=self.day_number,
            author=self.author,
            name=self.name,
            description=self.description,
            sport_type=self.sport_type,
            tags=list(self.tags),
            segments=[seg.copy() for seg in self.segments],
            total_duration=self.total_duration,
            original_duration=self.original_duration,
            classification=self.classification,
            difficulty_score=self.difficulty_score,
            is_weekend_ride=self.is_weekend_ride,
            should_skip=self.should_skip,
            modification_status=self.modification_status,
            skip_reason=self.skip_reason,
            original_xml=copy.deepcopy(self.original_xml) if self.original_xml is not None else None
        )


@dataclass
class ModificationResult:
    """Result of modification for reporting."""
    workout_name: str
    filename: str
    week_number: int
    day_number: int
    status: str  # 'skipped', 'unchanged', 'modified'
    original_duration: int
    new_duration: int
    time_saved: int
    reason: Optional[str] = None  # For skipped workouts
    warning: Optional[str] = None
    segments_cut: Dict[str, int] = field(default_factory=dict)  # segment type -> seconds cut


@dataclass
class WeekSummary:
    """Summary of modifications for a week."""
    week_number: int
    workouts: List[ModificationResult]
    original_duration: int = 0
    new_duration: int = 0
    time_saved: int = 0
    workouts_modified: int = 0
    workouts_skipped: int = 0
    workouts_unchanged: int = 0
