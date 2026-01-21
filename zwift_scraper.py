#!/usr/bin/env python3
"""
Zwift Workout Scraper - Entry point script.

Scrape workouts from whatsonzwift.com and generate Zwift .zwo files.

Usage:
    python zwift_scraper.py [url] [options]

Examples:
    python zwift_scraper.py --output-dir ./workouts
    python zwift_scraper.py --output-dir ./workouts --organize-by-week --verbose
    python zwift_scraper.py --dry-run
"""

import sys
from zwift_scraper.main import main

if __name__ == '__main__':
    sys.exit(main())
