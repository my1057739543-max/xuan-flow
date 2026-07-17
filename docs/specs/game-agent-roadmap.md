# Xuan-Flow 游戏领域多智能体改造 Spec

## 1. 背景

当前 Xuan-Flow 的主体仍然是通用多智能体框架，已经具备 LangGraph 状态编排、Tool Calling、MCP、Memory、Sub-Agent、FastAPI 和 Next.js 前端能力。

最近已完成第一块游戏领域能力：

- 构建了单机解谜游戏意图识别数据集。
- 基于 `chinese-macbert-base` 微调了 11 分类 intent classifier。
- 新增 `xuan_flow.game_intent` 模块，支持本地分类、路由归一和 JSONL 审计日志。
- 新增 `classify_game_intent` LangChain tool，并注册进工具列表。
- 已有 `puzzle_hint` 工具雏形，用于低剧透渐进提示。

但目前系统仍然更像“通用 Agent + 游戏意图分类工具”。接下来目标是把它推进成真正的 **面向单机解谜游戏的多智能体攻略助手**。

## 2. 产品目标

Xuan-Flow 游戏方向的核心目标：

让用户在玩单机解谜、叙事、密室、推理类游戏时，可以用自然语言询问：

- 我卡在这个机关了，给我一点提示。
- 这个谜题答案是什么？
- 地下室钥匙在哪里？
- 我拿到钥匙了但门打不开，是不是 bug？
- 这个结局是什么意思？
- 不要剧透，只告诉我下一步去哪。

系统需要先识别用户意图，再根据意图、剧透偏好和游戏上下文路由到不同 Agent 或工具。

核心体验不是“直接剧透答案”，而是：

- 能区分提示、完整解法、流程攻略、物品位置、剧情解释、卡关排查。
- 能识别并尊重用户的剧透偏好。
- 能维护玩家当前游戏状态，例如游戏名、章节、位置、道具、当前谜题。
- 能基于可控知识源回答，降低幻觉。
- 能记录每次路由和判断效果，便于持续迭代数据集。

## 3. 非目标

第一阶段不做以下内容：

- 不做完整游戏百科平台。
- 不做大型向量数据库和复杂 RAG 系统。
- 不做所有游戏的完整攻略覆盖。
- 不做实时图像识别和截图理解。
- 不追求一次性替换通用 Agent，而是逐步增加游戏领域路由能力。

## 4. 已完成能力

### 4.1 意图数据集

目录：

- `data/game_intent/train.jsonl`
- `data/game_intent/valid.jsonl`
- `data/game_intent/test.jsonl`
- `data/game_intent/labels.json`

当前标签：

- `hint_request`
- `puzzle_solution`
- `walkthrough_request`
- `item_location`
- `lore_explanation`
- `character_query`
- `mechanic_explanation`
- `spoiler_control`
- `bug_or_stuck`
- `game_recommendation`
- `meta_chat`

### 4.2 微调模型

基础模型：

- `models/chinese-macbert-base`

微调产物：

- `models/game_intent_classifier`

当前指标：

- valid accuracy: `0.8864`
- test accuracy: `0.9091`

### 4.3 游戏意图模块

已新增：

- `xuan_flow/game_intent/classifier.py`
- `xuan_flow/game_intent/router.py`
- `xuan_flow/game_intent/__main__.py`
- `xuan_flow/tools/game_intent.py`

能力：

- 输入用户 query。
- 输出 top-k intent predictions。
- 根据置信度、辅助剧透意图和显式低剧透短语生成最终 route。
- 写入 `.xuan-flow/game_intent_routes.jsonl` 作为审计日志。

## 5. 目标架构

目标数据流：

```text
用户输入
  ↓
Lead Agent
  ↓
classify_game_intent
  ↓
IntentRoute
  ├── intent
  ├── confidence
  ├── route_to
  ├── spoiler_level
  ├── needs_game_context
  └── status
  ↓
Game Context Resolver
  ↓
Game Agent Router
  ├── hint_agent / puzzle_hint
  ├── puzzle_agent
  ├── item_agent
  ├── walkthrough_agent
  ├── lore_agent
  ├── mechanic_agent
  ├── debug_agent
  └── recommendation_agent
  ↓
最终回答
```

## 6. 模块设计

### 6.1 Intent Classifier

职责：

- 加载本地微调模型。
- 对用户输入做 top-k intent 分类。
- 不处理业务规则。

已有文件：

- `xuan_flow/game_intent/classifier.py`

后续优化：

