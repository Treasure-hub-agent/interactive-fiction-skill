# 酒馆卡导入（SillyTavern / Tavo / Chub）· P2 按需加载

> 本章在用户提供酒馆卡文件、要求导入或使用外部角色卡时加载。
> 转换脚本 `scripts/tavern_prep.py`（纯标准库）；本文件规定**怎么读进来、怎么按酒馆语义注入、哪些不注入**。

## 一、能读什么

| 载体 | 说明 | 实测 |
|------|------|------|
| **PNG** | tEXt chunk 内嵌 base64 JSON（键 `chara` 或 `ccv3`）；酒馆/Chub 下载卡的主流形态 | ✅ 40 张实测通过 |
| **JSON** | 裸 V2 对象，或带 `spec`/`data` 包裹的 V2/V3 | ✅ 15 张实测通过 |
| **CHARX** | zip 包（内含 `card.json`） | ✅ 结构可读 |

源文件**只读**：解析全程不修改、不回写用户提供的卡；导入前会算 sha256，导入后复核一致。

## 二、导入流程

### 触发

- `导入酒馆卡 <路径>` / `加载酒馆卡 <路径>` / `读一下这张卡 <路径>`
- 用户直接给卡文件路径（PNG / JSON / CHARX）时同样触发
- 未给路径时**先问一句**要卡文件还是要卡目录，**不自行搜索本地路径猜位置**

### 步骤

1. **识别与预览**（只读，不写盘）：
   ```
   python3 scripts/tavern_prep.py inspect <卡文件>
   ```
   输出「接入卡」：角色名 / 作者 / 标签 / 开场白字数 / 字段齐缺 / 世界书条目数与构成。
   以角色口吻向用户复述摘要（不弹系统界面），缺失字段标 `[待补]`，由用户决定先补还是直接开。

2. **确认后落盘**：
   ```
   python3 scripts/tavern_prep.py import <卡文件> --novel <小说名>
   ```
   （预演加 `--dry-run`）

3. **落盘结构**（全部在小说目录内，不新建存储体系）：
   ```
   {小说}/{characters}/{角色名}/           profile.md / personality.md / interaction.md / openings.md
   {小说}/lorebook/{角色名}/              条目文件（每条一个 md，头部带酒馆语义）
   {小说}/source/tavern/{角色名}/         源卡原样留档 + 卡信息.json
   ```

## 三、字段映射表

| 酒馆卡字段 | 落到 IF 的哪里 | 说明 |
|---|---|---|
| `name` | 角色目录名 + `{角色名}` 宏替换值 | |
| `description` | `characters/<名>/profile.md` | 身份/外貌/背景 |
| `personality` | `personality.md` | 缺失时由 description 兜底 |
| `mes_example` | `interaction.md`（声线基因） | 对话示例是最强的声线锚点 |
| `scenario` | 世界观段（由模型并入 `worldbuilding/`） | 只作底色 |
| `first_mes` / `alternate_greetings` | `openings.md` | 开局首轮 / 备选开局 |
| **`character_book.entries`** | **`lorebook/<名>/`** | **按酒馆语义注入（见下节）** |
| `{{user}}` / `{{char}}` | 替换为「你」/ 角色名 | 其余 `{{...}}` 宏去掉花括号保留内容 |
| `system_prompt` | ⚠️ **只留档 `source/`，不注入** | 规则主权归本 skill |
| `post_history_instructions` | ⚠️ **只留档 `source/`，不注入** | 同上 |
| `creator_notes` / `creator` / `tags` | 留档 `卡信息.json` | 仅作署名与追溯 |
| `extensions`（含 chub/depth_prompt） | 留档 | 非 IF 概念，不注入 |

**为什么 system_prompt / post_history_instructions 不注入**：卡内这两个字段是酒馆的**全局写作规则**
（如「你是叙事者，必须…」），与本 skill 的 P0 铁律（五选项 / 字数区间 / 视角规则）是两套规则源，
同时生效会互相冲撞并冲掉铁律 #0。因此**内容保真（原样留档可查），规则主权归本 skill**。

