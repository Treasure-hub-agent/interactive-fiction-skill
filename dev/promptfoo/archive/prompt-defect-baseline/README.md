# 基线归档：prompt 缺陷版（2026-10-17）

**这份数据的用途：留证，不是当前基线。**

- 通过率 92/100（唯一失败项 `opt_separator` × 8）
- 成因：首轮 `prompt_p0.txt` **未写清选项格式**，子代理自创了 `、` / `.` 分隔符；
  而 SKILL.md:290 与 references/options-quickref.md 规定的是 `{字母} · [{标签}] {摘要}`（居中点）
- 修正：prompt 已补格式规范与示例 → 重跑取干净基线（当前 `samples/hermes-subagent/`）
- 另一处同时修掉的评测器缺陷：`asserts.py` 的 `OPTION_RE` 原漏掉 `·`，
  会让**规范输出被判「无选项」**且选项行计入正文致字数虚高；已补 `·` 并加回归用例
