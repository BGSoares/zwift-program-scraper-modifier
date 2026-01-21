# Product Specification: Zwift Workout Scraper

## 1. Overview

### 1.1 Purpose
Extract workout data from whatsonzwift.com and generate valid Zwift workout files (.zwo format, XML) that can be imported directly into Zwift.

### 1.2 Target User
Amateur cyclist who needs to obtain Zwift Active Offseason training program workouts without accessing them through the Zwift application directly.

### 1.3 Success Criteria
- Successfully scrape all Active Offseason workouts from whatsonzwift.com
- Generate valid .zwo XML files that Zwift can import
- Preserve all workout structure: segments, durations, power zones, descriptions
- Output files organized by week and workout name
- Handle scraping errors gracefully

---

## 2. Technical Background

### 2.1 Target Website Structure

**Base URL:** `https://whatsonzwift.com/workouts/active-offseason`

**Page hierarchy:**
```
Landing page (12 weeks overview)
  ├── Week 1 page (4-7 workouts)
  │   ├── Day 1 - Workout detail page
  │   ├── Day 2 - Workout detail page
  │   └── ...
  ├── Week 2 page
  └── ...
```

### 2.2 Data Available on Pages

**Landing page:**
- Week cards with total duration, workout count, TSS
- Links to individual week pages

**Week page:**
- Individual workout cards with name, duration, TSS
- Visual workout profile (graph)
- Links to workout detail pages

**Workout detail page:**
- Complete workout name
- Duration
- Stress points (TSS)
- Segment-by-segment breakdown:
  - Segment type (warmup, steady, intervals, cooldown)
  - Duration (minutes)
  - Power target (% FTP)
- Zone distribution chart
- Text description of workout
- Visual workout profile

### 2.3 .zwo File Format

**.zwo files** are XML documents with this structure:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <author>WhatsOnZwift</author>
    <name>Active Offseason - Week 1 Day 1 - Endurance</name>
    <description>Endurance ride. Set a pace at Endurance and hold this pace for the prescribed workout time...</description>
    <sportType>bike</sportType>
    <tags>
        <tag name="ACTIVE OFFSEASON"/>
    </tags>
    <workout>
        <Warmup Duration="600" PowerLow="0.50" PowerHigh="0.75" pace="0"/>
        <SteadyState Duration="7200" Power="0.73" pace="0"/>
        <Cooldown Duration="600" PowerLow="0.60" PowerHigh="0.50" pace="0"/>
    </workout>
</workout_file>
```

**Key XML elements:**
- `<workout_file>` - root element
- `<author>` - author name (can be "WhatsOnZwift")
- `<name>` - workout title
- `<description>` - workout instructions
- `<sportType>` - always "bike"
- `<tags>` - optional categorization
- `<workout>` - container for all segments
- Segment types:
  - `<Warmup Duration="X" PowerLow="Y" PowerHigh="Z"/>` - gradual power increase
  - `<Cooldown Duration="X" PowerLow="Y" PowerHigh="Z"/>` - gradual power decrease
  - `<SteadyState Duration="X" Power="Y"/>` - constant power
  - `<IntervalsT Repeat="X" OnDuration="Y" OffDuration="Z" OnPower="A" OffPower="B"/>` - structured intervals
  - `<FreeRide Duration="X" FlatRoad="1"/>` - unstructured riding

**Duration:** Always in seconds
**Power:** Always as decimal (e.g., 0.73 = 73% FTP)

---

## 3. Functional Requirements

### 3.1 Input Handling

**FR-1.1: URL Input**
- Accept base URL: `https://whatsonzwift.com/workouts/active-offseason`
- Validate URL format and accessibility
- Handle HTTP errors (404, 403, timeout)

**FR-1.2: Configuration**
- Output directory path (required)
- Delay between requests (default: 1 second, to be respectful to server)
- User agent string (default: descriptive user agent)
- Timeout settings (default: 30 seconds per request)

### 3.2 Web Scraping

**FR-2.1: Landing Page Scraping**

Extract from main page:
```python
weeks_data = [
    {
        'week_number': 1,
        'week_url': 'https://whatsonzwift.com/workouts/active-offseason#week-1',
        'total_duration': '8h41m',
        'workout_count': 4,
        'tss': 465
    },
    # ... for all 12 weeks
]
```

