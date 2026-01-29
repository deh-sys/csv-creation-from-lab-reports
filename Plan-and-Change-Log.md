# Plan and Change Log

## Project: Lab Report Parser

### Purpose
Extract structured lab test data from medical PDF reports (RCMC, Kaiser, Monument Health) into a unified CSV format for analysis and tracking.

---

## Version History

### v1.6.0 - 2026-01-29 (Component Name Normalization)
**Features:**
- **Standardized Component Names:** Merged variations into standard medical names:
  - `WBC`, `WBC, AUTO` -> **White Blood Cell Count (WBC)**
  - `CREA`, `CREATININE` -> **Creatinine**
  - `ALB`, `ALBUMIN` -> **Albumin**
  - `A1C`, `d%A1c` -> **Hemoglobin A1c (HbA1c)**
  - And many more...
- Ensures consistent analysis across different lab providers.

---

### v1.5.0 - 2026-01-29 (Parallel Processing)
**Performance:**
- **Multi-Core Support:** Now processes multiple PDFs simultaneously using all available CPU cores (`ProcessPoolExecutor`).
- **Safety:** Refactored extraction logic into stateless workers to prevent memory/resource conflicts.
- **Optimization:** Configured OCR to run single-threaded per file to maximize throughput without overloading the system.

---

### v1.4.0 - 2026-01-29 (Panel Name Normalization)
**Features:**
- **Standardized Panel Names:** Merged different facility names into a single standard using "Full Name (Abbreviation)" format:
  - `Comprehensive Metabolic Panel (CMP)`
  - `Complete Blood Count (CBC)`
  - `Lipid Panel`
  - `Thyroid Stimulating Hormone (TSH)`
  - `Urinalysis (UA)`
  - `Hemoglobin A1c (HbA1c)`
- Improves sorting and pivot table analysis in Excel.

---

### v1.3.0 - 2026-01-29 (Excel Output)
**Features:**
- Switched primary output from CSV to Excel (`.xlsx`) to prevent data corruption (e.g., "7-35" becoming "Jul-35").
- **Smart Formatting:**
  - Frozen top row (headers).
  - Auto-filters enabled by default.
  - Columns auto-sized to fit content.
  - `ref_range` explicitly set to Text format.
  - **Conditional Formatting:** Results with flags (H, L, A) are highlighted in red.

---

### v1.2.1 - 2026-01-29 (Regex Refinements)
**Bug Fixes:**
- **RCMC:** Fixed reference ranges spanning multiple lines (e.g. capturing "Test performed at..." in Ratio).
- **RCMC:** Added support for rows with no units (e.g., Lipid Panel Ratio).
- **RCMC:** Fixed "HH" flag getting merged into reference range (e.g., "HH 1.12-1.32").
- **Monument:** Fixed truncated reference ranges (e.g., "11.5" instead of "11.5-15.5") by enforcing Method matching.

---

### v1.2.0 - 2026-01-29 (Interactive Output)
**Features:**
- Added interactive prompt for output folder location
- Defaults to Desktop (`~/Desktop`) if no folder selected
- Automatically asks to create folder if it doesn't exist
- Logs remain in the script's `logs/` directory

---

### v1.1.2 - 2026-01-29 (Panel Name Extraction Fix)
**Bug Fixes:**
- Fixed panel name extraction to work across all pages (was only extracting from individual pages)
- Extract panel name from full document first, then apply to all results
- Added filename fallback when panel header not found in document (e.g., `DATE--PANEL_NAME--FACILITY.pdf`)
- Improved Kaiser panel pattern to handle various header formats

**Result:** All Kaiser and Monument results now have panel names populated.

---

### v1.1.1 - 2026-01-29 (Monument Reference Range Fix)
**Bug Fixes:**
- Fixed Monument multi-line reference range parsing (e.g., "0.60 -" on one line, "1.10" on next)
- Handle OCR artifacts like "=" between method and date
- Added multiple pattern matching approach: complete ref range, partial ref range, and fallback

**Known Limitations:**
- Some OCR corruption cannot be fixed programmatically (e.g., "3-11" read as "321")

