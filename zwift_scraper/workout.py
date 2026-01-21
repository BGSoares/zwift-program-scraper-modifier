"""Workout data structures for Zwift Workout Scraper."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class WorkoutSegment:
    """Single segment within a workout."""
    type: str  # 'warmup', 'cooldown', 'steady', 'intervals', 'freeride'
    duration_seconds: int
    power: Optional[float] = None  # For steady state (decimal, e.g., 0.73)
    power_low: Optional[float] = None  # For warmup/cooldown
    power_high: Optional[float] = None  # For warmup/cooldown
    repeat: Optional[int] = None  # For intervals
    on_duration: Optional[int] = None  # For intervals (seconds)
    off_duration: Optional[int] = None  # For intervals (seconds)
    on_power: Optional[float] = None  # For intervals
    off_power: Optional[float] = None  # For intervals
    cadence: Optional[int] = None  # Optional RPM target

    def to_dict(self) -> Dict:
        """Convert segment to dictionary, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Workout:
    """Complete workout definition."""
    week_number: int
    day_number: int
    name: str
    description: str
    duration_minutes: int
    tss: int
    segments: List[WorkoutSegment]
    url: str
    zone_distribution: Dict[str, int] = field(default_factory=dict)

    @property
    def full_name(self) -> str:
        """Generate full workout name including program and week info."""
        return f"Active Offseason - Week {self.week_number} Day {self.day_number} - {self.name}"

    @property
    def filename(self) -> str:
        """Generate sanitized filename for .zwo file."""
        import re
        from .config import MAX_FILENAME_LENGTH, FILENAME_INVALID_CHARS

        # Create base filename
        name_part = self.name.replace(' ', '_')
        name_part = re.sub(FILENAME_INVALID_CHARS, '', name_part)
        name_part = re.sub(r'_+', '_', name_part)  # Replace multiple underscores
        name_part = name_part.strip('_')

        filename = f"Week{self.week_number}_Day{self.day_number}_{name_part}"

        # Truncate if necessary
        if len(filename) > MAX_FILENAME_LENGTH:
            filename = filename[:MAX_FILENAME_LENGTH]

        return f"{filename}.zwo"


@dataclass
class TrainingProgram:
    """Collection of all workouts in a training program."""
    name: str
    weeks: int
    workouts: List[Workout] = field(default_factory=list)

    def add_workout(self, workout: Workout) -> None:
        """Add a workout to the program."""
        self.workouts.append(workout)

    def get_workouts_by_week(self, week_number: int) -> List[Workout]:
        """Get all workouts for a specific week."""
        return [w for w in self.workouts if w.week_number == week_number]

    @property
    def total_workouts(self) -> int:
        """Get total number of workouts."""
        return len(self.workouts)

    @property
    def total_duration_minutes(self) -> int:
        """Get total duration of all workouts in minutes."""
        return sum(w.duration_minutes for w in self.workouts)
