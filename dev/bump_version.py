#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""bump_version.py — 版本号统一同步（dev 侧，纯标准库）

为什么自己写而不用 release-please / commitizen：
  本项目版本号散布在**多处异形位置**，且其中一部分带语义（README 的「新卷标题」
  含功能名），机械替换会毁掉文案：
    ① VERSION                     纯版本号
    ② SKILL.md frontmatter        纯版本号
    ③ package.json                纯版本号
    ④ MANIFEST.json               纯版本号（须最后重生成，含 hash）
    ⑤ README.md     badge 链接    纯版本号（可自动）
    ⑤ README.md     引言行        纯版本号（可自动）
    ⑤ README.md     新卷标题      含功能名（**须人工**）
    ⑥ README.en.md  同上三类
    ⑦ CHANGELOG.md                段标题（**须人工**，含能力描述）
    ⑧ references/changelog.md     段标题（**须人工**）
    ⑨ docs/index.html             纯版本号（meta 描述 / 顶栏 / 首屏徽标 / 数字条；可自动）
    ⑨ docs/index.html             首屏「本版主题」文案（含功能名，**须人工**）
  release-please / commitizen 面向「单一版本文件 + GitHub PR 流程」，
  无法安全处理这种自定义多源结构；自写脚本可按「可自动 / 须人工」精确分流。

用法：
    python3 dev/bump_version.py 10.3.0            # 执行替换（MANIFEST 需后续重生成）
    python3 dev/bump_version.py 10.3.0 --dry-run  # 预览
    python3 dev/bump_version.py 10.3.0 --with-manifest   # 顺带重生成 MANIFEST
"""
import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 可自动替换的纯版本号位置：(相对路径, 说明)
AUTO_TARGETS = [
    ("VERSION", "版本真源"),
    ("SKILL.md", "frontmatter version"),
    ("package.json", "npm 包版本"),
    ("README.md", "引言行 + badge"),
    ("README.en.md", "引言行 + badge"),
    ("docs/index.html", "网页版：meta 描述 + 顶栏 + 首屏徽标 + 数字条"),
]

# 须人工处理的位置：含功能语义，机械替换会毁文案
MANUAL_HINTS = [
    ("README.md", re.compile(r"^##\s*📌\s*新卷.*$", re.MULTILINE), "新卷标题（含功能名，需按本版内容改写）"),
    ("README.en.md", re.compile(r"^##\s*What's New.*$", re.MULTILINE), "What's New 标题（含功能名）"),
    ("CHANGELOG.md", re.compile(r"^##\s*当前版本：.*$", re.MULTILINE), "当前版本段标题"),
    # references/changelog.md 只提示**最新一条**（历史段是过往版本，不该动）
    ("references/changelog.md", re.compile(r"^##\s*v[\d.]+\s*（.*$", re.MULTILINE), "历史 changelog 顶部段落（仅最新一条需补本版）"),
    # 网页版首屏徽标的「本版主题」是文案，机械替换会毁掉表达
    ("docs/index.html", re.compile(r"^\s*<b>v[\d.]+</b>\s*·\s*.*$", re.MULTILINE), "网页版首屏「本版主题」文案（含功能名，需按本版内容改写）"),
]


def read_current() -> str:
    with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
        return f.read().strip()


def replace_version_number(text: str, old: str, new: str) -> tuple:
    """只替换**作为版本号出现**的 old（前有 v 或 = 或 - 或行首等边界），避免误伤。

    例：`version-10.2.1-orange.svg`、`v10.2.1`、`"version": "10.2.1"` 都要改；
    但 `10.2.10`（若有）不能被 `10.2.1` 前缀命中。
    """
    pattern = re.compile(r"(?<![\d.])" + re.escape(old) + r"(?![\d])")
    return pattern.subn(new, text)


def bump_files(new: str, dry: bool) -> list:
    old = read_current()
    if old == new:
        print(f"ℹ️  当前已是 {new}，无需变更")
        return []
    changes = []
    for rel, desc in AUTO_TARGETS:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            print(f"  ⚠️  跳过 {rel}：文件不存在")
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        updated, n = replace_version_number(text, old, new)
        if n == 0:
            print(f"  ⚠️  {rel}({desc})：未找到版本号 {old}，未改动")
            continue
        changes.append((rel, desc, n))
        if not dry:
            # newline="\n"：避免在 Windows 上把全文改成 CRLF（仓库与 MANIFEST 均以 LF 为准）
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(updated)
        print(f"  {'[预演] ' if dry else ''}{rel}({desc})：替换 {n} 处")
    return changes


def report_manual(new: str) -> None:
    """列出可自动替换之外、须人工润色的位置（每处只列首条，避免历史刷屏）。"""
    print("\n" + "=" * 68)
    print("⚠️  以下位置含功能语义，脚本不代改，发版前须人工更新：")
    print("=" * 68)
    for rel, rx, desc in MANUAL_HINTS:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            text = f.read()
        hits = list(rx.finditer(text))
        if not hits:
            continue
        print(f"  · {rel} → {desc}")
        print(f"      {hits[0].group(0).strip()}")
        if len(hits) > 1:
            print(f"      （另有 {len(hits) - 1} 条同类段落，属历史版本，无需改动）")
    print("\n  · docs/og.png → 社交预览图内嵌版本号与首屏文案，改完 docs/index.html 后需重新截图生成")

    print(f"\n  提示：这些段落应描述 **{new} 本版的实际能力变化**，")
    print("        可直接用 `git-cliff` 生成草稿后按用户视角精修：")
    print("        git-cliff --unreleased --config cliff.toml")


def regen_manifest() -> int:
    print("\n=== 重生成 MANIFEST（版本号与哈希同步）===")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "gen_manifest.py")],
                       capture_output=True, text=True, cwd=ROOT)
    print(r.stdout.strip() or r.stderr.strip())
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="版本号统一同步（dev 侧）")
    ap.add_argument("version", help="目标版本号，如 10.3.0")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写入")
    ap.add_argument("--with-manifest", action="store_true", help="顺带重生成 MANIFEST.json")
    args = ap.parse_args()

    new = args.version.lstrip("v")
    old = read_current()
    print(f"版本同步：{old} → {new}{'（预演）' if args.dry_run else ''}\n")

    bump_files(new, args.dry_run)
    report_manual(new)

    rc = 0
    if args.with_manifest and not args.dry_run:
        rc = regen_manifest()

    if not args.dry_run:
        print("\n下一步：人工更新上面列出的语义段落 → 跑 `python3 scripts/validate.py` 复核")
    return rc


if __name__ == "__main__":
    sys.exit(main())
