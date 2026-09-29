#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
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
            "scs": {}, "npcs": {}, "choices": [], "st": {},
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
    def brief(self, full=False, user_input=None):
        return capture(novel.cmd_brief, argparse.Namespace(
            root=self.tmp, novel=self.NAME, full=full, input=user_input))

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


class TestRobustness(Base):
    """修复回归：崩溃路径 / 容错降级 / 类型归一 / 旧档兼容（v10.2.0）。"""

    def test_brief_survives_same_lag_due_choices(self):
        """两条到期后果 lag 相同时不得崩溃（原 sorted(due) 会 TypeError）。"""
        self.runtime["seg_count"] = 20
        self.runtime["choices"] = [
            {"seg": 17, "type": "consequence", "detail": "后果甲",
             "tier": "短期", "surface_by": 19},
            {"seg": 18, "type": "consequence", "detail": "后果乙",
             "tier": "短期", "surface_by": 19},
        ]
        self._flush()
        act = section(self.brief(), "[行动]")
        self.assertIn("后果甲", act)
        self.assertIn("后果乙", act)
        self.assertEqual(act.count("逾期 1 段"), 2)

    def test_brief_survives_broken_assist(self):
        """侧车损坏时重置空侧车并继续（原硬 die 会阻断 brief/record/save）。"""
        with open(os.path.join(self.meta, "novel_assist.json"), "w",
                  encoding="utf-8") as f:
            f.write("{ bad json")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            out = self.brief()
        self.assertIn("[行动]", out)
        self.assertIn("内容损坏", err.getvalue())

    def test_record_notes_string_stays_single_entry(self):
        """notes 传字符串时作为单条背景登记，不逐字拆分。"""
        self.write_assist(turn=0)
        self.record({"notes": "客栈落了脚"})
        notes = self.read_assist()["notes"]
        self.assertEqual([n["text"] for n in notes], ["客栈落了脚"])

    def test_record_notes_accepts_object_and_empty(self):
        """notes 支持对象写法；空串/空对象被忽略。"""
        self.write_assist(turn=0)
        self.record({"notes": [{"text": "对象写法"}, {"t": "简写"}, "", {}]})
        notes = [n["text"] for n in self.read_assist()["notes"]]
        self.assertEqual(notes, ["对象写法", "简写"])

    def test_record_close_choices_string_seg_truly_closes(self):
        """close_choices 传字符串 seg 须归一为 int 并真正回收（原为假成功）。"""
        self.runtime["seg_count"] = 20
        self.runtime["choices"] = [
            {"seg": 17, "type": "consequence", "detail": "待回收条目",
             "tier": "短期", "surface_by": 19}]
        self._flush()
        self.write_assist(turn=1)
        out = self.record({"close_choices": ["17"]})
        self.assertIn("账本 seg17 已回收", out)
        self.assertEqual(self.read_assist()["closed_choices"], [17])
        self.assertNotIn("待回收条目", section(self.brief(), "[行动]"))

    def test_record_close_choices_unknown_seg_warns(self):
        """回收标记的 seg 在账本中不存在时须明确提示，不得静默假成功。"""
        self.write_assist(turn=1)
        out = self.record({"close_choices": [99]})
        self.assertIn("无此条目", out)

    def test_legacy_ledger_without_seg_count_still_due(self):
        """v9.x 旧档无 seg_count 时 [行动] 仍须判定到期（原整段静默消失）。"""
        self.runtime.pop("seg_count")
        self.runtime["choices"] = [
            {"seg": 9, "type": "consequence", "detail": "旧档后果",
             "tier": "短期", "surface_by": 9}]
        self._flush()
        self.write_assist(turn=1)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            act = section(self.brief(), "[行动]")
        self.assertIn("旧档后果", act)
        self.assertIn("无 seg_count", err.getvalue())

    def test_legacy_ledger_seg_count_backfilled_on_record(self):
        """旧档首次 record 以账本最大 seg 回填基准，再累加本轮增量。"""
        self.runtime.pop("seg_count")
        self.runtime["choices"] = [{"seg": 30, "type": "consequence",
                                    "detail": "x", "tier": "短期",
                                    "surface_by": 40}]
        self._flush()
        self.write_assist(turn=1)
        self.record({"seg": 1})
        self.assertEqual(self.read_runtime()["seg_count"], 31)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0,
                     "root 下目录权限不生效")
    def test_index_write_failure_does_not_fail_record(self):
        """索引写失败（派生数据）不得让记账失败 —— 否则调用方重试会字数双计。"""
        self.write_assist(turn=0)
        os.chmod(self.tmp, 0o555)
        self.addCleanup(os.chmod, self.tmp, 0o755)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            out = self.record({"w": 100})
        os.chmod(self.tmp, 0o755)
        self.assertIn("已记账", out)
        self.assertIn("写入失败", err.getvalue())
        self.assertEqual(self.read_runtime()["wc"], 1100)

    def test_save_files_accepts_prefixed_name(self):
        """存档文件名容忍非数字前缀（随机开局 🎲001.md），不得被读档链路跳过。"""
        d = os.path.join(self.tmp, self.NAME, "saves", "自创")
        os.makedirs(d)
        with open(os.path.join(d, "🎲001.md"), "w", encoding="utf-8") as f:
            f.write("#存档 1\n>骰子开局\n")
        out = self.save()
        self.assertIn("#1", out)
        self.assertIn("骰子开局", out)
        self.save("后续存档")
        self.assertTrue(os.path.isfile(os.path.join(d, "002.md")))


