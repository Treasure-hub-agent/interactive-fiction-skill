<p align="center">
  <img alt="互动小说创作规范" src="assets/banner.svg#gh-light-mode-only" width="100%"/>
  <img alt="互动小说创作规范（深色）" src="assets/banner-dark.svg#gh-dark-mode-only" width="100%"/>
</p>

<h1 align="center" style="font-family: 'Noto Serif SC', 'Songti SC', serif; font-size: 1.9em; letter-spacing: 0.08em; margin-bottom: 0.1em; margin-top: 0.6em;">
  interactive-fiction
</h1>

<p align="center" style="color:#8a7c6f;">
  —— 互动小说创作完整规范 v10.3.0 ——
</p>

<p align="center" style="color:#4a3f35;line-height:1.95;">
  <b>不是「AI 替你写小说」，是「你选，它写」。</b><br/>
  你说开头 → 它写一段 + 摆出 5 个选项 → 你选 → 接着演<br/>
  <span style="color:#8a7c6f;">不部署、不配 API、不写代码 —— 装进 AI 助手就能开演</span>
</p>

<p align="center">
  🌐 <b>中文</b> ｜ <a href="README.en.md">English</a> ｜ <a href="https://treasure-hub-agent.github.io/interactive-fiction-skill/"><b>🖥 网页版</b></a>
</p>

<p align="center"><sub>
An AI-agent skill for interactive fiction — Chinese-first: choice-driven storytelling with 5 options per turn, long-novel consistency, save/load, and character cards.
</sub></p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"/></a>
  <a href="VERSION"><img alt="Version" src="https://img.shields.io/badge/version-10.3.0-orange.svg"/></a>
  <a href="https://github.com/Treasure-hub-agent/ai-with-u"><img alt="ai-with-u" src="https://img.shields.io/badge/ecosystem-ai--with--u-9cf.svg"/></a>
  <a href="https://treasure-hub-agent.github.io/interactive-fiction-skill/"><img alt="网页版" src="https://img.shields.io/badge/%E7%BD%91%E9%A1%B5%E7%89%88-online-C4553F.svg"/></a>
</p>

---

## ✨ 一拍三式

<img alt="玩法循环：你说开头 → 它写一段 → 你选 A–E" src="assets/how.svg" width="100%"/>

**interactive-fiction** 是给 AI 用的「互动小说创作指南」——装上它，AI 就能写出一部有选项、有张力、有沉浸感的互动小说，像玩一场文字冒险游戏，却体验着商业软件般的打磨。

---

## 🕮 差在哪

<img alt="普通 prompt 与装上 interactive-fiction 的对比" src="assets/compare.svg" width="100%"/>

普通 prompt 是「建议」，本 skill 是「硬规则 + 自检清单」——以上问题全部变成铁律，由 AI 每轮输出前强制自检。**落笔即合律，行文有法度。**

---

## 📖 它管什么

<img alt="六项核心能力" src="assets/features.svg" width="100%"/>

<details>
<summary><b>展开完整能力对照表</b>（含视角、字数、分层加载、记忆外置、子 Agent）</summary>

| 能力 | 说明 |
|:-----|:-----|
| 🔴 铁律 #0 选项机制 | 每轮正文输出后强制跟 A/B/C/D/E 五选项（参考指引+兜底），自由输入等权/优先推进；正文结束不结束对话 |
| 🎭 视角一致性 | 主角「我/你」、对象「他/她」切换有硬规则，多角色切换有格式约束 |
| 📏 字数区间 | 500-1200 字主区间，紧迫战斗 250-400 字，情感/氛围 800-1200 字 |
| 💾 存档系统 | 轻量/持久/里程碑三档，断连恢复、切换小说、导出 |
| 🎴 角色卡系统 | 弹出/修改/深度创建/短篇，配角静默落卡 |
| 📖 三种模式 | 主线（mainline）/ 沉浸（immersion）/ 爽文（shuangwen） |
| 🧩 P0/P1/P2 分层 | 常驻规则精简，按需加载，上下文零持续负担 |
| 🧠 记忆外置助手 | 可选：四级简报 + 自动衰减，字数与账本自动记账，长篇设定不遗忘也不反复干扰 |
| 🤖 子 Agent 模式 | 可选：子任务派发生成正文（不支持时自动主 Agent 直出） |

</details>

---

## 🛠 装进你的 AI 助手

### 方式 1 · npx skills（最省事）

