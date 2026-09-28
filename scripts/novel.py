#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""novel.py — 记忆外置助手（纯标准库，无第三方依赖）。

设计原则：脚本只做「记账、算数、提醒」，不做「校验、审判」。
- 账本外置：小说状态在 novel_runtime.json（格式不变、旧档零迁移），
  助手簿记在同目录 novel_assist.json（侧车：背景项/衰减计数/已回收标记）。
- 简报分层（权重 + 衰减）：
    [行动] 到期/逾期后果，每轮显示直到回收 ；
    [事实] 长期硬事实（核心冲突/关键决策），持续显示 ；
    [变化] 近 2 轮增量，过期即沉降 ；
    [背景] 软状态合并一行，6 轮后完全静默（--full 可查）。
- 无副作用读回：简报是中性书记腔（无感叹号/情感符号/写作指令）；
  [变化][背景] 仅作事实参考，无自然契机不得提及。

用法：
    python3 scripts/novel.py brief [--full]
    python3 scripts/novel.py record (--entry 小票.json | --json '{...}' | stdin)
    python3 scripts/novel.py save [书签摘要]
    python3 scripts/novel.py load (N | --latest)

全局参数：--root 存储根（默认 $NOVEL_STORAGE_ROOT 或 ~/novels）；
          --novel 小说名（默认 _index.json 的 act）。
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone

PRV_MAX = 200      # 前情提要字数上限
DELTA_TURNS = 2    # [变化] 显示窗口（轮）
BG_TURNS = 6       # [背景] 显示窗口（轮），之后完全静默
DUE_AHEAD = 3      # 「即将到期」前瞻窗口（段）

ROUTE_DIRS = {"穿越成原著角色": "穿越", "自创角色": "自创",
              "创世模式": "创世", "随机开局": "随机"}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def die(msg: str):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as e:
        die(f"{path} JSON 损坏：{e}")


