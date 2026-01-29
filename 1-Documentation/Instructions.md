# Lab Report Parser

Extracts structured lab test results from medical PDF reports into a formatted Excel file.

## Supported Facilities

| Facility | Pattern | OCR Required |
|----------|---------|--------------|
| RCMC (Rapid City Medical Center) | `--RCMC.pdf` or `--RCB.pdf` | No |
| Kaiser | `--Kaiser.pdf` or `--KPA.pdf` | Yes |
| Monument Health | `--Monument.pdf` or `--MHB.pdf` | Yes |

## How to Run

```bash
.venv/bin/python3 lab_parser.py
```

1. Drag and drop your **input folder** (containing PDFs) when prompted.
2. Drag and drop your **output folder** (or press Enter for Desktop) when prompted.

## Requirements

- Python 3.10+
- **ocrmypdf** (for Kaiser and Monument files): `brew install ocrmypdf`
- All Python dependencies are pre-installed in the `.venv` folder.

## Output

| File | Location | Description |
|------|----------|-------------|
| Lab results Excel | `lab_results.xlsx` | All extracted lab values (Formatted) |
| Debug log | `logs/_debug.log` | Verbose processing details |
| Missed files | `logs/missed_files.txt` | Files that failed processing |

## Performance

- **Parallel Processing:** Automatically uses all available CPU cores to process files significantly faster.
- **OCR Optimization:** Smartly manages OCR threads to prevent system slowdowns while maximizing throughput.

## Excel Formatting

- **Header:** 14pt Baskerville (Frozen & Filtered).
- **Data:** 13pt Calibri.
- **Reference Ranges:** Forced to Text format (prevents date conversion).
- **Abnormal Flags:** Highlighted in Red.

## Excel Columns

| Column | Description | Example |
|--------|-------------|---------|
| Date | Collection date | `11/14/2024` |
| Panel Name | Test panel name | `CBC Auto Diff` |
| Component | Individual measurement | `WBC` |
| Result | Result value | `5.1` |
| Flag | Abnormal flag (H/L/blank) | `L` |
| Ref Range | Reference range | `4.5-10.5` |
| Units | Measurement unit | `K/uL` |
| Bates | Page marker from footer | `RCB 3` |
| Facility | Facility name | `RCMC` |
| Source File | Source PDF filename | `2024-11-14--Labs-CBC--RCMC.pdf` |

### Panel vs Component

- **panel_name**: The test panel or order (e.g., "CMP", "CBC Auto Diff", "Lipid Panel")
- **component**: The individual measurement within that panel (e.g., "Glucose", "WBC", "Cholesterol")

## File Naming Convention

Files must include the facility marker at the end of the filename:
- `2024-11-14--Labs-CBC--RCMC.pdf` (RCMC facility)
- `2021-08-06--LIPID PANEL--Kaiser.pdf` (Kaiser facility)
- `2025-08-18--PHOSPHORUS--Monument.pdf` (Monument facility)

## For Developers

See [Developer-Guide.md](Developer-Guide.md) for architectural details, regex strategies, and lessons learned.