```bash
npx skills add Treasure-hub-agent/interactive-fiction-skill
```

> `npx skills` 是通用的 agent skill 安装工具；没有的话用下面的手动方式即可。

### 方式 2 · 手动复制

<img alt="支持的客户端与技能目录" src="assets/clients.svg" width="100%"/>

<details>
<summary><b>展开可复制的目录路径</b></summary>

| 客户端 | 技能目录 |
|--------|----------|
| Hermes | `~/.hermes/skills/creative/interactive-fiction/` |
| DeepSeek Harness（dsh） | `~/.dsh/skills/interactive-fiction/` |
| 通用约定（多 agent 共用） | `~/.agents/skills/interactive-fiction/` |
| Claude Code | `~/.claude/skills/interactive-fiction/` |
| Cursor | `~/.cursor/skills/interactive-fiction/` |
| Operit（Android） | `/sdcard/Download/Operit/skills/interactive-fiction/` |

</details>

> 只要客户端能读取 `SKILL.md`，本 skill 就能用（文件读写权限为必需项，见下方「平台表现」）。复制后重新加载 / 重启客户端，发送「加载小说包」即可开局。

### 方式 3 · Hermes 用户（skills tap）

```bash
hermes skills tap add Treasure-hub-agent/interactive-fiction-skill
```

添加后即可在 `hermes skills browse` / `hermes skills search` 中看到并安装，后续 `hermes skills check` 可检查更新。

### 方式 4 · Operit（Android）

全程不用命令行：

1. 打开 `包管理 → Skills`（或点右下角商店图标进市场直接搜本 skill）
2. 点 `+` → 选「仓库」，填 `https://github.com/Treasure-hub-agent/interactive-fiction-skill`（也可选「ZIP」导入发布包）
3. 确认该条目右侧开关处于**开启**状态，发「加载小说包」开局

> 小说数据落在 `/sdcard/Download/Operit/novels/`（与技能目录分开），升级或重装技能不影响存档。

### 升级路径

