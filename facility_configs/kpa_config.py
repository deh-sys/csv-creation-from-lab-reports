"""
Configuration for KPA/Kaiser lab reports.
These PDFs are image-based (require OCR) with complex multi-line format.

Panel structure:
  LIPID PANEL (LIPID PANEL (CHOL, TRIG, DHDL, CALC LDL)) - Final result (08/06/2021 5:16 PM EDT)
  Component Value Range ...
  CHOLESTEROL 195 0-199 08/06/2021 KAISER

Sample row formats (after OCR):
  CHOLESTEROL 195 0-199 08/06/2021 KAISER
  TSH 2.03 0.35 - 02/07/2022 GA
  HDL TES 39.0 - 08/06/2021 KAISER
  92.0 mg/dL ...  <- ref range continues on next line

Pattern notes:
  - Panel name appears in first line header before "- Final result"
  - Component name followed by value, partial ref range, date, and location
  - Reference range may span multiple lines
  - Unit often appears on continuation line
  - Location can be KAISER, GA, etc.
"""

import re
from typing import Generator

from .base_config import FacilityConfig, LabResult


class KPAConfig(FacilityConfig):
    """Configuration for Kaiser/KPA facility lab reports."""

    name = "Kaiser"
    filename_patterns = [
        r'--Kaiser\.pdf$',
        r'--KPA\.pdf$',
    ]
    requires_ocr = True

    # Date extracted from the header: "Final result (08/06/2021 5:16 PM EDT)"
    date_pattern = r'Final result\s*\((?P<date>\d{2}/\d{2}/\d{4})'

    # Panel name pattern: "LIPID PANEL (LIPID PANEL...) - Final result" or "TSH (THYROID...) - Final result"
    panel_pattern = r'^([A-Z][A-Z0-9\s,]+?)(?:\s*\([^)]*\))?\s*-\s*Final result'

    # Page marker: KPA 45
    page_marker_pattern = r'^KPA\s+\d+\s*$'

    # Result line patterns (flexible to handle OCR variations)
    # Pattern 1: Full line with complete ref range
    # CHOLESTEROL 195 0-199 08/06/2021 KAISER
    pattern_full = (
        r'^(?P<component>[A-Z][A-Z0-9\s,\'\-]+?)\s+'
        r'(?P<value>[\d.]+)\s+'
        r'(?P<ref_range>[\d.]+\s*-\s*[\d.]+)\s+'
        r'(?P<date>\d{2}/\d{2}/\d{4})\s+'
        r'(?P<location>KAISER|GA|REGIONAL)'
    )

    # Pattern 2: Line with partial ref range (continues on next line)
    # TSH 2.03 0.35 - 02/07/2022 GA
    # or: HDL TES 39.0 - 08/06/2021 KAISER
    pattern_partial_ref = (
        r'^(?P<component>[A-Z][A-Z0-9\s,\'\-]+?)\s+'
        r'(?P<value>[\d.]+)\s+'
        r'(?P<ref_start>[\d.]+)\s*-\s*'
        r'(?P<date>\d{2}/\d{2}/\d{4})\s+'
        r'(?P<location>KAISER|GA|REGIONAL)'
    )

    # Pattern 3: Simple pattern - component name, value, and date (no ref range on same line)
    pattern_simple = (
        r'^(?P<component>[A-Z][A-Z0-9\s,\'\-]+?)\s+'
        r'(?P<value>[\d.]+)\s+'
        r'(?P<date>\d{2}/\d{2}/\d{4})\s+'
        r'(?P<location>KAISER|GA|REGIONAL)'
    )

    # Skip lines that are comments or interpretive data
    skip_patterns = [
        r'^Comment:',
        r'^Interpretive Data',
        r'^<\d+\s+mg/dL',
        r'^\d+\s*-\s*\d+\s+mg/dL',
        r'^>\d+\s+mg/dL',
        r'^Ref\s+Analysis',
        r'^Component\s+Value',
        r'^Specimen\s+\(Source\)',
        r'^Anatomical Location',
        r'^Narrative',
        r'^Authorizing Provider',
        r'^Performing Organization',
        r'^SERUM',
        r'^PLASMA',
        r'^Blood',
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
            # Clean up the panel name
            return panel
        return ""

    def extract_results(self, text: str, source_filename: str) -> Generator[LabResult, None, None]:
        """Extract lab results from Kaiser page text."""
        # Get header date
        header_date = self.extract_date(text)

        # Get page marker
        page_marker = self.extract_page_marker(text)

        # Get panel name from header
        panel_name = self.extract_panel_name(text)

        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Skip empty or irrelevant lines
            if not line or self.should_skip_line(line):
                i += 1
                continue

            component = None
            value = None
            ref_range = ""
            row_date = None
            unit = ""

            # Try Pattern 1: Full ref range on same line
            match = re.match(self.pattern_full, line, re.IGNORECASE)
            if match:
                component = match.group('component')
                value = match.group('value')
                ref_range = match.group('ref_range')
                row_date = match.group('date')

            # Try Pattern 2: Partial ref range (start only)
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
                        # Look for number at start of next line
                        ref_end_match = re.match(r'^([\d.]+)', next_line)
                        if ref_end_match:
                            ref_range = f"{ref_start}-{ref_end_match.group(1)}"
                            # Also check for unit on same line
                            unit_match = re.search(r'([a-zA-Z]+/[a-zA-Z]+|[a-zA-Z]+%|ulU/ml|mg/dL|g/dL|IU/L|K/uL|M/uL)', next_line, re.IGNORECASE)
                            if unit_match:
                                unit = unit_match.group(1)
                    else:
                        ref_range = f"{ref_start}-"

            # Try Pattern 3: Simple (no ref range on line)
            if not match:
                match = re.match(self.pattern_simple, line, re.IGNORECASE)
                if match:
                    component = match.group('component')
                    value = match.group('value')
                    row_date = match.group('date')

            # If we found a match, create result
            if component and value:
                # Look for unit if not already found
                if not unit and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    unit_match = re.match(r'^([a-zA-Z]+/[a-zA-Z]+|[a-zA-Z]+%)', next_line)
                    if unit_match:
                        unit = unit_match.group(1)

                result = LabResult(
                    source=source_filename,
                    facility=self.name,
                    panel_name=panel_name,
                    component=self.normalize_component(component),
                    test_date=row_date or header_date,
                    value=self.normalize_value(value),
                    ref_range=self.normalize_ref_range(ref_range),
                    unit=unit,
                    flag="",
                    page_marker=page_marker,
                )
                yield result

            i += 1

    def normalize_component(self, name: str) -> str:
        """Clean up component name."""
        # Remove trailing TES if present (OCR artifact)
        name = re.sub(r'\s+TES$', '', name)
        return ' '.join(name.split())
