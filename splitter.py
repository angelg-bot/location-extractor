"""Episode splitter — split full-text script into episodes."""

import re
from dataclasses import dataclass


@dataclass
class Episode:
    number: int
    text: str


# Patterns ordered by priority
EP_PATTERNS = [
    re.compile(r"^#\s*第\s*(\d+)\s*集", re.MULTILINE),                     # # 第N集
    re.compile(r"^#\s*Episode\s+(\d+)", re.MULTILINE | re.IGNORECASE),      # # Episode N
    re.compile(r"^#\s*EP\s*(\d+)", re.MULTILINE | re.IGNORECASE),           # # EP N
    re.compile(r"^第\s*(\d+)\s*集", re.MULTILINE),                          # 第N集 (line start)
    re.compile(r"^Episode\s+(\d+)", re.MULTILINE | re.IGNORECASE),          # Episode N (line start, PDF)
    re.compile(r"^EP\s*(\d+)", re.MULTILINE | re.IGNORECASE),               # EP N (line start)
]

SCENE_HEADER = re.compile(
    r"^(?:##\s*)?\d+\s*(?:[内外]景[。.]|INT\.|EXT\.)", re.MULTILINE | re.IGNORECASE
)

CONTINUATION = re.compile(r"紧接上集|continuous|CONTINUED", re.IGNORECASE)


def split_episodes(text: str) -> list[Episode]:
    """Split script text into episodes. Returns list sorted by episode number."""

    # Try each pattern to find episode markers
    for pattern in EP_PATTERNS:
        matches = list(pattern.finditer(text))
        if len(matches) >= 2:
            return _split_by_matches(text, matches)

    # Fallback: split by scene headers
    scene_matches = list(SCENE_HEADER.finditer(text))
    if scene_matches:
        episodes = []
        for i, m in enumerate(scene_matches):
            start = m.start()
            end = scene_matches[i + 1].start() if i + 1 < len(scene_matches) else len(text)
            chunk = text[start:end].strip()
            if chunk:
                episodes.append(Episode(number=i + 1, text=chunk))
        return episodes

    # Last resort: entire text is one episode
    return [Episode(number=1, text=text)]


def _split_by_matches(text: str, matches: list) -> list[Episode]:
    """Split text using regex matches for episode markers."""
    episodes = []
    for i, m in enumerate(matches):
        ep_num = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()

        if not chunk or len(chunk) < 20:
            continue

        # Check for continuation markers
        if CONTINUATION.search(chunk[:200]):
            # Still include it but mark in the text
            pass

        episodes.append(Episode(number=ep_num, text=chunk))

    return episodes


def split_md_files(file_texts: dict[str, str], offset: int = 0) -> list[Episode]:
    """
    Build episode list from pre-split markdown files.
    file_texts: {filename: content} — filenames should be like "2.md", "3.md"
    offset: episode number adjustment (e.g., if 2.md = Episode 1, offset = -1)
    """
    episodes = []
    for fname, content in sorted(file_texts.items(), key=lambda x: _file_sort(x[0])):
        name = fname.rsplit(".", 1)[0]
        try:
            file_num = int(name)
        except ValueError:
            continue
        ep_num = file_num + offset
        if ep_num < 1:
            continue
        content = content.strip()
        if content:
            episodes.append(Episode(number=ep_num, text=content))
    return episodes


def _file_sort(fname: str):
    name = fname.rsplit(".", 1)[0]
    try:
        return int(name)
    except ValueError:
        return 999999
