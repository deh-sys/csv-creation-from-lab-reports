"""
Configuration for RCB/RCMC (Rapid City Medical Center) lab reports.
These PDFs have native text (no OCR needed) with a consistent tabular format.

Panel structure:
  CMP (Complete Metabolic Panel)     <- Panel header
  NAME VALUE REFERENCE RANGE         <- Column header
  F CA 10.5 8.7-10.6 (mg/dL)        <- Component result
  F GLU 82 70-100 (mg/dL)           <- Component result

Sample row formats:
  F CA 10.5 8.7-10.6 (mg/dL)
  F RBC 4.09 L 4.20-5.40 (M/uL)  <- with flag
  F d%A1c 4.7 <6.0 (%)           <- lowercase, < in range
  F Calcium, Urine 4.4 Not Estab. (mg/dL)  <- text ref range
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

    # Panel header pattern - matches lines like:
    # "CMP (Complete Metabolic Panel)"
    # "CBC Auto Diff"
    # "A1C"
    # "Lipid Panel"
    # Must be followed by "NAME VALUE" line
    panel_header_pattern = r'^([A-Z][A-Za-z0-9\s,\(\)]+?)(?:\n|\r\n?)NAME\s+VALUE'

    # Row pattern with reference range (most common):
    # F CA 10.5 8.7-10.6 (mg/dL)
    # F IONIZED CALCIUM 1.43 HH 1.12-1.32 (mmol/L)
    row_pattern_with_ref = (
        r'^(?:F\s+)?'
        r'(?P<component>[A-Za-z][A-Za-z0-9+\-#%,\s]+?)\s+'
        r'(?P<value>[\d.,<>]+)\s*'
        r'(?P<flag>[HL]+)?\s+'
        r'(?P<ref_range>[^\(\n]+?)\s*'
        r'\((?P<unit>[^)]+)\)'
    )

    # Row pattern with reference range but NO unit (e.g., RATIO)
    # F RATIO 1.7 0.0-6.7
    row_pattern_no_unit = (
        r'^(?:F\s+)?'
        r'(?P<component>[A-Za-z][A-Za-z0-9+\-#%,\s]+?)\s+'
        r'(?P<value>[\d.,<>]+)\s*'
        r'(?P<flag>[HL]+)?\s+'
        r'(?P<ref_range>[\d.\-<>]+(?:-[0-9.]+)?)\s*$'
    )

    # Row pattern without reference range (e.g., F EAG 89 (mg/dL))
    row_pattern_no_ref = (
        r'^(?:F\s+)?'
        r'(?P<component>[A-Za-z][A-Za-z0-9+\-#%,\s]+?)\s+'
        r'(?P<value>[\d.,<>]+)\s*'
        r'\((?P<unit>[^)]+)\)'
    )

    # Row pattern with loose unit (not in parens), e.g. "50,000 CFU/ml"
    row_pattern_loose_unit = (
        r'^(?:F\s+)?'
        r'(?P<component>[A-Za-z][A-Za-z0-9+\-#%,\s]+?)\s+'
        r'(?P<value>[\d.,<>]+)\s+'
        r'(?P<unit>[^\s\(\)]+)'
    )

    def extract_panel_name(self, text: str) -> str:
        """Extract the panel/test name from header area."""
        match = re.search(self.panel_header_pattern, text, re.MULTILINE | re.IGNORECASE)
        if match:
            panel = match.group(1).strip()
            # Clean up the panel name
            return panel
        return ""

    def extract_results(self, text: str, source_filename: str) -> Generator[LabResult, None, None]:
        """Extract lab results from RCMC page text."""
        # Get collection date for the page
        test_date = self.extract_date(text)

        # Get page marker
        page_marker = self.extract_page_marker(text)

        # Get panel name from header
        raw_panel_name = self.extract_panel_name(text)
        panel_name = self.normalize_panel_name(raw_panel_name)

        # Track which lines we've matched to avoid duplicates
        matched_lines = set()

        # First pass: try pattern with reference range
        for match in re.finditer(self.row_pattern_with_ref, text, re.MULTILINE | re.IGNORECASE):
            line_start = match.start()
            matched_lines.add(line_start)

            result = LabResult(
                source=source_filename,
                facility=self.name,
                panel_name=panel_name,
                component=self.normalize_component_name(match.group('component')),
                test_date=test_date,
                value=self.normalize_value(match.group('value')),
                ref_range=self.normalize_ref_range(match.group('ref_range')),
                unit=self.normalize_unit(match.group('unit')),
                flag=match.group('flag') or "",
                page_marker=page_marker,
            )
            yield result

        # Second pass: try pattern with ref range but NO unit
        for match in re.finditer(self.row_pattern_no_unit, text, re.MULTILINE | re.IGNORECASE):
            line_start = match.start()
            if line_start in matched_lines:
                continue

            matched_lines.add(line_start)
            result = LabResult(
                source=source_filename,
                facility=self.name,
                panel_name=panel_name,
                component=self.normalize_component_name(match.group('component')),
                test_date=test_date,
                value=self.normalize_value(match.group('value')),
                ref_range=self.normalize_ref_range(match.group('ref_range')),
                unit="",  # No unit
                flag=match.group('flag') or "",
                page_marker=page_marker,
            )
            yield result

        # Third pass: try pattern without reference range for unmatched lines
        for match in re.finditer(self.row_pattern_no_ref, text, re.MULTILINE | re.IGNORECASE):
            line_start = match.start()
            if line_start in matched_lines:
                continue  # Already matched by first pattern

            result = LabResult(
                source=source_filename,
                facility=self.name,
                panel_name=panel_name,
                component=self.normalize_component_name(match.group('component')),
                test_date=test_date,
                value=self.normalize_value(match.group('value')),
                ref_range="",  # No reference range
                unit=self.normalize_unit(match.group('unit')),
                flag="",  # No flag without ref range
                page_marker=page_marker,
            )
            yield result

        # Fourth pass: try pattern with loose unit (no parens)
        for match in re.finditer(self.row_pattern_loose_unit, text, re.MULTILINE | re.IGNORECASE):
            line_start = match.start()
            if line_start in matched_lines:
                continue

            result = LabResult(
                source=source_filename,
                facility=self.name,
                panel_name=panel_name,
                component=self.normalize_component_name(match.group('component')),
                test_date=test_date,
                value=self.normalize_value(match.group('value')),
                ref_range="",  # No reference range
                unit=self.normalize_unit(match.group('unit')),
                flag="",  # No flag
                page_marker=page_marker,
            )
            yield result