- npx 安装：`npx skills update Treasure-hub-agent/interactive-fiction-skill`（或重新 add）
- 手动复制：以最新 [GitHub Releases](https://github.com/Treasure-hub-agent/interactive-fiction-skill/releases) 发布包整体覆盖，或增量覆盖变更文件
- 升级不影响已有运行数据（小说存档、角色卡存放于独立存储目录）

> 部署、升级与验证详见 `references/deployment.md`。

---

## 🚩 开场 · 快速开始

1. 用你的客户端加载本 skill（如 Hermes 的 `skill_view`、Claude Code 的 skill 机制）
2. 发送「加载小说包」→ 进入开局路线选择
3. 选路线 A（穿越成原著角色）/ B（自创角色）/ C（创世模式）/ 🎲 随机开局 → 开始正文
4. 每轮正文后从 A/B/C/D/E 选一个推进剧情
5. 随时发送「帮助」查看使用指南（全量指令速查）

> 提示：默认由主 Agent 直出正文，无需任何额外配置即可使用。子 Agent 模式、联网蒸馏等为可选增强。

---

## 📌 新卷 · v10.3.0 酒馆角色卡直接可用

> 本栏目介绍最新版本的变化，只保留当前版本；历史版本见 `references/changelog.md`。

**🃏 酒馆的角色卡，拿来就能接着演（本次重点）**

- **三种卡都认**：SillyTavern / Tavo / Chub 下载的 PNG、JSON、CHARX 卡，一句「导入酒馆卡」即可接入——先出一张「接入卡」让你看清他是谁、设定齐不齐，确认后自动归档
- **设定按酒馆的规矩生效**：常驻条目始终在场、关键词条目该出现时才出现，优先级与顺序照原卡写法——长篇跑下来设定依然在场，又不会把上下文撑爆
- **只取相关的那几条**：世界书完整内容留在本地随时回查，每轮只注入真正相关者（默认 ≤4 条、单条 ≤300 字）
- **原卡只读**：解析前后校验一致，并原样留档（含原作者署名），随时可回溯
- **写作规则仍由本 skill 统管**：卡内的全局规则字段（system_prompt 等）只留档不注入，五选项等既有机制不受外来规则干扰

**🧪 开发工具链闭环**

- 提交前自动门禁 + CI：改一行即跑工程门禁、单测与静态检查
- 属性测试：以随机生成的成千上万种输入代替手工用例，历史崩溃类问题变永久防线
- 模型输出硬契约评测基座：五选项 / 字数区间 / 符号分工 / 状态条等规则可自动核对，改一版规则一键回归

---

## 🏛 架构 · 书的骨架

```mermaid
%%{init: {"theme": "neutral", "themeVariables": {"fontFamily": "monospace"}}}%%
graph LR
  SKILL[SKILL.md<br/>P0 常驻] --> Data[data/*.json]
  SKILL --> Extended[extended/]
  SKILL --> Modes[modes/]
  SKILL --> References[references/]
  SKILL --> Schema[schema/]
  SKILL --> Scripts[scripts/]
```

```
interactive-fiction/
├── SKILL.md              # P0 常驻核心规则（铁律、视角、字数、选项）
├── MANIFEST.json         # 文件清单 + SHA256 校验
├── VERSION               # 当前版本号
├── assets/               # 视觉资源（横幅、能力图、对比图等 SVG）
├── data/                 # 标签词库 / 字数区间 / 指令路由 / 随机池
├── docs/                 # 网页版主页（GitHub Pages 源，不参与运行时加载）
├── extended/             # P1/P2 按需加载：角色卡、蒸馏、事件、存储
├── modes/                # 主线/沉浸/爽文三种模式
├── references/           # 指令导航、写作指南、使用指南、切换规则等
├── schema/               # 运行时 JSON Schema
└── scripts/              # 工程门禁 validate.py / MANIFEST 生成
```

---

## 🖥 平台表现

<img alt="平台表现矩阵" src="assets/compat.svg" width="100%"/>

> 只有「文件读写」是硬要求；其余缺什么都只是降级，剧情不会中断。

---

## 📚 存放 · 存储与权限

本 skill 会在存储根目录下创建数据（桌面宿主默认 `~/novels/`，手机端 `/sdcard/Download/Operit/novels/`；可用环境变量 `NOVEL_STORAGE_ROOT` 覆盖），用于存放：

- 小说存档与运行时状态（`{小说名}/meta/novel_runtime.json`）
- 助手簿记（`{小说名}/meta/novel_assist.json`）
- 角色卡（`{小说名}/characters/` 与 `通用角色卡/`）
- 蒸馏中间产物（`output/characters/`，会被 .gitignore 忽略）

**需要 agent 具备文件读写权限**。无文件写权限的环境会静默降级（不中断叙事，但存档不落盘），请确保你的运行环境允许写文件。

---

## ❓ 问与答

**Q: 和普通 prompt 写小说有什么区别？**
A: 普通 prompt 是「建议」，本 skill 是「硬规则 + 自检清单」。铁律 #0（选项必跟）、视角规则、字数区间都有强制自检步骤，AI 每轮输出前逐项核对。

**Q: 版本历史？**
A: 运行时详细变更说明见 `references/changelog.md`；面向 GitHub / Releases 的精简版本史见根目录 `CHANGELOG.md`（发版时追加）。版本号以 `VERSION` 文件为唯一权威。

**Q: 英文版有网页吗？**
A: 网页版只做中文。英文内容请直接看 [README.en.md](README.en.md)，保持纯文本。

---

## 📖 同卷 · 延伸阅读

- [ai-with-u](https://github.com/Treasure-hub-agent/ai-with-u) —— 聊天搭子 / 角色陪伴，零系统痕迹

---

## 🕮 说明与版权

- 本 skill 提供互动小说创作规范，支持多种题材与情感张力描写；涉及相关场景时按描写规范与情感递进执行
- **内容由 AI 生成** —— 所有剧情与人物由你所配置的模型实时产出，不代表作者观点；创作内容责任由使用者自负
- **数据与隐私** —— 运行时数据（存档、角色卡、账本）全部保存在你自己的设备上，不上传、不收集、不回传
- **合规提示** —— 涉及成人向题材时，请自行确保符合所在地法律法规与发布平台规则
- **模型与费用** —— 模型与运行环境需自备，相关费用与服务条款由你与服务商处理
- **无担保** —— 按「现状」提供，不保证生成质量、连续性与存档安全，建议自行备份
- **MIT License** —— 可自由使用、修改、分发；分发时请保留原始版权声明
- 完整条款见 [`DISCLAIMER.md`](DISCLAIMER.md)；版本变更记录见 `references/changelog.md`

---

<p align="right" style="color:#8a7c6f;">
  —— Treasure-hub-agent · 2026 · 第十二次修订
</p>
