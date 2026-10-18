#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""tavern_prep.py — 酒馆（SillyTavern / Tavo / Chub）角色卡解析与落盘（纯标准库）。

设计原则（与 txt_prep.py 同口径）：
- **脚本只做确定性转换，不做创作判断**：字段映射、宏替换、条目归一由脚本完成；
  哪些设定该写进哪、缺失字段怎么补，交模型按 extended/tavern_import.md 处理。
- **源文件只读**：绝不修改、绝不回写用户提供的卡；解析结果落到小说目录内。
- **纯标准库**：仅用 base64/json/struct/zipfile/re/hashlib 等标准库，无第三方依赖。
- **失败降级**：单张卡损坏只报该卡，不中断；字段缺失标 `[待补]` 不编造。

支持载体（均已实测）：
  · PNG（tEXt chunk 内嵌 base64 JSON，键为 `chara` 或 `ccv3`）
  · JSON（裸 V2 对象，或带 `spec`/`data` 包裹的 V2/V3）
  · CHARX（zip 包，内含 card.json / *.json）

用法：
    python3 scripts/tavern_prep.py inspect <卡文件> [--json]
    python3 scripts/tavern_prep.py import <卡文件> --novel <小说名> [--root <存储根>]
        [--dry-run] [--work <作品名>] [--source-dir <留档目录>]
