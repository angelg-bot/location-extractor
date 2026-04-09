"""Canonicalizer — LLM-based name standardization and dedup."""

import json
import re
import anthropic
from utils import retry_async, logger


LOCATION_PROMPT = """以下是从剧本中提取的所有场景名（原文）：

{raw_names}

请：
1. 找出指同一地点的不同写法（如大小写不同、简称/全称、中英混用），合并为一个标准名
2. 为每个标准名提供英文翻译
3. 输出 JSON 对象，格式：{{"原始名": {{"cn": "标准中文名", "en": "English Name"}}}}

只列需要改名或合并的条目。不需要改的也请列出，提供英文翻译。严格输出 JSON，不要多余解释。"""

CHARACTER_PROMPT = """以下是从剧本中提取的所有角色名：

{raw_names}

请：
1. 找出同一角色的不同写法（如 "RAVENNA" 和 "Ravenna"、昵称/全名），合并为标准名
2. 输出 JSON 对象，格式：{{"原始名": {{"standard": "标准名", "cn": "中文名"}}}}

只列需要合并的条目。严格输出 JSON，不要多余解释。"""


def _parse_json_obj(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        return json.loads(m.group(0))
    raise ValueError("No JSON object found in response")


async def canonicalize_locations(
    raw_names: list[str],
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """
    Returns canon_map: {raw_name: {"cn": str, "en": str}}
    """
    if not raw_names:
        return {}

    client = anthropic.AsyncAnthropic(api_key=api_key)
    user_msg = LOCATION_PROMPT.format(raw_names="\n".join(f"- {n}" for n in raw_names))

    async def _call():
        resp = await client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=0.1,
            system="你是一个影视制作术语标准化助手。",
            messages=[{"role": "user", "content": user_msg}],
        )
        return _parse_json_obj(resp.content[0].text)

    return await retry_async(_call)


async def canonicalize_characters(
    raw_names: list[str],
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """
    Returns canon_map: {raw_name: {"standard": str, "cn": str}}
    """
    if not raw_names:
        return {}

    client = anthropic.AsyncAnthropic(api_key=api_key)
    user_msg = CHARACTER_PROMPT.format(raw_names="\n".join(f"- {n}" for n in raw_names))

    async def _call():
        resp = await client.messages.create(
            model=model,
            max_tokens=4096,
            temperature=0.1,
            system="你是一个影视制作术语标准化助手。",
            messages=[{"role": "user", "content": user_msg}],
        )
        return _parse_json_obj(resp.content[0].text)

    return await retry_async(_call)
