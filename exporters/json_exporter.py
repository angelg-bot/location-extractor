"""JSON exporter for locations and characters."""

import json
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from aggregator import merge_variants


def export_locations_json(
    groups_ordered: dict,
    groups_raw: dict,
) -> str:
    """Generate JSON string for location data."""
    json_out = []

    for area_label, keys in groups_ordered.items():
        for cn, en in keys:
            scenes = groups_raw.get((cn, en), [])
            if not scenes:
                continue
            variants = merge_variants(scenes)
            for vk, v in variants.items():
                eps = sorted(v["episodes"])
                json_out.append({
                    "location_cn": cn,
                    "location_en": en,
                    "int_ext": v["int_ext"],
                    "time": v["time"],
                    "episodes": eps,
                    "scene_desc": " ".join(v["scene_descs"]),
                    "atmosphere": " ".join(v["atmospheres"]),
                    "events": [
                        {"episode": e, "event": ev}
                        for e, ev in sorted(set(v["events"]))
                    ],
                })

    return json.dumps(json_out, ensure_ascii=False, indent=2)


def export_characters_json(characters: list[dict]) -> str:
    """Generate JSON string for character data."""
    return json.dumps(characters, ensure_ascii=False, indent=2)
