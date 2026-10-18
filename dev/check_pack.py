#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""check_pack.py — 发布包边界检查（dev 侧，发布前跑）

为什么需要它：`package.json` 的 `files` 白名单里若写**目录名**（如 `scripts`），
npm 会整目录收录且**不应用 .gitignore / .npmignore**——本地跑过测试后，
`scripts/__pycache__/*.pyc` 会被打进 tarball，且 .pyc 内嵌本机绝对路径
（`/home/ubuntu/...`），造成信息泄露 + 包体膨胀。
（2026-10-17 实测：72 文件、含 11 个 .pyc、328KB；修正白名单后 61 文件、0 pyc、214KB）

本脚本用 `npm pack --dry-run` 的实际输出做断言，防止该类问题复发。

用法：
    python3 dev/check_pack.py            # 检查（失败退出码 1）
    python3 dev/check_pack.py --list     # 同时列出包内文件
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 绝对禁止出现在发布包里的模式（模式 → 原因）
FORBIDDEN = [
    (r"__pycache__|\.pyc$|\.pyo$", "Python 缓存/字节码（内嵌本机路径，且非源码）"),
    (r"^dev/|^tests/|^eval/", "dev/CI 侧代码（不随包分发）"),
    (r"^\.github/", "CI 配置（不随包分发）"),
    (r"\.npmignore$|\.pre-commit-config\.yaml$|^ruff\.toml$|^cliff\.toml$|^promptfooconfig\.yaml$",
     "dev 工具配置（不随包分发）"),
    (r"\.ruff_cache|\.mypy_cache|\.pytest_cache|\.hypothesis", "工具缓存"),
    (r"\.log$|^output/", "运行产物"),
]

# 发布包必须包含的关键文件（防止白名单写窄导致漏发）
REQUIRED = [
    "SKILL.md", "VERSION", "MANIFEST.json", "package.json", "LICENSE",
    "scripts/novel.py", "scripts/tavern_prep.py", "scripts/validate.py",
    "extended/tavern_import.md", "references/command_nav.md",
    "data/commands.json", "schema/novel_runtime.schema.json",
]


def pack_listing() -> tuple:
    """返回 (文件列表, 包体信息行)。"""
    r = subprocess.run(["npm", "pack", "--dry-run", "--json"], cwd=ROOT,
                       capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(f"npm pack 失败：{(r.stderr or r.stdout)[:400]}")
    import json
    # ⚠️ npm pack --json 会在 JSON 之后追加 notice 尾行 → 用 raw_decode 只解析首个 JSON 值
    start = r.stdout.index("{")
    data, _end = json.JSONDecoder().raw_decode(r.stdout[start:])
    entry = data[0] if isinstance(data, list) else data
    files = [f["path"] for f in entry.get("files", [])]
    info = (f"{entry.get('entryCount', len(files))} 文件 · "
            f"{entry.get('size', 0) / 1024:.1f} KB（打包后）· "
            f"{entry.get('unpackedSize', 0) / 1024:.1f} KB（解包后）")
    return files, info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="列出包内全部文件")
    args = ap.parse_args()

    what = subprocess.run(["node", "-e", "console.log(require('./package.json').name)"],
                          cwd=ROOT, capture_output=True, text=True).stdout.strip()
    print(f"check_pack.py — 发布包边界检查（{what}）\n")

    try:
        files, info = pack_listing()
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as e:
        print(f"❌ {e}")
        return 1

    print(f"包体概况：{info}\n")

    failed = []

    # ① 禁入项
    print("① 禁入项检查（缓存 / dev 侧 / 产物）")
    for pat, why in FORBIDDEN:
        hits = [f for f in files if re.search(pat, f)]
        if hits:
            failed.append(f"{why}：{hits[:5]}（共 {len(hits)} 项）")
            print(f"  ❌ 命中 {why}：{hits[:5]}")
        else:
            print(f"  ✅ 无{why}")

    # ② 必需项
    print("\n② 必需文件检查（防白名单写窄漏发）")
    missing = [f for f in REQUIRED if f not in files]
    if missing:
        failed.append(f"缺必需文件：{missing}")
        print(f"  ❌ 缺必需文件：{missing}")
    else:
        print(f"  ✅ {len(REQUIRED)} 个关键文件齐备")

    # ③ 敏感路径抽查（防 .pyc 类泄露）
    #    优化：不真打包（npm pack 实测约 60-80s，拖慢 CI），改为按「白名单命中的
    #    文件清单」直接读盘抽查——发布包内容 = 白名单命中的文件，等价且快百倍。
    print("\n③ 敏感内容抽查（包内文本文件不得含本机绝对路径/密钥）")
    hits = []
    for rel in files:
        p = os.path.join(ROOT, rel)
        if not os.path.isfile(p) or os.path.getsize(p) > 2_000_000:
            continue
        if not rel.endswith((".py", ".md", ".json", ".txt", ".yaml", ".yml")):
            continue
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                body = f.read()
        except OSError:
            continue
        if "/home/ubuntu" in body or re.search(r"sk-[A-Za-z0-9]{16,}", body):
            hits.append(rel)
    if hits:
        failed.append(f"包内含本机路径/疑似密钥：{hits}")
        print(f"  ❌ {hits}")
    else:
        print("  ✅ 未发现本机路径或疑似密钥")

    if args.list:
        print("\n包内文件：")
        for f in sorted(files):
            print("  ", f)

    print()
    if failed:
        print(f"❌ 发布包边界检查未通过：{len(failed)} 项")
        for x in failed:
            print(f"   · {x}")
        return 1
    print("✅ 发布包边界检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
