import xml.etree.ElementTree as ET
import os
import logging
import re

# Setup logger
logger = logging.getLogger("xml_to_htmlmd_colspan")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("xml_to_htmlmd_colspan.log")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

def get_element_text(element):
    logger.debug(f"Extracting text from element: {element.tag}")
    """Extracts all text from an element, including nested tags, and strips it."""
    text = element.text or ''
    for child in element:
        text += get_element_text(child)
        if child.tail:
            text += child.tail
    return text.strip()

def process_cell_content_for_html(cell):
    logger.debug(f"Processing cell content for HTML. Tag: {cell.tag}")
    """
    Processes the content of a cell for HTML output.
    It handles text, nested elements, and nested tables.
    """
    content_parts = []
    
    # 1. The direct text of the <cell> element
    if cell.text and cell.text.strip():
        content_parts.append(cell.text.strip())

    # 2. The child elements of the <cell>
    for child in cell:
        if child.tag == 'table':
            # If a child is a table, convert it to an HTML table recursively.
            content_parts.append(convert_table_to_html(child))
        else:
            # For any other tags (e.g., <bold>, <paragraph>), get their full text content.
            content_parts.append(get_element_text(child))
        
        # 3. The text that follows the child element (its tail)
        if child.tail and child.tail.strip():
            content_parts.append(child.tail.strip())
            
    # Join the parts with <br> for line breaks within a cell.
    # Filter out any empty strings that might have been added.
    return "<br>".join(filter(None, content_parts))

def convert_table_to_html(table_element):
    logger.info(f"Converting table element to HTML. Tag: {table_element.tag}")
    """Converts a single XML table element to an HTML table string."""
    html = "<table>\n"
    is_header = True
    for row in table_element.findall('row'):
        html += "  <tr>\n"
        cell_tag = "th" if is_header else "td"
        for cell in row.findall('cell'):
            cell_content = process_cell_content_for_html(cell)
            colspan = cell.get('colspan')
            rowspan = cell.get('rowspan')
            attrs = ''
            if colspan and colspan != '1':
                attrs += f' colspan="{colspan}"'
            if rowspan and rowspan != '1':
                attrs += f' rowspan="{rowspan}"'
            html += f"    <{cell_tag}{attrs}>{cell_content}</{cell_tag}>\n"
        html += "  </tr>\n"
        is_header = False
    html += "</table>"
    return html

class Section:
    def __init__(self, heading, level):
        self.heading = heading
        self.level = level
        self.content = []
        self.children = []

    def add_child(self, section):
        self.children.append(section)

    def add_content(self, item):
        self.content.append(item)