## 四、世界书条目：按酒馆语义注入

条目文件头部携带酒馆语义（由脚本写入，勿手改注释行）：

```
<!-- 酒馆卡条目（由 tavern_prep.py 转换，勿手改注释行）
keys: 宗门,门派
constant: false
probability: 85
order: 200
position: after_char
source_id: 5
-->
```

注入语义（`novel.py` 的 `tavern_hits`）：

| 酒馆字段 | IF 里的处理 | 说明 |
|---|---|---|
| `keys` | **命中词集** | 命中源权重：用户输入 > 场景/地点/主角状态 > 角色名 |
| `constant: true` | **必入**，排最前 | 但仍受预算硬约束（见下） |
| `probability` | 命中后的**注入权重** | 权重高者优先；不做随机，保证简报确定性 |
| `insertion_order` / `order` | **排序优先级** | 值小者优先（与酒馆习惯一致） |
| `secondary_keys` | 留档 | ⚠️ IF 单轮扫描，不实现二级条件 |
| `position` / depth | ⚠️ **降级** | IF 的 P0 常驻前缀顺序固定（红线 A4），一律并入 `[设定]` 段 |
| `recursive_scanning` | ⚠️ **降级** | 单轮扫描，不做递归触发 |

### 预算与配额（防爆窗）

实测真实卡的世界书规模差异极大：条目数 **0～48 条**、合计 **683～70,912 字**。
若把 constant 条目全部常驻，会挤掉关键词命中并爆占上下文（**红线 A5：勿退化为全量常驻**）。

因此硬约束如下：

- 单轮 `[设定]` 总条数 ≤ `LORE_MAX`（4 条；`--full` 不限）
- **常驻条目只占预算的 1/2**（`LORE_CONST_RATIO=2`），其余名额留给关键词命中
- 单条注入 ≤ `LORE_ENTRY_INJECT_MAX`（300 字），超出截断并标注「详见 lorebook 原文」
- 完整内容永远留在 `lorebook/` 与 `source/` 里，可随时回查，不进每轮上下文

### 与既有世界书的合并

`[设定]` 段同时吃两路来源并去重：① 既有 `worldbuilding/` + `characters/` 的词条表；
② 酒馆卡 `lorebook/` 条目。酒馆命中优先展示（更贴本轮输入），合并后统一受预算截断。

## 五、边界与不做

- ❌ **不改交互形态**：导入后仍是选项驱动的互动小说，不做免五选项的聊天模式（那是 `ai-with-u` 的职责）
- ❌ **不注入卡内规则字段**（system_prompt / post_history_instructions / extensions）
- ❌ **不新建存储体系 / 不新建 schema 文件**：落进 IF 现有 `characters/` 与新增的 `lorebook/`
- ❌ **不联网爬卡**：只读用户提供的本地文件；联网检索需用户明确要求（沿用数据获取铁律）
- ❌ **不改源卡**：解析全程只读，导入前后 sha256 必须一致

## 六、容错

- 单张卡损坏（PNG 无 chara chunk / JSON 语法错 / CHARX 无卡）→ 只报该卡，不影响其他
- 字段类型异常（`keys: 5`、`entries` 为任意结构）→ 归一化容错，不得崩溃
- 条目文件损坏 / 非酒馆格式 → 静默跳过，不中断简报
- 无 `lorebook/` 目录 → `[设定]` 段退化为既有行为（零回归）

## 七、用到的脚本

| 脚本 | 命令 | 说明 |
|---|---|---|
| `scripts/tavern_prep.py` | `inspect <卡>` | 只读解析，输出接入卡 |
| | `import <卡> --novel <名> [--dry-run]` | 解析并落盘 |
| `scripts/novel.py` | `brief --input <用户输入>` | 简报（含酒馆卡按需注入） |
