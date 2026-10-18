#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""run_eval.py — 硬契约评测跑手（dev 侧，纯标准库）

两种模式：
  1. --offline（默认）：用 dev/promptfoo/samples/ 下的**已采集模型输出样本**
     跑断言，产出「模型 × 断言」对照矩阵（.md + .json）。
     价值：无需 API key、可进 CI，断言逻辑与真实评测完全同源。
  2. --live：调真实模型（需 IFS_EVAL_API_BASE / IFS_EVAL_API_KEY 环境变量），
     把输出采集到 samples/ 后再走同一套断言。

用法：
    python3 dev/promptfoo/run_eval.py --offline
    python3 dev/promptfoo/run_eval.py --live --models deepseek-v4.1-flash,deepseek-v4.1
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import asserts as A  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
SAMPLES = os.path.join(HERE, "samples")
REPORT_DIR = os.path.join(ROOT, "dev", "promptfoo", "reports")

ASSERT_NAMES = ["five_options", "wordcount", "symbols", "status_bar", "no_em_dash",
                "no_ai_tone", "not_closed_loop", "e_option", "d_option", "opt_separator"]
ASSERT_FN = {
    "five_options": A.has_five_options, "wordcount": A.wordcount_in_range,
    "symbols": A.symbol_discipline, "status_bar": A.status_bar_format,
    "no_em_dash": A.no_em_dash, "no_ai_tone": A.no_ai_tone,
    "not_closed_loop": A.not_closed_loop, "e_option": A.e_option_not_key_decision,
    "d_option": A.d_option_is_protagonist_inference,
    "opt_separator": A.option_separator_canonical,
}


def load_cases():
    """读用例（轻量 YAML 子集解析：description / vars.scene / vars.input 三级）。

    必须支持 `input: |` 的多行块——用例输入都是多行的，不支持就会静默读空。
    """
    path = os.path.join(HERE, "cases.yaml")
    cases, cur = [], None
    pending_multiline = None      # 正在收集多行块的目标字段名
    buf = []
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")

            # 多行块收集中
            if pending_multiline is not None:
                if line.strip() == "" or line.startswith("      "):
                    buf.append(line.strip())
                    continue
                cur["vars"][pending_multiline] = "\n".join(buf).strip()
                pending_multiline, buf = None, []

            if line.startswith("- description:"):
                cur = {"description": line.split(":", 1)[1].strip(), "vars": {}}
                cases.append(cur)
                continue
            if cur is None:
                continue

            s = line.strip()
            if s.startswith("scene:"):
                cur["vars"]["scene"] = s.split(":", 1)[1].strip()
            elif s.startswith("input:"):
                rest = s.split(":", 1)[1].strip()
                if rest in ("|", ">", ""):
                    pending_multiline, buf = "input", []
                else:
                    cur["vars"]["input"] = rest.strip('"\'')
    if pending_multiline is not None and cur is not None:
        cur["vars"][pending_multiline] = "\n".join(buf).strip()
    return cases


def load_samples(model: str):
    """读某模型的样本目录：每个 <case>.txt 一份输出。"""
    d = os.path.join(SAMPLES, model)
    if not os.path.isdir(d):
        return None
    out = {}
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".txt"):
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                out[fn[:-4]] = f.read()
    return out


def slug(desc: str, idx: int) -> str:
    keep = "".join(c for c in desc if c.isalnum() or c in "·-_ ")[:40].strip().replace(" ", "_")
    return f"{idx:02d}_{keep}"


def evaluate(model: str, samples: dict, cases: list):
    """逐用例跑全部断言，返回结果表。"""
    rows = []
    for i, case in enumerate(cases, start=1):
        key = slug(case["description"], i)
        text = samples.get(key)
        ctx = {"vars": case["vars"]}
        if text is None:
            rows.append({"case": case["description"], "key": key, "missing": True,
                         "details": {n: {"pass": False, "reason": "缺样本"} for n in ASSERT_NAMES}})
            continue
        details = {}
        for n in ASSERT_NAMES:
            r = ASSERT_FN[n](text, ctx)
            ok = r if isinstance(r, bool) else bool(r.get("pass"))
            details[n] = {"pass": ok,
                          "reason": "" if isinstance(r, bool) else r.get("reason", "")}
        rows.append({"case": case["description"], "key": key, "missing": False,
                     "details": details})
    return rows