def dump_json(path, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def truncate_prv(text: str) -> str:
    """前情提要截断至 ≤200 字的最后一个完整句。"""
    text = text.strip()
    if len(text) <= PRV_MAX:
        return text
    cut = text[:PRV_MAX]
    pos = max(cut.rfind(c) for c in "。！？；…")
    return cut[:pos + 1] if pos >= 0 else cut


def set_path(obj: dict, dotted: str, value) -> None:
    keys = dotted.split(".")
    cur = obj
    for k in keys[:-1]:
        if not isinstance(cur, dict):
            die(f"set 路径非法：{dotted}")
        cur = cur.setdefault(k, {})
    if not isinstance(cur, dict):
        die(f"set 路径非法：{dotted}")
    cur[keys[-1]] = value


def brief_value(v, limit: int = 16) -> str:
    s = json.dumps(v, ensure_ascii=False)
    return s if len(s) <= limit else s[:limit] + "…"


class Novel:
    """一部小说的运行时 + 助手侧车。"""

    def __init__(self, root: str, name=None):
        self.root = os.path.expanduser(root)
        self.index = load_json(os.path.join(self.root, "_index.json"),
                               {"act": None, "nvs": []}) or {"act": None, "nvs": []}
        self.name = name or self.index.get("act")
        if not self.name:
            die("未指定小说名，且 _index.json 无激活小说（用 --novel 《名》 指定）")
        self.dir = os.path.join(self.root, self.name)
        if not os.path.isdir(self.dir):
            die(f"小说目录不存在：{self.dir}")
        self.runtime_path = os.path.join(self.dir, "meta", "novel_runtime.json")
        self.assist_path = os.path.join(self.dir, "meta", "novel_assist.json")
        self.runtime = load_json(self.runtime_path)
        if self.runtime is None:
            die(f"novel_runtime.json 不存在或损坏：{self.runtime_path}")
        self.assist = load_json(self.assist_path, {}) or {}
        self.assist.setdefault("turn", 0)
        self.assist.setdefault("notes", [])
        self.assist.setdefault("changes", [])
        self.assist.setdefault("closed_choices", [])

    # ---------- 持久化 ----------
    def save_all(self) -> None:
        if os.path.isfile(self.runtime_path):
            with open(self.runtime_path, "rb") as f, \
                    open(self.runtime_path + ".bak", "wb") as g:
                g.write(f.read())
        self.runtime["ua"] = now_iso()
        dump_json(self.runtime_path, self.runtime)
        dump_json(self.assist_path, self.assist)
        self.sync_index()

    def sync_index(self) -> None:
        rt = self.runtime
        entry = next((e for e in self.index.setdefault("nvs", [])
                      if e.get("n") == self.name), None)
        if entry is None:
            entry = {"n": self.name}
            self.index["nvs"].append(entry)
        entry["r"] = rt.get("rn", entry.get("r"))
        entry["u"] = rt.get("ua")
        entry["c"] = rt.get("wc")
        self.index["act"] = self.name
        dump_json(os.path.join(self.root, "_index.json"), self.index)

    # ---------- 账本视图 ----------
    def open_choices(self):
        closed = set(self.assist["closed_choices"])
        return [c for c in self.runtime.get("choices", [])
                if c.get("seg") not in closed]


# ---------- brief ----------
def cmd_brief(args):
    n = Novel(args.root, args.novel)
    rt, ast = n.runtime, n.assist
    turn = ast["turn"]
    seg = int(rt.get("seg_count", 0))

    nm = rt.get("nm", n.name)
    title = nm if str(nm).startswith("《") else f"《{nm}》"
    print(f"📖 记忆简报{title} · 第{rt.get('ch', '?')}章"
          f" · {rt.get('sc', '未定')}（seg_count={seg} · 累计 {rt.get('wc', 0)} 字）")

    print(f"[前情] {rt.get('prv', '（无）')}")

    # [行动] 到期/逾期/即将到期的未回收后果 —— 每轮显示直到回收
    due, soon = [], []
    for c in n.open_choices():
        sb = c.get("surface_by")
        if not isinstance(sb, int):
            continue
        if sb <= seg:
            due.append((seg - sb, c))
        elif sb <= seg + DUE_AHEAD:
            soon.append(c)
    print("[行动]（到期后果须本轮或下轮正面回收，禁旁白带过）")
    if not due and not soon:
        print("  · 本轮无到期事项")
    for lag, c in sorted(due):
        head = f"  ⏰ 逾期 {lag} 段" if lag > 0 else "  ⏰ 本轮到期"
        print(f"{head}：{c.get('detail', '（无描述）')}"
              f"（seg{c.get('seg')} · {c.get('type', '-')} · {c.get('tier', '-')}）")
    for c in soon:
        print(f"  · seg{c['surface_by']} 前后呼应：{c.get('detail', '（无描述）')}"
              f"（{c.get('type', '-')} · {c.get('tier', '-')}）")

    # [事实] 长期硬事实
    facts = []
    if rt.get("cc"):
        facts.append(f"核心冲突：{rt['cc']}")
    if rt.get("theme"):
        facts.append(f"主题锚点：{rt['theme']}")
    if rt.get("dv") is not None:
        facts.append(f"原著偏离度：{rt['dv']}")
    kp = rt.get("kp", [])
    if kp:
        facts.append("关键决策（最近）：" + "；".join(str(x) for x in kp[-3:]))
    st = rt.get("st") or {}
    if st:
        facts.append("主角状态：" + " ｜ ".join(
            f"{k}={brief_value(v, 20)}" for k, v in st.items()))
    print("[事实]（须遵守的长期事实）")
    print("  · " + ("\n  · ".join(facts) if facts else "（无）"))

    # [变化] 近 2 轮增量（d ≤ DELTA_TURNS；与 [背景] 的 d > DELTA_TURNS 无缝衔接）
    changes = [c for c in ast["changes"] if c["turn"] >= turn - DELTA_TURNS]
    print(f"[变化]（近 {DELTA_TURNS} 轮增量，过期即沉降）")
    if changes:
        for c in changes[-6:]:
            print(f"  · 第{c['turn']}轮：{c['text']}")
    else:
        print("  · （无）")

    # [背景] 软状态：沉降后合并一行，超过 BG_TURNS 完全静默
    notes = [x for x in ast["notes"]
             if DELTA_TURNS < turn - x["turn"] <= BG_TURNS]
    print("[背景]（仅供事实参考，无自然契机不得提及）")
    print("  · " + (" · ".join(x["text"] for x in notes) if notes else "（无）"))
    if args.full:
        old = [x for x in ast["notes"] if turn - x["turn"] > BG_TURNS]
        if old:
            print("[背景·全量]（已静默条目，仅 --full 显示）")
            for x in old:
                print(f"  · {x['text']}（第{x['turn']}轮登记）")

    # [关系]
    rs, cp = rt.get("rs") or {}, rt.get("cp") or {}
    rel = [f"{k} {v}" + (f"·{cp[k].get('stage', '')}{cp[k].get('progress', '')}%"
                         if isinstance(cp.get(k), dict) else "")
           for k, v in rs.items()]
    print("[关系] " + (" ｜ ".join(rel) if rel else "（无）"))

    # [伏笔]
    pf = [x for x in (rt.get("pf") or []) if x.get("s") == "active"]
    fs = [c for c in n.open_choices() if c.get("type") == "foreshadow"
          and isinstance(c.get("surface_by"), int) and c["surface_by"] > seg]
    fo = [f"{x.get('k')}（第{x.get('ch', '?')}章埋）" for x in pf[:5]] + \
         [f"{c.get('detail')}（seg{c.get('seg')}）" for c in fs[:5]]
    print("[伏笔] " + (("active：" + " ｜ ".join(fo)) if fo else "（无 active）"))

    # [提示]
    nxt = seg + 1
    hook = f"，命中锚定钩子：回响核对 + 语域/关系重锚" if nxt % 8 == 0 else ""
    print(f"[提示] 下轮 seg_count={nxt}{hook} ｜ open 账本 {len(n.open_choices())} 条")

    print("⚖️ 简报守则：[行动] 须正面回收；[事实] 须遵守；"
          "[变化][背景] 仅作事实参考，无自然契机不得提及、不得当情节推动器。")


# ---------- record ----------
def cmd_record(args):
    entry = {}
    if args.entry:
        entry = load_json(args.entry) or {}
    elif args.json:
        try:
            entry = json.loads(args.json)
        except json.JSONDecodeError as e:
            die(f"--json 解析失败：{e}")
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        if raw:
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError as e:
                die(f"stdin 解析失败：{e}")
    if not entry:
        die("record 需要小票 JSON（--entry 文件 / --json '{...}' / stdin）")

    n = Novel(args.root, args.novel)
    rt, ast = n.runtime, n.assist
    turn = ast["turn"] + 1
    changes = []

    for k, v in (entry.get("set") or {}).items():
        set_path(rt, k, v)
        changes.append(f"{k}→{brief_value(v)}")

    for k, items in (entry.get("add") or {}).items():
        arr = rt.setdefault(k, [])
        if not isinstance(arr, list):
            die(f"add 目标须为数组：{k}")
        added = 0
        for it in items:
            if it not in arr:
                arr.append(it)
                added += 1
        if added:
            changes.append(f"{k} 追加×{added}")

    for s in entry.get("close_choices") or []:
        if s not in ast["closed_choices"]:
            ast["closed_choices"].append(s)
            changes.append(f"账本 seg{s} 已回收")

    for t in entry.get("notes") or []:
        ast["notes"].append({"text": str(t), "turn": turn})
        changes.append(f"新增背景：{t}")
    for pat in entry.get("resolve_notes") or []:
        keep = [x for x in ast["notes"] if pat not in x["text"]]
        if len(keep) != len(ast["notes"]):
            changes.append(f"背景消解：{pat}")
        ast["notes"] = keep

    cs = entry.get("chapter_summary")
    if cs:
        old = rt.get("chapter_summary")
        if old:
            vols = rt.setdefault("volumes", [])
            vols.append({"ch_end": old.get("ch", rt.get("ch")),
                         "summary": old.get("summary", ""),
                         "generated_by": old.get("generated_by", "LLM"),
                         "created_at": old.get("created_at", now_iso())})
        cs.setdefault("ch", rt.get("ch"))
        cs.setdefault("generated_by", "LLM")
        cs.setdefault("created_at", now_iso())
        rt["chapter_summary"] = cs
        changes.append(f"章摘要更新（第{cs['ch']}章）")

    w = int(entry.get("w", 0))
    rt["wc"] = int(rt.get("wc", 0)) + w
    rt["seg_count"] = seg = int(rt.get("seg_count", 0)) + int(entry.get("seg", 1))
    if entry.get("prv"):
        rt["prv"] = truncate_prv(str(entry["prv"]))

    ast["turn"] = turn
    if changes:
        ast["changes"].append({"turn": turn, "text": "；".join(changes)})
    ast["changes"] = ast["changes"][-60:]
    n.save_all()

    print(f"✅ 已记账：第{turn}轮 · +{w} 字（累计 {rt['wc']}）· seg_count={seg}")
    for c in changes:
        print(f"   · {c}")


# ---------- save / load ----------
def route_dir(rt: dict) -> str:
    rn = rt.get("rn", "") or "未定"
    return ROUTE_DIRS.get(rn, re.sub(r'[\\/:*?"<>|]', "_", rn))


def save_dir(n: Novel) -> str:
    return os.path.join(n.dir, "saves", route_dir(n.runtime))


def save_files(d: str):
    out = {}
    if os.path.isdir(d):
        for fn in os.listdir(d):
            m = re.fullmatch(r"(\d+)\.md", fn)
            if m:
                out[int(m.group(1))] = os.path.join(d, fn)
    return out


def cmd_save(args):
    n = Novel(args.root, args.novel)
    d = save_dir(n)
    files = save_files(d)
    if args.note is None:  # 无参数 = 列出存档
        if not files:
            print("（该路线暂无存档）")
            return
        for k in sorted(files):
            head = open(files[k], encoding="utf-8").read(300)
            m = re.search(r"^#存档 \d+\s*\n>(.*)$", head, re.M)
            ts = datetime.fromtimestamp(os.path.getmtime(files[k]))
            print(f"  #{k} · {m.group(1).strip() if m else '（无书签）'}"
                  f" · {ts.strftime('%Y-%m-%d %H:%M')}")
        return

    num = (max(files) if files else 0) + 1
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{num:03d}.md")
    rt = n.runtime
    body = (f"#存档 {num}\n>{args.note}\n\n---状态摘要---\n"
            f"（自动快照 · {now_iso()} · 第{rt.get('ch', '?')}章"
            f" · seg_count={rt.get('seg_count', 0)} · {rt.get('wc', 0)} 字）\n\n"
            f"<!--NOVEL_STATE\n"
            f"{json.dumps(rt, ensure_ascii=False, indent=2)}\n-->\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(body)
    rt["ms"] = num
    n.save_all()
    print(f"💾 已存档 #{num}：{args.note}")


def cmd_load(args):
    n = Novel(args.root, args.novel)
    d = save_dir(n)
    files = save_files(d)
    if not files:
        die("该路线暂无存档")
    num = max(files) if args.latest else args.num
    if num not in files:
        die(f"存档 #{num} 不存在（现有：{sorted(files)}）")
    text = open(files[num], encoding="utf-8").read()
    m = re.search(r"<!--NOVEL_STATE\s*(\{.*?\})\s*-->", text, re.S)
    if not m:
        die(f"存档 #{num} 无机器快照，无法自动回填（需手工恢复）")
    state = json.loads(m.group(1))
    with open(n.runtime_path, "rb") as f, \
            open(n.runtime_path + ".bak", "wb") as g:
        g.write(f.read())
    dump_json(n.runtime_path, state)
    n.runtime = state
    n.sync_index()
    note = re.search(r"^#存档 \d+\s*\n>(.*)$", text, re.M)
    print(f"📂 已读档 #{num}：{note.group(1).strip() if note else ''}")
    print(f"[前情] {state.get('prv', '（无）')}")
    print(f"[状态] 第{state.get('ch', '?')}章 · {state.get('sc', '')}"
          f" · seg_count={state.get('seg_count', 0)} · 累计 {state.get('wc', 0)} 字")


# ---------- CLI ----------
def main() -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=argparse.SUPPRESS,
                        help="存储根（默认 $NOVEL_STORAGE_ROOT 或 ~/novels）")
    common.add_argument("--novel", default=argparse.SUPPRESS,
                        help="小说名（默认 _index.json 的 act）")

    p = argparse.ArgumentParser(description="记忆外置助手：记账、算数、提醒")
    p.add_argument("--root", default=os.environ.get("NOVEL_STORAGE_ROOT", "~/novels"),
                   help="存储根（默认 $NOVEL_STORAGE_ROOT 或 ~/novels）")
    p.add_argument("--novel", default=None,
                   help="小说名（默认 _index.json 的 act）")
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("brief", parents=[common], help="生成开场/恢复简报")
    pb.add_argument("--full", action="store_true", help="含已静默背景项与全量账本")
    pb.set_defaults(func=cmd_brief)

    pr = sub.add_parser("record", parents=[common], help="每轮记账（小票 JSON）")
    pr.add_argument("--entry", help="小票 JSON 文件路径")
    pr.add_argument("--json", help="小票 JSON 字符串")
    pr.set_defaults(func=cmd_record)

    ps = sub.add_parser("save", parents=[common], help="存档（无参数=列出存档）")
    ps.add_argument("note", nargs="?", help="存档书签摘要")
    ps.set_defaults(func=cmd_save)

    pl = sub.add_parser("load", parents=[common], help="读档回填运行时状态")
    g = pl.add_mutually_exclusive_group(required=True)
    g.add_argument("num", nargs="?", type=int, help="存档编号")
    g.add_argument("--latest", action="store_true", help="最新存档")
    pl.set_defaults(func=cmd_load)

    args = p.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
