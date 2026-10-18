#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""asserts.py — promptfoo 硬契约断言集（dev 侧，纯标准库）

为什么自己写断言而不用 promptfoo 内置：
  内置断言能查「包含某字符串」「正则匹配」，但本项目的契约是**结构性的**——
  「选项区必须是 A/B/C/D/E 五条且顺序正确、D 限主角推断、E 禁关键抉择」、
  「字数需排除状态条与选项行后统计正文」、这类判定用正则拼不出来且无法维护。
  写成一个可被单元测试的纯函数模块，既给 promptfoo 用，也能离线自检。

每个断言函数签名（promptfoo javascript 断言约定）：
    fn(output: str, context: dict) -> bool | dict
返回 True 通过；返回 {"pass": bool, "score": float, "reason": str} 可带说明。

契约来源：SKILL.md 铁律 #0 / §正文格式约束 / §迷你状态条 / §紧凑选项格式
"""

import re

# ---------- 常量（与 SKILL.md 口径一致，改动须同步） ----------
WORDCOUNT_MAIN = (500, 1200)
WORDCOUNT_SCENES = {
    "氛围展开": (800, 1200), "情感场景": (800, 1200),
    "日常过渡": (400, 600), "对话快速交换": (250, 400),
    "紧迫战斗": (250, 400), "快进首段": (250, 400),
    "随机开局首段": (300, 800),
}
OPTION_LETTERS = ["A", "B", "C", "D", "E"]

# 选项行：行首（可含列表符号/加粗）字母 + 分隔符
# 分隔符须含 `·`：SKILL.md §紧凑选项格式 规定默认输出为 `{字母} · [{标签}] {摘要}`，
# 若不含 `·`，规范输出会被判为「无选项」，并连带污染正文（选项行被吃进 body 导致字数虚高）。
OPTION_RE = re.compile(r"^\s*(?:[-*·]\s*)?(?:\*\*)?([A-E])(?:\*\*)?\s*[.、:：)）·]\s*\S")
# 状态条：🔖 开头
STATUS_RE = re.compile(r"^\s*🔖\s*\S")
# 提示行：💡 开头
HINT_RE = re.compile(r"^\s*[💡>]")
# 破折号（中英）
EM_DASH_RE = re.compile(r"——|—{1,}|--")
# AI 腔词表（审稿常用词，业务侧可增补）
AI_TONE_WORDS = [
    "总而言之", "综上所述", "值得注意的是", "不禁", "油然而生", "涌上心头",
    "心中一暖", "复杂的情绪", "意味深长", "仿佛时间静止", "空气中弥漫着",
    "感官的盛宴", "无数念头", "内心深处", "无言的沉默", "难以言喻",
]
# 闭环结论句（正文不得以「事情彻底解决」收尾）
CLOSED_LOOP_RE = re.compile(
    r"(事情(终于|彻底)?(解决|结束)了|全部结束|就此告一段落|一切归(于)?平静"
    r"|从此(过上了|幸福)|圆满(解决|结束)|尘埃落定|再无(后顾之忧|牵挂))")
# E 选项的禁止内容（关键抉择不得放进快进选项）
KEY_DECISION_RE = re.compile(r"(生死|杀死|杀了|背叛|表白|告白|分手|背叛|嫁|娶|自尽|同归于尽)")


def _lines(output: str):
    return (output or "").splitlines()


def _strip_markup(s: str) -> str:
    """去 markdown 强调/列表符号，便于统一识别。"""
    return re.sub(r"[*_`>]", "", s).strip()


# ---------- 分区提取 ----------
def locate_sections(output: str) -> dict:
    """把输出切成 状态条 / 正文 / 选项 / 提示 四段。

    返回 {"status": str|None, "body": str, "options": list[(letter, text)], "hint": str|None}
    这是所有断言的共同地基——先定位结构，再判内容。
    """
    ls = _lines(output)
    status = None
    opts = []
    hint = None
    body_lines = []

    for ln in ls:
        s = ln.rstrip()
        if STATUS_RE.match(s):
            if status is None:
                status = s
            continue                      # 状态条不计入正文
        m = OPTION_RE.match(s)
        if m:
            opts.append((m.group(1), _strip_markup(s)))
            continue
        if HINT_RE.match(s) and opts:
            hint = _strip_markup(s)
            continue
        if not opts:
            body_lines.append(s)
        # 选项区之后的散行归入提示，不污染正文
    return {"status": status, "body": "\n".join(body_lines).strip(),
            "options": opts, "hint": hint}


def count_body_chars(output: str) -> int:
    """正文净字数：剔除状态条、选项行、提示行、空白与 markdown 符号。"""
    body = locate_sections(output)["body"]
    cleaned = re.sub(r"\s", "", body)
    cleaned = re.sub(r"[*_`#>\-—]{1,}", "", cleaned)
    return len(cleaned)


# ---------- 分项断言 ----------
def has_five_options(output: str, context=None):
    """铁律 #0：A/B/C/D/E 五选项齐全、顺序正确、无重复。

    合法豁免：标 [集] 的段、沉浸模式。此处按「普通轮次」判定（豁免轮次应在
    用例侧用专门的 test 标注，不混入本断言）。
    """
    out = output or ""
    if "[集]" in out or "沉浸模式" in out:
        return {"pass": True, "score": 1.0, "reason": "命中合法豁免（[集]/沉浸模式）"}
    opts = locate_sections(out)["options"]
    letters = [l for l, _ in opts]
    if letters != OPTION_LETTERS:
        return {"pass": False, "score": 0.0,
                "reason": f"选项不为 A→E 五条顺序序列：{letters or '（无选项）'}"}
    return {"pass": True, "score": 1.0, "reason": "五选项齐全且顺序正确"}


def wordcount_in_range(output: str, context=None):
    """字数区间：正文净字数须落在主区间 500-1200（或有明确场景档）。

    例外场景（对话快速交换/紧迫战斗/快进首段等）在用例里通过 context.vars.scene
    指定；未指定时按主区间判。
    """
    n = count_body_chars(output)
    vars_ = (context or {}).get("vars") or {}
    scene = vars_.get("scene") if isinstance(vars_, dict) else None
    lo, hi = WORDCOUNT_SCENES.get(scene, WORDCOUNT_MAIN)
    if not (lo <= n <= hi):
        return {"pass": False, "score": 0.0,
                "reason": f"正文净字数 {n} 不在 {scene or '主区间'} 的 {lo}-{hi} 内"}
    return {"pass": True, "score": 1.0, "reason": f"正文净字数 {n} ∈ {lo}-{hi}"}


def symbol_discipline(output: str, context=None):
    """符号分工：动作（）/ 心理〔〕内不得混入台词（对话须裸写或引号）。

    判定锚点：括号内出现成对引号（「」『』""）即视为把台词塞进动作/心理描述。
    """
    body = locate_sections(output)["body"]
    bad = []
    for m in re.finditer(r"[（(]([^）)]{0,200})[）)]", body):
        if re.search(r"[「」『』“”\"]", m.group(1)):
            bad.append(("动作（）", m.group(0)[:40]))
    for m in re.finditer(r"[〔【]([^〕】]{0,200})[〕】]", body):
        if re.search(r"[「」『』“”\"]", m.group(1)):
            bad.append(("心理〔〕", m.group(0)[:40]))
    if bad:
        return {"pass": False, "score": 0.0,
                "reason": f"符号分工违规（台词混入动作/心理）：{bad[:3]}"}
    return {"pass": True, "score": 1.0, "reason": "符号分工合规"}


def status_bar_format(output: str, context=None):
    """状态条格式：🔖 开头；含「第N章」或「序章」；含万字计数。"""
    out = output or ""
    st = locate_sections(out)["status"]
    if st is None:
        return {"pass": False, "score": 0.0, "reason": "缺迷你状态条（🔖 开头的独立行）"}
    if "章" not in st and "序章" not in st:
        return {"pass": False, "score": 0.0, "reason": f"状态条缺章节位：{st}"}
    if not re.search(r"\d+(\.\d+)?\s*万字", st):
        return {"pass": False, "score": 0.0, "reason": f"状态条缺字数位（N万字）：{st}"}
    return {"pass": True, "score": 1.0, "reason": f"状态条合规：{st}"}


def no_em_dash(output: str, context=None):
    """正文不得出现破折号（项目既有规范）。"""
    body = locate_sections(output)["body"]
    hits = EM_DASH_RE.findall(body)
    if hits:
        return {"pass": False, "score": 0.0, "reason": f"正文含破折号 {len(hits)} 处：{hits[:5]}"}
    return {"pass": True, "score": 1.0, "reason": "无破折号"}


def no_ai_tone(output: str, context=None):
    """AI 腔词表清零。"""
    body = locate_sections(output)["body"]
    hits = [w for w in AI_TONE_WORDS if w in body]
    if hits:
        return {"pass": False, "score": 0.0, "reason": f"正文含 AI 腔词：{hits}"}
    return {"pass": True, "score": 1.0, "reason": "无 AI 腔词命中"}


def not_closed_loop(output: str, context=None):
    """收尾不得闭环整个场景事件（不得给出「事情彻底解决了」的结论）。"""
    body = locate_sections(output)["body"]
    if not body:
        return {"pass": False, "score": 0.0, "reason": "无正文可判"}
    tail = body[-120:]        # 只看收尾段
    m = CLOSED_LOOP_RE.search(tail)
    if m:
        return {"pass": False, "score": 0.0, "reason": f"正文收尾闭环：{m.group(0)}"}
    return {"pass": True, "score": 1.0, "reason": "收尾未闭环"}


def e_option_not_key_decision(output: str, context=None):
    """E 选项（快进）不得承载关键抉择。"""
    opts = locate_sections(output)["options"]
    e = [t for l, t in opts if l == "E"]
    if not e:
        return {"pass": True, "score": 1.0, "reason": "（无 E 选项，或已豁免）"}
    m = KEY_DECISION_RE.search(e[0])
    if m:
        return {"pass": False, "score": 0.0, "reason": f"E 选项含关键抉择：{m.group(0)}"}
    return {"pass": True, "score": 1.0, "reason": "E 选项无关键抉择"}


def d_option_is_protagonist_inference(output: str, context=None):
    """D 选项须为「AI 按主角性格推断的最可能反应」，不得是玩家/用户视角指令。"""
    opts = locate_sections(output)["options"]
    d = [t for l, t in opts if l == "D"]
    if not d:
        return {"pass": True, "score": 1.0, "reason": "（无 D 选项，或已豁免）"}
    if re.search(r"(你来|请你|玩家|你选|你应该)", d[0]):
        return {"pass": False, "score": 0.0, "reason": f"D 选项越位为用户指令：{d[0][:40]}"}
    return {"pass": True, "score": 1.0, "reason": "D 选项为主角推断"}


def option_separator_canonical(output: str, context=None):
    """选项分隔符须为规范格式 `{字母} · [{标签}] {摘要}` 的居中点 `·`。

    为什么要单列这条：`locate_sections` 为了鲁棒性对分隔符是宽松的
    （同时接受 `·` / `、` / `.` / `：`），否则格式稍有偏差就定位不到选项区，
    连带把选项行吃进正文导致字数虚高。但宽松解析会让「用顿号」这类偏差
    静默通过——因此**另设本断言如实报出偏差**，而不是把尺子放松了当没看见。
    依据：SKILL.md §选项格式表 + references/options-quickref.md（规范为 `·`）。
    """
    opts_raw = []
    for ln in _lines(output):
        m = re.match(r"^\s*(?:[-*]\s*)?(?:\*\*)?([A-E])(?:\*\*)?\s*(\S)", ln)
        if m:
            opts_raw.append((m.group(1), m.group(2)))
    if not opts_raw:
        return {"pass": True, "score": 1.0, "reason": "（无选项行可判，或已豁免）"}
    bad = [(l, sep) for l, sep in opts_raw if sep != "·"]
    if bad:
        seps = sorted({s for _, s in bad})
        return {"pass": False, "score": 0.0,
                "reason": f"选项分隔符非规范（应为 `·`）：{bad} | 出现的分隔符 {seps}"}
    return {"pass": True, "score": 1.0, "reason": "选项分隔符均为规范 `·`"}


def assert_all(output: str, context=None):
    """聚合断言：全部硬契约一次判定，返回汇总与逐项明细。"""
    checks = {
        "five_options": has_five_options,
        "wordcount": wordcount_in_range,
        "symbols": symbol_discipline,
        "status_bar": status_bar_format,
        "no_em_dash": no_em_dash,
        "no_ai_tone": no_ai_tone,
        "not_closed_loop": not_closed_loop,
        "e_option": e_option_not_key_decision,
        "d_option": d_option_is_protagonist_inference,
        "opt_separator": option_separator_canonical,
    }
    details, failed = {}, []
    for name, fn in checks.items():
        r = fn(output, context)
        ok = r if isinstance(r, bool) else bool(r.get("pass"))
        reason = "" if isinstance(r, bool) else r.get("reason", "")
        details[name] = {"pass": ok, "reason": reason}
        if not ok:
            failed.append(f"{name}: {reason}")
    if failed:
        return {"pass": False, "score": 0.0, "reason": " | ".join(failed), "details": details}
    return {"pass": True, "score": 1.0, "reason": "全部契约通过", "details": details}
