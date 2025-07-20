import os
import json
import re

# --- Configuration ---
DATA_DIR = "/home/Comptroller_and_Auditor_General/data_md"
OUTPUT_DIR = "/home/Comptroller_and_Auditor_General/proper_md_json"

# --- Helper Functions ---
def table_to_html(table_lines):
    """Converts a markdown table (list of strings) to an HTML string."""
    html = "<table>"
    for i, line in enumerate(table_lines):
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        tag = "td"
        html += "<tr>"
        for cell in cells:
            html += f"<{tag}>{cell}</{tag}>"
        html += "</tr>"
    html += "</table>"
    return html

def extract_metadata_from_lines(lines):
    """Extracts metadata fields from the top of the markdown file if present as 'Field: Value'."""
    metadata = {
        "document_name": "",
        "document_heading": "",
        "audit_year": "N/A",
        "audit_dates": "N/A",
        "state": "N/A",
        "report_type": "Inspection Report"
    }
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.match(r'^(.*?):\s*(.*)$', line)
        if match:
            key, value = match.group(1).strip().lower(), match.group(2).strip()
            if key == "document name":
                metadata["document_name"] = value
            elif key == "document heading":
                metadata["document_heading"] = value
            elif key == "audit year":
                metadata["audit_year"] = value
            elif key == "audit dates":
                metadata["audit_dates"] = value
            elif key == "state":
                metadata["state"] = value
            elif key == "report type":
                metadata["report_type"] = value
    return metadata

def extract_audit_year_and_state_from_heading(heading):
    audit_years = []
    state = None
    # Find all year patterns like 2023-24, 2023/24, 2022-2023, etc.
    year_matches = re.findall(r'(20\d{2}[\-/][0-9]{2,4})', heading)
    # Also match 'from <Month> <YYYY> to <Month> <YYYY>' or 'for the period from <Month> <YYYY> to <Month> <YYYY>'
    period_match = re.search(r'from\s+([A-Za-z]+)\s+(20\d{2})\s+to\s+([A-Za-z]+)\s+(20\d{2})', heading, re.IGNORECASE)
    if period_match:
        # Add both years
        year1 = period_match.group(2)
        year2 = period_match.group(4)
        year_matches.extend([year1, year2])
    # Also match 'for the period <YYYY> to <YYYY>'
    period_years = re.findall(r'for the period.*?(20\d{2})\s*(?:-|to)\s*(20\d{2})', heading, re.IGNORECASE)
    for y1, y2 in period_years:
        year_matches.extend([y1, y2])
    if year_matches:
        audit_years = list(dict.fromkeys(year_matches))  # Remove duplicates, preserve order
    # Look for state names (add more as needed)
    states = [
        "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Delhi", "Puducherry", "Jammu and Kashmir", "Ladakh"
    ]
    for s in states:
        if s.lower() in heading.lower():
            state = s
            break
    return audit_years, state

