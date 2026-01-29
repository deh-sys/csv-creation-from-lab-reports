# Lab Report Parser

Extracts structured lab test results from medical PDF reports into a single CSV file.

## Supported Facilities

| Facility | Pattern | OCR Required |
|----------|---------|--------------|
| RCMC (Rapid City Medical Center) | `--RCMC.pdf` or `--RCB.pdf` | No |
| Kaiser | `--Kaiser.pdf` or `--KPA.pdf` | Yes |
| Monument Health | `--Monument.pdf` or `--MHB.pdf` | Yes |

## How to Run

```bash
python lab_parser.py
```

Then drag your input folder containing PDF files when prompted.

## Requirements

- Python 3.10+
- pdfplumber (`pip install pdfplumber`)
- tqdm (`pip install tqdm`)
- ocrmypdf (for Kaiser and Monument files): `brew install ocrmypdf`

## Output

| File | Location | Description |
|------|----------|-------------|
| Lab results CSV | `output/lab_results.csv` | All extracted lab values |
| Debug log | `logs/_debug.log` | Verbose processing details |
| Missed files | `logs/missed_files.txt` | Files that failed processing |

## CSV Columns

| Column | Description | Example |
|--------|-------------|---------|
| source | Source PDF filename | `2024-11-14--Labs-CBC--RCMC.pdf` |
| facility | Facility name | `RCMC` |
| test_name | Test/component name | `Glucose` |
| test_date | Collection date | `11/14/2024` |
| value | Result value | `85` |
| ref_range | Reference range | `70-100` |
| unit | Measurement unit | `mg/dL` |
| flag | Abnormal flag (H/L/blank) | `L` |
| page_marker | Page marker from footer | `RCB 3` |

## File Naming Convention

Files must include the facility marker at the end of the filename:
- `2024-11-14--Labs-CBC--RCMC.pdf` (RCMC facility)
- `2021-08-06--LIPID PANEL--Kaiser.pdf` (Kaiser facility)
- `2025-08-18--PHOSPHORUS--Monument.pdf` (Monument facility)