---

### v1.1.0 - 2026-01-29 (Panel Name Support)
**Features:**
- Added `panel_name` column to distinguish test panels from individual components
- Renamed `test_name` column to `component` for clarity
- Panel names extracted from PDF headers (e.g., "CMP (Complete Metabolic Panel)", "CBC Auto Diff")

**CSV Schema Change:**
- New column order: source, facility, panel_name, component, test_date, value, ref_range, unit, flag, page_marker

---

### v1.0.0 - 2026-01-28 (Initial Release)
**Features:**
- Interactive single-command script (`python3 lab_parser.py`)
- Modular facility configuration system
- Support for 3 medical facilities:
  - RCMC: Native text PDFs
  - Kaiser: Image PDFs with OCR
  - Monument: Image PDFs with OCR
- Automatic OCR via `ocrmypdf` for image-based PDFs
- Dual logging (minimal console, verbose file)
- Progress bar with tqdm
- Failed file tracking in `missed_files.txt`

**Files Created:**
- `lab_parser.py` - Main script
- `facility_configs/__init__.py` - Config package
- `facility_configs/base_config.py` - Base configuration class
- `facility_configs/rcb_config.py` - RCMC patterns
- `facility_configs/kpa_config.py` - Kaiser patterns
- `facility_configs/mhb_config.py` - Monument patterns
- `Instructions.md` - Usage documentation
- `Plan-and-Change-Log.md` - This file

**Test Results (135 test files):**
- Files processed: 48
- Lab values extracted: 285
- RCMC results: 187 (native text extraction)
- Kaiser results: 66 (OCR-based)
- Monument results: 32 (OCR-based)
- Missed files: 87 (mostly imaging reports without numeric lab values)

---

## Technical Specification

### Architecture Overview

The project uses a **modular plugin architecture** that separates the core parsing engine from facility-specific pattern definitions. This makes it easy to add support for new medical facilities without modifying the main script.

```
csv-creation-from-lab-reports/
├── lab_parser.py                    # Core engine (facility-agnostic)
├── facility_configs/                # Plugin directory
│   ├── __init__.py                  # Registry & auto-discovery
│   ├── base_config.py               # Abstract base class + LabResult dataclass
│   ├── rcb_config.py                # RCMC patterns (native text)
│   ├── kpa_config.py                # Kaiser patterns (OCR)
│   └── mhb_config.py                # Monument patterns (OCR)
├── output/
│   └── lab_results.csv              # Combined output
└── logs/
    ├── _debug.log                   # Verbose processing log
    └── missed_files.txt             # Failed files for review
```

### Core Components

#### 1. `lab_parser.py` - The Engine (Facility-Agnostic)

The main script handles:
- User input (folder path)
- PDF discovery and facility detection
- OCR preprocessing (when `config.requires_ocr = True`)
- Text extraction via pdfplumber
- Delegating parsing to the appropriate facility config
- CSV output and logging

**Key principle:** The engine knows nothing about specific PDF formats. It simply:
1. Finds the right config using `get_config_for_filename()`
2. Calls `config.extract_results(text, filename)`
3. Collects the `LabResult` objects returned

#### 2. `base_config.py` - The Contract

Defines what every facility config must provide:

```python
@dataclass
class LabResult:
    """Standard output format for all facilities."""
    source: str          # Source filename
    facility: str        # Facility name
    panel_name: str      # Test panel (CMP, CBC, etc.)
    component: str       # Individual test (Glucose, WBC, etc.)
    test_date: str       # Collection date
    value: str           # Result value
    ref_range: str       # Reference range
    unit: str            # Measurement unit
    flag: str            # Abnormal flag (H/L/A)
    page_marker: str     # Page identifier

class FacilityConfig(ABC):
    """Abstract base - every facility config must implement this."""

    # Required attributes
    name: str                      # e.g., "RCMC", "Kaiser"
    filename_patterns: list[str]   # Regex to match filenames
    requires_ocr: bool             # Does this facility need OCR?

    # Optional patterns (can be overridden)
    date_pattern: str
    page_marker_pattern: str

    # Required method
    @abstractmethod
    def extract_results(self, text: str, source_filename: str) -> Generator[LabResult, None, None]:
        """Parse text and yield LabResult objects."""
        pass

    # Provided helper methods
    def matches_filename(self, filename: str) -> bool
    def extract_date(self, text: str) -> str
    def extract_page_marker(self, text: str) -> str
    def normalize_test_name(self, name: str) -> str
```

