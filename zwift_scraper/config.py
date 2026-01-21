"""Configuration constants for Zwift Workout Scraper."""

# URL structure
BASE_URL = 'https://whatsonzwift.com'
PROGRAM_PATH = '/workouts/active-offseason'

# Scraping behavior
DEFAULT_DELAY = 1.0  # seconds
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]  # seconds

# User agent
USER_AGENT = 'ZwiftWorkoutScraperBot/1.0 (Training Program Parser)'

# Power zone definitions (% FTP)
ZONE_1_MAX = 55
ZONE_2_MAX = 75
ZONE_3_MAX = 90
ZONE_4_MAX = 105
ZONE_5_MAX = 120
ZONE_6_MIN = 120

# File naming
MAX_FILENAME_LENGTH = 50
FILENAME_INVALID_CHARS = r'[<>:"/\\|?*]'

# Validation
MIN_WORKOUT_DURATION = 300  # 5 minutes in seconds
MAX_WORKOUT_DURATION = 14400  # 4 hours in seconds
MIN_POWER = 0.0  # 0% FTP
MAX_POWER = 3.0  # 300% FTP (for sprints)

# Expected program structure
EXPECTED_WEEKS = 12
EXPECTED_MIN_WORKOUTS = 40
EXPECTED_MAX_WORKOUTS = 70