- 支持懒加载缓存，避免每次 tool 调用重复加载模型。
- 支持配置模型路径、设备和 max_length。
- 后续可扩展 ONNX 或更轻量推理后端。

### 6.2 Intent Router

职责：

- 把模型概率转换成稳定路由决策。
- 合并 `spoiler_control` 这类辅助意图。
- 根据显式短语识别低剧透需求。
- 对低置信度输出 `low_confidence` 或 `needs_clarification`。
- 写入路由审计日志。

已有文件：

- `xuan_flow/game_intent/router.py`

关键策略：

- `confidence >= 0.60`：直接接受 top1。
- `0.40 <= confidence < 0.60`：接受但标记 `low_confidence`。
- `confidence < 0.40`：建议澄清，路由到 `general_agent`。
- 显式出现“别剧透”“只给提示”“别告诉答案”等短语时，强制 `spoiler_level=low`。

### 6.3 Game Session State

新增模块：

- `xuan_flow/game_context/state.py`
- `xuan_flow/tools/game_context.py`

第一版存储：

- `.xuan-flow/game_sessions.json`

建议 schema：

```json
{
  "thread_id": "default",
  "game": "rusty-lake",
  "chapter": "chapter_2",
  "location": "地下室",
  "inventory": ["旧钥匙", "手电筒"],
  "current_puzzle": "clock_puzzle",
  "spoiler_preference": "low",
  "solved_puzzles": [],
  "updated_at": "..."
}
```

工具：

- `get_game_context(thread_id: str | None = None)`
- `update_game_context(...)`
- `clear_game_context(thread_id: str | None = None)`

目的：

当 `needs_game_context=true` 时，Lead Agent 可以读取上下文。如果上下文缺失，则先向用户追问游戏名、章节、当前位置或当前道具。

### 6.4 Game Knowledge Base

新增目录：

```text
data/games/
  rusty_lake/
    game.json
    guide.md
    items.json
    puzzles.json
    lore.md
```

第一版不做向量库，先做结构化文件读取。

建议 schema：

`game.json`：

```json
{
  "game_id": "rusty_lake",
  "display_name": "Rusty Lake",
  "aliases": ["锈湖", "Rusty Lake"]
}
```

`items.json`：

```json
[
  {
    "item": "地下室钥匙",
    "location": "二楼书房抽屉",
    "chapter": "chapter_2",
    "spoiler_level": "medium"
  }
]
```

`puzzles.json`：

```json
[
  {
    "puzzle_id": "clock_puzzle",
    "name": "钟表谜题",
    "chapter": "chapter_2",
    "hint_layers": [
      "先观察钟表旁边的符号。",
      "符号和日记里的时间顺序有关。"
    ],
    "solution": "..."
  }
]
```

### 6.5 Game Agents

后续新增或扩展子 Agent：

```text
hint_agent              低剧透提示
puzzle_agent            完整解谜
item_agent              物品位置
walkthrough_agent       流程攻略
lore_agent              剧情/世界观解释
mechanic_agent          操作/机制说明
debug_agent             卡关/疑似 bug 排查
recommendation_agent    游戏推荐
```

第一阶段不必全部实现成独立 LangGraph agent，可以先通过 system prompt + tool routing 落地。

优先级：

1. `hint_agent` / `puzzle_hint`
2. `item_agent`
3. `walkthrough_agent`
4. `lore_agent`
5. `debug_agent`

## 7. Lead Agent 改造

需要修改：

- `xuan_flow/agents/lead_agent.py`

新增 prompt 规则：

```text
For single-player puzzle-game related user requests, first call classify_game_intent.
Use route_to, spoiler_level, needs_game_context, and status to decide next action.
If needs_game_context is true and required context is missing, ask a concise clarification.
Respect spoiler_level. If spoiler_level is low, do not reveal direct solutions.
```

路由策略：

- `route_to=hint_agent`：优先调用 `puzzle_hint` 或低剧透提示流程。
- `route_to=puzzle_agent`：允许完整解法，但如果 `spoiler_level=low`，降级为提示。
- `route_to=item_agent`：读取 game context 和 items data。
- `route_to=walkthrough_agent`：读取 guide data。
- `route_to=lore_agent`：读取 lore data。
- `route_to=debug_agent`：先确认上下文，再给排查步骤。
- `status=needs_clarification`：追问用户，不直接答。

## 8. 日志和评估

已有日志：

- `.xuan-flow/game_intent_routes.jsonl`

每条记录包括：