def process_markdown_file(doc_path):
    file_id = os.path.splitext(os.path.basename(doc_path))[0]
    with open(doc_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    metadata = extract_metadata_from_lines(lines)
    if not metadata["document_name"]:
        metadata["document_name"] = file_id

    # Find document heading and extract audit year/state if present
    heading_line_idx = None
    detected_state = None
    for idx, line in enumerate(lines):
        if line.strip().startswith('# '):
            heading = line.strip()[2:].strip()
            metadata["document_heading"] = heading
            audit_years, state = extract_audit_year_and_state_from_heading(heading)
            if audit_years:
                if len(audit_years) == 1:
                    metadata["audit_year"] = audit_years[0]
                else:
                    metadata["audit_year"] = audit_years
            if state:
                detected_state = state
            heading_line_idx = idx
            break
    # Set state in metadata: detected from heading or N/A
    metadata["state"] = detected_state if detected_state else "N/A"
    # Find audit dates just below heading, skipping blank lines
    audit_date_line_idx = None
    if heading_line_idx is not None:
        i = heading_line_idx + 1
        while i < len(lines):
            next_line = lines[i].strip()
            if next_line:  # first non-empty line after heading
                # Look for date range pattern or 'date' keyword
                if re.search(r'(\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4})', next_line) or 'date' in next_line.lower():
                    metadata["audit_dates"] = next_line
                    audit_date_line_idx = i
                break
            i += 1

    json_data = {
        "metadata": metadata,
        "parts": []
    }
    current_part = None
    current_section = None
    current_sub_section = None
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # Skip the audit date line if it was extracted for metadata
        if audit_date_line_idx is not None and i == audit_date_line_idx:
            i += 1
            continue
        if not line:
            i += 1
            continue
        # Table HTML block detection (handle nested tables)
        if '<table>' in line:
            table_lines = [line]
            table_open = line.count('<table>')
            table_close = line.count('</table>')
            i += 1
            while i < len(lines):
                table_open += lines[i].count('<table>')
                table_close += lines[i].count('</table>')
                table_lines.append(lines[i].rstrip())
                if table_open > 0 and table_open == table_close:
                    i += 1
                    break
                i += 1
            html_table = '\n'.join(table_lines)
            table_item = {"type": "table", "table": html_table}
            if current_sub_section is not None:
                current_sub_section["content"].append(table_item)
            elif current_section is not None:
                current_section["content"].append(table_item)
            elif current_part is not None:
                if not current_part["sections"]:
                    current_part["sections"].append({"section_title": "General", "content": [], "sub_sections": []})
                current_part["sections"][-1]["content"].append(table_item)
            continue
        if line.startswith('# '):
            # Already handled above for metadata, skip
            i += 1
        elif line.startswith('## '):
            current_part = {"part_title": line[3:].strip(), "sections": []}
            json_data["parts"].append(current_part)
            current_section = None
            current_sub_section = None
            i += 1
        elif line.startswith('### '):
            if current_part is None:
                current_part = {"part_title": "General", "sections": []}
                json_data["parts"].append(current_part)
            current_section = {"section_title": line[4:].strip(), "content": [], "sub_sections": []}
            current_part["sections"].append(current_section)
            current_sub_section = None
            i += 1
        elif line.startswith('#### '):
            if current_section is None:
                if current_part is None:
                    current_part = {"part_title": "General", "sections": []}
                    json_data["parts"].append(current_part)
                current_section = {"section_title": "General", "content": [], "sub_sections": []}
                current_part["sections"].append(current_section)
            current_sub_section = {"sub_section_title": line[5:].strip(), "content": []}
            current_section["sub_sections"].append(current_sub_section)
            i += 1
        elif '|' in line:
            # Markdown table block (as before)
            table_lines = []
            while i < len(lines) and '|' in lines[i]:
                if not re.match(r'^\s*\|(?:\s*:?---:?.*\|)+\s*$', lines[i]):
                    table_lines.append(lines[i].rstrip())
                i += 1
            if table_lines:
                html_table = table_to_html(table_lines)
                table_item = {"type": "table", "table": html_table}
                if current_sub_section is not None:
                    current_sub_section["content"].append(table_item)
                elif current_section is not None:
                    current_section["content"].append(table_item)
                elif current_part is not None:
                    if not current_part["sections"]:
                        current_part["sections"].append({"section_title": "General", "content": [], "sub_sections": []})
                    current_part["sections"][-1]["content"].append(table_item)
        else:
            content_item = {"type": "paragraph", "text": line}
            if current_sub_section is not None:
                current_sub_section["content"].append(content_item)
            elif current_section is not None:
                current_section["content"].append(content_item)
            elif current_part is not None:
                if not current_part["sections"]:
                    current_part["sections"].append({"section_title": "General", "content": [], "sub_sections": []})
                current_part["sections"][-1]["content"].append(content_item)
            else:
                current_part = {"part_title": "General", "sections": []}
                json_data["parts"].append(current_part)
                current_section = {"section_title": "General", "content": [], "sub_sections": []}
                current_part["sections"].append(current_section)
                current_section["content"].append(content_item)
            i += 1
    return json_data

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".md"):
            doc_path = os.path.join(DATA_DIR, filename)
            print(f"Processing {filename}...")
            try:
                structured_data = process_markdown_file(doc_path)
                base_filename = os.path.splitext(filename)[0]
                output_path = os.path.join(OUTPUT_DIR, f"{base_filename}.json")
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(structured_data, f, indent=2, ensure_ascii=False)
                print(f"Successfully created structured JSON: {output_path}")
            except Exception as e:
                print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    main()