**FR-2.2: Week Page Scraping**

For each week, extract workout data:
```python
workouts_in_week = [
    {
        'day_number': 1,
        'workout_name': 'Day 1 - Endurance',
        'workout_url': 'https://whatsonzwift.com/workouts/active-offseason#week-1',
        'duration': '1h50m',
        'tss': 96
    },
    # ... for all workouts in week
]
```

**FR-2.3: Workout Detail Page Scraping**

For each workout, extract complete structure:
```python
workout_detail = {
    'name': 'Active Offseason - Week 1 Day 1 - Endurance',
    'description': 'Endurance ride. Set a pace at Endurance...',
    'duration_minutes': 110,
    'tss': 96,
    'zone_distribution': {
        'Z1': 14,  # minutes
        'Z2': 116,
        'Z3': 0,
        'Z4': 0,
        'Z5': 0,
        'Z6': 0
    },
    'segments': [
        {
            'type': 'warmup',
            'duration_minutes': 10,
            'power_low': 50,  # % FTP
            'power_high': 75
        },
        {
            'type': 'steady',
            'duration_minutes': 120,
            'power': 73
        },
        {
            'type': 'cooldown',
            'duration_minutes': 10,
            'power_low': 60,
            'power_high': 50
        }
    ]
}
```

### 3.3 Segment Type Inference

**FR-3.1: Identifying Segment Types**

Based on whatsonzwift.com visual representation and text:

**Warmup:**
- First segment(s) of workout
- Power range (e.g., "50 to 75% FTP")
- Typically 5-15 minutes
- Gray color in visual (transitions to blue)

**Cooldown:**
- Last segment(s) of workout
- Power range (e.g., "60 to 50% FTP")
- Typically 5-15 minutes
- Gray color in visual (transitions from blue)

**SteadyState:**
- Single power target (e.g., "73% FTP")
- Duration varies widely
- Blue or green color in visual
- No "x" repetition indicator

**IntervalsT:**
- Text contains pattern like "10 x 1-minute"
- Alternating power levels
- Green/blue alternating colors
- Has repetition count

**FreeRide:**
- Text says "Rest" or "Recovery"
- No power target specified
- Duration only

**FR-3.2: Parsing Segment Text**

Examples of text patterns to parse:

```
"10min from 50 to 75% FTP" 
  → Warmup, 600 seconds, 0.50 to 0.75

"2hr @ 73% FTP"
  → SteadyState, 7200 seconds, 0.73

"1hr 30min @ 95rpm, 73% FTP"
  → SteadyState, 5400 seconds, 0.73 (note cadence)

"2min @ 40% FTP" (repeated in list)
  → SteadyState, 120 seconds, 0.40 (multiple instances)

"15min @ 73% FTP"
  → SteadyState, 900 seconds, 0.73

"1min @ 88% FTP" (alternating pattern visible)
  → Part of intervals (needs context from surrounding segments)

"10min from 55 to 60% FTP"
  → Cooldown, 600 seconds, 0.55 to 0.60
```

**FR-3.3: Interval Detection**

For intervals, detect patterns:
```
Sequence like:
  - 2min @ 73% FTP
  - 1min @ 88% FTP
  - 2min @ 73% FTP
  - 1min @ 88% FTP
  (repeated pattern)

Convert to:
  <IntervalsT 
    Repeat="X" 
    OnDuration="60" 
    OffDuration="120" 
    OnPower="0.88" 
    OffPower="0.73"/>
```

Detect by:
1. Looking for alternating power levels
2. Identifying repetition count from visual or text
3. Calculating on/off durations and powers

**FR-3.4: Edge Cases**

Handle special cases:
- Ramp segments (gradual power increase/decrease within segment)
- Variable cadence targets (capture if available)
- Multiple warmup/cooldown phases
- Mixed intervals (different on/off times in same workout)
- Freeride sections

### 3.4 XML Generation

**FR-4.1: XML Structure Creation**

For each workout, generate valid .zwo XML:

