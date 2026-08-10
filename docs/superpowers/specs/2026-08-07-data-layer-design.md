# v9.4.0 设计文档：数据层外置 + Schema 正式化（实验性）

> 版本：9.4.0（实验性）｜ 日期：2026-08-07 ｜ 状态：已批准（待实施）
> 定位：实验性架构更新——将「确定性 / 查表 / 存储」类功能从纯文字 prompt 固化为数据文件与 schema，保留 AI 全部创作与判断能力。

---

## 一、背景与动机

当前 skill 大部分规则以纯文字 prompt 承载，AI 每轮需「记忆 + 遵守」大量查表型规则（标签词库、字数区间、指令路由、运行时字段结构），存在以下问题：

1. **记忆负担**：标签词库、字数区间等需 AI 记住并准确复述，模型能力弱时易错、易单调
2. **token 占用**：常驻规则包含大量可外置的静态数据，占用每轮上下文
3. **无机器校验**：novel_runtime.json 字段结构靠 AI 自觉，字段错漏无法自动发现
4. **体验天花板**：模型能力越强体验越好——固化应只移除「AI 推理无价值」的机械部分，最大化释放 AI 创作力

**核心定位**：数据层外置（data/）+ 运行时格式正式化（schema/），**不改变任何叙事行为规则**。

---

## 二、设计原则