"""
import argparse
import base64
import hashlib
import json
import os
import re
import struct
import sys
import unicodedata
import zipfile

# PNG 中承载卡数据的 tEXt 关键字（顺序即优先级：ccv3 为 V3 规范）
CHARA_KEYS = ("ccv3", "chara")
# 单轮注入预算上限（条）：防止 constant 条目无限常驻导致爆窗
DEFAULT_BUDGET = 8
# 单条 content 超长时的截断阈值（字符）
ENTRY_CONTENT_MAX = 2000
# CHARX（zip）安全边界：防 zip 炸弹（卡来自用户下载，不可信）
CHARX_MAX_JSON_BYTES = 8 * 1024 * 1024   # 单个 JSON 解压后上限 8MB（真实卡实测 <1MB）
CHARX_MAX_RATIO = 200                    # 压缩比上限（正常 JSON 约 3~10:1）
CHARX_MAX_CANDIDATES = 8                 # 最多尝试解析的候选 JSON 数（防遍历成千上万项）
# 保留档（源卡信息）子目录名
SOURCE_SUBDIR = "source"

# 酒馆宏 → IF 口径
MACRO_MAP = {
    "{{user}}": "你",
    "{{char}}": "{角色名}",     # 由调用侧替换为实际角色名
    "<USER>": "你",
    "<CHAR>": "{角色名}",
    "{{persona}}": "你",
    "{{description}}": "",
}


# ---------- 载体解析：PNG ----------
def iter_png_chunks(data: bytes):
    """遍历 PNG chunk（从 IHDR 之后到 IEND），产出 (类型, 数据)。"""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return
    pos = 8
    n = len(data)
    while pos + 8 <= n:
        (ln,) = struct.unpack(">I", data[pos:pos + 4])
        typ = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + ln]
        yield typ, payload
        pos += 12 + ln
        if typ == b"IEND":
            break


def read_png_card(path: str):
    """从 PNG 的 tEXt chunk 读出卡 JSON。

    返回 (card_dict, 载体描述)；找不到卡数据返回 (None, 原因)。
    """
    with open(path, "rb") as f:
        data = f.read()
    found = {}
    for typ, payload in iter_png_chunks(data):
        if typ != b"tEXt":
            continue
        nul = payload.find(b"\x00")
        if nul <= 0:
            continue
        try:
            key = payload[:nul].decode("latin-1")
        except UnicodeDecodeError:
            continue
        if key not in CHARA_KEYS:
            continue
        raw = payload[nul + 1:]
        raw += b"=" * (-len(raw) % 4)          # 补齐 base64 padding
        try:
            obj = json.loads(base64.b64decode(raw).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        found[key] = obj
    if not found:
        return None, "PNG 中未找到 chara/ccv3 tEXt chunk（可能不是酒馆卡）"
    key = next(k for k in CHARA_KEYS if k in found)
    return found[key], f"PNG(tEXt:{key})"


# ---------- 载体解析：JSON ----------
def read_json_card(path: str):
    """读 JSON 卡：兼容裸 V2 与带 spec/data 包裹的 V2/V3。"""
    try:
        with open(path, encoding="utf-8") as f:
            obj = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return None, f"JSON 解析失败：{e}"
    if not isinstance(obj, dict):
        return None, "JSON 顶层不是对象"
    if "data" in obj and isinstance(obj["data"], dict):
        spec = obj.get("spec", "?")
        return obj, f"JSON(spec={spec})"
    return obj, "JSON(裸 V2)"


# ---------- 载体解析：CHARX ----------
def read_charx_card(path: str):
    """读 CHARX（zip）：优先 card.json，否则取首个含 name 的 JSON。

    ⚠️ 安全边界：CHARX 来自用户下载，需防「zip 炸弹」——高压缩比的恶意包
    解压后可达数十 GB，直接 `zf.read()` 会撑爆内存。因此在**解压前**用
    `ZipInfo.file_size` 预检声明大小，超限即拒绝（不解压），并限制候选数。
    """
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        return None, f"CHARX 打开失败：{e}"
    with zf:
        names = zf.namelist()
        candidates = [n for n in names if n.lower().endswith(".json")]
        candidates.sort(key=lambda n: (0 if n.lower().endswith("card.json") else 1, len(n)))
        candidates = candidates[:CHARX_MAX_CANDIDATES]
        for n in candidates:
            try:
                info = zf.getinfo(n)
            except KeyError:
                continue
            # 预检：声明大小超限则不解压（zip 炸弹防护）
            declared = getattr(info, "file_size", 0) or 0
            if declared > CHARX_MAX_JSON_BYTES:
                return None, (f"CHARX 内 {n} 声明大小 {declared} 字节，超出上限 "
                              f"{CHARX_MAX_JSON_BYTES}（疑似 zip 炸弹，已拒绝解压）")
            if info.compress_size and declared / max(info.compress_size, 1) > CHARX_MAX_RATIO:
                return None, (f"CHARX 内 {n} 压缩比 {declared / max(info.compress_size, 1):.0f}:1 "
                              f"超出上限 {CHARX_MAX_RATIO}:1（疑似 zip 炸弹，已拒绝解压）")
            try:
                raw = zf.read(n)
            except (zipfile.BadZipFile, OSError, RuntimeError) as e:
                return None, f"CHARX 内 {n} 解压失败：{e}"
            if len(raw) > CHARX_MAX_JSON_BYTES:      # 双保险：解压后复核实际长度
                return None, (f"CHARX 内 {n} 实际大小 {len(raw)} 字节超出上限"
                              f"（疑似 zip 炸弹，已丢弃）")
            try:
                obj = json.loads(raw.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            if isinstance(obj, dict) and ("data" in obj or "name" in obj):
                return obj, f"CHARX({n})"
    return None, f"CHARX 中未找到卡 JSON（内含 {len(names)} 项）"


def load_card(path: str):
    """按扩展名分派解析。返回 (card_dict, 载体描述, 错误)。"""
    if not os.path.isfile(path):
        return None, "", f"文件不存在：{path}"
    low = path.lower()
    if low.endswith(".png"):
        obj, desc = read_png_card(path)
    elif low.endswith(".charx"):
        obj, desc = read_charx_card(path)
    elif low.endswith(".json"):
        obj, desc = read_json_card(path)
    else:
        return None, "", f"不支持的格式（仅 PNG / JSON / CHARX）：{os.path.basename(path)}"
    if obj is None:
        return None, desc, desc
    card, sub = normalize_card(obj)
    if card is None:
        return None, desc, sub
    return card, f"{desc}/{sub}", None


def normalize_card(obj: dict):
    """把各种包裹形态归一为「卡数据字典」。

    返回 (data_dict, 说明)。data_dict 含 name/description/first_mes/character_book 等。
    """
    if "data" in obj and isinstance(obj["data"], dict):
        return obj["data"], "spec 包裹"
    if "name" in obj or "first_mes" in obj or "description" in obj:
        return obj, "扁平"
    # 独立世界书形态（entries 直接挂顶层）
    if "entries" in obj:
        return {"name": obj.get("name", ""), "character_book": obj}, "独立世界书"
    return None, "无法识别为角色卡或世界书"


# ---------- 字段映射 ----------
def clean_macro(text, char_name: str = "") -> str:
    """替换酒馆宏为 IF 口径（{{user}}→你、{{char}}→角色名）。"""
    if not isinstance(text, str):
        return ""
    out = text
    for k, v in MACRO_MAP.items():
        v = v.replace("{角色名}", char_name or "TA")
        out = out.replace(k, v)
    # 其余 {{...}} 宏：去掉花括号保留内容（避免残留在正文里）
    out = re.sub(r"\{\{\s*([^{}]{0,40}?)\s*\}\}", r"\1", out)
    return out


def _norm_keys(raw) -> list:
    """归一 keys 字段：容错任意类型（str / list / 数字 / None / 嵌套）。

    酒馆卡由用户从各处下载，字段类型完全不可控（实测有 `keys: 5` 这类写法），
    任何非预期类型都不得让解析崩溃。
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        parts = re.split(r"[,，、\s]+", raw)
    elif isinstance(raw, (list, tuple, set)):
        parts = []
        for x in raw:
            if isinstance(x, (list, tuple, set)):
                parts.extend(str(i) for i in x)
            else:
                parts.append(str(x))
    else:
        parts = [str(raw)]
    out = []
    for p in parts:
        p = p.strip()
        if p and p not in out:
            out.append(p)
    return out