```python
def generate_zwo(workout_detail):
    """
    Generate .zwo XML from workout detail dictionary
    """
    # Create XML structure
    root = ET.Element('workout_file')
    
    # Add metadata
    author = ET.SubElement(root, 'author')
    author.text = 'WhatsOnZwift'
    
    name = ET.SubElement(root, 'name')
    name.text = workout_detail['name']
    
    description = ET.SubElement(root, 'description')
    description.text = workout_detail['description']
    
    sport_type = ET.SubElement(root, 'sportType')
    sport_type.text = 'bike'
    
    # Add tags
    tags = ET.SubElement(root, 'tags')
    tag = ET.SubElement(tags, 'tag')
    tag.set('name', 'ACTIVE OFFSEASON')
    
    # Add workout segments
    workout = ET.SubElement(root, 'workout')
    
    for segment in workout_detail['segments']:
        add_segment_to_workout(workout, segment)
    
    return root
```

**FR-4.2: Segment XML Mapping**

Map segment types to XML elements:

| Segment Type | XML Element | Attributes |
|-------------|-------------|------------|
| Warmup | `<Warmup>` | Duration (s), PowerLow (decimal), PowerHigh (decimal) |
| Cooldown | `<Cooldown>` | Duration (s), PowerLow (decimal), PowerHigh (decimal) |
| SteadyState | `<SteadyState>` | Duration (s), Power (decimal) |
| Intervals | `<IntervalsT>` | Repeat (count), OnDuration (s), OffDuration (s), OnPower (decimal), OffPower (decimal) |
| FreeRide | `<FreeRide>` | Duration (s), FlatRoad="1" |

**FR-4.3: Unit Conversion**

Convert scraped data to .zwo format:
- **Duration**: minutes → seconds (multiply by 60)
- **Power**: percentage → decimal (divide by 100)
- **Cadence**: RPM → integer (if available)

**FR-4.4: XML Formatting**

Output requirements:
- Valid XML 1.0 with UTF-8 encoding
- Proper indentation (2 or 4 spaces)
- Declaration: `<?xml version="1.0" encoding="UTF-8"?>`
- No trailing whitespace
- Unix line endings (LF)

### 3.5 File Output

**FR-5.1: File Naming Convention**

Generate filenames from workout data:
```
Format: "Week{N}_Day{D}_{WorkoutType}.zwo"

Examples:
  - Week1_Day1_Endurance.zwo
  - Week1_Day3_Cadence_Tempo.zwo
  - Week2_Day2_Rest.zwo
  - Week5_Day5_Endurance.zwo
```

Sanitize workout names:
- Remove special characters: `/`, `\`, `?`, `*`, `:`
- Replace spaces with underscores
- Limit length to 50 characters
- Convert to title case

**FR-5.2: Directory Structure**

Organize output files:
```
output_directory/
├── Week1_Day1_Endurance.zwo
├── Week1_Day2_Rest.zwo
├── Week1_Day3_Cadence_Tempo.zwo
├── Week1_Day5_Endurance.zwo
├── Week1_Day6_Endurance_With_Cadence.zwo
├── Week2_Day1_Endurance.zwo
├── ...
└── Week12_Day6_Endurance.zwo
```

Alternative (optional): organize by week subdirectories
```
output_directory/
├── week_01/
│   ├── Day1_Endurance.zwo
│   ├── Day2_Rest.zwo
│   └── ...
├── week_02/
│   └── ...
└── week_12/
    └── ...
```

**FR-5.3: File Writing**

- Write each .zwo file with proper encoding (UTF-8)
- Set file permissions (readable by user)
- Validate XML before writing
- Skip if file already exists (optional overwrite flag)

### 3.6 Progress and Logging

**FR-6.1: Progress Indicators**

Show scraping progress:
```
🔍 Scraping Active Offseason workouts...
📄 Found 12 weeks

Week 1/12: Scraping 4 workouts...
  ✓ Day 1 - Endurance (110 min)
  ✓ Day 2 - Rest
  ✓ Day 3 - Cadence & Tempo (70 min)
  ✓ Day 5 - Endurance (120 min)

Week 2/12: Scraping 5 workouts...
  ✓ Day 1 - Endurance (120 min)
  ...

