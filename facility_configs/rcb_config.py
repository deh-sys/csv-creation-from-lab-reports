"""
Configuration for RCB/RCMC (Rapid City Medical Center) lab reports.
These PDFs have native text (no OCR needed) with a consistent tabular format.

Sample row formats:
  F CA 10.5 8.7-10.6 (mg/dL)
  F RBC 4.09 L 4.20-5.40 (M/uL)  <- with flag
  F d%A1c 4.7 <6.0 (%)           <- lowercase, < in range
  F Calcium, Urine 4.4 Not Estab. (mg/dL)  <- text ref range

Pattern breakdown:
  F = status marker (Final)
  test_name = letters, numbers, symbols (flexible)
  value = numeric with optional < or >
  flag = optional H or L
  ref_range = numeric range OR text like "Not Estab."
  unit = inside parentheses
"""

import re
from typing import Generator

from .base_config import FacilityConfig, LabResult


class RCBConfig(FacilityConfig):
    """Configuration for RCB/RCMC facility lab reports."""

    name = "RCMC"
    filename_patterns = [
        r'--RCMC\.pdf$',
        r'--RCB\.pdf$',
    ]
    requires_ocr = False

    # Collection Date: 12/09/2025 08:12:00
    date_pattern = r'Collection Date:\s*(?P<date>\d{2}/\d{2}/\d{4})'

    # Page marker: RCB 45 or RCB 3
    page_marker_pattern = r'^RCB\s+\d+\s*$'

    # Row pattern with reference range (most common):
    # F CA 10.5 8.7-10.6 (mg/dL)
    row_pattern_with_ref = (
        r'^F\s+'
        r'(?P<test_name>[A-Za-z][A-Za-z0-9+\-#%,\s]+?)\s+'
        r'(?P<value>[\d.<>]+)\s*'
        r'(?P<flag>[HL])?\s+'
        r'(?P<ref_range>[^\(]+?)\s*'
        r'\((?P<unit>[^)]+)\)'
    )

    # Row pattern without reference range (e.g., F EAG 89 (mg/dL))
    row_pattern_no_ref = (
        r'^F\s+'
        r'(?P<test_name>[A-Za-z][A-Za-z0-9+\-#%,\s]+?)\s+'
        r'(?P<value>[\d.<>]+)\s*'
        r'\((?P<unit>[^)]+)\)'
    )

    def extract_results(self, text: str, source_filename: str) -> Generator[LabResult, None, None]:
        """Extract lab results from RCMC page text."""
        # Get collection date for the page
        test_date = self.extract_date(text)

        # Get page marker
        page_marker = self.extract_page_marker(text)

        # Track which lines we've matched to avoid duplicates
        matched_lines = set()

        # First pass: try pattern with reference range
        for match in re.finditer(self.row_pattern_with_ref, text, re.MULTILINE | re.IGNORECASE):
            line_start = match.start()
            matched_lines.add(line_start)

            result = LabResult(
                source=source_filename,
                facility=self.name,
                test_name=self.normalize_test_name(match.group('test_name')),
                test_date=test_date,
                value=self.normalize_value(match.group('value')),
                ref_range=self.normalize_ref_range(match.group('ref_range')),
                unit=self.normalize_unit(match.group('unit')),
                flag=match.group('flag') or "",
                page_marker=page_marker,
            )
            yield result

        # Second pass: try pattern without reference range for unmatched lines
        for match in re.finditer(self.row_pattern_no_ref, text, re.MULTILINE | re.IGNORECASE):
            line_start = match.start()
            if line_start in matched_lines:
                continue  # Already matched by first pattern

            result = LabResult(
                source=source_filename,
                facility=self.name,
                test_name=self.normalize_test_name(match.group('test_name')),
                test_date=test_date,
                value=self.normalize_value(match.group('value')),
                ref_range="",  # No reference range
                unit=self.normalize_unit(match.group('unit')),
                flag="",  # No flag without ref range
                page_marker=page_marker,
            )
            yield result
