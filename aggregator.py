"""Aggregator — merge, deduplicate, and group extracted scenes."""

from collections import OrderedDict


def aggregate_locations(
    scenes: list[dict],
    canon_map: dict | None = None,
) -> tuple[OrderedDict, OrderedDict]:
    """
    Aggregate raw scenes into grouped structure.

    Args:
        scenes: Raw scene dicts from extractor
        canon_map: {raw_name: {"cn": str, "en": str}} or None

    Returns:
        (groups_ordered, groups_raw) for build_output
    """
    canon = {}
    if canon_map:
        for k, v in canon_map.items():
            canon[k] = (v["cn"], v["en"])

    # Filter continuation-only entries
    valid = [s for s in scenes if not s.get("continuation_only")]

    # Group by canonicalized name
    groups_raw = OrderedDict()
    for s in valid:
        raw = s["location_raw"]
        if raw in canon:
            key = canon[raw]
        else:
            key = (raw, raw)  # cn=en=raw if no canon
        groups_raw.setdefault(key, []).append(s)

    # Auto-detect area groups by prefix
    groups_ordered = _detect_groups(list(groups_raw.keys()))

    return groups_ordered, groups_raw


def _detect_groups(keys: list[tuple[str, str]]) -> OrderedDict:
    """Group locations by Chinese name prefix (before " - ")."""
    prefix_map = OrderedDict()
    for cn, en in keys:
        prefix = cn.split(" - ")[0].strip()
        prefix_map.setdefault(prefix, []).append((cn, en))

    groups = OrderedDict()
    other = []
    for prefix, members in prefix_map.items():
        if len(members) >= 2:
            en_prefix = members[0][1].split(" - ")[0].strip()
            label = f"{prefix}　/　{en_prefix}"
            groups[label] = members
        else:
            other.extend(members)
    if other:
        groups["其他场景　/　Other Locations"] = other
    return groups


def merge_variants(scenes: list[dict]) -> OrderedDict:
    """Merge scenes of one location into variants by (int_ext, time)."""
    variants = OrderedDict()
    for s in scenes:
        vk = f"{s['int_ext']}·{s.get('time', '未知')}"
        if vk not in variants:
            variants[vk] = {
                "int_ext": s["int_ext"],
                "time": s.get("time", "未知"),
                "episodes": set(),
                "scene_descs": [],
                "atmospheres": [],
                "events": [],
            }
        v = variants[vk]
        eps = s.get("episode", [])
        if isinstance(eps, int):
            eps = [eps]
        for e in eps:
            v["episodes"].add(e)
        if s.get("scene_desc") and s["scene_desc"] not in v["scene_descs"]:
            v["scene_descs"].append(s["scene_desc"])
        if s.get("atmosphere") and s["atmosphere"] not in v["atmospheres"]:
            v["atmospheres"].append(s["atmosphere"])
        for e in eps:
            if s.get("event"):
                v["events"].append((e, s["event"]))
    return variants