def xml_to_md(xml_path, md_path):
    logger.info(f"Converting XML to Markdown: {xml_path} -> {md_path}")
    """Converts an XML file to a Markdown file, grouping content under correct headings."""

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
    except ET.ParseError as e:
        logger.error(f"Error parsing XML file {xml_path}: {e}")
        print(f"Error parsing XML file {xml_path}: {e}")
        return

    def classify_heading(text):
        t = text.strip()
        # Main title - complete inspection report title (H1)
        if re.match(r"^INSPECTION REPORT", t, re.I):
            return 1
        
        # PART sections (H2) - covers PART I, PART II, PART III, etc.
        if re.match(r"^PART[\s\-]*[IVX]+", t, re.I):
            return 2
        # Also catch Part-I, Part II, Part III, Part IV, Part V variations
        if re.match(r"^Part[\s\-]*[IVX]+", t, re.I):
            return 2
        # Catch Part with Roman numerals or Arabic numerals
        if re.match(r"^Part[\s\-]*\d+", t, re.I):
            return 2
        # Catch Part with colon variations
        if re.match(r"^Part[\s\-]*[IVX]*\s*:", t, re.I):
            return 2
        
        # Level 3 headings (H3) - Main sections under PART
        if re.match(r"^Introductory$", t, re.I):
            return 3
        if re.match(r"^Budget and Expenditure$", t, re.I):
            return 3
        if re.match(r"^Revenue Receipt$", t, re.I):
            return 3
        if re.match(r"^Organisational set up$", t, re.I):
            return 3
        if re.match(r"^Scope of Audit$", t, re.I):
            return 3
        if re.match(r"^Sampling$", t, re.I):
            return 3
        if re.match(r"^Audit Objectives$", t, re.I):
            return 3
        if re.match(r"^Criteria$", t, re.I):
            return 3
        if re.match(r"^Audit Mandate$", t, re.I):
            return 3
        if re.match(r"^Best Practice", t, re.I):
            return 3
        if re.match(r"^Acknowledgement", t, re.I):
            return 3
        if re.match(r"^Review of old outstanding paras", t, re.I):
            return 3
        if re.match(r"^Introduction$", t, re.I):
            return 3
        
        # Reference numbers and major findings sections (H3)
        if re.match(r"^REFERENCE NUMBER", t, re.I):
            return 3
        if re.match(r"^\(.*Audit Findings\)", t, re.I):
            return 3
        if re.match(r"^A[:\s]", t) or re.match(r"^B[:\s]", t):
            return 3
        if re.match(r"^A\s*I[:\s]", t) or re.match(r"^A\s*II[:\s]", t) or re.match(r"^A\s*III[:\s]", t):
            return 3
        if re.match(r"^B\s*I[:\s]", t) or re.match(r"^B\s*II[:\s]", t):
            return 3
        
        # Level 4 headings (H4) - Para numbers, subjects, and Roman numeral subjects
        if re.match(r"^Para \d+", t):
            return 4
        # Roman numerals with Subject (I Subject:, II Subject:, III Subject:, etc.)
        if re.match(r"^[IVX]+\s+Subject", t, re.I):
            return 4
        # Standalone Subject: lines
        if re.match(r"^Subject:", t):
            return 4
        # Subject without colon but with description
        if re.match(r"^Subject\s+", t, re.I):
            return 4
        
        # Follow up sections and other subsections
        if re.match(r"^\(Follow up", t, re.I):
            return 3
        if re.match(r"^\([^)]+\)$", t):
            return 3
        
        # Fallback
        return 0

    # Build a tree of sections
    root_section = Section(None, 0)
    section_stack = [root_section]
    first_heading_encountered = False

    for element in root:
        logger.info(f"Processing element: {element.tag}")
        if element.tag in ('heading', 'bold'):
            heading_text = get_element_text(element)
            # First heading without leading spaces is always H1 (title)
            if not first_heading_encountered and not heading_text.startswith(' '):
                level = 1
                first_heading_encountered = True
                logger.info(f"First heading detected as title: {heading_text[:30]}...")
            else:
                level = classify_heading(heading_text)
            # Pop to the correct parent level
            while len(section_stack) > 1 and section_stack[-1].level >= level:
                section_stack.pop()
            new_section = Section(heading_text, level)
            section_stack[-1].add_child(new_section)
            section_stack.append(new_section)
            logger.info(f"Added heading: {heading_text[:30]}... as level {level}")
        elif element.tag == 'paragraph':
            content = get_element_text(element)
            if content.strip():  # Only add non-empty content
                # Always treat as paragraph, never heading
                section_stack[-1].add_content(content)
                logger.info(f"Added paragraph: {content[:30]}...")
        elif element.tag == 'table':
            table_html = convert_table_to_html(element)
            section_stack[-1].add_content(table_html)
            logger.info(f"Added table element as HTML.")

    # Recursively write sections
    def write_section(section, md_lines):
        if section.heading:
            md_lines.append(f"{'#' * section.level} {section.heading}\n\n")
        for item in section.content:
            md_lines.append(item + "\n\n")
        for child in section.children:
            write_section(child, md_lines)

    md_lines = []
    for child in root_section.children:
        write_section(child, md_lines)

    # Ensure the output directory exists
    output_dir = os.path.dirname(md_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"Created output directory: {output_dir}")

    try:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("".join(md_lines))
        print(f"Successfully converted {xml_path} to {md_path}")
        logger.info(f"Successfully converted {xml_path} to {md_path}")
    except Exception as e:
        logger.error(f"Failed to write Markdown file {md_path}: {e}")

def process_all_xml_in_folder(input_folder, output_folder):
    logger.info(f"Processing all XML files in folder: {input_folder}")
    """
    Converts all XML files in a given folder to Markdown files.
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        logger.info(f"Created output folder: {output_folder}")

    for filename in os.listdir(input_folder):
        if filename.endswith(".xml"):
            xml_path = os.path.join(input_folder, filename)
            md_filename = os.path.splitext(filename)[0] + ".md"
            md_path = os.path.join(output_folder, md_filename)
            logger.info(f"Converting {xml_path} to {md_path}...")
            print(f"Converting {xml_path} to {md_path}...")
            xml_to_md(xml_path, md_path)
            logger.info(f"Finished processing {xml_path}")

# --- Main execution ---
if __name__ == "__main__":
    input_directory = "/home/Comptroller_and_Auditor_General/data_xml"
    output_directory = "/home/Comptroller_and_Auditor_General/data_md"

    process_all_xml_in_folder(input_directory, output_directory)
