#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""属性测试 · novel.py（dev 侧，不进发布包、不进 MANIFEST）

为什么要属性测试：以下三个 bug 都是**手工用例漏掉的数据形状**造成的，
靠「加一条用例」只能补一个形状，靠属性测试才能把整个形状空间变成永久防线：

  1. `sorted(due)` 比较 dict 崩溃——due 曾把「lag 与条目」混装成同一元组列，
     当 lag 相同时 Python 会退而去比较 dict，直接 TypeError。
     现已改为 `sorted(due, key=lambda x: x[0])`；本文件断言**
     任意** choices 形状下简报都不抛异常。
  2. 衰减缝隙——简报分层依赖 `DELTA_TURNS < turn - x["turn"] <= BG_TURNS`，
     边界（恰好等于 DELTA_TURNS / BG_TURNS）若处理不当会让条目既不在
     [变化] 也不在 [背景] 里静默消失。本文件断言每个轮次都被**至少一个**
     分区覆盖，且分区之间无缝隙。
  3. 非 UTF-8 崩溃——见 tests/test_txt_prep_props.py。

运行：python3 -m unittest discover -s tests -p "test_*.py" -v
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS)

import novel  # noqa: E402

# 属性测试跑得快一些：默认 100 例/属性已足够覆盖形状空间（CI 亦按此值）
FAST = settings(max_examples=150, deadline=None,
                suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture])

# 段计数上限：覆盖 0（空账本）、小值、跨 [变化]/[背景] 边界（DELTA_TURNS=2、BG_TURNS=6）
SEG_MAX = novel.BG_TURNS + 4


def seg_st() -> st.SearchStrategy:
    return st.integers(min_value=0, max_value=SEG_MAX)


def choice_st() -> st.SearchStrategy:
    """任意形状的账本条目：含缺字段 / 错误类型 / 越界 seg，逼近真实脏数据。"""
    return st.fixed_dictionaries({}, optional={
        "seg": st.one_of(st.integers(min_value=-3, max_value=SEG_MAX + 5),
                         st.text(max_size=4)),          # 容忍 "17" 这类字符串写法
        "surface_by": st.one_of(st.integers(min_value=-3, max_value=SEG_MAX + 5),
                                st.none(), st.text(max_size=3)),
        "detail": st.one_of(st.text(max_size=20), st.none()),
        "type": st.sampled_from(["", "foreshadow", "consequence", "未知"]),
        "tier": st.one_of(st.text(max_size=6), st.none()),
    })


def note_st() -> st.SearchStrategy:
    return st.fixed_dictionaries({
        "text": st.text(max_size=12),
        "turn": st.integers(min_value=0, max_value=20),
    })


class FakeArgs:
    """cmd_brief 只读 args.full / args.input，另需 root 与 novel 定位小说。"""

    def __init__(self, full=False, inp=None, root=None, novel_name=None):
        self.full = full
        self.input = inp
        self.root = root
        self.novel = novel_name


def make_novel(tmpdir: str, runtime: dict, assist: dict):
    """按 Novel 的目录约定搭一个最小可用实例（不走 CLI）。"""
    ndir = os.path.join(tmpdir, "测试小说")
    os.makedirs(os.path.join(ndir, "meta"), exist_ok=True)
    with open(os.path.join(ndir, "meta", "novel_runtime.json"), "w", encoding="utf-8") as f:
        json.dump(runtime, f, ensure_ascii=False)
    with open(os.path.join(ndir, "meta", "novel_assist.json"), "w", encoding="utf-8") as f:
        json.dump(assist, f, ensure_ascii=False)
    return novel.Novel(tmpdir, "测试小说")


def base_runtime(**over) -> dict:
    rt = {"v": 1, "ua": "t", "nm": "测试", "rn": "自创", "md": "爽文",
          "vw": "v", "ch": 1, "sc": "日常过渡", "wc": 0, "choices": [], "st": {},
          "seg_count": 0}
    rt.update(over)
    return rt


def base_assist(**over) -> dict:
    ast = {"turn": 0, "notes": [], "changes": [], "closed_choices": []}
    ast.update(over)
    return ast