#### 3. `__init__.py` - The Registry

Auto-discovers and registers all facility configs:

```python
from .rcb_config import RCBConfig
from .kpa_config import KPAConfig
from .mhb_config import MHBConfig

# Add new configs here
FACILITY_CONFIGS = [
    RCBConfig(),
    KPAConfig(),
    MHBConfig(),
    # NewFacilityConfig(),  # <-- Just add new facilities here
]

def get_config_for_filename(filename: str) -> FacilityConfig | None:
    """Return the appropriate config based on filename."""
    for config in FACILITY_CONFIGS:
        if config.matches_filename(filename):
            return config
    return None
```

### Processing Flow

```
lab_parser.py
├── Startup Phase
│   ├── Check dependencies (pdfplumber, tqdm)
│   ├── Check ocrmypdf availability
│   └── Prompt for input folder (drag-and-drop)
├── Validation Phase
│   ├── Scan for PDFs recursively
│   ├── Match to facility configs by filename
│   └── Report file counts by facility
├── Processing Phase (with tqdm progress bar)
│   ├── For each PDF:
│   │   ├── Detect facility from filename
│   │   ├── Run OCR if needed (Kaiser, Monument)
│   │   ├── Extract text with pdfplumber
│   │   └── Apply regex patterns to extract results
│   └── Skip and log failures
└── Summary Phase
    ├── Write CSV output
    ├── Write missed files log
    └── Print summary statistics
```

---

## How to Add a New Facility

Adding support for a new medical facility requires **only 2 steps**:

### Step 1: Create the Config File

Create `facility_configs/new_facility_config.py`:

```python
"""
Configuration for NewFacility lab reports.
Document the PDF format here for future reference.
"""

import re
from typing import Generator
from .base_config import FacilityConfig, LabResult


class NewFacilityConfig(FacilityConfig):
    """Configuration for NewFacility lab reports."""

    # REQUIRED: Facility identification
    name = "NewFacility"
    filename_patterns = [
        r'--NewFacility\.pdf$',
        r'--NF\.pdf$',
    ]

    # REQUIRED: Does this facility need OCR?
    requires_ocr = True  # Set to False for native text PDFs

    # OPTIONAL: Patterns for common extractions
    date_pattern = r'Collection Date:\s*(?P<date>\d{2}/\d{2}/\d{4})'
    page_marker_pattern = r'^NF\s+\d+\s*$'

    # FACILITY-SPECIFIC: Your regex patterns
    row_pattern = (
        r'^(?P<component>[A-Z][A-Za-z\s]+)\s+'
        r'(?P<value>[\d.]+)\s+'
        r'(?P<ref_range>[\d.\-]+)\s+'
        r'(?P<date>\d{2}/\d{2}/\d{4})'
    )

    # REQUIRED: Implement the extraction logic
    def extract_results(self, text: str, source_filename: str) -> Generator[LabResult, None, None]:
        """Extract lab results from NewFacility page text."""

        # Get common metadata
        test_date = self.extract_date(text)
        page_marker = self.extract_page_marker(text)

        # Parse each line
        for line in text.split('\n'):
            line = line.strip()
            match = re.match(self.row_pattern, line)

            if match:
                yield LabResult(
                    source=source_filename,
                    facility=self.name,
                    panel_name="",  # Extract if available
                    component=match.group('component'),
                    test_date=match.group('date') or test_date,
                    value=match.group('value'),
                    ref_range=match.group('ref_range'),
                    unit="",  # Extract if available
                    flag="",  # Extract if available
                    page_marker=page_marker,
                )
```

### Step 2: Register in `__init__.py`

