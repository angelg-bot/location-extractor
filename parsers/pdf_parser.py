"""PDF → plain text using pdfplumber."""

import pdfplumber


def parse_pdf(file_path: str) -> str:
    lines = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                # Filter out page numbers (standalone numbers at top/bottom)
                page_lines = text.split("\n")
                filtered = [l for l in page_lines if not l.strip().isdigit()]
                lines.extend(filtered)
    return "\n".join(lines)
