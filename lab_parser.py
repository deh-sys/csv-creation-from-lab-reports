#!/usr/bin/env python3
"""
Lab Report Parser - Extracts structured lab data from medical PDFs into CSV.

Supports multiple facilities:
  - RCMC (Rapid City Medical Center) - Native text PDFs
  - Kaiser - Image-based PDFs requiring OCR
  - Monument Health - Image-based PDFs requiring OCR

Usage:
  python3 lab_parser.py
  Then drag your input folder when prompted.
"""

import concurrent.futures
import csv
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, Dict, Any

# Check dependencies before importing
try:
    import pdfplumber
except ImportError:
    print("ERROR: pdfplumber not installed. Run: pip install pdfplumber")
    sys.exit(1)

try:
    from tqdm import tqdm
except ImportError:
    print("ERROR: tqdm not installed. Run: pip install tqdm")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas not installed. Run: pip install pandas xlsxwriter")
    sys.exit(1)

try:
    import xlsxwriter
except ImportError:
    print("ERROR: xlsxwriter not installed. Run: pip install xlsxwriter")
    sys.exit(1)

from facility_configs import get_config_for_filename, FACILITY_CONFIGS


# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = SCRIPT_DIR / "output"
LOGS_DIR = SCRIPT_DIR / "logs"
OUTPUT_FILE = OUTPUT_DIR / "lab_results.xlsx"
DEBUG_LOG = LOGS_DIR / "_debug.log"
MISSED_FILES_LOG = LOGS_DIR / "missed_files.txt"