class TestLore(Base):
    """设定检索（世界书式按需注入）：命中 / 上限 / 摘要 / 降级 / 只读。"""

    def _write_lore(self):
        wb = os.path.join(self.tmp, self.NAME, "worldbuilding")
        os.makedirs(wb, exist_ok=True)
        with open(os.path.join(wb, "power_system.md"), "w", encoding="utf-8") as f:
            f.write("# 力量体系\n## 灵纹\n灵纹分九品，三品以上方可御物。\n")
        with open(os.path.join(wb, "geography.md"), "w", encoding="utf-8") as f:
            f.write("# 地理\n## 边城\n边城是北境咽喉。\n")
        ch = os.path.join(self.tmp, self.NAME, "characters", "linxiaoman")
        os.makedirs(ch, exist_ok=True)
        with open(os.path.join(ch, "profile.md"), "w", encoding="utf-8") as f:
            f.write("# 林小满\n## 身份\n边城驿站的掌事，表面冷淡实则护短。\n")

    def test_lore_section_absent_when_no_hit(self):
        """无设定目录时不得出现 [设定] 段（零回归）。"""
        self._write_lore()
        out = self.brief(user_input="完全无关的一句话")
        self.assertNotIn("\n[设定]", out)

    def test_lore_hits_on_user_input(self):
        """用户输入命中词条时必须带出该词条与其摘要。"""
        self._write_lore()
        out = self.brief(user_input="我催动灵纹去御剑")
        self.assertIn("[设定]", out)
        self.assertIn("灵纹", out)
        self.assertIn("三品以上方可御物", out)

    def test_lore_hits_on_scene(self):
        """未传 --input 时按当前场景命中。"""
        self._write_lore()
        self.runtime["sc"] = "边城·渡口"
        self._flush()
        out = self.brief()
        self.assertIn("[设定]", out)
        self.assertIn("边城是北境咽喉", out)

    def test_lore_limit_and_full(self):
        """默认每轮最多 4 条，--full 放开上限。"""
        self._write_lore()
        q = "灵纹 御物 边城 渡口 北境 林小满 身份"
        n_def = self.brief(user_input=q).split("[设定]")[1].split("\n[")[0].count("  · ")
        n_full = self.brief(full=True, user_input=q).split("[设定]")[1].split("\n[")[0].count("  · ")
        self.assertLessEqual(n_def, 4)
        self.assertGreaterEqual(n_full, n_def)

    def test_lore_summary_skips_subheading(self):
        """摘要须取正文首句，不得取下一级标题（如「身份」）。"""
        self._write_lore()
        out = self.brief(user_input="林小满")
        self.assertIn("边城驿站的掌事", out)
        self.assertNotIn("林小满 — 身份", out)

    def test_lore_survives_broken_non_utf8_file(self):
        """非 UTF-8 的损坏设定文件必须被跳过，不得让 brief 崩溃。"""
        self._write_lore()
        with open(os.path.join(self.tmp, self.NAME, "worldbuilding", "broken.md"),
                  "wb") as f:
            f.write(b"\x00\x01 not utf8 \xff\xfe")
        out = self.brief(user_input="灵纹")
        self.assertIn("灵纹", out)

    def test_lore_is_readonly(self):
        """brief 必须纯只读：设定文件内容不得被改写。"""
        self._write_lore()
        path = os.path.join(self.tmp, self.NAME, "worldbuilding", "power_system.md")
        before = open(path, "rb").read()
        self.brief(user_input="灵纹")
        self.assertEqual(open(path, "rb").read(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
