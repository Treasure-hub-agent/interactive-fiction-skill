# 参与贡献

感谢你愿意帮助这个项目变得更好！🎉

## 提交 Issue

- 🐛 **Bug 报告**：请使用 [Bug 报告模板](.github/ISSUE_TEMPLATE/bug_report.md)，说明复现步骤、期望行为与实际行为。
- ✨ **功能建议**：请使用 [功能建议模板](.github/ISSUE_TEMPLATE/feature_request.md)，描述使用场景与期望效果。

## 提交 Pull Request

1. Fork 本仓库并创建你的分支：`git checkout -b feat/your-feature`
2. 修改内容，保持与项目现有风格一致
3. 提交 PR 时使用 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md)

## 开发约定

- 本仓库是 AI Agent 使用的 skill 包，修改 `SKILL.md` 与 `references/`、`data/`、`schema/` 时请保持格式规范
- 新增/删除/修改文件后，请重新生成 `MANIFEST.json`（sha256 + bytes 清单）
- 版本号变更时，请同步 `VERSION` / `package.json` / `SKILL.md` / `README` / `MANIFEST.json`
- 提交信息使用简洁的约定式前缀（`feat:` / `fix:` / `docs:` / `chore:`）

## 行为准则

请遵守 [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md)，友善交流。
