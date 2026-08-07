# 部署与安装指南

> 当前版本以 `SKILL.md` YAML 头中 `version` 字段为准（参见项目根目录 `VERSION` 文件）。

---

## 一、目录结构

```
interactive-fiction/
├── SKILL.md                        # 技能入口（含 YAML frontmatter）
├── README.md                       # 项目说明
├── LICENSE                         # MIT License
├── MANIFEST.json                   # 文件清单与哈希
├── VERSION                         # 版本号（单点溯源）
├── .gitignore                      # Git 忽略规则
├── docs/                            # 设计文档与版本规划（不参与运行时加载）
├── modes/                          # 模式文件（爽文/主线/沉浸）
├── extended/                       # 扩展模块（按需加载）
└── references/                     # 参考文档与写作规范
```

**不变式**：
- `SKILL.md` 的 `name: interactive-fiction` 与目录叶节点名一致
- 规范采用 P0/P1/P2 三层物理拆分：SKILL.md 常驻（P0），其余按需加载
- 仅规则文件，不携带任何运行时数据（运行数据存储于用户存储根目录，见 SKILL.md 相关章节）

---

## 二、安装

### 方式 1：通过 npx skills 安装

```bash
npx skills add Treasure-hub-agent/interactive-fiction-skill
```

### 方式 2：手动复制

将仓库目录复制到你的 agent 技能目录。常见位置：

| 客户端 | 技能目录 |
|--------|----------|
| Hermes | `~/.hermes/skills/creative/interactive-fiction/` |
| Claude Code | `~/.claude/skills/interactive-fiction/` |
| Cursor | `~/.cursor/skills/interactive-fiction/` |

```bash
mkdir -p ~/.hermes/skills/creative/interactive-fiction
cp -r interactive-fiction/* ~/.hermes/skills/creative/interactive-fiction/
```

复制后重新加载 / 重启客户端即可识别，发送「加载小说包」即可开局。

---

## 三、升级

### 从 GitHub 获取新版

```bash
# 拉取仓库最新代码
git pull origin main

# 或直接下载最新 Release 覆盖（保留你的运行数据目录即可）
```

### 手动升级步骤

1. 增量覆盖 `SKILL.md`、`modes/`、`extended/`、`references/` 中的变更文件
2. 更新 `SKILL.md` YAML 头中 `version` 字段为目标版本号（如仓库已更新则无需手动改）
3. 重新加载 skill 生效

> ⚠️ 运行数据（小说存档、角色卡等）存放在独立存储目录，升级规则文件不影响已有数据。

---

## 四、验证

- [ ] `SKILL.md` 存在于技能目录且 `name: interactive-fiction` 与目录叶节点一致
- [ ] `modes/`、`extended/`、`references/` 目录均存在且含文件
- [ ] 技能列表中出现 `interactive-fiction`
- [ ] 发送「加载小说包」能正常弹出路线选择
