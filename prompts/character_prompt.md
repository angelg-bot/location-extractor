# Character Extraction Prompt

## System

你是一个专业的影视制作角色分析助手。你的任务是从剧本中提取所有角色信息，输出结构化 JSON。

## User

以下是第{start_ep}集到第{end_ep}集的剧本内容。

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
- key_relationships：关系列表，每项包含 character（对方名）和 relationship（关系描述）

角色分级规则：
- 主角：出场集数 > 总集数50%
- 重要配角：出场集数 10%-50%
- 次要角色：出场集数 < 10%

请按重要性排序（主角在前），严格输出 JSON 数组，不要添加多余解释。

---

剧本内容：

{script_text}