✅ Complete! Generated 48 workout files
   📁 Output: ./original_workouts/
   ⏱️  Total time: 58 seconds
```

**FR-6.2: Error Handling**

Log and handle errors:
- Network errors (retry with exponential backoff)
- Parsing errors (log and skip workout, continue with others)
- File write errors (report and exit gracefully)
- Missing data (log warning, use defaults where possible)

**FR-6.3: Detailed Logging**

Optional verbose logging:
```
[INFO] Fetching: https://whatsonzwift.com/workouts/active-offseason
[DEBUG] Parsing week cards...
[DEBUG] Found Week 1: 4 workouts, 8h41m total
[INFO] Scraping Week 1 Day 1...
[DEBUG] Extracted 3 segments: warmup, steady, cooldown
[DEBUG] Generated XML: Week1_Day1_Endurance.zwo
[INFO] Wrote: ./original_workouts/Week1_Day1_Endurance.zwo
```

### 3.7 Validation

**FR-7.1: Pre-write Validation**

Before writing each .zwo file, validate:
- XML is well-formed
- All required elements present
- Duration values are positive integers
- Power values are between 0.0 and 3.0 (0-300% FTP)
- Segment order makes sense (warmup first, cooldown last)

**FR-7.2: Post-scrape Validation**

After scraping all workouts:
- Verify expected number of files generated (typically 48-60 workouts)
- Check total duration matches expected program length
- Identify any missing weeks or workouts
- Report any workouts that failed to scrape

---

## 4. Non-Functional Requirements

### 4.1 Performance
- Scrape entire 12-week program in <2 minutes
- Respect server with 1-second delay between requests (configurable)
- Memory efficient (stream process, don't load all pages at once)

### 4.2 Reliability
- Retry failed requests (3 attempts with exponential backoff)
- Continue scraping even if individual workouts fail
- Generate partial output if complete scraping fails

### 4.3 Maintainability
- Modular code (separate scraping, parsing, XML generation)
- CSS selector configuration (easy to update if website changes)
- Clear error messages pointing to specific parsing issues

### 4.4 Ethical Scraping
- Identify bot with user agent (e.g., "ZwiftWorkoutScraperBot/1.0")
- Respect robots.txt if present
- Rate limit requests (default 1 second between requests)
- Cache results to avoid re-scraping

---

## 5. User Interface Specification

### 5.1 Command-Line Interface

```bash
python zwift_scraper.py [url] [options]

