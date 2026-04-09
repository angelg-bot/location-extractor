"""FDX (Final Draft XML) → plain text."""

import xml.etree.ElementTree as ET

SKIP_TYPES = {"General", "Transition", "Cast List", "New Act"}


def parse_fdx(file_path: str) -> str:
    tree = ET.parse(file_path)
    root = tree.getroot()
    lines = []

    # Only iterate paragraphs inside Content
    content_elem = root.find("Content")
    if content_elem is None:
        content_elem = root

    for para in content_elem.iter("Paragraph"):
        ptype = para.get("Type", "")
        if ptype in SKIP_TYPES:
            continue

        # Collect all text within the paragraph
        texts = []
        for text_elem in para.iter("Text"):
            if text_elem.text:
                texts.append(text_elem.text)
        content = "".join(texts).strip()
        if not content:
            continue

        if ptype == "Scene Heading":
            lines.append(f"\n## {content}")
        elif ptype == "Character":
            lines.append(f"\n{content}")
        elif ptype == "Parenthetical":
            lines.append(f"({content})")
        elif ptype == "Dialogue":
            lines.append(content)
        else:  # Action or untyped
            lines.append(f"\n{content}")

    return "\n".join(lines)
