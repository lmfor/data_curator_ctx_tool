"""
Workflow usability for later usage:

1. from html_to_markdown import convert_html_file, html_to_markdown

2. # Convert a file
   convert_html_file("input.html", "output.md")

3. # Convert HTML content directly
   markdown_content = html_to_markdown(html_string)
"""

import re
import os
import sys
from pathlib import Path

import markdownify
from bs4 import BeautifulSoup

# Regular expression for removing excessive newlines
EXCESSIVE_NEWLINES_RE = re.compile(r"\n\s*\n")

# Regular expression for removing unnecessary single tables
# ex.
#     | ``` code ``` |
#     | --- |
REDUNDANT_TABLES_RE = re.compile(r"\| ``` (.*?) ``` \|\n\| --- \|", re.DOTALL)


def unwrap_tables(soup):
    """
    Function to unwrap tables with class "wysiwyg-macro" and data-macro-name="panel" 
    that contains nested tables causing rendering issues for markdown.
    """
    # Find all tables with class "wysiwyg-macro" and data-macro-name="panel"
    for table in soup.find_all(
        "table", class_="wysiwyg-macro", attrs={"data-macro-name": "panel"}
    ):
        tbodies = table.find_all("tbody")
        for tbody in tbodies:
            rows = tbody.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                for cell in cells:
                    cell.unwrap()
                row.unwrap()
            tbody.unwrap()
        table.unwrap()

    return soup


def html_to_markdown(html_content: str) -> str:
    """
    Converts HTML content into Markdown format and cleans up unnecessary new lines.

    Args:
        html_content (str): The HTML content to be converted.

    Returns:
        str: The converted Markdown content.
    """
    # Preprocess the HTML to remove nested unwanted tables but keep their content
    soup = BeautifulSoup(html_content, "html.parser")
    soup = unwrap_tables(soup)

    # Convert HTML to Markdown using markdownify
    markdown = markdownify.markdownify(soup.prettify(), heading_style="ATX")

    # Remove excessive newlines that may appear after conversion
    markdown = EXCESSIVE_NEWLINES_RE.sub("\n\n", markdown).strip()
    # Remove unnecessary single tables
    markdown = REDUNDANT_TABLES_RE.sub(r"```\1```\n", markdown)

    return markdown


def convert_html_file(input_file: str, output_file: str = None) -> str: #type:ignore
    """
    Converts an HTML file to Markdown format.

    Args:
        input_file (str): Path to the input HTML file.
        output_file (str, optional): Path to the output Markdown file. 
                                   If None, creates a .md file with the same name.

    Returns:
        str: The converted Markdown content.
    
    Raises:
        FileNotFoundError: If the input file doesn't exist.
        IOError: If there's an error reading or writing files.
    """
    # Check if input file exists
    if not os.path.exists(input_file):
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Read HTML content
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except IOError as e:
        raise IOError(f"Error reading input file: {e}")

    # Convert to Markdown
    markdown_content = html_to_markdown(html_content)

    # Determine output file path
    if output_file is None:
        input_path = Path(input_file)
        output_file = input_path.with_suffix('.md')

    # Write Markdown content
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
    except IOError as e:
        raise IOError(f"Error writing output file: {e}")

    print(f"Successfully converted {input_file} to {output_file}")
    return markdown_content


def main():
    """
    Command-line interface for the HTML to Markdown converter.
    """
    if len(sys.argv) < 2:
        print("Usage: python html_to_markdown.py <input_file.html> [output_file.md]")
        print("Example: python html_to_markdown.py document.html")
        print("Example: python html_to_markdown.py document.html output.md")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        convert_html_file(input_file, output_file) #type: ignore
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()