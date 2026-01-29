"""
Configuration for MHB/Monument Health lab reports.
These PDFs are image-based (require OCR) with structured format.

Sample row format (after OCR):
  Phosphorus 28 2.5-4.9 SPECTROPHOTOMETRY 08/18/2025 MONUMENT
  mg/dL AND POTENTIOMETRY 10:34AM HEALTH

Pattern notes:
  - Test name, value, ref range, method, date, location
  - Method column contains test methodology
  - May have (ABNORMAL) prefix for flagged results
  - Unit often appears on the next line
"""

import re
from typing import Generator

from .base_config import FacilityConfig, LabResult


class MHBConfig(FacilityConfig):
    """Configuration for Monument Health/MHB facility lab reports."""

    name = "Monument"
    filename_patterns = [
        r'--Monument\.pdf$',
        r'--MHB\.pdf$',
    ]
    requires_ocr = True

    # Date from header: "Final result (08/18/2025 9:19 AM MDT)"
    date_pattern = r'Final result\s*\((?P<date>\d{2}/\d{2}/\d{4})'

    # Page marker: MHB 11 or MBB 12 (OCR sometimes misreads)
    page_marker_pattern = r'^M[HB]B\s+\d+\s*$'

    # Row pattern for Monument results
    # Format: TEST_NAME VALUE REF_RANGE METHOD DATE LOCATION
    # Note: Method is all caps like SPECTROPHOTOMETRY, IMMUNOASSAY, etc.
    row_pattern = (
        r'^(?P<test_name>[A-Za-z][A-Za-z0-9\s,\-#%\']+?)\s+'
        r'(?P<value>[\d.]+)\s+'
        r'(?P<ref_range>[\d.\-]+(?:\s*-\s*[\d.]+)?)\s+'
        r'(?P<method>[A-Z][A-Z\s&]+?)\s+'
        r'(?P<date>\d{2}/\d{2}/\d{4})\s+'
        r'(?P<location>MONUMENT)'
    )

    # Alternative simpler pattern for when method is complex/multiline
    simple_row_pattern = (
        r'^(?P<test_name>[A-Za-z][A-Za-z0-9\s,\-#%\']+?)\s+'
        r'(?P<value>[\d.]+)\s+'
        r'(?P<ref_range>[\d.\-]+(?:\s*-\s*[\d.]+)?)\s+'
        r'.*?'
        r'(?P<date>\d{2}/\d{2}/\d{4})\s+'
        r'(?P<location>MONUMENT)'
    )

    # Skip lines that are headers or metadata
    skip_patterns = [
        r'^Ref\s+Analysis',
        r'^Component\s+Value',
        r'^Specimen\s+\(Source\)',
        r'^Anatomical Location',
        r'^Narrative',
        r'^Authorizing Provider',
        r'^Performing Organization',
        r'^Blood\s+Venous',
        r'^Collection Method',
    ]

    def __init__(self):
        self._skip_compiled = [re.compile(p, re.IGNORECASE) for p in self.skip_patterns]

    def should_skip_line(self, line: str) -> bool:
        """Check if line should be skipped."""
        for pattern in self._skip_compiled:
            if pattern.match(line.strip()):
                return True
        return False

    def extract_results(self, text: str, source_filename: str) -> Generator[LabResult, None, None]:
        """Extract lab results from Monument page text."""
        # Get header date
        header_date = self.extract_date(text)

        # Get page marker
        page_marker = self.extract_page_marker(text)

        # Check for (ABNORMAL) prefix in the entire text
        has_abnormal = '(ABNORMAL)' in text.upper()

        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty lines and headers
            if not line or self.should_skip_line(line):
                i += 1
                continue

            # Try main pattern first
            match = re.match(self.row_pattern, line, re.IGNORECASE)
            if not match:
                # Try simpler pattern
                match = re.match(self.simple_row_pattern, line, re.IGNORECASE)

            if match:
                test_name = match.group('test_name')
                value = match.group('value')
                ref_range = match.group('ref_range')
                row_date = match.group('date')

                # Look for unit on the next line
                unit = ""
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    # Unit patterns like "mg/dL", "pg/mL", etc.
                    unit_match = re.match(r'^([a-zA-Z/%]+(?:/[a-zA-Z]+)?)\s', next_line)
                    if unit_match:
                        unit = unit_match.group(1)

                # Determine if this result is flagged
                flag = ""
                if has_abnormal:
                    # Check if this specific test might be abnormal
                    # This is a simple heuristic - could be improved
                    flag = "A"  # Abnormal marker

                result = LabResult(
                    source=source_filename,
                    facility=self.name,
                    test_name=self.normalize_test_name(test_name),
                    test_date=row_date or header_date,
                    value=self.normalize_value(value),
                    ref_range=self.normalize_ref_range(ref_range),
                    unit=unit,
                    flag=flag,
                    page_marker=page_marker,
                )
                yield result

            i += 1
