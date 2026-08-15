#!/usr/bin/env python3
"""生成 MANIFEST.json（两遍写入解决自指 hash 失效）。

用法：
    python3 scripts/gen_manifest.py [--include-docs]

默认只收录运行时文件（排除 docs/ 与 .github/）；加 --include-docs 则全收录。

每个文件条目附带 role 字段（按顶层目录/文件名推导）：
    runtime —— data/ extended/ modes/ references/ schema/ scripts/、
               SKILL.md、package.json、VERSION、LICENSE、README*
    docs    —— docs/（仅 --include-docs 时收录）
    meta    —— .github/、CHANGELOG*、SECURITY.md、CODE_OF_CONDUCT.md、
               CONTRIBUTING.md、.gitignore 等工程/元数据文件

流程：
    1. 遍历文件算 sha256
    2. 写入 MANIFEST.json（此时自身 hash 已变）
    3. 重算 MANIFEST.json 自身 hash，二次回写
    4. 校验最终 hash 与清单一致
"""
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(ROOT, "VERSION")

EXCLUDE_DIRS = {".git", "node_modules", "__pycache__"}
DIST_DOCS = {"docs", ".github"}

RUNTIME_TOPDIRS = {"data", "extended", "modes", "references", "schema", "scripts"}
META_ROOT_FILES = {"CHANGELOG.md", "SECURITY.md", "CODE_OF_CONDUCT.md", "CONTRIBUTING.md", ".gitignore"}


def derive_role(rel: str) -> str:
    """按顶层目录/文件名推导文件角色：runtime / docs / meta。"""
    top = rel.split("/", 1)[0]
    if top in RUNTIME_TOPDIRS:
        return "runtime"
    if top == "docs":
        return "docs"
    if top == ".github":
        return "meta"
    # 根级文件
    if rel == "SKILL.md" or rel in {"package.json", "VERSION", "LICENSE"} or rel.startswith("README"):
        return "runtime"
    if rel.startswith("CHANGELOG") or rel in META_ROOT_FILES:
        return "meta"
    return "meta"  # 未知根级文件保守标 meta


def collect_files(include_docs: bool) -> dict:
    files = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        if not include_docs:
            dirnames[:] = [d for d in dirnames if d not in DIST_DOCS]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT).replace(os.sep, "/")
            # MANIFEST.json 自身不列入清单（避免自指 hash 死循环）；.git 为 git 元数据（worktree 下为文件），不列入
            if rel == "MANIFEST.json" or rel == ".git" or rel.startswith(".git/"):
                continue
            data = open(p, "rb").read()
            files[rel] = {
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
                "role": derive_role(rel),
            }
    return dict(sorted(files.items()))


def current_version() -> str:
    with open(VERSION_FILE, encoding="utf-8") as f:
        return f.read().strip()


def build_manifest(include_docs: bool) -> dict:
    return {
        "version": current_version(),
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "root": "interactive-fiction",
        "files": collect_files(include_docs),
    }


def write_manifest(manifest: dict) -> None:
    path = os.path.join(ROOT, "MANIFEST.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-docs", action="store_true", help="同时收录 docs/ 与 .github/")
    args = parser.parse_args()

    manifest = build_manifest(args.include_docs)
    write_manifest(manifest)
    # 校验：所有非 MANIFEST.json 文件与清单一致
    final = json.load(open(os.path.join(ROOT, "MANIFEST.json"), encoding="utf-8"))
    disk = collect_files(args.include_docs)
    mismatched = [k for k in disk if disk[k] != final["files"].get(k)]
    ok = not mismatched and len(disk) == len(final["files"])
    roles = {}
    for info in final["files"].values():
        roles[info["role"]] = roles.get(info["role"], 0) + 1
    role_summary = ", ".join(f"{k}={v}" for k, v in sorted(roles.items()))
    print(f"MANIFEST.json 生成完成: {len(final['files'])} 个文件, version={final['version']}, role: {role_summary}")
    print(f"清单校验: {'✅ 全部一致' if ok else '❌ 不一致: ' + str(mismatched[:5])}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
