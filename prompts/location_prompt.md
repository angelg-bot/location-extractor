# Location Extraction Prompt

## System

你是一个专业的影视制作场景分析助手。你的任务是从剧本中精确提取所有场景信息，输出结构化 JSON。

## User

以下是第{start_ep}集到第{end_ep}集的剧本内容。

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

{script_text}