Add two lines to `facility_configs/__init__.py`:

```python
from .new_facility_config import NewFacilityConfig  # Add import

FACILITY_CONFIGS = [
    RCBConfig(),
    KPAConfig(),
    MHBConfig(),
    NewFacilityConfig(),  # Add to registry
]
```

**That's it.** The main script will automatically:
- Detect files matching your `filename_patterns`
- Run OCR if `requires_ocr = True`
- Call your `extract_results()` method
- Include results in the unified CSV output

### Tips for New Facility Configs

1. **Start by examining the OCR output**
   ```bash
   ocrmypdf --force-ocr input.pdf /tmp/output.pdf
   python3 -c "import pdfplumber; print(pdfplumber.open('/tmp/output.pdf').pages[0].extract_text())"
   ```

2. **Document the expected format** in the module docstring (see existing configs)

3. **Use multiple patterns** for different row formats (with/without ref range, flags, etc.)

4. **Implement fallbacks** for multi-line data (see `kpa_config.py` and `mhb_config.py`)

5. **Test incrementally** - run the parser and check `missed_files.txt` and CSV output

### Regex Patterns

**RCMC Row Pattern:**
```regex
^F\s+(?P<test_name>[A-Z0-9+\-#%\s]+?)\s+(?P<value>[\d.<>]+)\s*(?P<flag>[HL])?\s+(?P<ref_range>[\d.<>\-\s]+)\s*\((?P<unit>[^)]+)\)
```
Example match: `F CA 10.5 8.7-10.6 (mg/dL)`

**Kaiser Row Pattern:**
```regex
^(?P<test_name>[A-Z][A-Z0-9\s,\'\-]+?)\s+(?P<value>[\d.]+)\s+(?P<ref_range>[\d.\-]+)\s+(?P<date>\d{2}/\d{2}/\d{4})\s+KAISER
```
Example match: `CHOLESTEROL 195 0-199 08/06/2021 KAISER`

**Monument Row Pattern:**
```regex
^(?P<test_name>[A-Za-z][A-Za-z0-9\s,\-#%\']+?)\s+(?P<value>[\d.]+)\s+(?P<ref_range>[\d.\-]+)\s+(?P<method>[A-Z][A-Z\s&]+?)\s+(?P<date>\d{2}/\d{2}/\d{4})\s+MONUMENT
```
Example match: `Phosphorus 28 2.5-4.9 SPECTROPHOTOMETRY 08/18/2025 MONUMENT`

---

## Tips for Future AI Coders: Pattern Extraction Lessons Learned

This section documents the challenges encountered and solutions developed for extracting structured data from medical PDFs. These lessons apply to any regex-based PDF extraction project.

### 1. OCR Output is Unpredictable

**Problem:** OCR (Optical Character Recognition) introduces errors and formatting inconsistencies that break rigid regex patterns.

**Examples encountered:**
- `3-11` (reference range) read as `321` or `3211` (hyphen lost)
- `1.40` read as `140` (decimal point lost)
- `=` characters inserted between fields: `SPECTROPHOTOMETRY = 12/23/2025`
- Page markers misread: `MHB` sometimes appears as `MBB`

**Solutions:**
- Use flexible patterns with optional characters: `\s*[=\s]*` between fields
- Accept multiple spellings: `M[HB]B` matches both `MHB` and `MBB`
- Some OCR corruption is unfixable without a lookup table of valid values

### 2. Multi-Line Data Splits

**Problem:** OCR frequently splits logical data across multiple lines, especially:
- Reference ranges: `0.60 -` on line 1, `1.10` on line 2
- Long component names split mid-word
- Units appearing on the line after the value

**Solutions:**
- Implement multiple patterns: complete (all on one line) and partial (continues on next line)
- When partial pattern matches, explicitly look at `lines[i + 1]` for continuation
- Example from `mhb_config.py`:
```python
# Pattern for partial ref range
pattern_partial_ref = r'(?P<ref_start>[\d.]+)\s*-\s*(?P<method>...)'

# Then look for continuation:
if i + 1 < len(lines):
    next_line = lines[i + 1].strip()
    ref_end_match = re.match(r'^([\d.]+)', next_line)
    if ref_end_match:
        ref_range = f"{ref_start}-{ref_end_match.group(1)}"
```

