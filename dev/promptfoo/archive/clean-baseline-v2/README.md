# 干净基线：v10.3.0 硬契约评测（2026-10-17）

**这是当前权威基线。**

| 项 | 值 |
|---|---|
| 结果 | **100/100（10 用例 × 10 断言全通过）** |
| 模型 | hermes-subagent（部署的 deepseek-v4.1-flash，经子代理产出，不烧 API） |
| 断言 | five_options / wordcount / symbols / status_bar / no_em_dash / no_ai_tone / not_closed_loop / e_option / d_option / opt_separator |
| 独立复算 | ✅ 用**不 import asserts.py 的朴素脚本**复算，净字数/选项数/破折号/AI腔/状态条/提示行逐项一致 |

## 与首轮（prompt-defect-baseline）的差异

首轮 92%，唯一失败项 `opt_separator`（8 处分隔符偏差），根因是**测试提示词未写清选项格式**。
修正 prompt 后重跑 → 100%。两个基线共同证明：**评测器能敏感地捕捉格式偏差**，
且模型在规则写清后能稳定合规。

## 复核命令

```bash
cd <repo>
python3 dev/promptfoo/run_eval.py --offline --models hermes-subagent-v2
```