def _truthy(v, default: bool = False) -> bool:
    """把酒馆卡的布尔字段归一为真布尔。

    ⚠️ 不可用 `bool(v)`：卡片来自多平台导出/手写 JSON，布尔常被写成字符串——
    `bool("false")` 与 `bool("0")` 都是 **True**，会导致「本应禁用的条目被启用」
    或「本应关键词触发的条目变成常驻」（实测复现）。此处按字符串语义判定。
    """
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("false", "0", "no", "off", "n", ""):
            return False
        if s in ("true", "1", "yes", "on", "y"):
            return True
        return default
    return default


def normalize_entries(cb) -> list:
    """归一世界书条目：兼容 entries 为 list 或 {id: {...}} 两种形态。

    返回统一结构的条目列表（保留酒馆语义字段）：
      keys / secondary_keys / content / constant / probability / order /
      position / enabled / comment / 原始 id
    """
    if not isinstance(cb, dict):
        return []
    raw = cb.get("entries")
    if isinstance(raw, dict):
        raw = list(raw.values())
    if not isinstance(raw, list):
        return []
    out = []
    for i, e in enumerate(raw):
        if not isinstance(e, dict):
            continue
        content = e.get("content")
        if not isinstance(content, str):
            content = "" if content is None else str(content)
        # keys：酒馆用 keys / key，类型不可控（str / list / 数字均有实测）→ 统一容错归一
        keys = _norm_keys(e.get("keys", e.get("key", [])))
        sk = _norm_keys(e.get("secondary_keys", e.get("keysecondary", [])))
        ext = e.get("extensions") if isinstance(e.get("extensions"), dict) else {}
        prob = e.get("probability", ext.get("probability"))
        try:
            prob = int(prob) if prob is not None else None
        except (TypeError, ValueError):
            prob = None
        order = e.get("insertion_order", e.get("order"))
        try:
            order = int(order) if order is not None else None
        except (TypeError, ValueError):
            order = None
        out.append({
            "id": e.get("id", i),
            "keys": keys,
            "secondary_keys": sk,
            "content": content.strip(),
            "constant": _truthy(e.get("constant"), default=False),
            "probability": prob,
            "order": order,
            "position": e.get("position", ""),
            # enabled 缺省为 True（酒馆语义：未声明即启用），故 default=True
            "enabled": _truthy(e.get("enabled"), default=True),
            "comment": str(e.get("comment", "") or ""),
            # selective 目前仅留档（未参与注入判定），但同样按字符串语义归一，
            # 避免将来启用该字段时踩「'false' 为真」的坑
            "selective": _truthy(e.get("selective"), default=False),
        })
    return [e for e in out if e["enabled"] and (e["content"] or e["keys"])]


