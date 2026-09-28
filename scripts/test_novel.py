#!/usr/bin/env python3
"""test_novel.py — 记忆外置助手 novel.py 单元测试（v10.2.0 新增）。

覆盖：简报四级权重与衰减边界、到期后果提醒与回收、record 自动簿记、
章摘要滚动入卷、存档/读档回填、前情提要截断、_index 同步、参数与错误路径。

用法：
    python3 -m unittest scripts.test_novel -v
或：
    python3 scripts/test_novel.py
"""
import argparse
import contextlib
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_novel():
    spec = importlib.util.spec_from_file_location(
        "novel", os.path.join(ROOT, "scripts", "novel.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


novel = _load_novel()


def capture(func, *args, **kwargs):
    """执行会 print 的命令函数并返回其输出。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        func(*args, **kwargs)
    return buf.getvalue()


def section(text, tag):
    """取简报中某一段（`[标签]` 到下一个 `[标签]` 之间）的内容。"""
    return text.split(tag, 1)[1].split("\n[", 1)[0]


class Base(unittest.TestCase):
    """公共夹具：临时存储根 + 一部开局小说。"""

    NAME = "《测试样本》"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="novel-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.meta = os.path.join(self.tmp, self.NAME, "meta")
        os.makedirs(self.meta)
        self.runtime = {
            "v": "10.2.0", "ua": "2026-09-28T00:00:00+08:00", "nm": self.NAME,
            "rn": "自创角色", "md": "爽文模式", "vw": 3, "ch": 1,
            "sc": "场景·起点", "wc": 1000, "mp": "区域·起点", "dv": None,
            "cc": "核心冲突", "sb": [], "kp": [], "pf": [], "rs": {}, "cp": {},
            "scs": {}, "npcs": {}, "choices": [], "st": {}, "theme": None,
            "prv": "起点前情。", "ex": 0, "eb": 0, "seg_count": 0, "ms": 0,
            "scs_bak": None,
        }
        self._flush()
        self.write_index()

    # ---------- 夹具写入 ----------
    def _flush(self):
        with open(os.path.join(self.meta, "novel_runtime.json"), "w",
                  encoding="utf-8") as f:
            json.dump(self.runtime, f, ensure_ascii=False, indent=2)

    def write_index(self, act=True):
        idx = {"act": self.NAME if act else None,
               "nvs": [{"n": self.NAME, "r": "自创角色",
                        "u": self.runtime["ua"], "c": self.runtime["wc"]}]}
        with open(os.path.join(self.tmp, "_index.json"), "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)

    def write_assist(self, turn, notes=None, changes=None, closed=None):
        data = {"turn": turn, "notes": notes or [], "changes": changes or [],
                "closed_choices": closed or []}
        with open(os.path.join(self.meta, "novel_assist.json"), "w",
                  encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---------- 命令调用 ----------
    def brief(self, full=False):
        return capture(novel.cmd_brief, argparse.Namespace(
            root=self.tmp, novel=self.NAME, full=full))

    def record(self, entry):
        return capture(novel.cmd_record, argparse.Namespace(
            root=self.tmp, novel=self.NAME, entry=None,
            json=json.dumps(entry, ensure_ascii=False)))

    def save(self, note=None):
        return capture(novel.cmd_save, argparse.Namespace(
            root=self.tmp, novel=self.NAME, note=note))

    def load(self, num=None, latest=False):
        return capture(novel.cmd_load, argparse.Namespace(
            root=self.tmp, novel=self.NAME, num=num, latest=latest))

    def read_runtime(self):
        with open(os.path.join(self.meta, "novel_runtime.json"), encoding="utf-8") as f:
            return json.load(f)

    def read_assist(self):
        with open(os.path.join(self.meta, "novel_assist.json"), encoding="utf-8") as f:
            return json.load(f)

    def read_index(self):
        with open(os.path.join(self.tmp, "_index.json"), encoding="utf-8") as f:
            return json.load(f)


class TestHelpers(Base):
    def test_truncate_short_text_untouched(self):
        self.assertEqual(novel.truncate_prv(" 一句话。 "), "一句话。")

    def test_truncate_to_last_sentence(self):
        out = novel.truncate_prv("甲" * 50 + "。" + "乙" * 300)
        self.assertEqual(out, "甲" * 50 + "。")

    def test_truncate_hard_cut_without_punctuation(self):
        self.assertEqual(len(novel.truncate_prv("甲" * 300)), 200)

    def test_set_path_nested(self):
        obj = {}
        novel.set_path(obj, "st.位置", "渡口")
        self.assertEqual(obj, {"st": {"位置": "渡口"}})


class TestBrief(Base):
    def test_section_layout_complete(self):
        out = self.brief()
        for tag in ("[前情]", "[行动]", "[事实]", "[变化]", "[背景]",
                    "[关系]", "[伏笔]", "[提示]"):
            self.assertIn(tag, out)

    def test_anchor_hook_only_on_seg_multiple_of_8(self):
        self.runtime["seg_count"] = 22
        self._flush()
        self.assertNotIn("命中锚定钩子", self.brief())
        self.runtime["seg_count"] = 23
        self._flush()
        self.assertIn("命中锚定钩子", self.brief())

    def test_change_window_covers_two_turns(self):
        """[变化] 覆盖 d ≤ 2，且与 [背景]（d ≥ 3）无缝衔接。"""
        self.write_assist(turn=3, changes=[
            {"turn": 1, "text": "第一轮变更"},
            {"turn": 2, "text": "第二轮变更"},
            {"turn": 3, "text": "第三轮变更"},
        ])
        body = section(self.brief(), "[变化]")
        self.assertIn("第二轮变更", body)
        self.assertIn("第三轮变更", body)
        self.assertIn("第一轮变更", body)   # d = 2，仍在窗口内

    def test_change_window_drops_old_entries(self):
        self.write_assist(turn=4, changes=[{"turn": 1, "text": "陈年变更"}])
        self.assertNotIn("陈年变更", section(self.brief(), "[变化]"))

    def test_note_decay_chain(self):
        """背景项：d ≤ 2 不显示 → 3 ≤ d ≤ 6 显示一行 → d > 6 静默。"""
        note = [{"text": "主角右臂轻伤", "turn": 1}]
        for turn, shown in ((3, False), (4, True), (7, True), (8, False)):
            self.write_assist(turn=turn, notes=note)
            out = self.brief()
            seg = section(out, "[背景]")
            self.assertEqual("主角右臂轻伤" in seg, shown,
                             f"turn={turn} 时 [背景] 显示应为 {shown}")

    def test_silent_note_recoverable_with_full(self):
        self.write_assist(turn=8, notes=[{"text": "主角右臂轻伤", "turn": 1}])
        self.assertIn("主角右臂轻伤", self.brief(full=True))

    def test_due_choice_flagged_and_ahead_window(self):
        self.runtime["choices"] = [{
            "seg": 17, "picked": "B", "tag": "周旋", "type": "consequence",
            "detail": "本地势力记恨", "tier": "短期", "surface_by": 19,
            "foreclosed": ["A", "C"]}]
        self.runtime["seg_count"] = 17
        self._flush()
        self.assertIn("seg19 前后呼应", section(self.brief(), "[行动]"))
        self.runtime["seg_count"] = 19
        self._flush()
        self.assertIn("本轮到期", section(self.brief(), "[行动]"))
        self.runtime["seg_count"] = 23       # 逾期 4 段
        self._flush()
        self.assertIn("逾期", section(self.brief(), "[行动]"))

    def test_closed_choice_no_longer_shown(self):
        self.runtime["choices"] = [{
            "seg": 17, "picked": "B", "tag": "周旋", "type": "consequence",
            "detail": "本地势力记恨", "tier": "短期", "surface_by": 19,
            "foreclosed": []}]
        self.runtime["seg_count"] = 20
        self._flush()
        self.write_assist(turn=5, closed=[17])
        self.assertNotIn("本地势力记恨", self.brief())

    def test_foreshadow_listed(self):
        self.runtime["pf"] = [{"k": "卷宗下落", "s": "active", "ch": 1},
                              {"k": "已搁置线索", "s": "dropped", "ch": 2}]
        self._flush()
        body = section(self.brief(), "[伏笔]")
        self.assertIn("卷宗下落", body)
        self.assertNotIn("已搁置线索", body)


class TestRecord(Base):
    def test_accumulates_wordcount_seg_and_turn(self):
        self.record({"w": 800, "seg": 1})
        self.record({"w": 900, "seg": 2})
        rt, ast = self.read_runtime(), self.read_assist()
        self.assertEqual(rt["wc"], 2700)
        self.assertEqual(rt["seg_count"], 3)
        self.assertEqual(ast["turn"], 2)

    def test_set_uses_dotted_path(self):
        self.record({"set": {"st.位置": "渡口", "ch": 2}})
        rt = self.read_runtime()
        self.assertEqual(rt["st"]["位置"], "渡口")
        self.assertEqual(rt["ch"], 2)

    def test_add_deduplicates(self):
        self.record({"add": {"kp": ["决策一"]}})
        self.record({"add": {"kp": ["决策一", "决策二"]}})
        self.assertEqual(self.read_runtime()["kp"], ["决策一", "决策二"])

    def test_prv_truncated_on_record(self):
        self.record({"prv": "甲" * 50 + "。" + "乙" * 300})
        rt = self.read_runtime()
        self.assertEqual(rt["prv"], "甲" * 50 + "。")

    def test_index_synced(self):
        self.record({"w": 500, "set": {"rn": "创世模式"}})
        idx = self.read_index()
        self.assertEqual(idx["act"], self.NAME)
        self.assertEqual(idx["nvs"][0]["c"], 1500)
        self.assertEqual(idx["nvs"][0]["r"], "创世模式")

    def test_bak_written_before_overwrite(self):
        self.record({"w": 100})
        self.assertTrue(os.path.isfile(
            os.path.join(self.meta, "novel_runtime.json.bak")))

    def test_notes_registered_and_resolved(self):
        self.record({"notes": ["客栈落了脚"]})
        self.assertEqual(self.read_assist()["notes"][0]["text"], "客栈落了脚")
        self.record({"resolve_notes": ["落了脚"]})
        self.assertEqual(self.read_assist()["notes"], [])

    def test_close_choices_marked(self):
        self.record({"close_choices": [17, 20]})
        self.assertEqual(self.read_assist()["closed_choices"], [17, 20])

    def test_chapter_summary_rolls_into_volumes(self):
        self.record({"chapter_summary": {"summary": "第一章概要", "ch": 1}})
        self.record({"chapter_summary": {"summary": "第二章概要", "ch": 2}})
        rt = self.read_runtime()
        self.assertEqual(rt["chapter_summary"]["summary"], "第二章概要")
        self.assertEqual(rt["volumes"][0]["summary"], "第一章概要")
        self.assertEqual(rt["volumes"][0]["ch_end"], 1)

    def test_change_log_recorded(self):
        self.record({"w": 300, "set": {"sc": "场景·新"}})
        self.assertIn("第1轮", self.brief())


class TestSaveLoad(Base):
    def test_save_lists_and_loads(self):
        self.record({"w": 800, "set": {"sc": "场景·存档点"}})
        out = self.save("渡口夜谈")
        self.assertIn("#1", out)
        self.assertIn("渡口夜谈", self.save())          # 无参数 = 列出存档
        before = self.read_runtime()

        self.record({"w": 200, "set": {"sc": "场景·之后"}})
        self.assertEqual(self.read_runtime()["sc"], "场景·之后")   # 已漂移

        out = self.load(num=1)
        after = self.read_runtime()
        self.assertIn("已读档 #1", out)
        self.assertEqual(after["sc"], before["sc"])
        self.assertEqual(after["wc"], before["wc"])
        self.assertEqual(after["seg_count"], before["seg_count"])

    def test_load_latest_alias(self):
        self.record({"w": 100})
        self.save("第一次")
        self.record({"w": 100})
        self.save("第二次")
        self.assertIn("已读档 #2", self.load(latest=True))

    def test_save_split_by_route(self):
        self.runtime["rn"] = "穿越成原著角色"
        self._flush()
        self.save("穿越线存档")
        self.assertTrue(os.path.isdir(
            os.path.join(self.tmp, self.NAME, "saves", "穿越")))


class TestErrorPaths(Base):
    def test_missing_novel_dir_exits(self):
        with self.assertRaises(SystemExit):
            capture(novel.cmd_brief, argparse.Namespace(
                root=self.tmp, novel="《不存在的书》", full=False))

    def test_no_active_novel_exits(self):
        self.write_index(act=False)
        with self.assertRaises(SystemExit):
            capture(novel.cmd_brief, argparse.Namespace(
                root=self.tmp, novel=None, full=False))

    def test_load_missing_archive_exits(self):
        with self.assertRaises(SystemExit):
            self.load(num=9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
