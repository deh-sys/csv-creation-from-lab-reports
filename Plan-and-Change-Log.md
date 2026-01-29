# Plan and Change Log

## Project: Lab Report Parser

### Purpose
Extract structured lab test data from medical PDF reports (RCMC, Kaiser, Monument Health) into a unified CSV format for analysis and tracking.

---

## Version History

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

## Future Enhancements (Backlog)

- [ ] Add support for additional facilities
- [ ] Improve OCR error detection
- [ ] Add data validation/range checking
- [ ] Support for encrypted PDFs (with password prompt)
- [ ] Export to additional formats (JSON, Excel)