# ---------- 元信息统计 ----------
def card_stats(card: dict, entries: list) -> dict:
    """产出接入卡所需的确定性统计（供模型汇报用，不做判断）。"""
    name = str(card.get("name") or "").strip()
    cb = card.get("character_book") if isinstance(card.get("character_book"), dict) else {}
    const_n = sum(1 for e in entries if e["constant"])
    keyed_n = sum(1 for e in entries if e["keys"] and not e["constant"])
    total_chars = sum(len(e["content"]) for e in entries)
    fm = card.get("first_mes") or ""
    alts = card.get("alternate_greetings") or []
    if not isinstance(alts, list):
        alts = []
    return {
        "name": name,
        "creator": str(card.get("creator") or ""),
        "tags": card.get("tags") or [],
        "first_mes_chars": len(fm) if isinstance(fm, str) else 0,
        "alternate_greetings": len(alts),
        "has_description": bool((card.get("description") or "").strip()),
        "has_personality": bool((card.get("personality") or "").strip()),
        "has_scenario": bool((card.get("scenario") or "").strip()),
        "has_mes_example": bool((card.get("mes_example") or "").strip()),
        "has_system_prompt": bool((card.get("system_prompt") or "").strip()),
        "has_post_history": bool((card.get("post_history_instructions") or "").strip()),
        "book_name": str(cb.get("name") or ""),
        "scan_depth": cb.get("scan_depth"),
        "token_budget": cb.get("token_budget"),
        "recursive": bool(cb.get("recursive_scanning", False)),
        "entries_total": len(entries),
        "entries_constant": const_n,
        "entries_keyed": keyed_n,
        "entries_chars": total_chars,
    }


# ---------- 落盘：写入 IF 结构 ----------
def slugify(name: str) -> str:
    """文件名安全化（保留中文，去掉路径分隔与非法字符）。"""
    s = unicodedata.normalize("NFKC", str(name or "未命名")).strip()
    s = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", s)
    return s[:60] or "未命名"


def write_entry_files(entries: list, target_dir: str, char_name: str) -> tuple:
    """把世界书条目写成 IF 的 lorebook/ 条目文件（每条一个 md，前置元数据注释）。

    ⚠️ 格式约定：条目文件用 YAML 风格头部注释承载酒馆语义，供 novel.py 的
    lore_entries 读取；正文部分保留原始 content（仅替换宏）。

    ⚠️ 清理旧条目：本目录由本函数独占管理，写入前先移除既有 `*.md`。
    否则「同一角色换版卡（条目变少/重排）」会留下旧文件，而这些残留会被
    `novel.py::tavern_entries` 全目录扫描后**继续注入**（实测复现：3 条换 2 条后
    目录残留 `003_丙.md`）。只清本目录下的 `*.md`，不动子目录与其他文件。

    返回 (写入条数, 文件列表)。
    """
    os.makedirs(target_dir, exist_ok=True)
    # 清理上一版遗留的条目文件（仅本目录、仅 .md）
    for fn in os.listdir(target_dir):
        if fn.endswith(".md"):
            try:
                os.remove(os.path.join(target_dir, fn))
            except OSError:
                pass
    written = []
    for i, e in enumerate(entries, start=1):
        title = e["comment"] or (e["keys"][0] if e["keys"] else f"条目{i}")
        fname = f"{i:03d}_{slugify(title)}.md"
        path = os.path.join(target_dir, fname)
        keys = ",".join(e["keys"])
        body = clean_macro(e["content"], char_name)
        if len(body) > ENTRY_CONTENT_MAX:
            body = body[:ENTRY_CONTENT_MAX] + "\n…（内容超长已截断，完整内容见 source/ 留档）"
        lines = [
            "<!-- 酒馆卡条目（由 tavern_prep.py 转换，勿手改注释行）",
            f"keys: {keys}",
        ]
        if e["secondary_keys"]:
            lines.append("secondary_keys: " + ",".join(e["secondary_keys"]))
        lines.append(f"constant: {'true' if e['constant'] else 'false'}")
        if e["probability"] is not None:
            lines.append(f"probability: {e['probability']}")
        if e["order"] is not None:
            lines.append(f"order: {e['order']}")
        if e["position"]:
            lines.append(f"position: {e['position']}")
        lines.append(f"source_id: {e['id']}")
        lines.append("-->")
        lines.append("")
        lines.append(f"## {title}")
        lines.append("")
        lines.append(body)
        lines.append("")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        written.append(fname)
    return len(written), written


