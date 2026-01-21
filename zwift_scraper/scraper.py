"""Web scraping logic for Zwift Workout Scraper."""

import logging
import time
from typing import List, Optional, Callable
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import (
    BASE_URL, DEFAULT_DELAY, DEFAULT_TIMEOUT,
    MAX_RETRIES, RETRY_BACKOFF, USER_AGENT
)
from .parser import parse_landing_page, parse_all_workouts_from_page
from .workout import Workout, TrainingProgram

logger = logging.getLogger(__name__)


class ScraperError(Exception):
    """Base exception for scraper errors."""
    pass


class NetworkError(ScraperError):
    """Network-related error."""
    pass


class ParseError(ScraperError):
    """Parsing-related error."""
    pass


class ZwiftWorkoutScraper:
    """Scraper for whatsonzwift.com workout data."""

    def __init__(
        self,
        delay: float = DEFAULT_DELAY,
        timeout: int = DEFAULT_TIMEOUT,
        progress_callback: Optional[Callable[[str], None]] = None
    ):
        """Initialize the scraper.

        Args:
            delay: Delay between requests in seconds
            timeout: Request timeout in seconds
            progress_callback: Optional callback for progress updates
        """
        self.delay = delay
        self.timeout = timeout
        self.progress_callback = progress_callback or (lambda x: None)
        self.session = self._create_session()
        self._last_request_time = 0

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry logic."""
        session = requests.Session()

        # Configure retries
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set headers
        session.headers.update({
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        })

        return session

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request_time = time.time()

    def _fetch_page(self, url: str) -> str:
        """Fetch a page with rate limiting and error handling.

        Args:
            url: URL to fetch

        Returns:
            HTML content of the page

        Raises:
            NetworkError: If the request fails
        """
        self._rate_limit()

        logger.debug(f"Fetching: {url}")

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.text

        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout fetching {url}: {e}")
            raise NetworkError(f"Timeout fetching {url}") from e

        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 'unknown'
            logger.error(f"HTTP error {status_code} fetching {url}: {e}")

            if status_code == 403:
                raise NetworkError(f"Access forbidden (403) for {url}. Check robots.txt.") from e
            elif status_code == 404:
                raise NetworkError(f"Page not found (404): {url}") from e
            else:
                raise NetworkError(f"HTTP error {status_code} for {url}") from e

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            raise NetworkError(f"Failed to fetch {url}") from e

    def scrape_program(self, program_url: str) -> TrainingProgram:
        """Scrape the entire training program.

        The whatsonzwift.com Active Offseason page has all workouts inline,
        so we only need to fetch a single page.

        Args:
            program_url: URL to the program landing page

        Returns:
            TrainingProgram containing all workouts
        """
        self.progress_callback("Scraping Active Offseason workouts...")

        # Fetch the landing page (contains all workout data)
        try:
            html = self._fetch_page(program_url)
        except NetworkError as e:
            logger.error(f"Failed to fetch page: {e}")
            raise

        # Parse week information
        weeks = parse_landing_page(html, program_url)
        self.progress_callback(f"Found {len(weeks)} weeks")

        # Parse all workouts from the page
        workouts = parse_all_workouts_from_page(html, program_url)

        # Create program
        program = TrainingProgram(
            name="Active Offseason",
            weeks=len(weeks)
        )

        # Group workouts by week for progress reporting
        current_week = 0
        for workout in workouts:
            if workout.week_number != current_week:
                current_week = workout.week_number
                week_info = next((w for w in weeks if w['week_number'] == current_week), {})
                count = week_info.get('workout_count', '?')
                self.progress_callback(f"\nWeek {current_week}: {count} workouts")

            program.add_workout(workout)
            duration_str = f"{workout.duration_minutes}min" if workout.duration_minutes else ""
            self.progress_callback(f"  Day {workout.day_number} - {workout.name} ({duration_str})")

        self.progress_callback(f"\nComplete! Scraped {program.total_workouts} workouts")

        return program

    def dry_run(self, program_url: str) -> None:
        """Preview what would be scraped without parsing all workout details.

        Args:
            program_url: URL to the program landing page
        """
        self.progress_callback("DRY RUN: Previewing scrape...")

        # Fetch landing page
        try:
            landing_html = self._fetch_page(program_url)
        except NetworkError as e:
            logger.error(f"Failed to fetch landing page: {e}")
            raise

        weeks = parse_landing_page(landing_html, program_url)

        self.progress_callback(f"\nFound {len(weeks)} weeks:\n")

        for week_info in weeks:
            week_num = week_info['week_number']
            duration = week_info.get('total_duration', 'N/A')
            count = week_info.get('workout_count', 'N/A')
            tss = week_info.get('tss', 'N/A')

            self.progress_callback(f"  Week {week_num}: {count} workouts, {duration}, TSS {tss}")

        self.progress_callback("\nDry run complete. No workout details parsed.")