### 3. Page-Level vs Document-Level Extraction

**Problem:** Headers (like panel names) typically appear only on page 1, but results span multiple pages. Per-page extraction misses the context.

**Example:** "COMPREHENSIVE METABOLIC PANEL - Final result" appears on page 1, but SODIUM, CHLORIDE, etc. are on pages 2-3 with no header.

**Solution:**
1. First pass: concatenate all page texts, extract document-level metadata (panel name, date)
2. Second pass: extract results from each page, applying document-level metadata
```python
# First pass
full_text = '\n'.join(page_texts)
doc_panel_name = config.extract_panel_name(full_text)

# Second pass
for result in config.extract_results(page_text, filename):
    if not result.panel_name and doc_panel_name:
        result.panel_name = doc_panel_name
```

### 4. Always Have Fallback Strategies

**Problem:** Some documents lack expected headers entirely (different report format, truncated PDF, etc.)

**Solution:** Layer multiple fallback approaches:
1. Try primary pattern (document header)
2. Try alternate patterns (simpler format)
3. Fall back to filename parsing: `2023-02-27--LIPID PANEL--Kaiser.pdf` → `LIPID PANEL`
```python
if not doc_panel_name:
    parts = filename.replace('.pdf', '').split('--')
    if len(parts) >= 3:
        doc_panel_name = '--'.join(parts[1:-1]).upper()
```

### 5. Use Non-Greedy Quantifiers Carefully

**Problem:** Non-greedy `+?` and `*?` can match too little, causing patterns to fail.

**Example:** `(?P<method>[A-Z][A-Z\s&]+?)` might match just `S` instead of `SPECTROPHOTOMETRY` because it's non-greedy.

**Solution:** Ensure the pattern after the non-greedy group forces it to consume appropriately:
- `[A-Z]+?\s+\d` forces the `[A-Z]+?` to consume until whitespace before digit
- Test patterns with actual OCR output, not idealized examples

### 6. Debug with Actual OCR Output

**Problem:** Patterns written against expected format fail on actual OCR output.

**Debugging workflow:**
1. Run OCR on a failing file:
```bash
ocrmypdf --force-ocr input.pdf /tmp/ocr_output.pdf
```
2. Extract and print the text:
```python
import pdfplumber
with pdfplumber.open('/tmp/ocr_output.pdf') as pdf:
    for page in pdf.pages:
        print(page.extract_text())
```
3. Compare actual output to your regex pattern
4. Note unexpected whitespace, line breaks, and character substitutions

### 7. Handle Facility-Specific Variations

**Problem:** Each facility has different PDF formats, column orders, and terminology.

**Solution:** Use a modular config system with a base class:
```
facility_configs/
├── base_config.py      # Abstract base with common methods
├── rcb_config.py       # RCMC-specific patterns (native text)
├── kpa_config.py       # Kaiser-specific patterns (OCR)
└── mhb_config.py       # Monument-specific patterns (OCR)
```

Each config defines:
- `filename_patterns` - regex to match filenames to facility
- `requires_ocr` - whether OCR preprocessing is needed
- `row_pattern` - regex for extracting result rows
- `extract_results()` - custom extraction logic

### 8. Common Regex Pitfalls in Medical Data

| Pattern Issue | Problem | Fix |
|---------------|---------|-----|
| `[\d.]+` for values | Matches `10.5.3` | Use `\d+\.?\d*` or validate after |
| `[A-Z]+` for components | Misses `d%A1c`, `CO2` | Use `[A-Za-z][A-Za-z0-9%]+` |
| `\d{2}/\d{2}/\d{4}` for dates | Strict format | Works well, OCR rarely mangles dates |
| `\s+` between fields | Fails on single space | Use `\s+` not `\s{2,}` |
| `$` for line end | Includes `\r` on Windows | Use `\s*$` or strip lines first |