def write_profile(target_dir: str, card: dict, char_name: str) -> list:
    """把卡的身份/性格/声线等文本落成 IF 的 characters/<slug>/ 文件。

    只做映射与宏替换；缺失字段不编造（留空由模型按规范补）。
    返回写入的文件名列表。
    """
    os.makedirs(target_dir, exist_ok=True)
    written = []
    mapping = [
        ("profile.md", "# 角色档案（酒馆卡导入）\n\n## 基本信息\n\n" +
         (clean_macro(card.get("description"), char_name) or "[待补]")),
        ("personality.md", "# 性格\n\n" +
         (clean_macro(card.get("personality"), char_name)
          or clean_macro(card.get("description"), char_name) or "[待补]")),
        ("interaction.md", "# 声线基因\n\n## 对话示例\n\n" +
         (clean_macro(card.get("mes_example"), char_name) or "[待补]")),
    ]
    for fn, body in mapping:
        path = os.path.join(target_dir, fn)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body.rstrip() + "\n")
        written.append(fn)
    return written


def write_source_archive(src_path: str, target_dir: str) -> str:
    """把源卡原样留档（只读复制，供追溯/回查；卡内 system_prompt 等不参与注入）。"""
    os.makedirs(target_dir, exist_ok=True)
    base = slugify(os.path.basename(src_path))
    dst = os.path.join(target_dir, base)
    if not dst.endswith((".png", ".json", ".charx")):
        dst += ".bin"
    with open(src_path, "rb") as f:
        data = f.read()
    with open(dst, "wb") as f:
        f.write(data)
    return os.path.relpath(dst, target_dir)


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- CLI ----------
def cmd_inspect(args) -> int:
    card, desc, err = load_card(args.card)
    if err:
        print(f"❌ {err}", file=sys.stderr)
        return 1
    assert card is not None      # load_card 成功时保证非空（err 已在上方返回）
    entries = normalize_entries(card.get("character_book"))
    st = card_stats(card, entries)
    if args.json:
        print(json.dumps({"载体": desc, "统计": st,
                          "条目": [{k: e[k] for k in ("id", "keys", "constant",
                                                     "probability", "order", "position")}
                                   for e in entries]}, ensure_ascii=False, indent=2))
        return 0
    print("📇 酒馆卡接入卡")
    print(f"  载体：{desc}")
    print(f"  角色：{st['name'] or '（无 name 字段）'}"
          + (f" · 作者 {st['creator']}" if st["creator"] else ""))
    if st["tags"]:
        print(f"  标签：{'、'.join(str(t) for t in st['tags'][:6])}")
    print(f"  开场白：{st['first_mes_chars']} 字"
          + (f" · 备选 {st['alternate_greetings']} 条" if st["alternate_greetings"] else ""))
    have = [k for k, v in (("description", st["has_description"]),
                           ("personality", st["has_personality"]),
                           ("scenario", st["has_scenario"]),
                           ("mes_example", st["has_mes_example"]),
                           ("system_prompt", st["has_system_prompt"]),
                           ("post_history", st["has_post_history"])) if v]
    miss = [k for k, v in (("description", st["has_description"]),
                           ("personality", st["has_personality"]),
                           ("scenario", st["has_scenario"]),
                           ("mes_example", st["has_mes_example"])) if not v]
    print(f"  字段：有 {'、'.join(have) or '（无）'}"
          + (f" ｜ 缺 {'、'.join(miss)} [待补]" if miss else ""))
    print(f"  世界书：{st['entries_total']} 条"
          f"（常驻 {st['entries_constant']} · 关键词 {st['entries_keyed']}）"
          f" · 合计 {st['entries_chars']} 字")
    if st["book_name"] or st["token_budget"] or st["scan_depth"]:
        print(f"         名称 {st['book_name'] or '（无）'}"
              f" · token_budget {st['token_budget']} · scan_depth {st['scan_depth']}"
              f" · recursive {'是' if st['recursive'] else '否'}")
    return 0