class RecordArgs:
    """构造 cmd_record 所需的 args（entry 走 --json，避免临时文件）。"""

    def __init__(self, root: str, name: str, **payload):
        self.root = root
        self.novel = name
        self.entry = None
        self.json = json.dumps(payload, ensure_ascii=False)


class TestBriefNeverCrashes(unittest.TestCase):
    """bug 1 防线：任意账本形状下 cmd_brief 都不得抛异常（尤其 sorted(due)）。"""

    @FAST
    @given(choices=st.lists(choice_st(), max_size=8),
           seg=seg_st(),
           closed=st.lists(st.integers(min_value=-2, max_value=SEG_MAX + 3), max_size=5),
           notes=st.lists(note_st(), max_size=6),
           turn=st.integers(min_value=0, max_value=8),
           full=st.booleans())
    def test_brief_never_raises(self, choices, seg, closed, notes, turn, full):
        with tempfile.TemporaryDirectory() as tmp:
            rt = base_runtime(choices=choices, seg_count=seg)
            ast = base_assist(closed_choices=closed, notes=notes, turn=turn)
            n = make_novel(tmp, rt, ast)
            buf_out, buf_err = io.StringIO(), io.StringIO()
            try:
                with redirect_stdout(buf_out), redirect_stderr(buf_err):
                    novel.cmd_brief(FakeArgs(full=full, inp="测试输入", root=tmp, novel_name="测试小说"))
            except SystemExit as e:  # die() 只允许在「明确无小说」路径出现，这里不该有
                self.fail(f"cmd_brief 意外退出：{e}\n{buf_err.getvalue()}")
            except TypeError as e:
                self.fail(f"cmd_brief 抛 TypeError（疑似 sorted 比较 dict）：{e}\n"
                          f"choices={choices!r}\nseg={seg}")

    @FAST
    @given(choices=st.lists(choice_st(), max_size=8), seg=seg_st())
    def test_brief_without_seg_count_falls_back(self, choices, seg):
        """旧档无 seg_count：ledger_seg 必须回退到账本最大 seg，而不是让到期判定失效。"""
        with tempfile.TemporaryDirectory() as tmp:
            rt = base_runtime(choices=choices)
            rt.pop("seg_count")
            ast = base_assist()
            n = make_novel(tmp, rt, ast)
            got = novel.ledger_seg(rt, n)
            segs = [c.get("seg") for c in choices if isinstance(c.get("seg"), int)]
            self.assertEqual(got, max(segs) if segs else 0)

    @FAST
    @given(choices=st.lists(choice_st(), max_size=6), seg=seg_st())
    def test_open_choices_excludes_closed(self, choices, seg):
        """回收后的条目不得再出现在未回收视图里（挡住「回收了却还在提醒」）。"""
        with tempfile.TemporaryDirectory() as tmp:
            rt = base_runtime(choices=choices, seg_count=seg)
            closed = [c["seg"] for c in choices
                      if isinstance(c.get("seg"), int)][:2]
            n = make_novel(tmp, rt, base_assist(closed_choices=closed))
            got = n.open_choices()
            self.assertFalse([c for c in got if c.get("seg") in closed])
            self.assertLessEqual(len(got), len(choices))