1. **不约束 AI 能力**：只固化确定性 / 机械 / 查表 / 存储类功能；叙事生成、选项设计、角色塑造、后果设计等 AI 核心能力全部保留在 prompt
2. **类型兼容（genre-neutral）**：词库、示例、规则表述不绑定特定题材（战斗 / 都市 / 悬疑 / 情感 / 权谋 / 日常等均适用），延续 v9.3.0 性别通用化原则
3. **可回退**：删除 data/ 与 schema/ 即回到 v9.3.x 行为，实验性零成本回退
4. **单一权威源**：data/*.json 为 AI 运行时的权威数据源；对应 md 表格保留给人审阅并标注「以 data/*.json 为准」

---

## 三、目标与非目标

### 目标
- 标签词库 / 字数区间 / 指令路由 三张查表外置为 data/*.json
- novel_runtime.json 补 JSON Schema（含 v9.3.1 `choices[]` 升级字段）
- SKILL.md P0 瘦身：正文抽走查表数据，改为「读取 data/*.json」指针
- MANIFEST.json 收录新文件

### 非目标（本版不做）
- 不做生成后校验器 / 脚本工具（依赖宿主执行能力，违背纯静态分发定位）
- 不做流程状态机（约束 AI 流程）
- 不新增 timeline.json / world_state.json（顺延下一阶段，复用 schema 体系）
- 不删除现有 md 表格（保留双源，实验期）

---

## 四、详细设计

### 第一节：目录结构

```
interactive-fiction/
├── data/                        # 数据层：AI 按需读取，纯静态 JSON
│   ├── tags.json                # 策略标签词库（类型中性，含亲密池）
│   ├── wordcount.json           # 字数区间表
│   └── commands.json            # 指令路由表
├── schema/                      # 运行时数据格式定义
│   └── novel_runtime.schema.json
└── (现有文件不变)
```

### 第二节：data/tags.json（标签词库 · 类型中性）

通用池 7 类 × 5 变体 + 亲密池 5 个：

```json
{
  "general": [
    { "type": "进攻型", "pace": "快",     "tags": ["进攻", "直取", "强攻", "摊牌", "抢攻"] },
    { "type": "避险型", "pace": "慢",     "tags": ["避险", "退守", "隐忍", "拖延", "回避"] },
    { "type": "策略型", "pace": "迂回",   "tags": ["策略", "周旋", "设局", "借力", "谈判"] },
    { "type": "探索型", "pace": "慢",     "tags": ["探索", "调查", "观察", "试探", "摸索"] },
    { "type": "社交型", "pace": "迂回",   "tags": ["社交", "安抚", "套话", "示好", "周旋"] },
    { "type": "亲密型", "pace": "慢/迂回", "tags": ["亲密", "暧昧", "撩拨", "示弱", "靠近"] },
    { "type": "越轨型", "pace": "快",     "tags": ["越轨", "冒险", "赌注", "破格", "孤注一掷"] }
  ],
  "intimacy": [
    { "tag": "温柔主导", "pace": "慢" },
    { "tag": "克制回应", "pace": "慢" },
    { "tag": "主动迎合", "pace": "快" },
    { "tag": "被动承受", "pace": "慢" },
    { "tag": "退让收束", "pace": "迂回" }
  ]
}
```

**约束（保留，不改）**：A/B/C 标签互不相同且来自不同类型（互斥），覆盖快 / 慢 / 迂回三种节奏；亲密场景用 intimacy 池并覆盖三节奏。变体词为建议选择面，AI 可依据世界观与场景基调取最贴切者，实验期允许使用词库外贴切词。

### 第三节：data/wordcount.json（字数区间表）

```json
{
  "main": { "min": 500, "max": 1200 },
  "scenes": {
    "氛围展开":     { "min": 800, "max": 1200 },
    "日常过渡":     { "min": 400, "max": 600 },
    "紧迫战斗":     { "min": 250, "max": 400 },
    "对话快速交换": { "min": 250, "max": 400 },
    "快进首段":     { "min": 250, "max": 400 },
    "随机开局首段": { "min": 300, "max": 800 }
  }
}
```

### 第四节：data/commands.json（指令路由表）

```json
[
  { "domain": "激活", "aliases": ["加载小说包", "加载互动小说技能包"], "effect": "弹出路线选择", "load": null },
  { "domain": "存档", "aliases": ["存档", "存一下", "记个档"], "effect": "手动持久存档", "load": "extended/storage_runtime.md" },
  { "domain": "进度", "aliases": ["进度"], "effect": "剧情进度仪表盘", "load": "extended/route_system.md" },
  { "domain": "帮助", "aliases": ["帮助", "使用指南"], "effect": "加载使用指南", "load": "references/usage-guide.md" }
]
```

> 完整指令→效果映射以 `references/command_nav.md` 为权威；data/commands.json 为高频指令的快速路由切片。

### 第五节：schema/novel_runtime.schema.json

JSON Schema（draft-07）定义 novel_runtime.json 全字段，含 v9.3.1 升级：

- `choices[]`：`type` 枚举 `consequence / foreshadow / promise` + 兼容既有值（`关系` / `flag` 等）、`surface_by`（到期段落号）、`foreclosed`（未选路径）、`flag`（dilemma / 世界状态长期印记）
- 全部字段 optional 或含默认 → 旧存档无缝兼容

### 第六节：SKILL.md 改造

- 字数区间表 → 指针：「区间数值见 `data/wordcount.json`，按场景查表」
- 标签词库 → 指针：「选词从 `data/tags.json` 读取，A/B/C 互斥 / 节奏约束不变」
- 指令路由 → 指针：「指令解析查 `data/commands.json`，完整导航见 `references/command_nav.md`」
- 加载索引表新增 `data/` / `schema/` 路由行
- 现有 md 表格保留，标注「以 data/*.json 为准」

### 第七节：版本工程

| 文件 | 动作 |
|------|------|
| `data/tags.json` | 新增 |
| `data/wordcount.json` | 新增 |
| `data/commands.json` | 新增 |
| `schema/novel_runtime.schema.json` | 新增 |
| `SKILL.md` | P0 瘦身 + 指针改造 + 加载索引更新 |
| `references/options-quickref.md` | 标签词库表标注「以 data/tags.json 为准」+ 同步扩充变体词 |
| `references/command_nav.md` | 标注「以 data/commands.json 为准」 |
| `references/changelog.md` | 新增 v9.4.0 条目 |
| `VERSION` | 9.4.0 |
| `MANIFEST.json` | 重新生成（收录 data/ + schema/） |

---

## 五、实验性边界与回退

- 删除 data/ + schema/ 并还原 SKILL.md 指针即回退 v9.3.x
- 不改变任何叙事行为规则，只改变数据载体
- 词库变体词为「建议选择面」，AI 仍可依据世界观用词库外贴切词（实验期宽松）

---

## 六、验证方式

- MANIFEST.json 校验：data/ + schema/ 全部收录，SHA 匹配（LF 基准）
- JSON 语法校验：data/*.json 与 schema 文件可被解析
- novel_runtime.schema.json 用样例数据验证（choices[] 新旧字段均可通过）
- 交叉引用审查：SKILL.md 指针 → data/ 文件全部可达

---

## 七、后续计划

- schema 扩展：character_card.schema.json、index.schema.json
- timeline.json / world_state.json 账本（原 v9.4.0 规划，复用 schema 体系）
- 依据实验反馈决定：数据文件是否成为唯一权威源（移除 md 表）
