# Developer Guide & Architectural Insights

*For future maintainers: This document captures the "struggles" and specific solutions evolved during the development of the Lab Parser. Read this before refactoring.*

## 1. Core Architecture

The system uses a **Config-based Strategy Pattern**.
- `lab_parser.py`: The orchestrator. Handles file discovery, multiprocessing, and Excel writing. It knows *nothing* about regex.
- `facility_configs/`: Contains the logic.
    - `base_config.py`: Defines the `LabResult` data structure and standard component mappings.
    - `kpa_config.py` (Kaiser), `rcb_config.py` (RCMC), `mhb_config.py` (Monument): Each class implements `extract_results(text)` differently.

**Key Rule:** If you need to support a new facility, add a new `Config` class. Do not clutter `lab_parser.py`.

## 2. Regex Strategies & "The Struggles"

### A. The "Header as Data" Trap (RCMC)
**Problem:** Native PDF tables often repeat headers like "NAME VALUE REFERENCE RANGE" on every page. Simple regexes like `(?P<comp>\w+)\s+(?P<val>\d+)` will happily match "NAME VALUE" as a component and "REFERENCE" as a value if digits follow nearby.
**Solution:** Do not rely solely on Regex.
- **Implement a Garbage Filter:** In `extract_results`, strictly check `if 'NAME VALUE' in component.upper(): continue`.
- **Why:** Regex is good at patterns, but bad at semantic exclusion. Python string checks are faster and safer for filtering known garbage.

### B. Multi-line Extraction (Imaging/Narratives)
**Problem:** Lab results are line-based, but Imaging "Impressions" span multiple paragraphs.
**Solution:**
- Use `re.DOTALL` to allow `.` to match newlines.
- **Stop-Tokens are Critical:** You cannot just capture `(.*)`. You must define where to STOP.
    ```python
    # Lookahead for the next section header
    r'IMPRESSION:\s*(?P<text>.*?)(?=\n(?:Electronically signed|Procedure Note|Authorizing Provider)|$)'
    ```
- **Execution:** Run this "Narrative Extraction" *once per page/file text* before processing the line-by-line numeric results.

### C. Text-Based Results (Microbiology)
**Problem:** Regex optimized for `[\d.]+` (Chemistry) fails on "Negative", "Heavy Growth", "Detected".
**Solution:**
- **Allow-list, don't Wildcard:** Do NOT match `\w+` as a value (it captures everything).
- Use a specific list: `(?P<value>Negative|Positive|Detected|Not Detected|Heavy|Reactive|Nonreactive)`.
- Create a separate `result_type="Microbiology"` to handle these differently in the output (e.g., put text in "Narrative" column).

### D. Component Normalization
**Problem:** Raw data is messy. "WBC'S AUTO", "WBC, Urine", "Leukocytes".
**Solution:**
- **Centralized Mapping:** `base_config.py` contains `COMPONENT_MAPPINGS`.
- **Regex Keys:** The keys in the mapping are the *Target Name* (e.g., "White Blood Cell Count (WBC)"), and the values are lists of *Regexes* to match the raw input.
- **Always Normalize:** Every extraction calls `self.normalize_component_name(raw)`.

## 3. False Positives in Abnormal Flags
**Problem:** Some reports have a header "ABNORMAL LAB REPORT". A naive check `if 'ABNORMAL' in text:` flagged *every* result as Abnormal ("A").
**Solution:**
- **Line-Level Specificity:** Only flag a result if the *specific line* contains a marker like `(H)`, `(L)`, or `*`.
- Never trust document-level headers for item-level flags.

## 4. Excel & Data Types
**Problem:** String dates ("01/25/2024") sort alphabetically, putting January 2025 before February 2024.
**Solution:**
- **Convert to Objects:** Use `pd.to_datetime()` before writing.
- **Format in Excel:** Use `xlsxwriter` formats (`num_format='mm/dd/yyyy'`) to display them as strings but keep them as serial numbers for sorting.

## 5. Adding a New Facility
1. Duplicate `base_config.py` structure.
2. Determine if it needs OCR (Kaiser/Monument) or native text (RCMC).
3. **Capture 3-4 sample lines** and ask an LLM to "Generate a Python Regex with named groups for this text".
4. **Test specifically for Garbage:** Does your regex match the header row? If so, add a filter.
