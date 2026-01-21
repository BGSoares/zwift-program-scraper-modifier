"""Configuration constants for Zwift Workout Modifier."""

# Target durations (in seconds)
TARGET_WEEKDAY_DURATION = 75 * 60  # 75 minutes
MIN_WARMUP_DURATION = 5 * 60  # 5 minutes
MIN_COOLDOWN_DURATION = 5 * 60  # 5 minutes
MIN_SEGMENT_DURATION = 60  # 1 minute

# Skip threshold
SKIP_THRESHOLD_WORKOUTS = 5  # Skip recovery if week has >= 5 workouts

# Power zones (decimal, % FTP)
ZONE_1_MAX = 0.55  # 55% FTP - Active Recovery
ZONE_2_MAX = 0.75  # 75% FTP - Endurance
ZONE_3_MAX = 0.90  # 90% FTP - Tempo
ZONE_4_MAX = 1.05  # 105% FTP - Threshold
ZONE_5_MAX = 1.20  # 120% FTP - VO2 Max
ZONE_6_MIN = 1.20  # 120%+ FTP - Anaerobic/Sprint

# Validation
MIN_WORKOUT_DURATION = 300  # 5 minutes
MAX_WORKOUT_DURATION = 14400  # 4 hours

# Filename patterns for week/day extraction
WEEK_PATTERNS = [
    r'[Ww]eek[_\s-]?(\d+)',
    r'[Ww](\d+)',
]
DAY_PATTERNS = [
    r'[Dd]ay[_\s-]?(\d+)',
    r'[Dd](\d+)',
]

# Workout type keywords for classification
FILENAME_KEYWORDS = {
    'recovery': ['rest', 'recovery', 'easy', 'active_recovery', 'active-recovery'],
    'endurance': ['endurance', 'base', 'long', 'steady'],
    'interval': [
        'interval', 'vo2', 'threshold', 'sweet', 'spot', 'tempo',
        'cadence', 'over', 'under', 'ftp', 'hiit', 'sprint', 'explosive',
        'crisscross', 'step'
    ],
}