- `timestamp`
- `text`
- `intent`
- `confidence`
- `route_to`
- `spoiler_level`
- `needs_game_context`
- `status`
- `secondary_intent`
- `predictions`

后续新增脚本：

- `scripts/analyze_game_intent_routes.py`

功能：

- 统计低置信度样本。
- 统计 `needs_clarification` 样本。
- 导出 top1/top2 接近的样本。
- 辅助生成下一轮 hard negative 数据。

## 9. 阶段计划

### Milestone 1：Lead Agent 使用分类器

目标：

让游戏相关请求优先调用 `classify_game_intent`，并根据 route 做初步处理。

任务：

- 更新 Lead Agent system prompt。
- 明确 `classify_game_intent` 的使用时机。
- 增加 5-10 条手动测试样例。

验收：

- “地下室钥匙在哪”会先调用分类器。
- “别剧透，只给提示”会得到低剧透处理。
- `.xuan-flow/game_intent_routes.jsonl` 出现对应记录。

### Milestone 2：GameSessionState

目标：

让系统知道玩家当前游戏、章节、位置、道具和剧透偏好。

任务：

- 新增 `xuan_flow/game_context/state.py`。
- 新增 `xuan_flow/tools/game_context.py`。
- 注册 `get_game_context` / `update_game_context`。
- 在 Lead Agent prompt 中要求缺上下文时先追问。

验收：

- 用户可以说“我在锈湖地下室，手上有旧钥匙和手电筒”并更新上下文。
- 后续问“下一步去哪”时能读取上下文。

### Milestone 3：文件型游戏知识库

目标：

让 item、walkthrough、lore 类回答不完全依赖模型常识。

任务：

- 建 `data/games/rusty_lake` 示例知识库。
- 新增读取工具。
- item_agent / lore_agent 使用本地资料回答。

验收：

- “地下室钥匙在哪”从 `items.json` 回答。
- “这个结局是什么意思”从 `lore.md` 摘要回答。

### Milestone 4：游戏子 Agent 扩展

目标：

从通用 researcher/coder 扩展到游戏领域 agent。

任务：

- 增加 `item_agent`、`walkthrough_agent`、`lore_agent`、`debug_agent` 配置。
- 给每个 agent 定义明确的 system prompt 和工具白名单。
- 接入 `task` 委派或 Lead Agent 直接调用。

验收：

- route_to 不同会触发不同处理策略。
- 子 Agent 不越权剧透。

### Milestone 5：数据闭环

目标：

用真实路由日志持续改进意图分类器。

任务：

- 写 `analyze_game_intent_routes.py`。
- 从日志中抽取 low_confidence / wrong_route 样本。
- 扩充训练集。
- 训练 v2 模型。

验收：

- v2 模型在新增 hard cases 上表现更好。
- 测试集 accuracy 不低于当前 0.90。

## 10. 风险和边界

### 10.1 数据集仍偏小

当前数据集主要是合成样本。测试集 0.91 accuracy 只能说明第一版可用，不能说明真实用户泛化很好。

缓解：

- 使用路由日志收集真实表达。
- 加入口语化、错别字、中英混杂、游戏名别名。
- 加入 hard negatives。

### 10.2 游戏知识覆盖不足

没有知识库时，模型可能幻觉。

缓解：

- 第一版只支持少数游戏。
- 明确回答“我缺少当前游戏资料，需要你补充场景/线索”。
- 优先做文件型知识库。

### 10.3 剧透控制需要强约束

仅靠 prompt 容易泄漏答案。

缓解：

- 继续保留 `puzzle_hint` 的 deterministic depth gate。
- 对 `spoiler_level=low` 的请求禁止完整解法。
- 把完整 solution 和 hint layers 分开存储。

### 10.4 现有中文文件存在编码显示问题

当前部分 prompt 文件在 PowerShell 输出中显示乱码，可能影响维护。

缓解：

- 后续整理游戏相关 prompt 时统一使用 UTF-8。
- 给关键 prompt 写英文或干净中文版本。

## 11. 下一步建议

下一步直接做 Milestone 1：

1. 修改 `lead_agent.py` 的 system prompt。
2. 明确要求游戏相关问题先调用 `classify_game_intent`。
3. 根据 `route_to` 和 `spoiler_level` 决定是否调用 `puzzle_hint`、追问上下文或普通回答。
4. 手动跑 5 条游戏请求，检查日志。

这一步完成后，项目才会从“分类器已接入”变成“Lead Agent 会主动使用游戏意图路由”。