def cmd_import(args) -> int:
    src_hash_before = file_sha256(args.card)
    card, desc, err = load_card(args.card)
    if err:
        print(f"❌ {err}", file=sys.stderr)
        return 1
    assert card is not None      # load_card 成功时保证非空（err 已在上方返回）
    entries = normalize_entries(card.get("character_book"))
    char_name = str(card.get("name") or "").strip() or slugify(
        os.path.splitext(os.path.basename(args.card))[0])

    root = os.path.expanduser(args.root or
                              os.environ.get("NOVEL_STORAGE_ROOT") or "~/novels")
    novel_dir = os.path.join(root, args.novel)
    if not os.path.isdir(novel_dir):
        print(f"❌ 小说目录不存在：{novel_dir}", file=sys.stderr)
        return 1

    slug = slugify(char_name)
    char_dir = os.path.join(novel_dir, "characters", slug)
    lore_dir = os.path.join(novel_dir, "lorebook", slug)
    src_dir = os.path.join(novel_dir, SOURCE_SUBDIR, "tavern", slug)

    if args.dry_run:
        print(f"[预演] 角色：{char_name} → characters/{slug}/")
        print(f"[预演] 世界书条目 {len(entries)} 条 → lorebook/{slug}/")
        print(f"[预演] 源卡留档 → {SOURCE_SUBDIR}/tavern/{slug}/")
        return 0

    # ① 源卡留档（先留档，保证可追溯）
    os.makedirs(src_dir, exist_ok=True)
    archived = write_source_archive(args.card, src_dir)
    # ② 源卡信息（system_prompt / post_history 只留档，不参与注入）
    meta = {
        "载体": desc,
        "源文件": os.path.basename(args.card),
        "源文件sha256": src_hash_before,
        "署名": {"creator": card.get("creator"), "character_version": card.get("character_version")},
        "留档": {
            "system_prompt": card.get("system_prompt") or "",
            "post_history_instructions": card.get("post_history_instructions") or "",
            "creator_notes": card.get("creator_notes") or "",
            "备注": "以上为酒馆卡原始规则字段，按 IF 口径只留档不注入（规则主权归本 skill）",
        },
        "统计": card_stats(card, entries),
        "世界书元信息": {
            k: (card.get("character_book") or {}).get(k)
            for k in ("name", "description", "scan_depth", "token_budget", "recursive_scanning")
        },
    }
    with open(os.path.join(src_dir, "卡信息.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # ③ 角色文件
    prof_files = write_profile(char_dir, card, char_name)
    # ④ 世界书条目
    n_entries, entry_files = write_entry_files(entries, lore_dir, char_name)

    # ⑤ 开场白单独落盘（供开局首轮使用）
    fm = clean_macro(card.get("first_mes"), char_name)
    alts = card.get("alternate_greetings") or []
    if not isinstance(alts, list):
        alts = []
    if fm or alts:
        with open(os.path.join(char_dir, "openings.md"), "w", encoding="utf-8") as f:
            f.write("# 开场白（酒馆卡导入）\n\n## 默认开局\n\n")
            f.write((fm or "[待补]").rstrip() + "\n")
            for i, a in enumerate(alts, start=1):
                a_clean = clean_macro(a, char_name).strip()
                if a_clean:
                    f.write(f"\n## 备选 {i}\n\n{a_clean}\n")

    # ⑥ 源文件只读校验
    src_hash_after = file_sha256(args.card)
    readonly_ok = (src_hash_before == src_hash_after)

    print(f"✅ 已导入酒馆卡：{char_name}")
    print(f"  载体：{desc}")
    print(f"  角色文件：characters/{slug}/（{'、'.join(prof_files)}"
          + ("、openings.md" if (fm or alts) else "") + "）")
    print(f"  世界书：lorebook/{slug}/ 共 {n_entries} 条")
    print(f"  源卡留档：{SOURCE_SUBDIR}/tavern/{slug}/{archived}（只读，sha256 校验 "
          f"{'通过' if readonly_ok else '❌ 失败'}）")
    print("  ⚠️ 卡内 system_prompt / post_history_instructions 已留档但**不注入**"
          "（规则主权归本 skill）")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="酒馆卡解析与导入（纯标准库）")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("inspect", help="只读解析，输出接入卡")
    pi.add_argument("card", help="卡文件（PNG / JSON / CHARX）")
    pi.add_argument("--json", action="store_true", help="以 JSON 输出")
    pi.set_defaults(func=cmd_inspect)

    pm = sub.add_parser("import", help="解析并落盘到小说目录")
    pm.add_argument("card", help="卡文件（PNG / JSON / CHARX）")
    pm.add_argument("--novel", required=True, help="目标小说名（须已存在）")
    pm.add_argument("--root", default=None, help="存储根（默认 $NOVEL_STORAGE_ROOT 或 ~/novels）")
    pm.add_argument("--dry-run", action="store_true", help="只预演，不写盘")
    pm.set_defaults(func=cmd_import)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
