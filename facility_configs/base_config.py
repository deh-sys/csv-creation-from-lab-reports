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
    panel_name: str = ""      # Test panel (e.g., "CMP", "CBC", "Lipid Panel")
    component: str = ""       # Individual measurement within the panel
    test_date: str = ""
    value: str = ""
    ref_range: str = ""
    unit: str = ""
    flag: str = ""
    page_marker: str = ""
    result_type: str = "Chemistry"
    narrative: str = ""

    def to_dict(self) -> dict:
        return {
            'source': self.source,
            'facility': self.facility,
            'panel_name': self.panel_name,
            'component': self.component,
            'test_date': self.test_date,
            'value': self.value,
            'ref_range': self.ref_range,
            'unit': self.unit,
            'flag': self.flag,
            'page_marker': self.page_marker,
            'result_type': self.result_type,
            'narrative': self.narrative,
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

    # Standard Panel Name Mappings
    # Key = Standardized Name
    # Value = List of regex patterns to match against the raw panel name
    PANEL_MAPPINGS = {
        'Comprehensive Metabolic Panel (CMP)': [
            r'Comprehensive\s*Metabolic',
            r'^CMP',
            r'ABNORMAL_COMPREHENSIVE_METABOLIC',
        ],
        'Complete Blood Count (CBC)': [
            r'^CBC',
            r'ABNORMAL_CBC',
        ],
        'Lipid Panel': [
            r'Lipid\s*Panel',
        ],
        'Thyroid Stimulating Hormone (TSH)': [
            r'^TSH',
        ],
        'Urinalysis (UA)': [
            r'LABS-UA',
            r'URINALYSIS',
        ],
        'Iron Panel': [
            r'LABS-IRON',
        ],
        'Vitamin B12 and Folate': [
            r'Vitamin\s*B12\s*and\s*Folate',
        ],
        'Vitamin B12 (Cobalamin)': [
            r'VITAMIN\s*B12',
        ],
        'Serum Protein Electrophoresis (SPEP)': [
            r'PROTEIN\s*ELECTROPHORESIS',
        ],
        'Parathyroid Hormone (PTH)': [
            r'^PTH',
        ],
        'Hemoglobin A1c (HbA1c)': [
            r'^A1C',
        ],
    }

    # Standard Component Name Mappings
    COMPONENT_MAPPINGS = {
        'Albumin': [r'^ALB(UMIN)?(\s+SPEP)?$'],
        'Alkaline Phosphatase (ALP)': [r'^AL(KP|KALINE)(\s+Phosphatase)?$'],
        'Alanine Aminotransferase (ALT)': [
            r'^ALT(\s+\(SGPT\))?.*$',
            r'^ALT.*$',
        ],
        'Aspartate Aminotransferase (AST)': [
            r'^AST.*$',
        ],
        'Basophils Absolute': [r'^BASO\s*#$'],
        'Basophils %': [r'^BASO(PHILS)?\s*%?,?$'],
        'Total Bilirubin': [r'^(TBIL|BILIRUBIN,\s*TOTAL|Total\s+Bilirubin)$'],
        'Blood Urea Nitrogen (BUN)': [r'^BUN(\s+\d+)?$'],
        'Calcium': [r'^(CA|CALCIUM)$'],
        'Chloride': [r'^(CHLORIDE|Cl-)$'],
        'Total Cholesterol': [r'^(CHOL(ESTEROL)?)$'],
        'Carbon Dioxide (CO2)': [r'^CO2$'],
        'Calcium, Corrected': [r'^(CORR\s+CA|Corrected\s+Calcium)$'],
        'Creatinine': [r'^(CREA|CREATININE)$'],
        'Creatinine, Urine 24H': [r'^Creatinine,\s*24H\s*Ur$'],
        'Estimated Average Glucose (eAG)': [r'^EAG$'],
        'Eosinophils Absolute': [r'^EOS\s*#$'],
        'Eosinophils %': [r'^EOS(INOPHILS)?\s*%?,?$'],
        'Iron (Fe)': [r'^FE$'],
        'Folate': [r'^FOLAT$'],
        'Glucose': [r'^GLU(COSE)?(,\s*RANDOM)?$'],
        'Hematocrit (Hct)': [r'^(HCT|HEMATOCRIT)(,\s*AUTO)?$'],
        'HDL Cholesterol': [r'^d?HDL$'],
        'Hemoglobin (Hgb)': [r'^HGB|Hemoglobin$'],
        'Immature Granulocytes Absolute': [r'^IG\s*#$'],
        'Immature Granulocytes %': [r'^IMMATURE\s+GRAN\s*%$'],
        'Calcium, Ionized': [r'^IONIZED\s+CALCIUM$'],
        'Potassium': [r'^(K\+|POTASSIUM)$'],
        'LDL Cholesterol': [r'^LDL(\s+(DIRECT|CALCULATED))?$'],
        'Lymphocytes Absolute': [r'^LYMPH\s*#$'],
        'Lymphocytes %': [r'^LYMPH(OCYTES)?\s*%?,?$'],
        'Mean Corpuscular Hemoglobin (MCH)': [r'^MCH$'],
        'Mean Corpuscular Hemoglobin Concentration (MCHC)': [r'^MCHC$'],
        'Mean Corpuscular Volume (MCV)': [r'^MCV$'],
        'Monocytes Absolute': [r'^MONO\s*#$'],
        'Monocytes %': [r'^MONO(CYTES)?\s*%?,?$'],
        'Mean Platelet Volume (MPV)': [r'^MPV$'],
        'Sodium': [r'^(NA\+|SODIUM)$'],
        'Neutrophils Absolute': [r'^NEUT\s*#$'],
        'Neutrophils %': [r'^NEUT(ROPHILS)?\s*%?,?$'],
        'Platelet Count': [r'^(PLT|PLATELETS(,\s*AUTOMATED)?)$'],
        'Total Protein': [r'^(TP|TOTAL\s+PROTEIN|PROTEIN\s+TOTAL)$'],
        'Parathyroid Hormone (PTH), Intact': [r'^PTH(\s+INTACT)?$'],
        'Red Blood Cell Count (RBC)': [r'^RBC(,\s*AUTO)?$'],
        'Red Cell Distribution Width (RDW)': [r'^RDW(,\s*BLOOD)?.*$', r'^RDW,\s*RATIO.*$'],
        'Total Iron Binding Capacity (TIBC)': [r'^TIBC$'],
        'Triglycerides': [r'^TRIG(LYCERIDE)?$'],
        'Thyroid Stimulating Hormone (TSH)': [r'^TSH$'],
        'Vitamin B12': [r'^VIT(AMIN)?\s*B12$'],
        'White Blood Cell Count (WBC)': [r'^(WBC|WBC\'S)(,?\s*AUTO)?$'],
        'Hemoglobin A1c (HbA1c)': [r'^(d%A1c|A1C)$'],
        'Anion Gap': [r'^Anion\s+Gap$'],
        'Lipase': [r'^Lipase$'],
        'Magnesium': [r'^Magnesium$'],
        'Phosphorus': [r'^Phosphorus$'],
        'Urine pH': [r'^(F\s+)?U\s+PH|PH,\s+UA$'],
        'Calcium, Urine': [r'^Calcium,\s*Urine$'],
        'Glucose, Urine': [r'^GLUCOSE,\s+UA$'],
        'Specific Gravity, Urine': [r'^SPECIFIC\s+GRAVITY,\s+UA$'],
        'Protein, Urine': [r'^PROTEIN,\s+UA$'],
        'Ketones, Urine': [r'^KETONES,\s+UA|KET$'],
        'Bilirubin, Urine': [r'^BILIRUBIN,\s+UA$'],
        'Urobilinogen, Urine': [r'^UROBILINOGEN,.*$'],
        'Nitrite, Urine': [r'^NITRITE,\s+UA$'],
        'Leukocyte Esterase, Urine': [r'^LEUKOCYTE\s+ESTERASE,.*$'],
        'Blood, Urine': [r'^UA\s+HGB$'],
        'Mucus, Urine': [r'^MUCUS,\s+URINE$'],
        'Granulocytes %': [r'^GRANULOCYTES\s*%,.*$'],
        'Granulocytes': [r'^GRANULOCYTES$'],
        'Monocytes %': [r'^MONO(CYTES|S)?\s*%?(,?\s*AUTO)?.*$'],
        'Immature Granulocytes %': [r'^(IMMATURE|IMMATURE\s+GRAN\s*%)$'],
        'WBC, Urine': [r'^WBC,\s*Urine.*$'],
        'Urine pH': [r'^(F\s+)?U\s+PH|PH,\s+(UA|Urine)$'],
    }

    def matches_filename(self, filename: str) -> bool:
        """Check if this config should handle the given filename."""
        for pattern in self.filename_patterns:
            if re.search(pattern, filename, re.IGNORECASE):
                return True
        return False

    def normalize_panel_name(self, raw_name: str) -> str:
        """
        Normalize standard panel names (e.g., 'CMP (Complete...)' -> 'CMP').
        """
        if not raw_name:
            return ""
        
        raw_clean = raw_name.strip()
        
        for standard_name, patterns in self.PANEL_MAPPINGS.items():
            for pattern in patterns:
                if re.search(pattern, raw_clean, re.IGNORECASE):
                    return standard_name
                    
        # Return Title Case if no match found (cleans up ALL CAPS)
        if raw_clean.isupper():
            return raw_clean.title()
            
        return raw_clean

    def normalize_component_name(self, raw_name: str) -> str:
        """
        Normalize standard component names (e.g., 'WBC, AUTO' -> 'White Blood Cell Count (WBC)').
        """
        if not raw_name:
            return ""
        
        # Basic cleanup first
        clean_name = self.normalize_test_name(raw_name)
        
        for standard_name, patterns in self.COMPONENT_MAPPINGS.items():
            for pattern in patterns:
                if re.search(pattern, clean_name, re.IGNORECASE):
                    return standard_name
        
        # Return original cleaned name if no match
        return clean_name

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
