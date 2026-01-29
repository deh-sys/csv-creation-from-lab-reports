import pdfplumber
import subprocess
import sys
import os

pdf_path = "test-files/2025-08-18--VITAMIN_D_25--Monument.pdf"
ocr_output = "debug_ocr_vitd.pdf"

print(f"Running OCR on {pdf_path}...")
subprocess.run(['ocrmypdf', '--force-ocr', pdf_path, ocr_output], check=True, capture_output=True)

print("\nExtracting text...")
with pdfplumber.open(ocr_output) as pdf:
    for page in pdf.pages:
        print(page.extract_text())

if os.path.exists(ocr_output):
    os.remove(ocr_output)
