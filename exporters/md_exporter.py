"""Markdown exporter for locations and characters."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aggregator import merge_variants


def export_locations_md(
    groups_ordered: dict,
    groups_raw: dict,
    title: str = "",
) -> str:
    """Generate Markdown for location asset library."""
    header = f"# {title} — 场景库（Location Asset 用）" if title else "# 场景库（Location Asset 用）"
    total = sum(len(v) for v in groups_ordered.values())

    lines = [header, "", f"> 共 {total} 个场景", "", "---", ""]

    for area_label, keys in groups_ordered.items():
        lines.append(f"# ▸ {area_label}")
        lines.append("")

        for cn, en in keys:
            scenes = groups_raw.get((cn, en), [])
            if not scenes:
                continue
            variants = merge_variants(scenes)
            lines.append(f"## {cn}　/　{en}")
            lines.append("")

            for vk, v in variants.items():
                eps = sorted(v["episodes"])
                eps_str = ", ".join(f"E{e}" for e in eps)
                lines.append(f"### Variant: {v['int_ext']} · {v['time']}")
                lines.append(f"**出现集数：** {eps_str}")
                lines.append("")
                lines.append(f"**场景描述：** {' '.join(v['scene_descs'])}")
                lines.append("")
                lines.append(f"**氛围：** {' '.join(v['atmospheres'])}")
                lines.append("")
                lines.append("**主要事件：**")
                for e, ev in sorted(set(v["events"])):
                    lines.append(f"- E{e}：{ev}")
                lines.append("")

            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def export_characters_md(characters: list[dict], title: str = "") -> str:
    """Generate Markdown for character library."""
    header = f"# {title} — 角色库" if title else "# 角色库"
    lines = [header, "", f"> 共 {len(characters)} 个角色", "", "---", ""]

    for c in characters:
        name = c.get("character_name", "Unknown")
        name_cn = c.get("character_name_cn", "")
        tier = c.get("role_tier", "")
        tier_tag = f" [{tier}]" if tier else ""

        lines.append(f"## {name}　/　{name_cn}{tier_tag}")
        lines.append("")

        eps = c.get("episodes", [])
        if eps:
            eps_str = ", ".join(f"E{e}" for e in sorted(eps))
            lines.append(f"**出场集数（{len(eps)}集）：** {eps_str}")
            lines.append("")

        for field, label in [
            ("gender", "性别"),
            ("age", "年龄"),
            ("identity", "身份"),
            ("appearance", "外貌"),
            ("personality", "性格"),
        ]:
            val = c.get(field, "")
            if val:
                lines.append(f"**{label}：** {val}")
                lines.append("")

        rels = c.get("key_relationships", [])
        if rels:
            lines.append("**主要关系：**")
            for r in rels:
                lines.append(f"- {r.get('character', '?')}：{r.get('relationship', '')}")
            lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)
