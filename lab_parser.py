#!/usr/bin/env python3
"""
Lab Report Parser - Extracts structured lab data from medical PDFs into CSV.

Supports multiple facilities:
  - RCMC (Rapid City Medical Center) - Native text PDFs
  - Kaiser - Image-based PDFs requiring OCR
  - Monument Health - Image-based PDFs requiring OCR

Usage:
  python lab_parser.py
  Then drag your input folder when prompted.
"""

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

from facility_configs import get_config_for_filename, FACILITY_CONFIGS


# ============================================================================
# Configuration
# ============================================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
OUTPUT_DIR = SCRIPT_DIR / "output"
LOGS_DIR = SCRIPT_DIR / "logs"
OUTPUT_CSV = OUTPUT_DIR / "lab_results.csv"
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


def ocr_pdf(pdf_path: Path, output_path: Path, logger: logging.Logger) -> bool:
    """Run OCR on a PDF file."""
    try:
        result = subprocess.run(
            ['ocrmypdf', '--force-ocr', str(pdf_path), str(output_path)],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode != 0:
            logger.error(f"OCR failed for {pdf_path.name}: {result.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"OCR timeout for {pdf_path.name}")
        return False
    except Exception as e:
        logger.error(f"OCR error for {pdf_path.name}: {e}")
        return False


# ============================================================================
# PDF Processing
# ============================================================================

def process_pdf(pdf_path: Path, logger: logging.Logger, temp_dir: Path) -> list[dict]:
    """
    Process a single PDF file and extract lab results.

    Returns:
        List of result dictionaries, or empty list on failure.
    """
    results = []
    filename = pdf_path.name

    # Get facility config
    config = get_config_for_filename(filename)
    if not config:
        logger.warning(f"Unknown facility pattern: {filename}")
        return []

    logger.debug(f"Processing {filename} with {config.name} config")

    # Determine which file to read (original or OCR'd)
    read_path = pdf_path

    if config.requires_ocr:
        # Check if OCR is actually needed
        if needs_ocr(pdf_path):
            ocr_output = temp_dir / f"ocr_{pdf_path.stem}.pdf"
            if ocr_pdf(pdf_path, ocr_output, logger):
                read_path = ocr_output
            else:
                logger.error(f"OCR failed, skipping: {filename}")
                return []
        else:
            logger.debug(f"PDF already has text, skipping OCR: {filename}")

    # Extract text and parse
    try:
        with pdfplumber.open(read_path) as pdf:
            # First pass: extract all page texts and find document-level panel name
            page_texts = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    page_texts.append(text)

            # Extract panel name from full document (typically in first page header)
            full_text = '\n'.join(page_texts)
            doc_panel_name = config.extract_panel_name(full_text) if hasattr(config, 'extract_panel_name') else ""

            # Fallback: extract panel name from filename if not found in document
            # Filename format: DATE--PANEL_NAME--FACILITY.pdf
            if not doc_panel_name:
                parts = filename.replace('.pdf', '').split('--')
                if len(parts) >= 3:
                    # Middle parts are the panel name (may have multiple -- separators)
                    doc_panel_name = '--'.join(parts[1:-1]).upper()
                    logger.debug(f"Panel name from filename: {doc_panel_name}")

            logger.debug(f"Document panel name: {doc_panel_name}")

            # Second pass: extract results from each page
            for page_num, text in enumerate(page_texts, start=1):
                logger.debug(f"Page {page_num} text length: {len(text)}")

                # Extract results using facility-specific config
                for result in config.extract_results(text, filename):
                    # Use document-level panel name if page-level is empty
                    result_dict = result.to_dict()
                    if not result_dict.get('panel_name') and doc_panel_name:
                        result_dict['panel_name'] = doc_panel_name
                    results.append(result_dict)

    except Exception as e:
        logger.exception(f"Error processing {filename}: {e}")
        return []

    logger.debug(f"Extracted {len(results)} results from {filename}")
    return results


# ============================================================================
# Main Processing Loop
# ============================================================================

def process_all_pdfs(pdf_files: list[Path], logger: logging.Logger) -> tuple[list[dict], list[str], list[str]]:
    """
    Process all PDF files and return results.

    Returns:
        Tuple of (all_results, processed_files, missed_files)
    """
    all_results = []
    processed_files = []
    missed_files = []

    # Create temp directory for OCR output
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Process with progress bar
        for pdf_path in tqdm(pdf_files, desc="Processing PDFs", unit="file"):
            try:
                results = process_pdf(pdf_path, logger, temp_path)
                if results:
                    all_results.extend(results)
                    processed_files.append(str(pdf_path))
                else:
                    missed_files.append(f"{pdf_path.name}: No results extracted")
            except Exception as e:
                logger.exception(f"Unexpected error processing {pdf_path.name}")
                missed_files.append(f"{pdf_path.name}: {str(e)}")

    return all_results, processed_files, missed_files


def write_csv(results: list[dict], output_path: Path):
    """Write results to CSV file."""
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(results)


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

    # Write output CSV
    OUTPUT_DIR.mkdir(exist_ok=True)
    write_csv(all_results, OUTPUT_CSV)

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

    print(f"✅ Processed: {processed_count} | ⚠️  Skipped: {skipped_count} | ❌ Errors: {error_count}")
    print(f"\nResults: {len(all_results)} lab values extracted")
    print(f"Output:  {OUTPUT_CSV}")

    if missed_files:
        print(f"Missed:  {MISSED_FILES_LOG}")

    print(f"Log:     {DEBUG_LOG}")

    logger.info(f"Completed: {processed_count} processed, {error_count} errors, {len(all_results)} results")


if __name__ == '__main__':
    main()
