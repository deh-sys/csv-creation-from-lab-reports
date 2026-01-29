"""
Base class for facility configurations.
Each facility (RCMC, Kaiser, Monument) extends this class with specific patterns.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator


@dataclass
class LabResult:
    """Represents a single lab test result."""
    source: str = ""
    facility: str = ""
    test_name: str = ""
    test_date: str = ""
    value: str = ""
    ref_range: str = ""
    unit: str = ""
    flag: str = ""
    page_marker: str = ""

    def to_dict(self) -> dict:
        return {
            'source': self.source,
            'facility': self.facility,
            'test_name': self.test_name,
            'test_date': self.test_date,
            'value': self.value,
            'ref_range': self.ref_range,
            'unit': self.unit,
            'flag': self.flag,
            'page_marker': self.page_marker,
        }


class FacilityConfig(ABC):
    """Abstract base class for facility-specific PDF parsing configurations."""

    # Facility identification
    name: str = ""
    filename_patterns: list[str] = field(default_factory=list)

    # OCR requirement
    requires_ocr: bool = False

    # Regex patterns for extraction
    date_pattern: str = ""
    row_pattern: str = ""
    page_marker_pattern: str = ""

    def matches_filename(self, filename: str) -> bool:
        """Check if this config should handle the given filename."""
        for pattern in self.filename_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                return True
        return False

    def extract_date(self, text: str) -> str:
        """Extract the collection/test date from page text."""
        if not self.date_pattern:
            return ""
        match = re.search(self.date_pattern, text, re.IGNORECASE)
        if match:
            # Try to get named group 'date', otherwise return full match
            try:
                return match.group('date')
            except IndexError:
                return match.group(0)
        return ""

    def extract_page_marker(self, text: str) -> str:
        """Extract the page marker from footer area."""
        if not self.page_marker_pattern:
            return ""
        match = re.search(self.page_marker_pattern, text, re.MULTILINE)
        if match:
            return match.group(0).strip()
        return ""

    @abstractmethod
    def extract_results(self, text: str, source_filename: str) -> Generator[LabResult, None, None]:
        """
        Extract lab results from page text.

        Args:
            text: Full text extracted from a PDF page
            source_filename: Name of the source PDF file

        Yields:
            LabResult objects for each test result found
        """
        pass

    def normalize_test_name(self, name: str) -> str:
        """Clean up test name by removing extra whitespace."""
        return ' '.join(name.split())

    def normalize_value(self, value: str) -> str:
        """Clean up value string."""
        return value.strip()

    def normalize_ref_range(self, ref_range: str) -> str:
        """Clean up reference range string."""
        return ref_range.strip()

    def normalize_unit(self, unit: str) -> str:
        """Clean up unit string."""
        return unit.strip()