### 9. Log Extensively for Pattern Debugging

Enable verbose logging to see exactly what's being matched:
```python
logger.debug(f"Line: {repr(line)}")
logger.debug(f"Pattern match: {match.groups() if match else 'None'}")
logger.debug(f"Extracted: component={component}, value={value}, ref={ref_range}")
```

Check `logs/_debug.log` when results look wrong.

### 10. Test Incrementally

1. Start with the cleanest format (RCMC native text)
2. Add OCR facilities one at a time
3. Check `missed_files.txt` after each run to identify pattern gaps
4. Inspect CSV output for obviously wrong values (empty fields, truncated data)

---

## Regex Strategy & Troubleshooting Guide (Advanced)

This section documents advanced strategies developed during V1.6+ debugging to handle edge cases in medical report parsing.

### 1. The "Prefix Rule" for Garbage Collection
**Problem:** When a regex pattern is too permissive (e.g., optional prefixes like `^(?:F\s+)?`), it starts matching random text in the document (addresses, patient demographics) as lab results.
**Solution:**
- **Strict Mode:** For ambiguous patterns (like those without a reference range or unit), **require** a distinct prefix (like `F ` in RCMC reports).
- **Relaxed Mode:** Only allow optional prefixes if the rest of the pattern is highly specific (e.g., requires a reference range like `1.5-5.0`).
- **Example:**
  - `row_pattern_with_ref` (Has `1.5-5.0`): Can be `^(?:F\s+)?...` (Safe)
  - `row_pattern_no_unit` (Has `1.5`): Must be `^F\s+...` (Unsafe otherwise)

### 2. Handling "Loose" Units
**Problem:** Units often appear without parentheses (e.g., `50,000 CFU/ml`) or are attached to narrative text.
**Solution:**
- Create a dedicated pattern for loose units: `(?P<unit>[^\s\(\)]+)`.
- **Constraint:** Ensure this unit pattern doesn't eat into subsequent columns (like flags).
- **Validation:** Disallow colons in units `[^\s:]+` to prevent matching keys like `Phone:`.

### 3. OCR Artifacts & Special Characters
**Problem:** OCR is imperfect.
- **Hyphens:** `DIOXETANE-BASED` -> Hyphen inside a word.
- **Commas:** `>2,000` -> Comma inside a number.
- **Inequalities:** `<4.0` -> Symbols inside a value.
- **Component Names:** `1,25-Dihydroxyvitamin D` -> Starts with digit.
**Solution:**
- **Values:** Always use `[<>]*[\d.,]+` instead of `[\d.]+`.
- **Methods:** Allow hyphens `[A-Z][A-Z\s&-]+`.
- **Components:** Allow starting with digits `[A-Za-z0-9]...`.

### 4. Visit Summaries (Column Order Swaps)
**Problem:** "Visit Summary" documents often list labs in a different column order than the official "Lab Report".
- Standard: `Name Value Flag Ref Unit`
- Visit Summary: `Name Value Ref Unit Flag`
**Solution:**
- Create a specific regex for the alternate layout.
- Use **Strict Validation** on fields like Reference Range to differentiate valid rows from noise.
- **Ref Range Validator:** `(?P<ref_range>(?:[\d.]+\s*-\s*[\d.]+|[<>]=?\s*[\d.]+))` matches `1-5` or `<10` but rejects years like `1951`.

### 5. Date & Panel Fallbacks
**Problem:** Summaries often lack headers (Date, Panel Name) for every row.
**Solution:**
- **Date Fallback:** If row text has no date, extract `YYYY-MM-DD` from the filename.
- **Panel Fallback:** If Panel Name is missing or generic (e.g., "LABS-VISIT"), default to the **Component Name** (e.g., Panel="Glucose" for a Glucose test). This is cleaner than grouping unrelated tests under a generic name.

---

## Future Enhancements (Backlog)

- [ ] Add support for additional facilities
- [ ] Improve OCR error detection
- [ ] Add data validation/range checking
- [ ] Support for encrypted PDFs (with password prompt)
- [ ] Export to additional formats (JSON, Excel)
