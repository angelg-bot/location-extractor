"""File parsers — convert uploaded files to plain text."""

import os
import tempfile

from parsers.pdf_parser import parse_pdf
from parsers.fdx_parser import parse_fdx
from parsers.md_parser import parse_md
from parsers.xlsx_parser import parse_xlsx

PARSERS = {
    ".pdf": parse_pdf,
    ".fdx": parse_fdx,
    ".md": parse_md,
    ".xlsx": parse_xlsx,
}


def parse_file(file_path: str) -> str:
    """Auto-detect format and parse to plain text."""
    ext = os.path.splitext(file_path)[1].lower()
    parser = PARSERS.get(ext)
    if not parser:
        raise ValueError(f"Unsupported format: {ext}")
    return parser(file_path)


def parse_uploaded(name: str, data: bytes) -> str:
    """Parse from in-memory uploaded file."""
    ext = os.path.splitext(name)[1].lower()
    parser = PARSERS.get(ext)
    if not parser:
        raise ValueError(f"Unsupported format: {ext}")
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
        f.write(data)
        f.flush()
        result = parser(f.name)
    os.unlink(f.name)
    return result
