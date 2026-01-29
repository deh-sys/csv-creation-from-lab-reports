Project Spec: Regex-Based Medical Record Parser
Goal: Create a Python script to extract structured lab data from searchable PDFs into a CSV. Constraint: Use Regex and spatial logic only (No AI/LLM API calls). The script must be modular so I can easily swap out Regex patterns for different medical facilities.

1. Technical Environment
Language: Python 3.14

Primary Library: pdfplumber (Already installed).

Why: It allows extracting text and spatial coordinates (x,y), which is crucial for distinguishing the "Body" (lab results) from the "Footer" (Bates stamps).

Output: csv (Standard library) or pandas (if available).

2. The Script Architecture (Instruction to Coder)
Structure the script with a clear Configuration Section at the top. I need to be able to tweak these patterns without rewriting the whole logic.

A. Configuration Class (LabPatternConfig) Create a class or dictionary that defines:

Bates_Pattern: Regex to find the Bates stamp (e.g., r'[A-Z]{3}\d{5}').

Header_Date_Pattern: Regex to find the "Collection Date" or "Report Date" usually found at the top of the page.

Row_Pattern: The complex Regex that identifies a data line. It needs named groups.

Example Target: Glucose 85 mg/dL 70-100

Example Regex: r'(?P<test_name>[\w\s]+?)\s+(?P<value>[\d\.<>]+)\s+(?P<unit>[a-zA-Z/%]+)\s+(?P<ref_range>[\d\.-]+)'

Bates_Zone: A coordinate box for the "Bottom Right" (e.g., x > page_width * 0.7 and y > page_height * 0.9).

B. The Logic Flow

Iterate through all PDFs in a target folder.

Process per Page:

Extract Bates: Use pdfplumber to crop the bottom-right footer area. Apply Bates_Pattern. If found, store it; if not, assume it continues from the previous page or mark as "Unknown".

Extract Header Info: Crop the top 20% of the page. Apply Header_Date_Pattern to find the test_date. Keep this date for all rows found on this page.

Extract Body Rows: Crop the middle section (exclude header/footer). Extract text line-by-line.

Apply Row Regex: Test every line against Row_Pattern.

If it matches: Extract test_name, value, unit, ref_range, flag.

Append source_filename, bates_stamp, and facility_name (derived from filename or config).

Save: Write row to CSV.

3. Required CSV Columns
Ensure the output CSV has exactly these headers: source, test_name, test_date, component, value, ref_range, unit, flag, bates

4. Special Instructions for the AI Coder
"Write the Row_Pattern regex to be resilient to extra whitespace."

"Include a try/except block. If a line looks like data but fails the regex, log it to a missed_lines.txt file so I can inspect what patterns I missed."

"Since flag (High/Low) is often a separate column that might be empty, make the flag regex group optional."

How to "Tweak" This for New Records
When you get a new set of records from a different hospital:

Open the PDF and copy 3-4 lines of the lab results (e.g., "Sodium ... 138 ... 135-145").

Paste them into Manus/Claude.

Prompt: "Here are 3 lines of text from a new PDF. The format is [Test Name] [Value] [Units] [Range]. Write a Python Regex with named groups to capture these fields."

Copy the resulting Regex and paste it into the Row_Pattern variable in your script.