"""Markdown → plain text (direct read, with multi-file merge support)."""

import os


def parse_md(file_path: str) -> str:
    """Read a single markdown file."""
    with open(file_path, encoding="utf-8") as f:
        return f.read()


def parse_md_directory(dir_path: str) -> str:
    """Merge multiple markdown files from a directory, sorted by filename."""
    files = sorted(
        [f for f in os.listdir(dir_path) if f.endswith(".md")],
        key=lambda x: _sort_key(x),
    )
    parts = []
    for f in files:
        with open(os.path.join(dir_path, f), encoding="utf-8") as fh:
            parts.append(fh.read())
    return "\n\n".join(parts)


def _sort_key(filename: str):
    """Sort numerically if possible, else alphabetically."""
    name = os.path.splitext(filename)[0]
    try:
        return (0, int(name))
    except ValueError:
        return (1, name)