def render_matrix(models: dict):
    """产出 .md 矩阵：行=用例，列=模型×断言汇总。"""
    lines = ["# 硬契约评测 · 模型 × 断言 对照矩阵", "",
             "> 由 `dev/promptfoo/run_eval.py` 生成（dev 侧，不入发布包）", ""]
    for model, rows in models.items():
        total = sum(len(r["details"]) for r in rows)
        passed = sum(1 for r in rows for d in r["details"].values() if d["pass"])
        rate = (passed / total * 100) if total else 0.0
        lines += [f"## {model}", "",
                  f"**总体通过率 {passed}/{total} = {rate:.1f}%**", "",
                  "| 用例 | " + " | ".join(ASSERT_NAMES) + " |",
                  "|---|" + "---|" * len(ASSERT_NAMES)]
        for r in rows:
            cells = []
            for n in ASSERT_NAMES:
                d = r["details"][n]
                cells.append("✅" if d["pass"] else ("⚠️缺失" if r.get("missing") else "❌"))
            lines.append(f"| {r['case']} | " + " | ".join(cells) + " |")
        lines += ["", "**逐项失败原因**", ""]
        any_fail = False
        for r in rows:
            for n in ASSERT_NAMES:
                d = r["details"][n]
                if not d["pass"]:
                    any_fail = True
                    lines.append(f"- `{r['case']}` · {n}：{d['reason']}")
        if not any_fail:
            lines.append("- （全部通过）")
        lines.append("")
    return "\n".join(lines)


def write_report(models: dict):
    os.makedirs(REPORT_DIR, exist_ok=True)
    md = render_matrix(models)
    md_path = os.path.join(REPORT_DIR, "matrix.md")
    json_path = os.path.join(REPORT_DIR, "matrix.json")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md + "\n")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(models, f, ensure_ascii=False, indent=2)
    return md_path, json_path


def call_model(model: str, prompt: str, base: str, key: str, timeout=120) -> str:
    """最小 OpenAI 兼容调用（零依赖，用 urllib）。"""
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.8,
    }).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def run_live(models_: list):
    base = os.environ.get("IFS_EVAL_API_BASE")
    key = os.environ.get("IFS_EVAL_API_KEY")
    if not (base and key):
        print("❌ --live 需设置 IFS_EVAL_API_BASE 与 IFS_EVAL_API_KEY", file=sys.stderr)
        return 1
    with open(os.path.join(HERE, "prompt_p0.txt"), encoding="utf-8") as f:
        tmpl = f.read()
    cases = load_cases()
    for model in models_:
        d = os.path.join(SAMPLES, model)
        os.makedirs(d, exist_ok=True)
        for i, case in enumerate(cases, start=1):
            prompt = tmpl.replace("{{input}}", case["vars"].get("input", "（无输入）"))
            try:
                out = call_model(model, prompt, base, key)
            except (urllib.error.URLError, KeyError, TimeoutError) as e:
                print(f"⚠️ {model} · {case['description']} 调用失败：{e}")
                continue
            with open(os.path.join(d, slug(case["description"], i) + ".txt"),
                      "w", encoding="utf-8") as f:
                f.write(out)
            print(f"✅ {model} · {case['description']}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="用已采集样本跑断言（默认）")
    ap.add_argument("--live", action="store_true", help="调真实模型采集样本")
    ap.add_argument("--models", default="deepseek-flash",
                    help="逗号分隔的模型列表（默认单模型；横向对比需主人明确要求）")
    args = ap.parse_args()
    models_ = [m.strip() for m in args.models.split(",") if m.strip()]

    if args.live:
        rc = run_live(models_)
        if rc:
            return rc

    cases = load_cases()
    results = {}
    for model in models_:
        samples = load_samples(model)
        if samples is None:
            print(f"⚠️ 跳过 {model}：缺 samples/{model}/ 目录（先跑 --live 采集）")
            continue
        results[model] = evaluate(model, samples, cases)

    if not results:
        print("❌ 无可评测模型（samples/ 为空）", file=sys.stderr)
        return 1

    md_path, json_path = write_report(results)
    print(f"\n📊 报告已生成：\n  {md_path}\n  {json_path}\n")
    for model, rows in results.items():
        total = sum(len(r["details"]) for r in rows)
        passed = sum(1 for r in rows for d in r["details"].values() if d["pass"])
        print(f"  {model}: {passed}/{total} 通过（{passed / total * 100:.1f}%）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