Required:
  url                    URL to Active Offseason page
                         (e.g., https://whatsonzwift.com/workouts/active-offseason)

Options:
  --output-dir DIR       Output directory for .zwo files (default: ./workouts)
  --delay SECONDS        Delay between requests in seconds (default: 1)
  --timeout SECONDS      Request timeout in seconds (default: 30)
  --organize-by-week     Create week subdirectories
  --overwrite            Overwrite existing files
  --verbose              Detailed logging
  --validate-only        Validate generated XML without writing files
  --dry-run              Show what would be scraped without actually scraping
```

### 5.2 Example Usage

```bash
# Basic usage
python zwift_scraper.py https://whatsonzwift.com/workouts/active-offseason \
    --output-dir ./original_workouts

# With week organization and verbose logging
python zwift_scraper.py https://whatsonzwift.com/workouts/active-offseason \
    --output-dir ./original_workouts \
    --organize-by-week \
    --verbose

# Dry run to preview
python zwift_scraper.py https://whatsonzwift.com/workouts/active-offseason \
    --dry-run

# Faster scraping (use responsibly)
python zwift_scraper.py https://whatsonzwift.com/workouts/active-offseason \
    --output-dir ./original_workouts \
    --delay 0.5
```

---

## 6. Technical Implementation

### 6.1 Recommended Libraries

```python
import requests              # HTTP requests
from bs4 import BeautifulSoup  # HTML parsing
import xml.etree.ElementTree as ET  # XML generation
from pathlib import Path     # File operations
import re                    # Regular expressions for parsing
import time                  # Rate limiting
import logging              # Logging
import argparse             # CLI
from typing import List, Dict
from dataclasses import dataclass
```

### 6.2 Suggested Code Structure

```
zwift_scraper/
├── __init__.py
├── main.py              # CLI entry point
├── scraper.py           # Web scraping logic
├── parser.py            # HTML/text parsing
├── workout.py           # Workout data structures
├── xml_generator.py     # .zwo XML generation
├── validator.py         # XML validation
├── config.py            # Configuration constants
└── utils.py             # Helper functions

tests/
├── test_scraper.py
├── test_parser.py
├── test_xml_generator.py
├── test_validator.py
└── fixtures/            # Sample HTML pages
```

### 6.3 Key Data Structures

```python
@dataclass
class WorkoutSegment:
    """Single segment within a workout"""
    type: str  # 'warmup', 'cooldown', 'steady', 'intervals', 'freeride'
    duration_seconds: int
    power: float = None  # For steady state
    power_low: float = None  # For warmup/cooldown
    power_high: float = None  # For warmup/cooldown
    repeat: int = None  # For intervals
    on_duration: int = None  # For intervals
    off_duration: int = None  # For intervals
    on_power: float = None  # For intervals
    off_power: float = None  # For intervals
    cadence: int = None  # Optional

@dataclass
class Workout:
    """Complete workout definition"""
    week_number: int
    day_number: int
    name: str
    description: str
    duration_minutes: int
    tss: int
    zone_distribution: Dict[str, int]
    segments: List[WorkoutSegment]
    url: str

@dataclass
class TrainingProgram:
    """Collection of all workouts"""
    name: str  # "Active Offseason"
    weeks: int  # 12
    workouts: List[Workout]
```

### 6.4 CSS Selectors (may need adjustment)

Based on whatsonzwift.com structure (will need to be verified/updated):

```python
SELECTORS = {
    'week_cards': 'div.week-card',  # Placeholder
    'week_link': 'a.week-link',
    'workout_cards': 'div.workout-card',
    'workout_link': 'a.workout-link',
    'workout_name': 'h1.workout-title',
    'workout_description': 'div.workout-description',
    'workout_duration': 'span.duration',
    'workout_tss': 'span.tss',
    'segment_list': 'div.segment-list li',
    'segment_text': 'span.segment-text',
    'zone_distribution': 'div.zone-distribution'
}
```

**Note:** These selectors are placeholders and must be determined by inspecting the actual HTML structure of whatsonzwift.com.

### 6.5 Parsing Strategy

**Approach 1: Structured HTML Parsing**
- If whatsonzwift exposes segments in structured HTML elements
- Use BeautifulSoup to extract each segment's attributes
- Most reliable if structure is consistent

**Approach 2: Text Pattern Matching**
- Parse segment text descriptions with regex
- More fragile but works if HTML structure varies
- Fallback if structured data not available

**Approach 3: Visual Profile Parsing**
- Extract data from workout graph/visual representation
- Most complex, only if other methods fail
- Would require analyzing SVG or canvas elements

**Recommended: Combination approach**
1. Try structured HTML parsing first
2. Fall back to text pattern matching if needed
3. Validate extracted data against visual profile

### 6.6 Text Parsing Patterns

```python
PATTERNS = {
    'duration_with_power': r'(\d+)min (?:from )?(\d+)(?: to (\d+))?% FTP',
    'hour_duration': r'(\d+)hr(?: (\d+)min)? @ (\d+)% FTP',
    'interval_pattern': r'(\d+) ?x (\d+)[- ]min(?:ute)?',
    'power_range': r'(\d+) to (\d+)% FTP',
    'single_power': r'@ (\d+)% FTP',
    'cadence': r'(\d+)rpm',
}
```

---

## 7. Error Handling

### 7.1 Network Errors

| Error Type | Handling Strategy |
|-----------|------------------|
| Connection timeout | Retry 3 times with exponential backoff (1s, 2s, 4s) |
| 404 Not Found | Log error, skip workout, continue |
| 403 Forbidden | Log error, suggest checking robots.txt, exit |
| 500 Server Error | Wait 5s, retry once, then skip |
| DNS failure | Exit with clear error message |

### 7.2 Parsing Errors

| Error Type | Handling Strategy |
|-----------|------------------|
| Missing segment data | Log warning, use default values |
| Invalid power value | Log error, skip segment |
| Malformed duration | Attempt multiple parse patterns |
| Ambiguous segment type | Use heuristics, log assumption |
| Missing workout name | Generate default name from week/day |

### 7.3 Validation Errors

| Error Type | Handling Strategy |
|-----------|------------------|
| Invalid XML structure | Don't write file, log error |
| Duration ≤ 0 | Log error, skip workout |
| Power < 0 or > 300% | Log error, clamp to valid range |
| Empty segments list | Log error, skip workout |
| Missing required fields | Log error, skip workout |

---

## 8. Testing Requirements

### 8.1 Unit Tests

**Test Coverage:**
- HTML parsing functions
- Text pattern matching
- Segment type inference
- XML generation for each segment type
- Unit conversions (minutes→seconds, %→decimal)
- Filename sanitization
- Data validation

**Test Data:**
Create fixtures for:
- Sample HTML from whatsonzwift.com pages
- Various segment text patterns
- Edge case workouts (very long, very short, complex intervals)

### 8.2 Integration Tests

- Scrape a single week and verify output
- Generate .zwo for each segment type
- Validate all generated XML files
- Test rate limiting delays
- Test error recovery (with mocked failures)

### 8.3 End-to-End Tests

**Manual testing checklist:**
- [ ] Scrape complete Active Offseason program
- [ ] Import generated .zwo files into Zwift
- [ ] Verify workouts display correctly in Zwift
- [ ] Spot-check 5-10 workouts for accuracy
- [ ] Test on different network conditions
- [ ] Verify file naming and organization

### 8.4 Validation Tests

**Generated .zwo file validation:**
- [ ] All files are valid XML
- [ ] All files have required elements
- [ ] Durations sum correctly
- [ ] Power zones are reasonable
- [ ] No duplicate filenames
- [ ] File encoding is UTF-8

---

## 9. Configuration

### 9.1 Constants

```python
# URL structure
BASE_URL = 'https://whatsonzwift.com'
PROGRAM_PATH = '/workouts/active-offseason'

# Scraping behavior
DEFAULT_DELAY = 1.0  # seconds
DEFAULT_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
RETRY_BACKOFF = [1, 2, 4]  # seconds

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
```

### 9.2 User Agent

```python
USER_AGENT = 'ZwiftWorkoutScraperBot/1.0 (Training Program Parser; +https://github.com/yourrepo)'
```

---

## 10. Acceptance Criteria

The implementation is complete when:

1. ✅ Program successfully scrapes all Active Offseason workouts from whatsonzwift.com
2. ✅ Generated .zwo files are valid XML
3. ✅ Generated .zwo files import successfully into Zwift
4. ✅ Workouts display correctly in Zwift with proper structure
5. ✅ All segment types are correctly identified and generated
6. ✅ Power zones and durations match source data (within 5% tolerance)
7. ✅ Rate limiting is implemented and respectful
8. ✅ Error handling recovers gracefully from network/parsing issues
9. ✅ Progress indicators show clear scraping status
10. ✅ All unit and integration tests pass
11. ✅ Documentation includes usage examples

---

## 11. Future Enhancements (Out of Scope for V1)

- Support for other training programs on whatsonzwift.com
- GUI interface for non-technical users
- Caching system to avoid re-scraping
- Diff tool to compare scraped vs. existing workouts
- Automatic detection of program updates
- Export to other formats (.mrc, .erg)
- FTP calculator integration
- Training plan comparison tool
- Web service API (scrape on demand)

---

## 12. Known Limitations

- **Website dependency**: Breaks if whatsonzwift.com changes structure significantly
- **Incomplete data**: Some workout details may not be available (e.g., exact cadence targets)
- **Interval detection**: Complex interval patterns may be misidentified
- **Manual verification needed**: Generated workouts should be spot-checked
- **No authentication**: Cannot access premium/restricted content
- **Static data**: No real-time updates from Zwift's own platform

---

## 13. Security & Ethics

### 13.1 Responsible Scraping
- Honor robots.txt
- Rate limit requests
- Identify bot with descriptive user agent
- Don't overload server
- Cache results when possible

### 13.2 Legal Considerations
- Workout data structures (power/duration) are factual and not copyrightable
- Workout descriptions may be copyrighted (keep only essential text)
- Visual designs should not be copied
- Generated .zwo files are for personal use only
- Do not redistribute whatsonzwift.com's proprietary content

### 13.3 Attribution
- Include attribution in generated files: `<author>WhatsOnZwift</author>`
- Consider adding source URL in description
- Do not claim original authorship of workout designs

---

## 14. Appendix

### 14.1 Sample Workout Data

**Example: Week 1 Day 1 - Endurance (1h50m)**

Scraped segments:
```
10min from 70 to 75% FTP
1hr 30min @ 95rpm, 73% FTP
10min from 75 to 70% FTP
```

Generated .zwo:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <author>WhatsOnZwift</author>
    <name>Active Offseason - Week 1 Day 1 - Endurance</name>
    <description>Endurance ride. Set a pace at Endurance and hold this pace for the prescribed workout time. Focus on riding smooth and staying relaxed. Vary your cadence.</description>
    <sportType>bike</sportType>
    <tags>
        <tag name="ACTIVE OFFSEASON"/>
    </tags>
    <workout>
        <Warmup Duration="600" PowerLow="0.70" PowerHigh="0.75" pace="0"/>
        <SteadyState Duration="5400" Power="0.73" Cadence="95" pace="0"/>
        <Cooldown Duration="600" PowerLow="0.75" PowerHigh="0.70" pace="0"/>
    </workout>
</workout_file>
```

**Example: Week 1 Day 3 - Cadence & Tempo (1h40m)**

Scraped segments (complex intervals):
```
10min from 50 to 55% FTP
2min @ 40% FTP (repeated 10 times with 1min @ 88% FTP)
15min @ 73% FTP
10 x 1-minute HIGH CADENCE FAST PEDALS targeting 135+ RPM, with 2-minute rests
15min @ TEMPO
2min @ 73% FTP (repeated with 1min intervals)
```

This would require careful parsing to detect interval patterns.

### 14.2 HTML Structure Examples

**Note:** These are hypothetical examples. Actual selectors must be determined by inspecting whatsonzwift.com.

```html
<!-- Week card example -->
<div class="week-card">
    <h3>Week 1</h3>
    <div class="week-stats">
        <span class="duration">8h41m</span>
        <span class="workouts">4 wrkts</span>
    </div>
    <a href="#week-1">View workouts</a>
</div>

<!-- Workout detail example -->
<div class="workout-detail">
    <h1>Day 1 - Endurance</h1>
    <div class="workout-overview">
        <span class="duration">1h50m</span>
        <span class="tss">96</span>
    </div>
    <ul class="segment-list">
        <li>
            <span class="segment-duration">10min</span>
            <span class="segment-power">from 70 to 75% FTP</span>
        </li>
        <li>
            <span class="segment-duration">1hr 30min</span>
            <span class="segment-power">@ 95rpm, 73% FTP</span>
        </li>
    </ul>
</div>
```

### 14.3 Testing with Mock Data

For development without network access, create mock HTML files:

```
tests/fixtures/
├── landing_page.html
├── week1_page.html
├── week1_day1_detail.html
├── week1_day3_detail.html (complex intervals)
└── week2_day1_detail.html
```

Run tests against local files:
```bash
python zwift_scraper.py file://tests/fixtures/landing_page.html \
    --output-dir ./test_output
```

---

## 15. Glossary

- **FTP**: Functional Threshold Power - maximum average power a cyclist can sustain for 1 hour
- **TSS**: Training Stress Score - measure of workout intensity and duration
- **Zone**: Power zone (Z1-Z6) representing different training intensities
- **Cadence**: Pedaling rate in revolutions per minute (RPM)
- **.zwo**: Zwift Workout file format
- **Tempo**: Training at Zone 3 (75-90% FTP)
- **Sweet Spot**: Training at 88-93% FTP
- **VO2 Max**: Training at Zone 5 (105-120% FTP)
- **Active Recovery**: Very easy riding at Zone 1 (<55% FTP)

---

**End of Product Specification: Zwift Workout Scraper**