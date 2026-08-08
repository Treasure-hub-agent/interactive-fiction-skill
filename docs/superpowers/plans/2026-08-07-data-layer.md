# v9.4.0 数据层外置 + Schema 正式化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将标签词库 / 字数区间 / 指令路由三张查表外置为 `data/*.json`，为 `novel_runtime.json` 补 JSON Schema，SKILL.md P0 瘦身为「读数据指针」，不改变任何叙事行为规则。

**Architecture:** 纯静态 JSON 数据文件（AI 运行时按需读取）+ JSON Schema（draft-07，宽松兼容旧存档）；SKILL.md 保留全部行为规则，仅将查表数据改为指针；md 表格保留为人审阅并标注「以 data/*.json 为准」。不引入任何代码/脚本到运行时（MANIFEST 生成等仍为开发期工具）。

**Tech Stack:** JSON、JSON Schema draft-07、Markdown；验证用 Python（json 解析、SHA256）+ PowerShell（MANIFEST 生成）。

**关键约束（来自 spec）**：
- 类型兼容：词库与示例不绑定题材（战斗/都市/悬疑/情感/权谋均适用）
- 不约束 AI 能力：只固化查表/存储类功能
- 可回退：删除 data/ + schema/ 并还原 SKILL.md 即回退 v9.3.x
- 工作区文件均为 CRLF；git commit 时 autocrlf 转 LF；MANIFEST 的 SHA 以 LF 规范化内容为基准

---

## Task 1: 创建 `data/tags.json`（标签词库 · 类型中性）

**Files:**
- Create: `data/tags.json`

- [ ] **Step 1: 创建文件**

写入以下内容（UTF-8 无 BOM，CRLF 行尾）：

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

- [ ] **Step 2: 验证 JSON 语法**

Run: `python -c "import json;d=json.load(open(r'C:\Users\11387\interactive-fiction-skill\data\tags.json',encoding='utf-8'));assert len(d['general'])==7 and len(d['intimacy'])==5;print('OK', len(d['general']), len(d['intimacy']))"`
Expected: `OK 7 5`

- [ ] **Step 3: Commit**

```bash
git -C C:\Users\11387\interactive-fiction-skill add data/tags.json
git -C C:\Users\11387\interactive-fiction-skill commit -m "feat: v9.4.0 数据层 data/tags.json 标签词库（类型中性 7x5 + 亲密池）"
```

---

## Task 2: 创建 `data/wordcount.json`（字数区间表）

**Files:**
- Create: `data/wordcount.json`

- [ ] **Step 1: 创建文件**

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

- [ ] **Step 2: 验证 JSON 语法**

Run: `python -c "import json;d=json.load(open(r'C:\Users\11387\interactive-fiction-skill\data\wordcount.json',encoding='utf-8'));assert d['main']=={'min':500,'max':1200};print('OK', len(d['scenes']))"`
Expected: `OK 6`

- [ ] **Step 3: Commit**

```bash
git -C C:\Users\11387\interactive-fiction-skill add data/wordcount.json
git -C C:\Users\11387\interactive-fiction-skill commit -m "feat: v9.4.0 数据层 data/wordcount.json 字数区间表"
```

---

## Task 3: 创建 `data/commands.json`（指令路由表）

**Files:**
- Create: `data/commands.json`

- [ ] **Step 1: 创建文件**

```json
[
  { "domain": "激活", "aliases": ["加载小说包", "加载互动小说技能包"], "effect": "弹出路线选择", "load": null },
  { "domain": "存档", "aliases": ["存档", "存一下", "记个档"], "effect": "手动持久存档", "load": "extended/storage_runtime.md" },
  { "domain": "进度", "aliases": ["进度"], "effect": "剧情进度仪表盘", "load": "extended/route_system.md" },
  { "domain": "帮助", "aliases": ["帮助", "使用指南"], "effect": "加载使用指南", "load": "references/usage-guide.md" }
]
```

- [ ] **Step 2: 验证 JSON 语法 + 字段完整性**

Run: `python -c "import json;d=json.load(open(r'C:\Users\11387\interactive-fiction-skill\data\commands.json',encoding='utf-8'));assert all(set(x)=={'domain','aliases','effect','load'} for x in d);print('OK', len(d))"`
Expected: `OK 4`

- [ ] **Step 3: Commit**

```bash
git -C C:\Users\11387\interactive-fiction-skill add data/commands.json
git -C C:\Users\11387\interactive-fiction-skill commit -m "feat: v9.4.0 数据层 data/commands.json 指令路由表"
```

---

## Task 4: 创建 `schema/novel_runtime.schema.json`

**Files:**
- Create: `schema/novel_runtime.schema.json`

- [ ] **Step 1: 创建文件**（字段依据 `extended/storage_runtime.md` §字段速查 与 §`choices[]` 升级字段规范；全字段 optional 或宽松，旧存档兼容）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "novel_runtime",
  "type": "object",
  "properties": {
    "v":          { "type": "string" },
    "ua":         { "type": "string" },
    "nm":         { "type": "string" },
    "rn":         { "type": "string" },
    "md":         { "type": "string" },
    "vw":         { "type": "integer", "enum": [1, 2, 3] },
    "ch":         { "type": "integer" },
    "sc":         { "type": "string" },
    "wc":         { "type": "integer" },
    "mp":         { "type": "string" },
    "dv":         { "type": ["integer", "null"] },
    "cc":         { "type": ["string", "null"] },
    "sb":         { "type": "array", "items": { "type": "string" } },
    "kp":         { "type": "array", "items": { "type": "string" } },
    "pf":         { "type": "array", "items": { "type": "object" } },
    "rs":         { "type": "object" },
    "cp":         { "type": "object" },
    "scs":        { "type": "object" },
    "npcs":       { "type": "object" },
    "choices":    {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "seg":        { "type": "integer" },
          "picked":     { "type": "string" },
          "tag":        { "type": "string" },
          "type":       { "type": "string" },
          "detail":     { "type": "string" },
          "tier":       { "type": "string" },
          "surface_by": { "type": "integer" },
          "foreclosed": { "type": "array", "items": { "type": "string" } },
          "flag":       { "type": ["string", "object", "boolean", "null"] }
        },
        "additionalProperties": true
      }
    },
    "st":         { "type": "object" },
    "theme":      { "type": ["string", "null"] },
    "prv":        { "type": "string", "maxLength": 200 },
    "ex":         { "type": "integer" },
    "eb":         { "type": "integer" },
    "seg_count":  { "type": "integer" },
    "ms":         { "type": "integer" },
    "scs_bak":    { "type": ["object", "null"] }
  },
  "additionalProperties": true
}
```

- [ ] **Step 2: 验证 JSON 语法 + 结构断言**

Run: `python -c "import json;s=json.load(open(r'C:\Users\11387\interactive-fiction-skill\schema\novel_runtime.schema.json',encoding='utf-8'));assert s['properties']['choices']['items']['properties']['surface_by']['type']=='integer';print('schema OK')"`
Expected: `schema OK`

- [ ] **Step 3: Commit**

```bash
git -C C:\Users\11387\interactive-fiction-skill add schema/novel_runtime.schema.json
git -C C:\Users\11387\interactive-fiction-skill commit -m "feat: v9.4.0 schema/novel_runtime.schema.json 运行时格式定义（含 choices[] 升级字段）"
```

---

## Task 5: 修改 `SKILL.md`（P0 瘦身 + 指针化）

**Files:**
- Modify: `SKILL.md`

- [ ] **Step 1: 字数区间表 → 指针**

将「**字数区间**：每轮正文 **500-1200 字**（硬性主区间；下述压缩场景为合法例外，**例外优先于主区间判定**，例外轮次不受 500 字下限约束，仍须 ≤1200 字上限）。」之后的分项列表（氛围展开 / 日常过渡 / 紧迫战斗 / 快进首段 / 随机开局首段 / 超出 1200 字）合并为指针 + 保留超出规则：

```markdown
**字数区间**：每轮正文 **500-1200 字**（硬性主区间；下述压缩场景为合法例外，**例外优先于主区间判定**，例外轮次不受 500 字下限约束，仍须 ≤1200 字上限）。各场景区间数值见 `data/wordcount.json`（氛围展开 / 亲密场景充分使用区间；日常过渡 400-600；紧迫战斗 / 对话快速交换 / 快进首段 250-400；随机开局首段 300-800 字，见 `extended/route_system.md` §随机开局）。
- 超出 1200 字：在情势转折点自然收束，剩余内容作为截断尾注
```

- [ ] **Step 2: 标签词库 → 指针**

`#### 选项策略标签` 段落中「A/B/C 标签必须互不相同且至少覆盖两种策略类型。完整词汇库见 `references/options-quickref.md`。」改为：

```markdown
A/B/C 标签必须互不相同且至少覆盖两种策略类型。选词从 `data/tags.json` 读取（7 类 × 5 变体 + 亲密池，类型中性），词库外贴切词实验期允许。完整词汇库见 `references/options-quickref.md`（以 `data/tags.json` 为准）。
```

- [ ] **Step 3: 指令路由 → 指针**

「## 快速指令卡」段落开头追加一行：

```markdown
> 指令解析快速路由查 `data/commands.json`；完整指令→效果映射、菜单导航、非剧情阶段边界以 `references/command_nav.md` 为权威。
```

- [ ] **Step 4: 加载索引表新增 data/ / schema/ 路由行**

在「## 加载索引（路由表 · P0 常驻）」表格中新增两行：

```markdown
| 查表数据（标签词库 / 字数区间 / 指令快速路由） | `data/tags.json` / `data/wordcount.json` / `data/commands.json` |
| 运行时 JSON 格式（novel_runtime.json 字段） | `schema/novel_runtime.schema.json` |
```

- [ ] **Step 5: 验证指针存在**

Run: `Select-String -Path C:\Users\11387\interactive-fiction-skill\SKILL.md -Pattern "data/tags.json|data/wordcount.json|data/commands.json|schema/novel_runtime.schema.json" | Measure-Object | Select-Object -ExpandProperty Count`
Expected: 出现 4+ 次

- [ ] **Step 6: Commit**

```bash
git -C C:\Users\11387\interactive-fiction-skill add SKILL.md
git -C C:\Users\11387\interactive-fiction-skill commit -m "feat: v9.4.0 SKILL.md P0 瘦身（字数/标签/指令查表指针化 + 加载索引更新）"
```

---

## Task 6: 修改 `references/options-quickref.md`（词库扩充 + 标注）

**Files:**
- Modify: `references/options-quickref.md`

- [ ] **Step 1: 词库表扩充为 7 类 × 5 变体 + 标注**

将「## 标签词汇库」段落（原 7 类单标签表 + 亲密池说明）替换为：

```markdown
## 标签词汇库

> 权威数据源：`data/tags.json`（本表为人审阅副本）。选词从 `data/tags.json` 读取，A/B/C 互斥 / 节奏约束不变。

| 类型（节奏） | 变体词 |
|------|------|
| 进攻型（快） | 进攻 / 直取 / 强攻 / 摊牌 / 抢攻 |
| 避险型（慢） | 避险 / 退守 / 隐忍 / 拖延 / 回避 |
| 策略型（迂回） | 策略 / 周旋 / 设局 / 借力 / 谈判 |
| 探索型（慢） | 探索 / 调查 / 观察 / 试探 / 摸索 |
| 社交型（迂回） | 社交 / 安抚 / 套话 / 示好 / 周旋 |
| 亲密型（慢/迂回） | 亲密 / 暧昧 / 撩拨 / 示弱 / 靠近 |
| 越轨型（快） | 越轨 / 冒险 / 赌注 / 破格 / 孤注一掷 |

> 亲密场景标签池：温柔主导(慢) / 克制回应(慢) / 主动迎合(快) / 被动承受(慢) / 退让收束(迂回)，A/B/C 选自该池仍须覆盖快/慢/迂回三节奏；结合阶段收尾或选 E 后场景结束，恢复普通标签池
```

- [ ] **Step 2: 验证**

Run: `Select-String -Path C:\Users\11387\interactive-fiction-skill\references\options-quickref.md -Pattern "data/tags.json|进攻 / 直取" | Measure-Object | Select-Object -ExpandProperty Count`
Expected: 2+

- [ ] **Step 3: Commit**

```bash
git -C C:\Users\11387\interactive-fiction-skill add references/options-quickref.md
git -C C:\Users\11387\interactive-fiction-skill commit -m "feat: v9.4.0 options-quickref 词库扩充（7x5 类型中性）+ 标注权威源"
```

---

## Task 7: 修改 `references/command_nav.md`（标注权威源）

**Files:**
- Modify: `references/command_nav.md`

- [ ] **Step 1: 头部标注**

在文件头部「> 说明」块后追加一行：

```markdown
> **【数据层】** 高频指令快速路由见 `data/commands.json`；本文件为完整指令→效果映射与导航规范的**权威字典**。
```

- [ ] **Step 2: 验证 + Commit**

Run: `Select-String -Path C:\Users\11387\interactive-fiction-skill\references\command_nav.md -Pattern "data/commands.json" | Measure-Object | Select-Object -ExpandProperty Count`
Expected: 1+

```bash
git -C C:\Users\11387\interactive-fiction-skill add references/command_nav.md
git -C C:\Users\11387\interactive-fiction-skill commit -m "feat: v9.4.0 command_nav 标注 data/commands.json 为快速路由"
```

---

## Task 8: 更新 `VERSION` + `references/changelog.md`

**Files:**
- Modify: `VERSION`、`references/changelog.md`

- [ ] **Step 1: VERSION → 9.4.0**

将 `VERSION` 内容写为 `9.4.0`（5 字节无换行）。

- [ ] **Step 2: changelog 顶部新增 v9.4.0 条目**（在 `## v9.3.1...` 之前插入）

```markdown
## v9.4.0（2026-08-07）· 数据层外置 + Schema 正式化（实验性）

- **数据层外置**：标签词库 / 字数区间 / 指令快速路由三张查表从纯文字 prompt 固化为 `data/*.json`，AI 按需读取，SKILL.md P0 瘦身
- **Schema 正式化**：新增 `schema/novel_runtime.schema.json` 定义运行时 JSON 格式（含 v9.3.1 `choices[]` 升级字段），旧存档兼容
- **类型兼容**：标签词库扩充为 7 类 × 5 变体 + 亲密池 5 个，全部类型中性（战斗 / 都市 / 悬疑 / 情感 / 权谋等题材通用）
- **不约束 AI**：只固化查表 / 存储类功能，叙事生成与判断全部保留；删除 data/ + schema/ 即回退 v9.3.x
```

- [ ] **Step 3: 验证 + Commit**

Run: `Get-Content C:\Users\11387\interactive-fiction-skill\VERSION; Select-String -Path C:\Users\11387\interactive-fiction-skill\references\changelog.md -Pattern "## v9.4.0" | Measure-Object | Select-Object -ExpandProperty Count`
Expected: `9.4.0` + `1`

```bash
git -C C:\Users\11387\interactive-fiction-skill add VERSION references/changelog.md
git -C C:\Users\11387\interactive-fiction-skill commit -m "feat: v9.4.0 VERSION 9.4.0 + changelog 数据层条目"
```

---

## Task 9: 重新生成 MANIFEST + 全量校验

**Files:**
- Modify: `MANIFEST.json`

- [ ] **Step 1: 重新生成 MANIFEST（LF 基准，排除自身）**

Run（PowerShell）:
```powershell
$base = "C:\Users\11387\interactive-fiction-skill"
$all = Get-ChildItem -Path $base -Recurse -File -Force | Where-Object { $_.FullName -notmatch '\\.git\\' -and $_.Name -ne 'MANIFEST.json' }
$sorted = $all | Sort-Object FullName
$files = [ordered]@{}; $total = 0
foreach ($f in $sorted) {
  $rel = $f.FullName.Substring($base.Length + 1).Replace('\','/')
  $raw = [System.IO.File]::ReadAllBytes($f.FullName)
  $out = New-Object System.Collections.Generic.List[byte]
  for ($i=0; $i -lt $raw.Length; $i++) { if ($raw[$i] -eq 13 -and ($i+1) -lt $raw.Length -and $raw[$i+1] -eq 10) { continue }; $out.Add($raw[$i]) }
  $norm = $out.ToArray()
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $hash = [System.BitConverter]::ToString($sha.ComputeHash($norm)).Replace('-','').ToLower()
  $files[$rel] = [ordered]@{ sha256 = $hash; bytes = $norm.Length }
  $total += $norm.Length
}
$m = [ordered]@{ version = '9.4.0'; generated = '2026-08-07T00:00:00Z'; root = 'interactive-fiction'; files = $files; total_files = $sorted.Count; total_bytes = $total }
$json = $m | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText((Join-Path $base 'MANIFEST.json'), $json, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "total_files=$($sorted.Count) total_bytes=$total"
```
Expected: total_files = 38（34 现有 + 3 data + 1 schema；若计划文档已加入仓库则为 39）

- [ ] **Step 2: 校验 MANIFEST 全部 SHA 匹配（LF 基准）**

Run（Python）:
```python
import json, hashlib, os, sys
base = r"C:\Users\11387\interactive-fiction-skill"
m = json.load(open(os.path.join(base,'MANIFEST.json'),encoding='utf-8'))
fail = 0
for rel, meta in m['files'].items():
    raw = open(os.path.join(base, rel.replace('/', os.sep)),'rb').read().replace(b'\r\n', b'\n')
    if hashlib.sha256(raw).hexdigest() != meta['sha256'] or len(raw) != meta['bytes']:
        print('[FAIL]', rel); fail += 1
print('files=', len(m['files']), 'fail=', fail)
assert fail == 0 and m['version'] == '9.4.0'
print('MANIFEST OK')
```
Expected: `files= 38 fail= 0` + `MANIFEST OK`

- [ ] **Step 3: Commit**

```bash
git -C C:\Users\11387\interactive-fiction-skill add MANIFEST.json
git -C C:\Users\11387\interactive-fiction-skill commit -m "chore: v9.4.0 MANIFEST 重新生成（收录 data/ + schema/）"
```

---

## Task 10: 交叉引用审查 + 最终验证

**Files:**
- 只读验证，不改文件（除非发现断链）

- [ ] **Step 1: 交叉引用检查**

Run: `python C:\Users\11387\_xref_analysis.py`
Expected: 断链仅剩「运行时生成文件」描述（profile.md / 001.md / conflicts.md 等）；data/ schema/ 无断链；data/*.json 被 SKILL.md / options-quickref / command_nav 引用；schema 被 SKILL.md 加载索引引用

- [ ] **Step 2: 提交后 blob vs MANIFEST 全量匹配**

Run（Python）:
```python
import json, hashlib, subprocess, os
base = r"C:\Users\11387\interactive-fiction-skill"
m = json.load(open(os.path.join(base,'MANIFEST.json'),encoding='utf-8'))
fail = 0
for rel, meta in m['files'].items():
    blob = subprocess.check_output(['git','-C',base,'cat-file','blob','HEAD:'+rel])
    if hashlib.sha256(blob).hexdigest() != meta['sha256'] or len(blob) != meta['bytes']:
        print('[FAIL]', rel); fail += 1
print('blob vs MANIFEST fail=', fail)
assert fail == 0
```
Expected: `blob vs MANIFEST fail= 0`

- [ ] **Step 3: 确认工作区干净**

Run: `git -C C:\Users\11387\interactive-fiction-skill status --short`
Expected: 空输出
