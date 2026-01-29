"""
Configuration for MHB/Monument Health lab reports.
These PDFs are image-based (require OCR) with structured format.

Panel structure:
  PHOSPHORUS- Final result (08/18/2025 9:19 AM MDT)    <- Panel header
  Component Value Range ...
  Phosphorus 28 2.5-4.9 SPECTROPHOTOMETRY 08/18/2025 MONUMENT

Sample row formats (after OCR):
  Phosphorus 28 2.5-4.9 SPECTROPHOTOMETRY 08/18/2025 MONUMENT
  Creatinine 1.01 0.60 - SPECTROPHOTOMETRY 08/18/2025 MONUMENT  <- partial ref range
  1.10 MG/DL ...  <- continuation with ref range end and unit

Pattern notes:
  - Panel name appears in first line header before "- Final result"
  - Component name, value, ref range, method, date, location
  - Reference ranges may be split across lines (e.g., "0.60 -" on one line, "1.10" on next)
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

    # Pattern 1: Complete ref range on same line
    # e.g., "Phosphorus 28 2.5-4.9 SPECTROPHOTOMETRY 08/18/2025 MONUMENT"
    # Note: [=\s]* handles OCR artifacts like "=" between method and date
    pattern_complete = (
        r'^(?P<component>[A-Za-z][A-Za-z0-9\s,\(\)]+?)\s+'
        r'(?P<value>[\d.]+)\s+'
        r'(?P<ref_range>[\d.]+\s*-\s*[\d.]+)\s+'
        r'(?P<method>[A-Z][A-Z\s&]+?)\s*[=\s]*'
        r'(?P<date>\d{2}/\d{2}/\d{4})\s+'
        r'(?P<location>MONUMENT)'
    )

    # Pattern 2: Partial ref range (ends with -)
    # e.g., "Creatinine 1.01 0.60 - SPECTROPHOTOMETRY 08/18/2025 MONUMENT"
    # Note: [=\s]* handles OCR artifacts like "=" between method and date
    pattern_partial_ref = (
        r'^(?P<component>[A-Za-z][A-Za-z0-9\s,\(\)]+?)\s+'
        r'(?P<value>[\d.]+)\s+'
        r'(?P<ref_start>[\d.]+)\s*-\s*'
        r'(?P<method>[A-Z][A-Z\s&]+?)\s*[=\s]*'
        r'(?P<date>\d{2}/\d{2}/\d{4})\s+'
        r'(?P<location>MONUMENT)'
    )

    # Pattern 3: Simpler pattern as fallback
    # Matches: "Hemoglobin 13.9 11.5-15.5 SPECTROPHOTOMETRY..."
    # or "Hemoglobin 13.9 11.5 15.5 SPECTROPHOTOMETRY..." (missing hyphen)
    pattern_simple = (
        r'^(?P<component>[A-Za-z][A-Za-z0-9\s,\(\)]+?)\s+'
        r'(?P<value>[\d.]+)\s+'
        r'(?P<ref_range>[<>]?[\d.\-\s]+?)\s+'
        r'(?P<method>[A-Z][A-Z\s&]+?)\s+'
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
        r'^MONUMENT\s+HEALTH',
        r'^\d{2}/\d{2}/\d{4}',  # Lines starting with date
    ]

    def __init__(self):
        self._skip_compiled = [re.compile(p, re.IGNORECASE) for p in self.skip_patterns]

    def should_skip_line(self, line: str) -> bool:
        """Check if line should be skipped."""
        line = line.strip()
        if len(line) < 5:
            return True
        for pattern in self._skip_compiled:
            if pattern.match(line):
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
        raw_panel_name = self.extract_panel_name(text)
        panel_name = self.normalize_panel_name(raw_panel_name)

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

            component = None
            value = None
            ref_range = ""
            row_date = None
            unit = ""
            flag = ""

            # Try Pattern 1: Complete ref range
            match = re.match(self.pattern_complete, line, re.IGNORECASE)
            if match:
                component = match.group('component')
                value = match.group('value')
                ref_range = match.group('ref_range')
                row_date = match.group('date')

            # Try Pattern 2: Partial ref range (continues on next line)
            if not match:
                match = re.match(self.pattern_partial_ref, line, re.IGNORECASE)
                if match:
                    component = match.group('component')
                    value = match.group('value')
                    ref_start = match.group('ref_start')
                    row_date = match.group('date')

                    # Look for ref range end on next line
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        # Look for number at start of next line (ref range end)
                        ref_end_match = re.match(r'^([\d.]+)', next_line)
                        if ref_end_match:
                            ref_range = f"{ref_start}-{ref_end_match.group(1)}"
                            # Also check for unit on same line
                            unit_match = re.search(r'([a-zA-Z]+/[a-zA-Z0-9]+|[a-zA-Z]+%|U/L|MG/DL|MMOL/L|g/dL|mg/dL)', next_line, re.IGNORECASE)
                            if unit_match:
                                unit = unit_match.group(1)
                        else:
                            ref_range = f"{ref_start}-"
                    else:
                        ref_range = f"{ref_start}-"

            # Try Pattern 3: Simple fallback
            if not match:
                match = re.match(self.pattern_simple, line, re.IGNORECASE)
                if match:
                    component = match.group('component')
                    value = match.group('value')
                    ref_range = match.group('ref_range')
                    row_date = match.group('date')

            # If we found a match, create result
            if component and value:
                # Look for unit if not already found
                if not unit and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    unit_match = re.match(r'^([a-zA-Z]+/[a-zA-Z0-9]+|[a-zA-Z]+%|U/L)', next_line, re.IGNORECASE)
                    if unit_match:
                        unit = unit_match.group(1)

                # Check for flag markers like (H) or (L) in the line
                if '(H)' in line:
                    flag = 'H'
                elif '(L)' in line:
                    flag = 'L'
                elif has_abnormal:
                    flag = 'A'

                result = LabResult(
                    source=source_filename,
                    facility=self.name,
                    panel_name=panel_name,
                    component=self.normalize_component(component),
                    test_date=row_date or header_date,
                    value=self.normalize_value(value),
                    ref_range=self.normalize_ref_range(ref_range),
                    unit=unit,
                    flag=flag,
                    page_marker=page_marker,
                )
                yield result

            i += 1

    def normalize_component(self, name: str) -> str:
        """Clean up component name."""
        # Remove (H) or (L) flags from name
        name = re.sub(r'\s*\([HL]\)\s*', ' ', name)
        return ' '.join(name.split())

    def normalize_ref_range(self, ref_range: str) -> str:
        """Clean up reference range string."""
        ref_range = ref_range.strip()
        # Fix common OCR errors in ref ranges
        # e.g., "321" should probably be "3-11"
        # This is tricky - we can't always know what the correct value is
        return ref_range