CSV_COLUMNS = [
    'source',
    'facility',
    'panel_name',
    'component',
    'test_date',
    'value',
    'ref_range',
    'unit',
    'flag',
    'page_marker',
]


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging():
    """Configure dual logging: minimal console, verbose file."""
    LOGS_DIR.mkdir(exist_ok=True)

    # File handler - verbose DEBUG level
    file_handler = logging.FileHandler(DEBUG_LOG, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    # Console handler - minimal INFO level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(logging.Formatter('%(message)s'))

    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logging.getLogger(__name__)


# ============================================================================
# Input Helpers
# ============================================================================

def sanitize_path(path_str: str) -> str:
    """
    Sanitize a path dragged into macOS Terminal.
    Handles escaped spaces and quotes from drag-and-drop.
    """
    # Remove leading/trailing whitespace
    path_str = path_str.strip()
    # Remove surrounding quotes
    path_str = path_str.strip('"').strip("'")
    # Handle escaped spaces (macOS Terminal escapes spaces with backslash)
    path_str = path_str.replace(r'\ ', ' ')
    path_str = path_str.replace('\\', '')
    return path_str


def prompt_for_input_folder() -> Path:
    """Prompt user for input folder path."""
    print("\n" + "=" * 60)
    print("LAB REPORT PARSER")
    print("=" * 60)
    print("\nSupported facilities:", ", ".join(c.name for c in FACILITY_CONFIGS))
    print("\nDrag and drop your input folder here, then press Enter:")

    while True:
        user_input = input("> ").strip()
        if not user_input:
            print("No path provided. Please try again.")
            continue

        folder_path = Path(sanitize_path(user_input))

        if not folder_path.exists():
            print(f"Path does not exist: {folder_path}")
            continue

        if not folder_path.is_dir():
            print(f"Path is not a directory: {folder_path}")
            continue

        return folder_path


def prompt_for_output_folder() -> Path:
    """Prompt user for output folder path."""
    default_dir = Path.home() / "Desktop"
    print(f"\nDrag and drop your output folder here (Press Enter for Desktop):")

    while True:
        user_input = input(f"[{default_dir}] > ").strip()

        if not user_input:
            return default_dir

        folder_path = Path(sanitize_path(user_input))

        if folder_path.exists():
            if not folder_path.is_dir():
                print(f"Path is not a directory: {folder_path}")
                continue
            return folder_path

        # If path doesn't exist, ask to create
        print(f"Folder does not exist: {folder_path}")
        create = input("Create this folder? (y/N) > ").strip().lower()
        if create == 'y':
            try:
                folder_path.mkdir(parents=True, exist_ok=True)
                return folder_path
            except Exception as e:
                print(f"Error creating folder: {e}")
        else:
            print("Please choose an existing folder.")


# ============================================================================
# PDF Discovery
# ============================================================================

def find_all_pdfs(folder: Path) -> list[Path]:
    """Recursively find all PDF files in the folder."""
    return sorted(folder.rglob("*.pdf"))


def categorize_pdfs(pdf_files: list[Path]) -> dict[str, list[Path]]:
    """Group PDFs by facility config."""
    categorized = {config.name: [] for config in FACILITY_CONFIGS}
    categorized['unknown'] = []

    for pdf_path in pdf_files:
        config = get_config_for_filename(pdf_path.name)
        if config:
            categorized[config.name].append(pdf_path)
        else:
            categorized['unknown'].append(pdf_path)

    return categorized


# ============================================================================
# OCR Processing
# ============================================================================

def check_ocrmypdf_available() -> bool:
    """Check if ocrmypdf is available in PATH."""
    return shutil.which('ocrmypdf') is not None


def needs_ocr(pdf_path: Path) -> bool:
    """Check if PDF needs OCR (no extractable text)."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages[:2]:  # Check first 2 pages
                text = page.extract_text()
                if text and len(text.strip()) > 50:
                    return False
        return True
    except Exception:
        return True


def ocr_pdf(pdf_path: Path, output_path: Path, jobs: int = 1) -> Tuple[bool, str]:
    """Run OCR on a PDF file."""
    try:
        # --jobs limits the number of threads per OCR process
        cmd = ['ocrmypdf', '--force-ocr', '--jobs', str(jobs), str(pdf_path), str(output_path)]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # Increased timeout for safety
        )
        if result.returncode != 0:
            return False, result.stderr
        return True, ""
    except subprocess.TimeoutExpired:
        return False, "OCR timeout"
    except Exception as e:
        return False, str(e)


# ============================================================================
# PDF Processing
# ============================================================================

def process_pdf(pdf_path: Path) -> Dict[str, Any]:
    """
    Process a single PDF file and extract lab results.
    Designed to run in a separate process.

    Returns:
        Dict with keys: 'results', 'file_path', 'logs', 'error'
    """
    results = []
    logs = []
    error = None
    filename = pdf_path.name

    # Get facility config
    # Note: FACILITY_CONFIGS is global, so it should be available in forked process
    config = get_config_for_filename(filename)
    if not config:
        return {
            'results': [],
            'file_path': str(pdf_path),
            'logs': [f"Unknown facility pattern: {filename}"],
            'error': "Unknown facility pattern"
        }

    logs.append(f"Processing {filename} with {config.name} config")

    # Create a temporary directory for this specific task
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        read_path = pdf_path

        if config.requires_ocr:
            # Check if OCR is actually needed
            if needs_ocr(pdf_path):
                ocr_output = temp_path / f"ocr_{pdf_path.stem}.pdf"
                # Run OCR single-threaded since we are parallelizing at file level
                success, ocr_err = ocr_pdf(pdf_path, ocr_output, jobs=1)
                
                if success:
                    read_path = ocr_output
                else:
                    error_msg = f"OCR failed: {ocr_err}"
                    logs.append(error_msg)
                    return {
                        'results': [],
                        'file_path': str(pdf_path),
                        'logs': logs,
                        'error': error_msg
                    }
            else:
                logs.append(f"PDF already has text, skipping OCR: {filename}")

        # Extract text and parse
        try:
            with pdfplumber.open(read_path) as pdf:
                # First pass: extract all page texts
                page_texts = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        page_texts.append(text)

                # Extract panel name from full document
                full_text = '\n'.join(page_texts)
                doc_panel_name = ""
                if hasattr(config, 'extract_panel_name'):
                    raw_doc_panel = config.extract_panel_name(full_text)
                    doc_panel_name = config.normalize_panel_name(raw_doc_panel)

                # Fallback: extract panel name from filename
                if not doc_panel_name:
                    parts = filename.replace('.pdf', '').split('--')
                    if len(parts) >= 3:
                        raw_filename_panel = '--'.join(parts[1:-1]).upper()
                        doc_panel_name = config.normalize_panel_name(raw_filename_panel)
                        logs.append(f"Panel name from filename: {doc_panel_name}")

                logs.append(f"Document panel name: {doc_panel_name}")

                # Second pass: extract results from each page
                for page_num, text in enumerate(page_texts, start=1):
                    # Extract results using facility-specific config
                    for result in config.extract_results(text, filename):
                        # Use document-level panel name if page-level is empty
                        result_dict = result.to_dict()
                        
                        # 1. Panel Name Logic
                        # Use doc_panel_name if result has none
                        if not result_dict.get('panel_name') and doc_panel_name:
                            result_dict['panel_name'] = doc_panel_name
                        
                        # specific cleanup for "Labs-Visit" or empty panels -> use Component name
                        current_panel = result_dict.get('panel_name', '').strip().upper()
                        if not current_panel or current_panel == 'LABS-VISIT':
                            result_dict['panel_name'] = result_dict.get('component')

                        # 2. Date Logic
                        # If date is missing, try to extract from filename (YYYY-MM-DD)
                        if not result_dict.get('test_date'):
                            try:
                                # Filename format: YYYY-MM-DD--...
                                date_part = filename[:10]
                                # Simple validation regex
                                if re.match(r'^\d{4}-\d{2}-\d{2}$', date_part):
                                    # Convert YYYY-MM-DD to MM/DD/YYYY to match other dates
                                    y, m, d = date_part.split('-')
                                    result_dict['test_date'] = f"{m}/{d}/{y}"
                            except Exception:
                                pass

                        results.append(result_dict)

        except Exception as e:
            error = str(e)
            logs.append(f"Error processing {filename}: {e}")

    return {
        'results': results,
        'file_path': str(pdf_path),
        'logs': logs,
        'error': error
    }


# ============================================================================
# Main Processing Loop
# ============================================================================

def process_all_pdfs(pdf_files: list[Path], logger: logging.Logger) -> tuple[list[dict], list[str], list[str]]:
    """
    Process all PDF files in parallel and return results.

    Returns:
        Tuple of (all_results, processed_files, missed_files)
    """
    all_results = []
    processed_files = []
    missed_files = []
    
    # Use all available CPUs
    max_workers = os.cpu_count() or 1
    logger.info(f"Starting parallel processing with {max_workers} workers")

    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_file = {executor.submit(process_pdf, pdf): pdf for pdf in pdf_files}
        
        # Process as they complete
        for future in tqdm(concurrent.futures.as_completed(future_to_file), total=len(pdf_files), desc="Processing PDFs", unit="file"):
            pdf_path = future_to_file[future]
            try:
                data = future.result()
                
                # Unpack results
                file_results = data.get('results', [])
                file_logs = data.get('logs', [])
                error = data.get('error')
                
                # Write logs to main debug log
                for log_msg in file_logs:
                    logger.debug(log_msg)
                
                if error:
                    logger.error(f"Error in {pdf_path.name}: {error}")
                    missed_files.append(f"{pdf_path.name}: {error}")
                elif not file_results:
                    # No results but no crash
                    missed_files.append(f"{pdf_path.name}: No results extracted")
                else:
                    all_results.extend(file_results)
                    processed_files.append(str(pdf_path))
                    
            except Exception as e:
                logger.exception(f"Critical error getting result for {pdf_path.name}")
                missed_files.append(f"{pdf_path.name}: {str(e)}")

    return all_results, processed_files, missed_files


def write_excel(results: list[dict], output_path: Path):
    """
    Write results to a formatted Excel file.
    Features: Frozen headers, auto-filter, auto-width columns,
    conditional formatting for flags.
    """
    if not results:
        print("No results to write.")
        return

    output_path.parent.mkdir(exist_ok=True, parents=True)

    # Create DataFrame
    df = pd.DataFrame(results)

    # Ensure all defined internal columns exist
    for col in CSV_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    
    df = df[CSV_COLUMNS]  # Enforce initial internal order

    # Rename columns to display names
    column_map = {
        'source': 'Source File',
        'facility': 'Facility',
        'panel_name': 'Panel Name',
        'component': 'Component',
        'test_date': 'Date',
        'value': 'Result',
        'ref_range': 'Ref Range',
        'unit': 'Units',
        'flag': 'Flag',
        'page_marker': 'Bates'
    }
    df = df.rename(columns=column_map)

    # Reorder columns (Date first, Source/Facility last)
    display_order = [
        'Date',
        'Panel Name',
        'Component',
        'Result',
        'Flag',
        'Ref Range',
        'Units',
        'Bates',
        'Facility',
        'Source File'
    ]
    df = df[display_order]

    # Create Excel writer
    try:
        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            sheet_name = 'Lab Results'
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Get workbook and worksheet objects
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]

            # Define formats
            header_format = workbook.add_format({
                'bold': True,
                'text_wrap': False,
                'valign': 'vcenter',
                'align': 'center',
                'fg_color': '#D7E4BC',  # Light green/grayish
                'border': 1,
                'font_name': 'Baskerville',
                'font_size': 14
            })
            
            # Base format for all data cells
            data_format = workbook.add_format({
                'font_name': 'Calibri',
                'font_size': 13,
                'align': 'center',
                'valign': 'vcenter'
            })

            # Format for Flag column (Red text for abnormal)
            red_text = workbook.add_format({
                'font_color': '#9C0006', 
                'bg_color': '#FFC7CE',
                'align': 'center',
                'valign': 'vcenter'
            })
            
            # Format for Ref Range (Force text + data font)
            text_format = workbook.add_format({
                'num_format': '@',
                'font_name': 'Calibri',
                'font_size': 13,
                'align': 'center',
                'valign': 'vcenter'
            })

            # Apply formatting
            
            # 1. Set column widths and base format
            for idx, col in enumerate(df.columns):
                # Calculate max width of data in this column
                # Add more padding (+8) to make it spacious
                max_len = max(
                    df[col].astype(str).map(len).max(),
                    len(col)
                ) + 8
                
                # Cap width at 70 chars
                width = min(max_len, 70)
                
                # Apply text format to 'Ref Range', normal data format to others
                if col == 'Ref Range':
                    worksheet.set_column(idx, idx, width, text_format)
                else:
                    worksheet.set_column(idx, idx, width, data_format)

            # 2. Write headers again with format
            for col_num, value in enumerate(df.columns):
                worksheet.write(0, col_num, value, header_format)

            # 3. Freeze top row
            worksheet.freeze_panes(1, 0)

            # 4. Enable AutoFilter
            worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

            # 5. Conditional Formatting for Flag column
            # Find the 'Flag' column index (using new name)
            flag_col_idx = df.columns.get_loc('Flag')
            
            # Apply to all rows in flag column
            worksheet.conditional_format(1, flag_col_idx, len(df), flag_col_idx, {
                'type': 'cell',
                'criteria': '!=',
                'value': '""',  # Not empty
                'format': red_text
            })
            
    except Exception as e:
        print(f"Error writing Excel file: {e}")
        # Fallback to CSV if Excel fails? 
        # For now, just raise or print, as user explicitly wanted Excel.
        raise


def write_missed_files(missed_files: list[str], output_path: Path):
    """Write list of missed files for review."""
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f"Missed Files Report - {datetime.now().isoformat()}\n")
        f.write("=" * 60 + "\n\n")
        for entry in missed_files:
            f.write(f"- {entry}\n")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point."""
    # Setup logging
    logger = setup_logging()
    logger.info("Lab Parser starting")

    # Check ocrmypdf availability
    if not check_ocrmypdf_available():
        print("WARNING: ocrmypdf not found. Image-based PDFs (Kaiser, Monument) will be skipped.")
        logger.warning("ocrmypdf not available")

    # Get input folder
    input_folder = prompt_for_input_folder()
    logger.info(f"Input folder: {input_folder}")

    # Get output folder
    output_folder = prompt_for_output_folder()
    logger.info(f"Output folder: {output_folder}")
    output_file_path = output_folder / "lab_results.xlsx"

    # Find all PDFs
    print("\nScanning for PDF files...")
    pdf_files = find_all_pdfs(input_folder)

    if not pdf_files:
        print("No PDF files found in the specified folder.")
        sys.exit(1)

    # Categorize by facility
    categorized = categorize_pdfs(pdf_files)

    print(f"\nFound {len(pdf_files)} PDF files:")
    for facility, files in categorized.items():
        if files:
            print(f"  {facility}: {len(files)} files")

    if categorized['unknown']:
        print(f"\n  WARNING: {len(categorized['unknown'])} files with unrecognized facility patterns")
        logger.warning(f"Unknown facility files: {[f.name for f in categorized['unknown']]}")

    # Filter out unknown files
    known_pdfs = [f for f in pdf_files if get_config_for_filename(f.name)]

    if not known_pdfs:
        print("\nNo files match known facility patterns. Exiting.")
        sys.exit(1)

    print(f"\nProcessing {len(known_pdfs)} files...")
    print()

    # Process all PDFs
    all_results, processed_files, missed_files = process_all_pdfs(known_pdfs, logger)

    # Write output Excel
    print(f"Writing results to {output_file_path.name}...")
    write_excel(all_results, output_file_path)

    # Write missed files log if any
    if missed_files:
        write_missed_files(missed_files, MISSED_FILES_LOG)

    # Print summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    processed_count = len(processed_files)
    skipped_count = len(categorized['unknown'])
    error_count = len(missed_files)

    print(f"✅ Processed: {processed_count} | ⚠️  Skipped: {skipped_count} | ❌ No Results / Errors: {error_count}")
    print(f"\nResults: {len(all_results)} lab values extracted")
    print(f"Output:  {output_file_path}")

    if missed_files:
        print(f"\nFiles with No Results (First 10):")
        for i, msg in enumerate(missed_files[:10]):
            # Clean up the message to just show filename if possible, or short error
            # msg format is typically "filename: error"
            print(f"  - {msg}")
        
        if len(missed_files) > 10:
            print(f"  ...and {len(missed_files) - 10} more (see {MISSED_FILES_LOG.name})")
        
        print(f"\nFull List: {MISSED_FILES_LOG}")

    print(f"Log:       {DEBUG_LOG}")

    logger.info(f"Completed: {processed_count} processed, {error_count} errors, {len(all_results)} results")


if __name__ == '__main__':
    main()
