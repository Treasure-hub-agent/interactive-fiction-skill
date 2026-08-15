# 数据层说明（data/）

> 本目录为 skill 的**查表数据层**（v9.4.0 起）：AI 按需读取，纯静态 JSON，不包含任何代码或行为规则。删除本目录即回退到 v9.3.x 的纯文字规则（对应 SKILL.md 指针需同步还原）。

## 文件清单与约束

| 文件 | 用途 | 结构与约束 |
|------|------|-----------|
| `tags.json` | 选项策略标签词库 | `general[7]`（type/pace/tags[5]）+ `emotion[7]`（tag/pace）。约束：general 内 35 词全库去重；pace 取值 `快/慢/迂回`（单值）；A/B/C 选词须不同类型（互斥）且覆盖快/慢/迂回三节奏；情感场景用 emotion 池 |
| `wordcount.json` | 正文字数区间表 | `main{min,max}` + `scenes{}`（场景→区间）。约束：例外优先于主区间；场景判定见 SKILL.md §正文格式约束·场景区间选择 |
| `commands.json` | 指令快速路由（高频子集） | 数组，每项 `{domain, aliases[], effect, load}`。约束：完整指令→效果映射以 `references/command_nav.md` 为权威，本文件仅为高频子集 |
| `random_pool.json` | 随机开局抽取池 | `worldviews[12]`（id/name/hint）+ `dimensions{route,mode,view}` + `protagonist_templates[]`。约束：等权抽取；换批拒绝采样（四维重合≥3 或相同→重抽）；主角模板连续两次不得相同 |

## pace 校验

数据层的 `pace` 字段仅允许 `快 / 慢 / 迂回` 三个单值（情感互动池与通用池同规则）。开发期可用脚本校验全部 pace 合法、标签无重复（见 MANIFEST 生成流程的配套校验思路）。

## 维护约定

- 修改数据文件后须同步 `MANIFEST.json`（重新生成 SHA256）
- 修改词库/区间后，若对应 md 审阅表（options-quickref / SKILL.md）有副本，须同步或标注「以 data/*.json 为准」
