"""
Configuration for MHB/Monument Health lab reports.
These PDFs are image-based (require OCR) with structured format.

Panel structure:
  PHOSPHORUS- Final result (08/18/2025 9:19 AM MDT)    <- Panel header
  Component Value Range ...
  Phosphorus 28 2.5-4.9 SPECTROPHOTOMETRY 08/18/2025 MONUMENT

Sample row format (after OCR):
  Phosphorus 28 2.5-4.9 SPECTROPHOTOMETRY 08/18/2025 MONUMENT
  mg/dL AND POTENTIOMETRY 10:34AM HEALTH

Pattern notes:
  - Panel name appears in first line header before "- Final result"
  - Component name, value, ref range, method, date, location
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

    # Panel name pattern: "PHOSPHORUS- Final result" or "MAGNESIUM- Final result"
    panel_pattern = r'^([A-Z][A-Z0-9\s,]+?)\s*-\s*Final result'

    # Page marker: MHB 11 or MBB 12 (OCR sometimes misreads)
    page_marker_pattern = r'^M[HB]B\s+\d+\s*$'

    # Row pattern for Monument results
    # Format: COMPONENT VALUE REF_RANGE METHOD DATE LOCATION
    # Note: Method is all caps like SPECTROPHOTOMETRY, IMMUNOASSAY, etc.
    row_pattern = (
        r'^(?P<component>[A-Za-z][A-Za-z0-9\s,\-#%\']+?)\s+'
        r'(?P<value>[\d.]+)\s+'
        r'(?P<ref_range>[\d.\-]+(?:\s*-\s*[\d.]+)?)\s+'
        r'(?P<method>[A-Z][A-Z\s&]+?)\s+'
        r'(?P<date>\d{2}/\d{2}/\d{4})\s+'
        r'(?P<location>MONUMENT)'
    )

    # Alternative simpler pattern for when method is complex/multiline
    simple_row_pattern = (
        r'^(?P<component>[A-Za-z][A-Za-z0-9\s,\-#%\']+?)\s+'
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

    def extract_panel_name(self, text: str) -> str:
        """Extract the panel/test name from header."""
        match = re.search(self.panel_pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            panel = match.group(1).strip()
            return panel
        return ""

    def extract_results(self, text: str, source_filename: str) -> Generator[LabResult, None, None]:
        """Extract lab results from Monument page text."""
        # Get header date
        header_date = self.extract_date(text)

        # Get page marker
        page_marker = self.extract_page_marker(text)

        # Get panel name from header
        panel_name = self.extract_panel_name(text)

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
                component = match.group('component')
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
                    flag = "A"  # Abnormal marker

                result = LabResult(
                    source=source_filename,
                    facility=self.name,
                    panel_name=panel_name,
                    component=self.normalize_test_name(component),
                    test_date=row_date or header_date,
                    value=self.normalize_value(value),
                    ref_range=self.normalize_ref_range(ref_range),
                    unit=unit,
                    flag=flag,
                    page_marker=page_marker,
                )
                yield result

            i += 1
