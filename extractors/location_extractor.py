"""Location extractor — async batch extraction via Claude API."""

import asyncio
import json
import re
import anthropic
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import count_tokens, retry_async, logger


SYSTEM_PROMPT = "你是一个专业的影视制作场景分析助手。你的任务是从剧本中精确提取所有场景信息，输出结构化 JSON。"

USER_TEMPLATE = """以下是第{start_ep}集到第{end_ep}集的剧本内容。

请提取所有场景，找形如 "## N 内景/外景。LOCATION - 时段" 的 scene header（也可能没 ## 前缀，只要是"内景/外景。XXX"格式都算）。

如文件标注"紧接上集"或无 scene header，记 {{"continuation_only": true, "episode": N}}。

每个独立场景输出以下字段：
- episode：集数（整数或整数数组）
- location_raw：中文场景名，保持剧本原文
- int_ext：内景 或 外景
- time：时段（白天/夜/夜晚/黄昏 等）
- scene_desc：2句中文，描述物理空间（家具、建筑、道具、布局）
- atmosphere：2句中文，描述氛围（光线、情绪基调、声音、危险/温馨程度）
- event：一句中文，这场戏的主要事件

规则：
1. 同一 location 在不同时段（白天 vs 夜晚）算不同 variant，分开列
2. 同一 location 同一时段同一集内多次穿插只算一条，合并事件描述
3. "紧接上集"的集数不需要挂到上一条的 episode list，用 continuation_only 标记

请严格输出 JSON 数组，不要添加任何多余解释。

---

剧本内容：

{script_text}"""


def _build_batches(episodes: list, batch_size: int) -> list[dict]:
    """Group episodes into batches. Each batch = {start_ep, end_ep, text}."""
    batches = []
    for i in range(0, len(episodes), batch_size):
        chunk = episodes[i:i + batch_size]
        start_ep = chunk[0].number
        end_ep = chunk[-1].number
        combined = "\n\n".join(
            f"--- 第{ep.number}集 ---\n{ep.text}" for ep in chunk
        )
        batches.append({
            "start_ep": start_ep,
            "end_ep": end_ep,
            "text": combined,
        })
    return batches


def _parse_json_response(text: str) -> list[dict]:
    """Extract JSON array from LLM response."""
    # Try to find JSON block
    m = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if m:
        return json.loads(m.group(1))
    # Try raw JSON
    m = re.search(r"\[[\s\S]*\]", text)
    if m:
        return json.loads(m.group(0))
    raise ValueError("No JSON array found in response")


async def _extract_batch(
    client: anthropic.AsyncAnthropic,
    batch: dict,
    model: str,
    max_tokens: int,
    temperature: float,
    ref_locations: list[str] | None = None,
) -> list[dict]:
    """Extract locations from one batch."""

    system = SYSTEM_PROMPT
    if ref_locations:
        system += f"\n\n参考：以下是已知的场景名列表，请尽量使用一致的命名：\n{', '.join(ref_locations)}"

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
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        return _parse_json_response(resp.content[0].text)

    return await retry_async(_call)


async def extract_locations(
    episodes: list,
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
    batch_size: int = 10,
    max_concurrent: int = 5,
    max_tokens: int = 4096,
    temperature: float = 0.2,
    ref_locations: list[str] | None = None,
    progress_callback=None,
) -> list[dict]:
    """
    Extract locations from all episodes in parallel batches.

    Args:
        episodes: List of Episode objects
        api_key: Claude API key
        progress_callback: Optional callable(batch_idx, total_batches, results)

    Returns:
        List of raw scene dicts
    """
    client = anthropic.AsyncAnthropic(api_key=api_key)
    batches = _build_batches(episodes, batch_size)
    semaphore = asyncio.Semaphore(max_concurrent)
    all_scenes = []
    errors = []

    async def _run_batch(idx, batch):
        async with semaphore:
            try:
                results = await _extract_batch(
                    client, batch, model, max_tokens, temperature, ref_locations
                )
                # Normalize episode fields
                for r in results:
                    if isinstance(r.get("episode"), int):
                        r["episode"] = [r["episode"]]
                if progress_callback:
                    progress_callback(idx + 1, len(batches), results)
                return results
            except Exception as e:
                logger.error(f"Batch {idx+1} failed: {e}")
                errors.append((idx + 1, str(e)))
                if progress_callback:
                    progress_callback(idx + 1, len(batches), None)
                return []

    tasks = [_run_batch(i, b) for i, b in enumerate(batches)]
    results = await asyncio.gather(*tasks)

    for batch_result in results:
        all_scenes.extend(batch_result)

    return all_scenes, errors
