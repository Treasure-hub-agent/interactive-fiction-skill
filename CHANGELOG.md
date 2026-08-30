# 更新日志

完整版本历史与变更说明见 [references/changelog.md](references/changelog.md)。

## 当前版本：10.1.0

### v10.1.0（2026-08-30）定情之后 + 文艺感

**💗 定情之后，故事仍在继续（核心）**
- 情感叙事从「心动 → 暧昧 → 定情」三阶段，延伸到「定情之后」：日常亲密 / 共同决策 / 冲突 / 和解 四档场景
- 新增 `data/emotion_daily.json`（4 档 × 5 词标签池 + 触发关键词）
- 双锚定触发：`cp{}.stage = "定情"` + 用户输入命中关键词 → 自动切换到定情后语态
- 角色语态四类演变范式：沉淀型 / 释放型 / 震荡型 / 恒定型

**📖 长篇不再健忘**
- 每章自动生成「章摘要」（≤200 字），每 5 章自动生成「卷总结」（≤1000 字）
- 「章回顾」「卷回顾」「第N章讲了什么」指令
- 摘要可手动校准（`generated_by` 标记 LLM/human/verified）

**🧭 指令与工程**
- 标签池切换决策树（emotion / emotion_daily / general 三池互斥）
- `validate.py` 升级：emotion_daily 结构断言 + 决策树引用断言
- 单元测试 4 件套：test_data / test_schema / test_validate / test_manifest
- README 文艺感重写：水墨 Banner + 诗化引文 + 落款（全部视觉资源放 assets/）

详情见 [Releases](https://github.com/Treasure-hub-agent/interactive-fiction-skill/releases)。