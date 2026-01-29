# Plan and Change Log

## Project: Lab Report Parser

### Purpose
Extract structured lab test data from medical PDF reports (RCMC, Kaiser, Monument Health) into a unified CSV format for analysis and tracking.

---

## Version History

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
- Interactive single-command script (`python lab_parser.py`)
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

### Architecture
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

## Future Enhancements (Backlog)

- [ ] Add support for additional facilities
- [ ] Improve OCR error detection
- [ ] Add data validation/range checking
- [ ] Support for encrypted PDFs (with password prompt)
- [ ] Export to additional formats (JSON, Excel)
