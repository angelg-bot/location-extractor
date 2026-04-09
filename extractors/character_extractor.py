"""Character extractor — async batch extraction via Claude API."""

import asyncio
import json
import re
import anthropic
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import retry_async, logger


SYSTEM_PROMPT = "你是一个专业的影视制作角色分析助手。你的任务是从剧本中提取所有角色信息，输出结构化 JSON。"

USER_TEMPLATE = """以下是第{start_ep}集到第{end_ep}集的剧本内容。

请提取所有出现的角色（包括有名字的配角，但不包括纯路人群演如"路人A"）。

每个角色输出以下字段：
- character_name：英文名（剧本中的原始名）
- character_name_cn：中文名（如剧本中有中文名则用原文，否则音译）
- gender：男/女/未知
- age：年龄或年龄段描述（如"19岁"、"中年"）
- identity：角色身份/职业（如"魅魔/高中生"）
- appearance：2句中文，外貌描述（发型发色、体型、标志性穿着、特殊特征）
- personality：2句中文，性格特征
- episodes：出现的集数列表（整数数组）
- key_relationships：关系列表，每项含 character（对方名）和 relationship（关系描述）

请按重要性排序（主角在前），严格输出 JSON 数组。

---

剧本内容：

{script_text}"""

MERGE_TEMPLATE = """以下是从一部{total_eps}集剧本的分批提取中得到的所有角色数据（可能有重复）。

请：
1. 合并同一角色的不同条目（合并出场集数、关系、描述取最完整版本）
2. 按总出场集数排序（多→少）
3. 为每个角色添加 role_tier 字段：
   - "主角"：出场集数 > 总集数50%
   - "重要配角"：出场集数 10%-50%
   - "次要角色"：出场集数 < 10%

输出合并后的完整 JSON 数组。

---

原始数据：

{raw_data}"""


def _build_batches(episodes: list, batch_size: int) -> list[dict]:
    batches = []
    for i in range(0, len(episodes), batch_size):
        chunk = episodes[i:i + batch_size]
        start_ep = chunk[0].number
        end_ep = chunk[-1].number
        combined = "\n\n".join(
            f"--- 第{ep.number}集 ---\n{ep.text}" for ep in chunk
        )
        batches.append({"start_ep": start_ep, "end_ep": end_ep, "text": combined})
    return batches


def _parse_json_response(text: str) -> list[dict]:
    m = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        return json.loads(m.group(0))
    raise ValueError("No JSON array found in response")


async def _extract_batch(client, batch, model, max_tokens, temperature):
    user_msg = USER_TEMPLATE.format(
        start_ep=batch["start_ep"],
        end_ep=batch["end_ep"],
        script_text=batch["text"],
    )

    async def _call():
        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return _parse_json_response(resp.content[0].text)

    return await retry_async(_call)


async def _merge_characters(client, raw_chars, total_eps, model, max_tokens):
    """Second pass: merge all batch results into deduplicated character list."""
    user_msg = MERGE_TEMPLATE.format(
        total_eps=total_eps,
        raw_data=json.dumps(raw_chars, ensure_ascii=False, indent=2),
    )

    async def _call():
        resp = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0.1,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        return _parse_json_response(resp.content[0].text)

    return await retry_async(_call)


async def extract_characters(
    episodes: list,
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
    batch_size: int = 10,
    max_concurrent: int = 5,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    progress_callback=None,
) -> list[dict]:
    """
    Extract characters from all episodes: batch extract → merge/dedup.
    Returns (merged_characters, errors).
    """
    client = anthropic.AsyncAnthropic(api_key=api_key)
    batches = _build_batches(episodes, batch_size)
    semaphore = asyncio.Semaphore(max_concurrent)
    all_chars = []
    errors = []

    async def _run_batch(idx, batch):
        async with semaphore:
            try:
                results = await _extract_batch(
                    client, batch, model, max_tokens, temperature
                )
                if progress_callback:
                    progress_callback(idx + 1, len(batches), results)
                return results
            except Exception as e:
                logger.error(f"Character batch {idx+1} failed: {e}")
                errors.append((idx + 1, str(e)))
                if progress_callback:
                    progress_callback(idx + 1, len(batches), None)
                return []

    tasks = [_run_batch(i, b) for i, b in enumerate(batches)]
    results = await asyncio.gather(*tasks)

    for batch_result in results:
        all_chars.extend(batch_result)

    if not all_chars:
        return [], errors

    # Merge pass
    if progress_callback:
        progress_callback(-1, -1, None)  # signal: merging

    total_eps = max(ep.number for ep in episodes)
    try:
        merged = await _merge_characters(client, all_chars, total_eps, model, 8192)
    except Exception as e:
        logger.error(f"Character merge failed: {e}")
        errors.append(("merge", str(e)))
        merged = all_chars

    return merged, errors
