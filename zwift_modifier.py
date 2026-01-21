#!/usr/bin/env python3
"""
Zwift Workout Modifier - Entry point script.

Modify Zwift workout durations while preserving interval work.

Usage:
    python zwift_modifier.py [input_dir] [options]

Examples:
    python zwift_modifier.py ./original_workouts --output-dir ./modified_workouts
    python zwift_modifier.py ./original_workouts --dry-run
    python zwift_modifier.py ./original_workouts --target-duration 60 --verbose
"""

import sys
from zwift_modifier.main import main

if __name__ == '__main__':
    sys.exit(main())
