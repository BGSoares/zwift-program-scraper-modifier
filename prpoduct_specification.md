# Product Specification: Zwift Workout Modifier

## 1. Overview

### 1.1 Purpose
Automate the modification of Zwift Active Offseason training program workout files (.zwo format) to fit a realistic 5-6 hour/week training schedule while preserving training quality.

### 1.2 Target User
Amateur cyclist with limited weekday training time (60-75 min max) who needs to compress a structured training program without losing key interval work.

### 1.3 Success Criteria
- Correctly identify and categorize workout types
- Preserve all high-intensity interval training
- Reduce weekday workout durations to ≤75 minutes
- Maintain weekend endurance rides unchanged
- Output valid .zwo files importable into Zwift

---

## 2. Technical Background

### 2.1 File Format
- **Input format**: .zwo files (Zwift Workout format)
- **Structure**: XML-based with specific schema
- **Key elements**:
  - `<workout>` - root element
  - `<name>` - workout title
  - `<description>` - workout details
  - `<durationType>` - typically "time"
  - Segment types: `<Warmup>`, `<SteadyState>`, `<IntervalsT>`, `<Cooldown>`, `<FreeRide>`
  - Attributes: `Duration` (seconds), `Power` or `PowerLow/PowerHigh` (% FTP), `Cadence`

### 2.2 Power Zones (% FTP)
- **Z1 (Active Recovery)**: <55%
- **Z2 (Endurance)**: 55-75%
- **Z3 (Tempo)**: 75-90%
- **Z4 (Threshold)**: 90-105%
- **Z5 (VO2 Max)**: 105-120%
- **Z6+ (Anaerobic/Sprint)**: >120%

### 2.3 Workout Types in Active Offseason
- **Active Recovery**: Low intensity (Z1-Z2), typically 30-60 min
- **Endurance**: Mostly Z2-Z3, can be 2-4 hours
- **Tempo/Sweet Spot**: Mix of Z2-Z3 with Z3-Z4 blocks
- **Interval**: Structured high-intensity (Z4-Z6) with recovery periods

---

## 3. Functional Requirements

### 3.1 Input Handling

**FR-1.1: File Discovery**
- Accept input directory path containing .zwo files
- Recursively scan for all .zwo files
- Parse XML structure of each file
- Handle malformed/invalid XML gracefully with error logging

**FR-1.2: Workout Metadata Extraction**
- Extract: name, description, total duration, workout date/day if available
- Calculate total workout duration (sum of all segment durations)
- Identify all workout segments with type, duration, and power zones