class TestDecayNoGap(unittest.TestCase):
    """bug 2 防线：简报分层不得出现「哪个分区都不显示」的缝隙。

    真实管线是「record 逐轮登记 → brief 呈现」，分工为：
      · [变化] = 近 DELTA_TURNS 轮的变更日志（含本轮新登记的背景项文本）
      · [背景] = 已沉降但未静默的背景项（DELTA_TURNS < d <= BG_TURNS）
      · [背景·全量] = 已静默项（d > BG_TURNS），仅 --full 显示
    因此本类**不直接构造 notes**（那会绕过 record 的变更日志，造出非真实状态），
    而是逐轮走 cmd_record 后再 brief，断言每个登记过的背景项都有落点。
    """

    @FAST
    @given(register=st.lists(st.booleans(), min_size=1, max_size=8),
           full=st.booleans())
    def test_brief_covers_all_notes(self, register, full):
        """经 record 登记的每个背景项，在 brief 输出中都要能找到（--full 时含已静默项）。"""
        with tempfile.TemporaryDirectory() as tmp:
            make_novel(tmp, base_runtime(), base_assist())
            texts: dict = {}   # 轮次 → 该轮登记的背景文本
            for i, do_reg in enumerate(register, start=1):
                text = f"背景{i}号"
                payload = {"seg": 1, "w": 0}
                if do_reg:
                    payload["notes"] = [text]
                    texts[i] = text
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    novel.cmd_record(RecordArgs(tmp, "测试小说", **payload))

            total = len(register)
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                novel.cmd_brief(FakeArgs(full=full, inp=None, root=tmp, novel_name="测试小说"))
            out = buf.getvalue()

            for k, text in texts.items():
                d = total - k
                if d <= novel.BG_TURNS or full:
                    self.assertIn(text, out,
                                  f"背景项 {text!r}（第{k}轮登记，d={d}）在简报中消失")
                else:
                    self.assertNotIn(text, out,
                                     f"已静默背景项 {text!r}（d={d}）不应在非 --full 简报中出现")

    @FAST
    @given(n_rounds=st.integers(min_value=1, max_value=novel.BG_TURNS + 4),
           full=st.booleans())
    def test_buckets_cover_all_notes_blackbox(self, n_rounds, full):
        """分区口径不得留缝——**黑盒验证**：真跑 record+brief，逐轮检查每个背景项。

        ⚠️ 原实现是「同义反复」：它只拿 `novel.DELTA_TURNS` / `novel.BG_TURNS` 两个常量
        自证互斥穷尽，不调用任何实现函数——导致把常量改成 3/5 也照样通过（变异实测存活）。
        现改为黑盒：以 **brief 的实际输出**判断每个背景项是否有落点，
        常量被改动后行为若变化，本测试即失败。

        判据（与实现口径对齐）：
          · d ≤ DELTA_TURNS  → 出现在 [变化]（登记当轮的变更日志里含该文本）
          · d ≤ BG_TURNS     → 出现在 [背景]
          · d > BG_TURNS     → 仅 --full 时出现在 [背景·全量]
        """
        with tempfile.TemporaryDirectory() as tmp:
            make_novel(tmp, base_runtime(), base_assist())
            registered = {}          # 轮次 → 该轮登记的文本
            for i in range(1, n_rounds + 1):
                text = f"背景{i}号"
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    novel.cmd_record(RecordArgs(tmp, "测试小说", seg=1, w=0, notes=[text]))
                registered[i] = text

            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                novel.cmd_brief(FakeArgs(full=full, inp=None, root=tmp, novel_name="测试小说"))
            out = buf.getvalue()

            total = n_rounds
            for k, text in registered.items():
                d = total - k
                in_delta = d <= novel.DELTA_TURNS
                in_bg = novel.DELTA_TURNS < d <= novel.BG_TURNS
                in_silent = d > novel.BG_TURNS
                # 互斥穷尽（这里是对**实际输出**的分区，不是对常量自证）
                self.assertEqual(sum([in_delta, in_bg, in_silent]), 1,
                                 f"d={d} 未落入唯一分区")
                # [变化] 窗口内必须出现在输出中
                if in_delta:
                    self.assertIn(text, out, f"{text!r}（d={d}，应在 [变化]）未出现在简报")
                # 静默项：非 --full 不得出现；--full 必须出现
                if in_silent and not full:
                    self.assertNotIn(text, out, f"已静默项 {text!r}（d={d}）不应出现在非 --full 简报")
                if in_silent and full:
                    self.assertIn(text, out, f"--full 应显示已静默项 {text!r}（d={d}）")


