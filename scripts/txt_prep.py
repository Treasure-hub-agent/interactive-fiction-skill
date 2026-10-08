#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""txt_prep.py — 原著 txt 预处理助手（纯标准库，无第三方依赖）。

设计原则：脚本只做「确定性记账」，不做「创作判断」。
- 原文只读：不转码、不切分、不重写原文；slice 输出统一 UTF-8 窗口文本。
- 无状态、幂等：索引（book_map.json / 目录.txt）可随时重建；
  slice 不依赖索引，索引缺失时现场重扫。
- 失败降级：无脚本环境时由模型按 extended/txt_distillation.md 分窗口读。

用法：
    python3 scripts/txt_prep.py scan <原文.txt> [--out 目录] [--json]
    python3 scripts/txt_prep.py slice <原文.txt> [--map book_map.json]
        (--ch N | --from-line A [--to-line B] | --grep 关键词 [-C 行数])
        [--max-chars N] [--windows N]
"""
import argparse
import bisect
import json
import os
import re
import sys
from typing import NoReturn

BLOCK_CHARS = 3000      # 无章节标记时的兜底切块字数
DEFAULT_MAX = 3000      # slice 单窗口默认字数上限
DEFAULT_WINDOWS = 3     # --grep 默认输出窗口数
GREP_CONTEXT = 8        # --grep 默认上下文行数
TOP_ROLES = 5           # 接入卡展示的角色候选数
LORE_TOP = 10           # 设定密度章榜容量
INDEX_NAME = "book_map.json"
TOC_NAME = "目录.txt"

# ---------- 章节 / 卷标记 ----------
CN_NUM = "0-9一二三四五六七八九十百千零两"
CH_RE = re.compile(
    r"^\s*(?:第\s*([" + CN_NUM + r"]{1,8})\s*([章节回])"
    r"|(Chapter)\s*(\d{1,4}))([^\n]{0,28})\s*$",
    re.M)
VOL_RE = re.compile(r"^\s*第\s*([" + CN_NUM + r"]{1,6})\s*[卷部篇]([^\n]{0,28})\s*$", re.M)

# ---------- 角色候选（说话归属） ----------
# 陷阱：贪心写法会把动词吃进名字（产出「林战说」）——必须非贪婪 + 动词最长优先 + 尾部剥离。
VERB = (r"(?:说道|说着|问道|答道|笑道|冷声道|沉声道|喝道|喊道|叹道|开口|回答"
        r"|说|道|问|答)")
NAME_CHARS = r"[\u4e00-\u9fa5]"
SPEAK_RE = re.compile(r"(?<!" + NAME_CHARS + r")(" + NAME_CHARS + r"{2,4}?)"
                      r"(?=" + VERB + r"[：:，,。！？\n“「])")
QUOTE_RE = re.compile(r"[」』”\"]\s*(" + NAME_CHARS + r"{2,4}?)(?=" + VERB + r")")
TAIL_RE = re.compile(r"(?:说|道|问|答|笑|喊|喝|叹)$")
STOP_NAMES = {
    "众人", "大家", "所有人", "两人", "三人", "一人", "两个", "对方", "旁人",
    "男人", "女人", "老人", "少年", "此时", "这时", "现在", "然后", "因此",
    "所以", "可是", "但是", "如果", "只是", "自己", "他们", "我们", "你们",
    "一个", "一声", "一边", "一阵", "有些", "没有", "什么", "怎么", "这样",
}

# ---------- 设定密度词表 ----------
LORE_WORDS = [
    "境界", "修为", "灵力", "真气", "功法", "武技", "宗门", "门派", "家族",
    "势力", "组织", "大陆", "帝国", "王朝", "公会", "学院", "位面", "种族",
    "神明", "纪元", "历法", "货币", "灵石", "等级", "体系", "封印", "血脉",
]


# ================= 基础工具 =================

def die(msg: str, code: int = 1) -> NoReturn:
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(code)


def cn_num(s: str):
    """中文数字 / 阿拉伯数字 → int；失败返回 None。"""
    s = (s or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    digits = {"零": 0, "一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000}
    total, cur = 0, 0
    seen = False
    for ch in s:
        if ch in digits:
            cur = digits[ch]
            seen = True
        elif ch in units:
            total += (cur or 1) * units[ch]
            cur = 0
            seen = True
        else:
            return None
    return (total + cur) if seen else None


def detect_read(path: str):
    """编码探测：BOM → UTF-8 → GB18030 → UTF-16，全失败用 replace 兜底。"""
    try:
        raw = open(path, "rb").read()
    except OSError as e:
        die(f"原文读取失败：{e}")
    if raw[:3] == b"\xef\xbb\xbf":
        return raw[3:].decode("utf-8", "replace"), "utf-8-sig"
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", "replace"), "utf-16"
    for enc, label in (("utf-8", "utf-8"), ("gb18030", "gb18030")):
        try:
            return raw.decode(enc), label
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace"), "utf-8(replace)"


def line_starts(text: str):
    """每行起始字符偏移（1-based 行号索引 = 列表下标）。"""
    starts, pos = [0], 0
    for ln in text.split("\n"):
        pos += len(ln) + 1
        starts.append(pos)
    return starts


def line_of(starts, pos: int) -> int:
    return bisect.bisect_right(starts, pos)


def find_marks(text: str):
    """返回（章标记, 卷标记），每项 = (字符偏移, 行号, 原始标题)。"""
    starts = line_starts(text)
    chapters, volumes = [], []
    for m in CH_RE.finditer(text):
        raw = m.group(0).strip()
        no = cn_num(m.group(1)) if m.group(1) else (
            int(m.group(4)) if m.group(4) else None)
        chapters.append({"pos": m.start(), "line": line_of(starts, m.start()),
                         "title": raw, "no": no})
    for m in VOL_RE.finditer(text):
        volumes.append({"pos": m.start(), "line": line_of(starts, m.start()),
                        "title": m.group(0).strip()})
    return chapters, volumes, starts


def fallback_blocks(text: str, starts):
    """无章节标记兜底：按每 BLOCK_CHARS 字切块，标 块N。"""
    blocks, n = [], 1
    for i in range(0, len(text), BLOCK_CHARS):
        blocks.append({"pos": i, "line": line_of(starts, i),
                       "title": f"块{n}", "no": None})
        n += 1
    return blocks


def build_index(path: str, text: str, encoding: str):
    """构建索引结构（纯函数，便于测试）。"""
    marks, vols, starts = find_marks(text)
    fallback = not marks
    marks = marks or fallback_blocks(text, starts)
    lines_total = len(text.split("\n"))
    chapters = []
    for i, mk in enumerate(marks):
        nxt = marks[i + 1] if i + 1 < len(marks) else None
        end_pos = nxt["pos"] if nxt else len(text)
        body = text[mk["pos"]:end_pos]
        chapters.append({
            "idx": i + 1,
            "no": mk["no"],
            "title": mk["title"],
            "start_line": mk["line"],
            "end_line": (nxt["line"] - 1) if nxt else lines_total,
            "chars": len(body.strip()),
        })
    # 角色候选（说话归属；主角通常显著高居榜首）
    chapter_positions = [m["pos"] for m in marks]
    counts, first_ch = {}, {}
    for rx in (SPEAK_RE, QUOTE_RE):
        for m in rx.finditer(text):
            name = TAIL_RE.sub("", m.group(1))
            if len(name) < 2 or name in STOP_NAMES:
                continue
            counts[name] = counts.get(name, 0) + 1
            if name not in first_ch:
                ci = bisect.bisect_right(chapter_positions, m.start()) - 1
                first_ch[name] = max(ci, 0) + 1
    roles = [{"name": n, "count": c, "first_ch": first_ch.get(n)}
             for n, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    # 设定密度章榜（世界观说明段优先采样）
    chapter_positions.append(len(text))
    lore = []
    for i, ch in enumerate(chapters):
        body = text[chapter_positions[i]:chapter_positions[i + 1]]
        hits = sum(body.count(w) for w in LORE_WORDS)
        if hits:
            lore.append({"idx": ch["idx"], "title": ch["title"], "hits": hits})
    lore.sort(key=lambda x: (-x["hits"], x["idx"]))
    return {
        "version": 1,
        "generated_by": "txt_prep.py",
        "file": os.path.basename(path),
        "encoding": encoding,
        "bytes": os.path.getsize(path) if os.path.exists(path) else 0,
        "chars": len(text),
        "lines": lines_total,
        "fallback_blocks": fallback,
        "chapters": chapters,
        "volumes": [{"title": v["title"], "line": v["line"]} for v in vols],
        "roles": roles,
        "lore_top": lore[:LORE_TOP],
    }


# ================= scan =================

def render_toc(book: dict) -> str:
    out, vlines = [], {v["line"]: v["title"] for v in book["volumes"]}
    for ch in book["chapters"]:
        for ln, title in list(vlines.items()):
            if ln <= ch["start_line"]:
                out.append(f"\n【{title}】")
                del vlines[ln]
        out.append(f"{ch['title']} · {ch['chars']}字")
    return "\n".join(out) + "\n"


def render_card(book: dict) -> str:
    title = os.path.splitext(book["file"])[0]
    title = re.sub(r"[_\-—\s]*(全本|完结|精校|校对|无删减|txt)$", "", title,
                   flags=re.I) or title
    wan = f"{book['chars'] / 10000:.1f}"
    roles = " · ".join(f"{r['name']} {r['count']}" for r in book["roles"][:TOP_ROLES])
    note = "（未识别章节标记，已按 3,000 字切块）" if book["fallback_blocks"] else ""
    return "\n".join([
        f"📖 已接入原著《{title}》",
        f"   规模：{len(book['chapters'])} 章 · {wan} 万字 · "
        f"{len(book['volumes'])} 卷 · 编码 {book['encoding'].upper()}"
        f"（按检测结果解码，输出统一 UTF-8）{note}",
        f"   角色候选：{roles or '（未提取到，可改用模型知识推断）'}",
        f"   索引：{INDEX_NAME} · {TOC_NAME}",
    ])


def cmd_scan(args):
    text, encoding = detect_read(args.path)
    book = build_index(args.path, text, encoding)
    out_dir = os.path.abspath(args.out or os.path.dirname(os.path.abspath(args.path)))
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, INDEX_NAME), "w", encoding="utf-8") as f:
        json.dump(book, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, TOC_NAME), "w", encoding="utf-8") as f:
        f.write(render_toc(book))
    if args.json:
        print(json.dumps(book, ensure_ascii=False))
    else:
        print(render_card(book))
        print(f"   （已写入 {out_dir}/{INDEX_NAME} 与 {TOC_NAME}）")


# ================= slice =================

def load_book(path: str, map_path=None):
    """读索引；缺失则现场重扫（无状态）。"""
    cand = map_path or os.path.join(os.path.dirname(os.path.abspath(path)),
                                    INDEX_NAME)
    if os.path.isfile(cand):
        try:
            with open(cand, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            pass
    text, encoding = detect_read(path)
    return build_index(path, text, encoding)


def head(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    print(f"⚠️ 窗口已截断至 {limit} 字（--max-chars 可调大）", file=sys.stderr)
    return text[:limit] + "\n…（已截断）"


def cmd_slice(args):
    text, _ = detect_read(args.path)
    book = load_book(args.path, args.map)
    starts = line_starts(text)
    if args.ch is not None:
        ch = next((c for c in book["chapters"] if c["no"] == args.ch), None)
        if ch is None:
            ch = next((c for c in book["chapters"] if c["idx"] == args.ch), None)
        if ch is None:
            die(f"第 {args.ch} 章不存在（索引共 {len(book['chapters'])} 章）")
        body = text[starts[ch["start_line"] - 1]:starts[min(ch["end_line"], len(starts) - 1)]]
        print(f"# {ch['title']}（第 {ch['idx']} 章 · {ch['chars']}字）")
        print(head(body.strip(), args.max_chars))
        return
    if args.grep:
        lines = text.split("\n")
        hits = [i for i, ln in enumerate(lines) if args.grep in ln]
        if not hits:
            die(f"关键词「{args.grep}」未命中")
        # 合并重叠窗口
        spans, ctx = [], args.context
        for i in hits:
            a, b = max(i - ctx, 0), min(i + ctx + 1, len(lines))
            if spans and a <= spans[-1][1]:
                spans[-1][1] = max(spans[-1][1], b)
            else:
                spans.append([a, b])
        # 按窗口内命中密度取前 N 个（密度高者更可能是角色出场重头戏），再按行序输出
        def density(s):
            return sum(1 for i in hits if s[0] <= i < s[1])
        picked = sorted(sorted(spans, key=lambda s: (-density(s), s[0]))[:args.windows],
                        key=lambda s: s[0])
        print(f"# 「{args.grep}」命中 {len(hits)} 处 · "
              f"按密度取前 {len(picked)} 个窗口")
        chunks = []
        for a, b in picked:
            first_hit = next((i for i in hits if a <= i < b), a)
            ch = next((c for c in book["chapters"]
                       if c["start_line"] <= first_hit + 1 <= c["end_line"]), None)
            tag = f"（{ch['title']}）" if ch else ""
            chunks.append(f"--- 行 {a + 1}-{b} {tag} · 命中 {density([a, b])} 处 ---\n" +
                          "\n".join(lines[a:b]).strip())
        print(head("\n\n".join(chunks), args.max_chars))
        return
    a = args.from_line or 1
    b = args.to_line or (a + 200)
    body = "\n".join(text.split("\n")[a - 1:b])
    print(f"# 行 {a}-{b}")
    print(head(body.strip(), args.max_chars))


# ================= CLI =================

def main(argv=None):
    p = argparse.ArgumentParser(description="原著 txt 预处理：建索引 / 取窗口")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("scan", help="扫描原文，输出 book_map.json 与 目录.txt")
    ps.add_argument("path", help="原文 txt 路径")
    ps.add_argument("--out", help="索引输出目录（默认与原文同目录）")
    ps.add_argument("--json", action="store_true", help="以 JSON 输出索引摘要")
    ps.set_defaults(func=cmd_scan)

    pl = sub.add_parser("slice", help="按章节 / 行范围 / 关键词取窗口文本")
    pl.add_argument("path", help="原文 txt 路径")
    pl.add_argument("--map", help="book_map.json 路径（默认同目录自动查找）")
    g = pl.add_mutually_exclusive_group(required=True)
    g.add_argument("--ch", type=int, help="章节号（无号则按序号匹配）")
    g.add_argument("--from-line", type=int, help="起始行（1-based）")
    g.add_argument("--grep", help="关键词定位（字面匹配）")
    pl.add_argument("--to-line", type=int, help="结束行（默认起始行 +200）")
    pl.add_argument("-C", "--context", type=int, default=GREP_CONTEXT,
                    help=f"grep 上下文行数（默认 {GREP_CONTEXT}）")
    pl.add_argument("--windows", type=int, default=DEFAULT_WINDOWS,
                    help=f"grep 输出窗口数（默认 {DEFAULT_WINDOWS}）")
    pl.add_argument("--max-chars", type=int, default=DEFAULT_MAX,
                    help=f"单词输出字数上限（默认 {DEFAULT_MAX}）")
    pl.set_defaults(func=cmd_slice)

    args = p.parse_args(argv)
    if not os.path.isfile(getattr(args, "path", "")):
        die(f"原文不存在：{args.path}")
    args.func(args)


if __name__ == "__main__":
    main()