**FR-1.3: Week Grouping**
- Group workouts into weeks (7-day periods)
- If workout files contain date/day metadata: use that
- Fallback: assume sequential ordering, group every 7 files
- Handle incomplete weeks (programs that don't start on Monday)

### 3.2 Workout Classification

**FR-2.1: Primary Classification (Name/Description Analysis)**

Parse workout name and description for keywords:

**Active Recovery indicators:**
- Keywords: "recovery", "easy", "spin", "rest day"
- Typical duration: 30-60 min
- Typical intensity: mostly Z1-Z2

**Endurance indicators:**
- Keywords: "endurance", "base", "long", "steady"
- Typical duration: 90+ min
- Typical intensity: mostly Z2-Z3

**Interval indicators:**
- Keywords: "interval", "VO2", "threshold", "sweet spot", "tempo", "over-under"
- Typical duration: 45-90 min
- Typical intensity: contains Z4+ segments

**FR-2.2: Secondary Classification (Intensity/Duration Analysis)**

If name/description is ambiguous, analyze workout structure:

```
intensity_score = (sum of Z4+ segment durations) / total_duration

if intensity_score > 0.3:
    type = "interval"
elif total_duration > 90 min AND avg_power < 75% FTP:
    type = "endurance"
elif total_duration < 60 min AND avg_power < 65% FTP:
    type = "active_recovery"
else:
    type = "mixed" # tempo/sweet spot
```

**FR-2.3: Workout Difficulty Scoring**

Calculate difficulty for identifying "lightest" workout:
```
difficulty_score = (avg_power * total_duration_minutes) / 100

# Lower score = lighter workout
```

### 3.3 Workout Selection Rules

**FR-3.1: Skip Logic for High-Volume Weeks**
```
if workouts_in_week >= 5:
    identify active_recovery workouts (by classification)
    if multiple active_recovery:
        skip the one with lowest difficulty_score
    elif no active_recovery:
        skip workout with lowest difficulty_score
    else:
        skip the single active_recovery
```

**FR-3.2: Weekend Ride Identification**
```
weekend_ride = last_workout_in_week

# If day metadata available:
if saturday_or_sunday_workouts exist:
    weekend_ride = longest_duration_workout on Sat/Sun
```

Keep this workout completely unchanged (no modifications).

**FR-3.3: Weekday Ride Processing**
```
for each workout in week:
    if workout == weekend_ride:
        skip (keep unchanged)
    elif workout marked as skipped (FR-3.1):
        skip (don't output)
    elif workout.duration <= 75 minutes:
        keep unchanged
    else:
        apply_shortening_rules(workout)
```

### 3.4 Workout Modification Rules

**FR-4.1: Segment Type Identification**

Classify each workout segment:
- **Endurance segment**: SteadyState or FreeRide with power 55-90% FTP
- **Interval segment**: IntervalsT, or any segment with power >90% FTP
- **Warmup segment**: First segment(s) tagged as Warmup OR first segments <75% FTP
- **Cooldown segment**: Last segment(s) tagged as Cooldown OR last segments <75% FTP

**FR-4.2: Duration Calculation**
```
current_duration = sum(all_segment_durations)
target_duration = 75 * 60  # 75 minutes in seconds
time_to_cut = current_duration - target_duration
```

**FR-4.3: Proportional Cutting Algorithm**

```python
# Step 1: Identify cuttable segments
endurance_segments = [seg for seg in workout if is_endurance(seg)]
total_endurance_duration = sum(seg.duration for seg in endurance_segments)

# Step 2: Calculate cut ratio
cut_ratio = time_to_cut / total_endurance_duration

# Step 3: Apply cuts proportionally
for seg in endurance_segments:
    reduction = seg.duration * cut_ratio
    seg.duration -= reduction

# Step 4: Check and adjust warmup/cooldown if needed
if warmup.duration > 5 * 60:  # 5 minutes
    warmup.duration = max(5 * 60, warmup.duration - additional_cut)
if cooldown.duration > 5 * 60:
    cooldown.duration = max(5 * 60, cooldown.duration - additional_cut)

# Step 5: Recalculate total, adjust if needed to hit 75 min exactly
```

**FR-4.4: Interval Preservation**
- All segments with power ≥90% FTP: keep duration unchanged
- All IntervalsT blocks: keep structure, count, duration, and recovery unchanged
- If intervals include recovery periods <90% FTP: keep those too (they're part of the interval structure)

**FR-4.5: Edge Cases**

```
# Case 1: Insufficient endurance segments to cut
if total_endurance_duration < time_to_cut:
    # Try cutting from warmup (keep 5 min minimum)
    # Then try cutting from cooldown (keep 5 min minimum)
    # If still can't reach 75 min, output warning and cut as much as possible

# Case 2: Very short endurance segments
if any endurance segment would be cut to <60 seconds:
    remove segment entirely, redistribute cut to other segments

# Case 3: Workout becomes unbalanced
if (interval_duration / total_duration) > 0.8:
    output warning: "Workout heavily interval-focused after cuts"
```

### 3.5 Output Generation

**FR-5.1: File Naming Convention**
```
Original: "Week 1 - Endurance Ride.zwo"
Modified: "Week 1 - Endurance Ride_MODIFIED.zwo"

OR

Create subdirectory: "modified_workouts/"
Keep original names in new directory
```

**FR-5.2: XML Output**
- Preserve original XML structure and formatting
- Update segment durations with new values (in seconds)
- Maintain all other attributes (power, cadence, etc.)
- Ensure valid XML (proper escaping, closing tags)

**FR-5.3: Metadata Addition**
Add comment to modified files:
```xml
<!-- MODIFIED by Zwift Workout Modifier -->
<!-- Original duration: XXX min, New duration: 75 min -->
<!-- Endurance segments reduced proportionally -->
```

**FR-5.4: Modification Log**
Generate summary report (markdown or text):

```
# Zwift Workout Modification Report

## Week 1
- Monday: "Endurance Base" - 120 min → 75 min (cut 45 min from endurance)
- Tuesday: "VO2 Intervals" - 60 min → unchanged
- Wednesday: SKIPPED (Active Recovery)
- Thursday: "Tempo" - 65 min → unchanged
- Friday: "Sweet Spot" - 90 min → 75 min (cut 15 min from endurance)
- Saturday: "Long Endurance" - 180 min → unchanged (weekend ride)

Total weekly time: Original 575 min → Modified 385 min (6.4 hours)

## Week 2
...
```

---

## 4. Non-Functional Requirements

### 4.1 Performance
- Process entire 12-week program (<100 files) in <30 seconds
- Memory efficient (stream parse XML, don't load all files at once)

### 4.2 Reliability
- Validate all output .zwo files are valid XML
- Verify output files can be parsed by Zwift (schema compliance)
- Backup original files before modification (optional flag)

### 4.3 Usability
- Command-line interface with clear options
- Progress indicators for batch processing
- Clear error messages with file names and line numbers
- Dry-run mode to preview changes without writing files

### 4.4 Maintainability
- Modular code structure (separate parsing, classification, modification, output)
- Configurable parameters (target duration, min warmup/cooldown, zone definitions)
- Comprehensive logging

---

## 5. User Interface Specification

### 5.1 Command-Line Interface

```bash
python zwift_modifier.py [input_dir] [options]

Required:
  input_dir              Path to directory containing .zwo files

Options:
  --output-dir DIR       Output directory (default: ./modified_workouts)
  --target-duration MIN  Target weekday duration in minutes (default: 75)
  --min-warmup MIN       Minimum warmup duration in minutes (default: 5)
  --min-cooldown MIN     Minimum cooldown duration in minutes (default: 5)
  --skip-threshold N     Skip workouts if week has >= N workouts (default: 5)
  --dry-run             Preview changes without writing files
  --backup              Create backup of original files
  --verbose             Detailed logging
  --report FILE         Output modification report to file (default: report.md)
```

### 5.2 Example Usage

```bash
# Basic usage
python zwift_modifier.py ~/Zwift/Workouts/ActiveOffseason/

# Dry run to preview
python zwift_modifier.py ~/Zwift/Workouts/ActiveOffseason/ --dry-run

# Custom target duration with backup
python zwift_modifier.py ~/Zwift/Workouts/ActiveOffseason/ \
    --target-duration 60 \
    --backup \
    --output-dir ~/Zwift/Workouts/Modified/
```

### 5.3 Output Messages

```
🔍 Scanning for .zwo files...
   Found 48 workout files

📊 Analyzing workouts...
   Grouped into 12 weeks
   Week 1: 4 workouts (0 skipped)
   Week 2: 5 workouts (1 skipped - Active Recovery)
   ...

✂️  Modifying workouts...
   [Week 1] Monday Endurance: 120 min → 75 min ✓
   [Week 1] Tuesday VO2: 60 min → unchanged ✓
   [Week 1] Saturday Long Ride: 180 min → unchanged (weekend) ✓
   ...

✅ Complete! Modified 36 workouts
   📁 Output: ./modified_workouts/
   📄 Report: ./report.md
   ⏱️  Total time saved: 12.5 hours
```

---

## 6. Testing Requirements

### 6.1 Unit Tests

**Test Coverage:**
- XML parsing (valid files, malformed files, missing elements)
- Workout classification (all types, ambiguous cases)
- Duration calculations (various segment combinations)
- Proportional cutting algorithm (edge cases)
- Warmup/cooldown minimum enforcement
- Interval preservation
- Output XML generation

**Test Data:**
Create synthetic .zwo files representing:
- Pure endurance ride (2 hours, all Z2)
- Interval workout (60 min with 5x5min Z5 intervals)
- Mixed workout (90 min with Z2 base + Z3 tempo blocks)
- Short recovery ride (45 min, Z1-Z2)
- Workout with long warmup/cooldown (20 min each)

### 6.2 Integration Tests

- Process sample week (7 files) and verify output
- Process full program (12 weeks) and verify consistency
- Test skip logic with 5+ workout weeks
- Test weekend ride preservation
- Verify all output files are valid XML and Zwift-importable

### 6.3 Edge Case Tests

- Week with only 3 workouts (no skipping)
- Week with 6 workouts, all intervals (which to skip?)
- Workout with zero endurance segments
- Workout that's 74 minutes (shouldn't be modified)
- Workout that's 76 minutes (minimal cut)
- Workout with nested interval structures
- File with non-standard segment types

---

## 7. Implementation Notes

### 7.1 Recommended Python Libraries

```python
import xml.etree.ElementTree as ET  # XML parsing
from pathlib import Path             # File handling
import argparse                      # CLI
from dataclasses import dataclass    # Data structures
from typing import List, Dict, Tuple
import logging                       # Logging
from datetime import timedelta       # Duration handling
```

### 7.2 Suggested Code Structure

```
zwift_modifier/
├── __init__.py
├── main.py              # CLI entry point
├── parser.py            # .zwo XML parsing
├── classifier.py        # Workout type classification
├── modifier.py          # Workout modification logic
├── writer.py            # Output .zwo generation
├── reporter.py          # Report generation
├── config.py            # Configuration and constants
└── utils.py             # Helper functions

tests/
├── test_parser.py
├── test_classifier.py
├── test_modifier.py
├── test_integration.py
└── fixtures/            # Sample .zwo files
```

### 7.3 Key Data Structures

```python
@dataclass
class WorkoutSegment:
    type: str  # 'warmup', 'endurance', 'interval', 'cooldown'
    duration: int  # seconds
    power: float  # % FTP (or range for variable segments)
    cadence: int  # optional
    original_xml: ET.Element  # preserve for output

@dataclass
class Workout:
    filename: str
    name: str
    description: str
    total_duration: int  # seconds
    segments: List[WorkoutSegment]
    classification: str  # 'recovery', 'endurance', 'interval', 'mixed'
    difficulty_score: float
    week_number: int
    day_of_week: str  # if available
    is_weekend_ride: bool
    should_skip: bool
    modified: bool
```

### 7.4 Configuration Constants

```python
# Power zones (% FTP)
ZONE_1_MAX = 55
ZONE_2_MAX = 75
ZONE_3_MAX = 90
ZONE_4_MAX = 105
ZONE_5_MAX = 120

# Modification rules
TARGET_WEEKDAY_DURATION = 75 * 60  # seconds
MIN_WARMUP_DURATION = 5 * 60
MIN_COOLDOWN_DURATION = 5 * 60
SKIP_THRESHOLD_WORKOUTS = 5

# Classification keywords
RECOVERY_KEYWORDS = ['recovery', 'easy', 'spin', 'rest']
ENDURANCE_KEYWORDS = ['endurance', 'base', 'long', 'steady']
INTERVAL_KEYWORDS = ['interval', 'vo2', 'threshold', 'sweet spot', 'tempo', 'over-under']

# Minimum segment duration after cutting
MIN_SEGMENT_DURATION = 60  # seconds
```

---

## 8. Error Handling

### 8.1 Expected Errors

| Error Condition | Handling Strategy |
|----------------|-------------------|
| Invalid XML file | Log error, skip file, continue processing |
| Missing required XML elements | Log warning, attempt to infer, or skip workout |
| Cannot classify workout | Default to "mixed", apply standard rules |
| Insufficient segments to cut | Cut as much as possible, log warning |
| Output directory not writable | Fail with clear error message |
| Corrupted .zwo file | Skip with detailed error, continue with others |

### 8.2 Validation Checks

```python
# Pre-processing validation
- All input files are valid XML
- Input directory exists and is readable
- Output directory is writable

# Post-processing validation
- All output files are valid XML
- Total duration of modified workouts matches target (±30 sec tolerance)
- No interval segments were modified
- All segments have positive duration
- Sum of segment durations equals workout total duration
```

---

## 9. Future Enhancements (Out of Scope for V1)

- GUI interface for non-technical users
- Integration with Zwift API (if available) for direct upload
- Support for other workout file formats (.mrc, .erg)
- Machine learning classification of ambiguous workouts
- Workout library with pre-defined modification templates
- Calendar integration to auto-assign workouts to specific days
- Performance analytics (TSS, IF, normalized power recalculation)
- Multi-user profiles with different time constraints

---

## 10. Acceptance Criteria

The implementation is complete when:

1. ✅ Program successfully processes all Active Offseason .zwo files
2. ✅ Correctly identifies and skips active recovery rides in 5+ workout weeks
3. ✅ Weekend endurance rides remain completely unchanged
4. ✅ Weekday rides >75 min are reduced to exactly 75 min (±1 min tolerance)
5. ✅ All interval segments are preserved with original duration
6. ✅ Endurance segments are cut proportionally
7. ✅ Warmup/cooldown minimums are enforced
8. ✅ Output .zwo files are valid and Zwift-importable
9. ✅ Modification report is generated with clear summary
10. ✅ All unit and integration tests pass
11. ✅ Documentation includes usage examples and troubleshooting

---

## 11. Appendix

### 11.1 Sample .zwo File Structure

```xml
<workout_file>
    <author>Zwift</author>
    <name>Active Offseason - Week 1 Monday</name>
    <description>Endurance base building ride</description>
    <sportType>bike</sportType>
    <tags/>
    <workout>
        <Warmup Duration="600" PowerLow="0.50" PowerHigh="0.70"/>
        <SteadyState Duration="3600" Power="0.65"/>
        <SteadyState Duration="1800" Power="0.70"/>
        <SteadyState Duration="1800" Power="0.65"/>
        <Cooldown Duration="600" PowerLow="0.60" PowerHigh="0.50"/>
    </workout>
</workout_file>
```

### 11.2 Example Modification

**Before (120 minutes):**
```
Warmup: 10 min @ 50-70%
Endurance: 60 min @ 65%
Endurance: 30 min @ 70%
Endurance: 15 min @ 65%
Cooldown: 5 min @ 60-50%
```

**After (75 minutes):**
```
Warmup: 5 min @ 50-70% (cut 5 min, enforce minimum)
Endurance: 35.7 min @ 65% (cut proportionally: 60 * 0.595)
Endurance: 17.9 min @ 70% (cut proportionally: 30 * 0.595)
Endurance: 8.9 min @ 65% (cut proportionally: 15 * 0.595)
Cooldown: 5 min @ 60-50% (unchanged, already at minimum)

Total cut: 45 minutes from endurance sections
Cut ratio: 45 min / 105 min endurance = 0.429 (42.9% reduction)
```

---

## 12. Glossary

- **FTP**: Functional Threshold Power - maximum average power a cyclist can sustain for 1 hour
- **.zwo**: Zwift Workout file format (XML-based)
- **TSS**: Training Stress Score - measure of workout intensity and duration
- **Active Recovery**: Low-intensity workout for recovery between hard efforts
- **Endurance**: Aerobic base-building workout in Zone 2-3
- **Intervals**: High-intensity repeated efforts with recovery periods
- **Sweet Spot**: Training zone between tempo and threshold (~88-93% FTP)
- **VO2 Max**: Maximum rate of oxygen consumption during exercise