# Game Intent Dataset

面向单机解谜游戏多智能体路由的中文意图识别数据集。

## 文件

- `train.jsonl`: 176 条训练样本
- `valid.jsonl`: 44 条验证样本
- `test.jsonl`: 44 条测试样本
- `labels.json`: 标签说明和默认路由元数据

## 字段

- `text`: 用户原始输入
- `intent`: 主意图标签
- `description`: 标签说明
- `domain`: 任务领域
- `spoiler_level`: 剧透程度，取值为 `none`、`low`、`medium`、`high`
- `needs_game_context`: 是否需要当前游戏进度、场景或物品上下文
- `route_to`: 推荐路由到的 Agent
- `language`: 数据语言
- `game_genre`: 目标游戏类型
- `source`: 数据来源标记

## 标签

- `hint_request`: 用户想要低剧透提示，不希望直接得到答案。 默认路由 `hint_agent`
- `puzzle_solution`: 用户明确要求谜题、机关、密码或步骤的完整解法。 默认路由 `puzzle_agent`
- `walkthrough_request`: 用户询问主线推进、下一步去哪、流程路线。 默认路由 `walkthrough_agent`
- `item_location`: 用户询问钥匙、道具、线索、收集品的位置。 默认路由 `item_agent`
- `lore_explanation`: 用户询问剧情、结局、世界观、文本线索含义。 默认路由 `lore_agent`
- `character_query`: 用户询问角色身份、动机、关系或角色相关剧情。 默认路由 `lore_agent`
- `mechanic_explanation`: 用户询问游戏机制、操作、规则、系统说明。 默认路由 `mechanic_agent`
- `spoiler_control`: 用户主要表达剧透控制偏好，如不要剧透、只提示一点。 默认路由 `spoiler_guard`
- `bug_or_stuck`: 用户怀疑 bug、事件无法触发、卡死、无法交互。 默认路由 `debug_agent`
- `game_recommendation`: 用户请求推荐单机解谜、叙事、密室、推理类游戏。 默认路由 `recommendation_agent`
- `meta_chat`: 闲聊、能力询问、非游戏问题或无法归入游戏任务的问题。 默认路由 `general_agent`

## 建议用法

第一版先训练单标签分类器，输入 `text`，输出 `intent`。后续可以扩展为多任务输出，同时预测 `spoiler_level`、`needs_game_context` 和 `route_to`。
