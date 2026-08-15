#!/usr/bin/env python3
"""validate.py — 互动小说 skill 工程门禁（纯标准库，无第三方依赖）。

用法：
    python3 scripts/validate.py

检查项：
  ① data/ 四文件 JSON 语法 + 约束断言（tags / wordcount / commands / random_pool）
  ② commands.json 各 load 路径存在性（且 load 不允许为 null）
  ③ MANIFEST.json 与实际文件 diff（按 gen_manifest 规则重收集比对，含 role 标注）
  ④ VERSION / SKILL.md frontmatter / package.json / MANIFEST 四源版本一致
  ⑤ md 文件相对路径引用存在性（markdown 链接 + 反引号路径）
  ⑥ SKILL.md 路由表与 commands.json 域一致（域数不写死 + load 文件可达）

任一检查失败以非零退出码结束（CI / 发版门禁用）。
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import gen_manifest  # noqa: E402  复用角色推导与文件收集规则

PACE = {"快", "慢", "迂回"}
REPO_DIRS = ("data/", "extended/", "modes/", "references/", "schema/", "scripts/")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FAILED = []


def fail(msg: str) -> None:
    FAILED.append(msg)
    print(f"  ❌ {msg}")


def load_json(rel: str):
    """读取并解析 ROOT 下相对路径 JSON；语法错误直接记失败。"""
    path = os.path.join(ROOT, rel)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        fail(f"{rel} JSON 语法/读取错误: {e}")
        return None


def read_skill_frontmatter() -> str:
    with open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8") as f:
        head = f.read(4096)
    m = re.search(r"^version:\s*[\"']?([\w.]+)", head, re.MULTILINE)
    return m.group(1) if m else ""


# ---------- ① data 四文件 ----------
def check_data() -> None:
    print("① data 四文件 JSON 语法 + 约束断言")

    tags = load_json("data/tags.json")
    if tags is not None:
        general = tags.get("general") or []
        emotion = tags.get("emotion") or []
        if len(general) != 7:
            fail(f"tags.json general 池须为 7 项，实际 {len(general)}")
        words = []
        for t in general:
            words.extend(t.get("tags") or [])
            if t.get("pace") not in PACE:
                fail(f"tags.json general 类型「{t.get('type')}」pace 非法: {t.get('pace')}")
        if len(words) != 35:
            fail(f"tags.json general 词数须为 35（7 类 × 5），实际 {len(words)}")
        elif len(set(words)) != len(words):
            fail(f"tags.json general 35 词全库去重失败（重复 {len(words) - len(set(words))} 个）")
        if {t.get("pace") for t in general} != PACE:
            fail(f"tags.json general 池未覆盖全部节奏 {sorted(PACE)}")
        if len(emotion) != 7:
            fail(f"tags.json emotion 池须为 7 项，实际 {len(emotion)}")
        etags = [e.get("tag") for e in emotion]
        if len(set(etags)) != len(etags):
            fail("tags.json emotion 池 tag 重复")
        if any(e.get("pace") not in PACE for e in emotion):
            fail("tags.json emotion 池 pace 取值非法")

    wc = load_json("data/wordcount.json")
    if wc is not None:
        if not isinstance(wc, dict) or "main" not in wc or "scenes" not in wc:
            fail("wordcount.json 须含 main 与 scenes")
        else:
            if wc["main"]["min"] > wc["main"]["max"]:
                fail("wordcount.json main 区间 min > max")
            for name, rng in wc["scenes"].items():
                if rng["min"] > rng["max"]:
                    fail(f"wordcount.json scenes[{name}] 区间 min > max")
            if "情感场景" not in wc["scenes"]:
                fail("wordcount.json scenes 缺「情感场景」键")

    cmds = load_json("data/commands.json")
    if cmds is not None:
        domains = [c.get("domain") for c in cmds]
        if len(set(domains)) != len(domains):
            fail("commands.json 域（domain）重复")
        for c in cmds:
            if "load" in c and c.get("load") is None:
                fail(f"commands.json 域「{c.get('domain')}」load 为 null（应省略该键）")
            if "load" in c and not (isinstance(c["load"], str) and c["load"].strip()):
                fail(f"commands.json 域「{c.get('domain')}」load 非合法字符串")

    rp = load_json("data/random_pool.json")
    if rp is not None:
        wvs = rp.get("worldviews") or []
        if len(wvs) < 1:
            fail("random_pool.json worldviews 为空")
        if len({w.get("id") for w in wvs}) != len(wvs):
            fail("random_pool.json worldviews id 重复")
        dims = rp.get("dimensions") or {}
        for k, v in dims.items():
            if not isinstance(v, list) or len(v) < 1:
                fail(f"random_pool.json dimensions.{k} 为空")
        pts = rp.get("protagonist_templates") or []
        if len(pts) < 1 or len(set(pts)) != len(pts):
            fail("random_pool.json protagonist_templates 为空或重复")


# ---------- ② commands load 路径 ----------
def check_load_paths() -> None:
    print("② commands.json load 路径存在性")
    cmds = load_json("data/commands.json")
    if cmds is None:
        return
    for c in cmds:
        if "load" not in c:
            continue
        for p in re.split(r"\s+/\s+", c["load"]):  # 仅按「空格/空格」多文件分隔符拆分
            if not p:
                continue
            if not os.path.isfile(os.path.join(ROOT, p)):
                fail(f"commands.json 域「{c.get('domain')}」load 路径不存在: {p}")


# ---------- ③ MANIFEST diff ----------
def check_manifest() -> None:
    print("③ MANIFEST 与实际文件 diff（重生成比对，含 role）")
    path = os.path.join(ROOT, "MANIFEST.json")
    try:
        with open(path, encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        fail(f"MANIFEST.json 读取失败: {e}")
        return
    disk = gen_manifest.collect_files(include_docs=False)  # 与默认生成规则一致
    files = manifest.get("files") or {}
    if set(disk) != set(files):
        missing = sorted(set(disk) - set(files))
        extra = sorted(set(files) - set(disk))
        fail(f"MANIFEST 文件集合与磁盘不一致（缺 {len(missing)} / 多 {len(extra)}），请运行 python3 scripts/gen_manifest.py")
        return
    for rel, info in disk.items():
        if files.get(rel) != info:
            fail(f"MANIFEST 与磁盘不一致: {rel}（hash/bytes/role 变化）")
        if info.get("role") != gen_manifest.derive_role(rel):
            fail(f"MANIFEST role 标注错误: {rel}")


# ---------- ④ 四源版本一致 ----------
def check_version() -> None:
    print("④ VERSION / SKILL.md frontmatter / package.json / MANIFEST 四源版本一致")
    with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as f:
        v_version = f.read().strip()
    pkg = load_json("package.json")
    pkg_version = (pkg or {}).get("version")
    skill_version = read_skill_frontmatter()
    manifest = load_json("MANIFEST.json")
    man_version = (manifest or {}).get("version")
    sources = {
        "VERSION": v_version,
        "SKILL.md frontmatter": skill_version,
        "package.json": pkg_version,
        "MANIFEST.json": man_version,
    }
    bad = {k: v for k, v in sources.items() if not v}
    if bad:
        fail(f"版本字段缺失: {bad}")
        return
    if len(set(sources.values())) != 1:
        fail(f"四源版本不一致: {sources}（以 VERSION 文件为唯一权威）")


# ---------- ⑤ md 相对路径引用 ----------
def check_md_refs() -> None:
    print("⑤ md 文件相对路径引用存在性")
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "docs", ".github"}]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dirpath, fn)
            rel = os.path.relpath(p, ROOT)
            text = open(p, encoding="utf-8").read()
            refs = {m.group(1).strip().strip("<>") for m in LINK_RE.finditer(text)}
            # 反引号路径：按仓库约定为根相对路径，仅认 repo 顶层目录开头者（其余为运行时存储文件名等，不查）
            refs |= {
                m.group(1).strip()
                for m in re.finditer(r"`([^`\n]+)`", text)
                if m.group(1).strip().startswith(REPO_DIRS) and not any(ch in m.group(1) for ch in "*?{}<>")
            }
            for ref in sorted(refs):
                if not ref or ref.startswith(("http://", "https://", "mailto:", "data:", "#")):
                    continue
                if "://" in ref:
                    continue
                target = ref.split("#")[0].split("?")[0]
                if not target:
                    continue
                # 以 repo 顶层目录开头的引用按仓库约定为根相对路径，其余（如 README.en.md）按文件相对解析
                if target.startswith(REPO_DIRS) or target in {"SKILL.md", "VERSION", "package.json", "LICENSE", "MANIFEST.json", "CHANGELOG.md"}:
                    full = os.path.normpath(os.path.join(ROOT, target))
                else:
                    full = os.path.normpath(os.path.join(os.path.dirname(p), target))
                if not os.path.exists(full):
                    fail(f"{rel} 引用不存在: {target}")


# ---------- ⑥ 路由表与域一致 ----------
def check_routing() -> None:
    print("⑥ SKILL.md 路由表与 commands.json 域一致")
    skill = open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
    if "覆盖全部指令域" not in skill:
        fail("SKILL.md 未声明「覆盖全部指令域」（域数不应写死）")
    if re.search(r"覆盖\s*\d+\s*域", skill):
        fail("SKILL.md 写死了指令域数量（应使用「覆盖全部指令域」）")
    cmds = load_json("data/commands.json")
    if cmds is None:
        return
    # 权威可达集合：SKILL.md 全文 + command_nav.md（SKILL.md 路由表指向的权威指令表）中出现的相对路径
    known = set()
    for text in (skill, open(os.path.join(ROOT, "references", "command_nav.md"), encoding="utf-8").read()):
        known |= {m.group(1).strip() for m in LINK_RE.finditer(text)}
        known |= {
            m.group(1).strip()
            for m in re.finditer(r"`([^`\n]+)`", text)
            if m.group(1).strip().startswith(REPO_DIRS)
        }
    known = {k.split("#")[0] for k in known if k}
    for c in cmds:
        if "load" not in c:
            continue
        for p in re.split(r"\s+/\s+", c["load"]):  # 多文件分隔符拆分
            if not p:
                continue
            if p not in known:
                fail(f"commands.json 域「{c.get('domain')}」load 文件 {p} 不在 SKILL.md 路由表/权威链可达范围")


# ---------- 入口 ----------
def main() -> int:
    print(f"validate.py — 互动小说 skill 工程门禁（ROOT={ROOT}）\n")
    check_data()
    check_load_paths()
    check_manifest()
    check_version()
    check_md_refs()
    check_routing()
    print()
    if FAILED:
        print(f"❌ 校验未通过：{len(FAILED)} 项失败")
        return 1
    print("✅ 全部检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