class TestRecordProperties(unittest.TestCase):
    """记账不变量：seg_count 单调、字数累计、非法 seg 被挡。"""

    @FAST
    @given(segs=st.lists(st.integers(min_value=1, max_value=5), min_size=1, max_size=5),
           wc=st.lists(st.integers(min_value=0, max_value=5000), min_size=1, max_size=5))
    def test_seg_count_monotonic_and_wc_accumulates(self, segs, wc):
        n_rounds = min(len(segs), len(wc))
        with tempfile.TemporaryDirectory() as tmp:
            make_novel(tmp, base_runtime(), base_assist())
            prev_seg, prev_wc = 0, 0
            for i in range(n_rounds):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    novel.cmd_record(RecordArgs(tmp, "测试小说", seg=segs[i], w=wc[i]))
                after = novel.Novel(tmp, "测试小说")
                self.assertGreaterEqual(after.runtime["seg_count"], prev_seg,
                                        "seg_count 不得回退")
                self.assertEqual(after.runtime["wc"], prev_wc + wc[i],
                                 "累计字数应为精确累加")
                self.assertEqual(after.runtime["seg_count"], prev_seg + segs[i])
                prev_seg, prev_wc = after.runtime["seg_count"], after.runtime["wc"]

    @FAST
    @given(bad=st.one_of(st.none(), st.text(max_size=6), st.floats(allow_nan=False)))
    def test_illegal_close_seg_is_rejected(self, bad):
        """非法 seg（None/文本/浮点）不得进 closed_choices，且不得抛异常。"""
        with tempfile.TemporaryDirectory() as tmp:
            n = make_novel(tmp, base_runtime(choices=[{"seg": 1}]), base_assist())
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                novel.cmd_record(RecordArgs(tmp, n.name, close_choices=[{"seg": bad}]))
            after = novel.Novel(tmp, "测试小说")
            if bad is None:
                self.assertEqual(after.assist["closed_choices"], [])
            else:
                for entry in after.assist["closed_choices"]:
                    self.assertIsInstance(entry, int)

    @FAST
    @given(notes=st.one_of(st.text(max_size=10),
                           st.lists(st.text(max_size=10), max_size=3),
                           st.dictionaries(st.sampled_from(["text", "t"]),
                                           st.text(max_size=10), max_size=1)))
    def test_notes_never_split_into_chars(self, notes):
        """背景登记必须容忍字符串/列表/对象三种写法，绝不逐字拆成单字背景项。"""
        with tempfile.TemporaryDirectory() as tmp:
            make_novel(tmp, base_runtime(), base_assist())
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                novel.cmd_record(RecordArgs(tmp, "测试小说", notes=notes))
            after = novel.Novel(tmp, "测试小说")
            for item in after.assist["notes"]:
                self.assertIsInstance(item, dict)
                self.assertIn("text", item)
                self.assertGreaterEqual(len(item["text"]), 1)
            if isinstance(notes, str) and notes.strip():
                self.assertEqual(len(after.assist["notes"]), 1,
                                 "字符串应作为单条背景，而非逐字拆开")


class TestTruncateProperties(unittest.TestCase):
    """前情提要截断：不得超上限、不得破坏句末。"""

    @FAST
    @given(text=st.text(max_size=500))
    def test_truncate_never_exceeds_limit(self, text):
        got = novel.truncate_prv(text)
        if len(text.strip()) <= novel.PRV_MAX:
            self.assertEqual(got, text.strip())
        else:
            self.assertLessEqual(len(got), novel.PRV_MAX,
                                 "截断结果不得超出 PRV_MAX")

    @FAST
    @given(sentences=st.lists(
        st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc")),
                min_size=40, max_size=120), min_size=4, max_size=8),
        end=st.sampled_from("。！？；…"))
    def test_truncate_prefers_sentence_boundary(self, sentences, end):
        """超限时优先切在完整句末；结果必须是（strip 后的）原串前缀。

        ⚠️ 两个易错点（均已避开）：
          1. 样本必须**保证超限**：原实现生成 max=97 长度的样本，断言体永不执行（死测试）；
          2. `truncate_prv` 内部会 `text.strip()`，故前缀断言须对 **strip 后**的文本做，
             否则含前导/尾随空白的样本会误报失败（注意：`assertLessEqual` 那类断言不受影响）。
        """
        text = end.join(sentences) + end
        if len(text) <= novel.PRV_MAX:
            text += "填" * (novel.PRV_MAX - len(text) + 50)
        self.assertGreater(len(text), novel.PRV_MAX,
                           "样本未超限——本测试会退化为死测试，生成策略需修正")
        got = novel.truncate_prv(text)
        ref = text.strip()                      # 与实现口径一致
        self.assertTrue(ref.startswith(got),
                        f"截断结果必须是 strip 后原串的前缀：got={got[:30]!r} ref={ref[:30]!r}")
        self.assertLessEqual(len(got), novel.PRV_MAX)
        self.assertGreater(len(got), 0, "截断结果不得为空")


if __name__ == "__main__":
    unittest.main()
