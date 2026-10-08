#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""test_txt_prep.py — 原著预处理助手 txt_prep.py 单元测试（v10.3.0 新增）。

覆盖：编码探测（UTF-8/BOM/GB18030/UTF-16）、章节与卷切分（章/节/回/Chapter）、
无标记兜底切块、角色候选（非贪婪修正 + 停用词过滤）、设定密度章榜、
scan 幂等与接入卡格式、slice 三种定位（章节/行范围/关键词）、截断、
索引缺失时现场重扫、错误路径。

用法：
    python3 -m unittest scripts.test_txt_prep -v
或：
    python3 scripts/test_txt_prep.py
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    spec = importlib.util.spec_from_file_location(
        "txt_prep", os.path.join(ROOT, "scripts", "txt_prep.py"))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tp = _load()

NAMES = ["林战", "苏瑶", "赵铁柱", "钱多多", "孙长老", "周管事", "吴天"]


def make_text(chapters=12, volumes=True):
    parts = ["《示例长篇》\n\n作者：某某\n\n内容简介：用于单元测试的合成文本。\n"]
    for i in range(1, chapters + 1):
        if volumes and i == 6:
            parts.append("第二卷 风起云涌\n")
        head = f"第{i}章 试炼之路{i}" if i % 3 else f"第{_cn(i)}章 转章{i}"
        body = (
            f"清晨，灵气翻涌。林战盘膝而坐，修为又进一层，境界稳固。\n"
            f"“{NAMES[i % 7]}，你可知道这方大陆的宗门规矩？”林战说道。\n"
            f"{NAMES[(i + 1) % 7]}笑道：“自然是知道的。功法等级分九品，灵石为王。”\n"
            f"{NAMES[(i + 2) % 7]}沉声道：“别大意，那位孙长老还在盯着我们。”\n"
            f"林战点头，抬眼望向远方。{NAMES[(i + 3) % 7]}问：“下一步去哪？”\n"
            f"{NAMES[(i + 4) % 7]}答道：“先去坊市换些灵石再说。”\n"
        )
        parts.append(head + "\n" + body + "\n")
    return "".join(parts)


def _cn(n):
    d = "零一二三四五六七八九"
    if n < 10:
        return d[n]
    if n < 20:
        return "十" + (d[n % 10] if n % 10 else "")
    return d[n // 10] + "十" + (d[n % 10] if n % 10 else "")


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="txtprep-")
        self.text = make_text()
        self.utf8 = os.path.join(self.dir, "示例长篇.txt")
        with open(self.utf8, "w", encoding="utf-8") as f:
            f.write(self.text)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_cli(self, argv):
        """执行 CLI，返回 (退出码, stdout, stderr)。"""
        out, err = io.StringIO(), io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                tp.main(argv)
            except SystemExit as e:
                code = e.code or 0
        return code, out.getvalue(), err.getvalue()


class TestEncoding(Base):
    def test_utf8(self):
        text, enc = tp.detect_read(self.utf8)
        self.assertEqual(text, self.text)
        self.assertEqual(enc, "utf-8")

    def test_utf8_bom(self):
        p = os.path.join(self.dir, "bom.txt")
        with open(p, "w", encoding="utf-8-sig") as f:
            f.write(self.text)
        text, enc = tp.detect_read(p)
        self.assertEqual(text, self.text)
        self.assertEqual(enc, "utf-8-sig")
        self.assertFalse(text.startswith("\ufeff"))

    def test_gbk(self):
        p = os.path.join(self.dir, "gbk.txt")
        with open(p, "w", encoding="gb18030") as f:
            f.write(self.text)
        text, enc = tp.detect_read(p)
        self.assertEqual(text, self.text)
        self.assertEqual(enc, "gb18030")

    def test_utf16_bom(self):
        p = os.path.join(self.dir, "u16.txt")
        with open(p, "w", encoding="utf-16") as f:
            f.write(self.text)
        text, enc = tp.detect_read(p)
        self.assertEqual(text, self.text)
        self.assertEqual(enc, "utf-16")

    def test_missing_file(self):
        code, _, err = self.run_cli(["scan", os.path.join(self.dir, "无.txt")])
        self.assertEqual(code, 1)
        self.assertIn("原文不存在", err)


class TestCnNum(unittest.TestCase):
    def test_values(self):
        for s, want in [("1", 1), ("12", 12), ("一", 1), ("十", 10), ("十二", 12),
                        ("二十三", 23), ("一百零五", 105), ("一千二百", 1200),
                        ("两", 2)]:
            self.assertEqual(tp.cn_num(s), want, s)

    def test_invalid(self):
        self.assertIsNone(tp.cn_num("abc"))
        self.assertIsNone(tp.cn_num(""))


class TestChapterSplit(Base):
    def test_counts_and_numbers(self):
        book = tp.build_index(self.utf8, self.text, "utf-8")
        self.assertFalse(book["fallback_blocks"])
        self.assertEqual(len(book["chapters"]), 12)
        self.assertEqual(len(book["volumes"]), 1)
        self.assertEqual(book["volumes"][0]["title"], "第二卷 风起云涌")
        nos = [c["no"] for c in book["chapters"]]
        self.assertEqual(nos[0], 1)
        self.assertEqual(nos[2], 3)        # 第3章 转章 → 中文数字
        # 行号单调递增且区间可闭合
        for prev, cur in zip(book["chapters"], book["chapters"][1:]):
            self.assertLess(prev["start_line"], cur["start_line"])
            self.assertLess(prev["end_line"], cur["start_line"])
        self.assertGreater(book["chapters"][0]["chars"], 0)

    def test_mixed_markers(self):
        text = ("第1节 开始\n内容。\nChapter 2 The Road\ncontent.\n"
                "第三回 归途\n内容。\n")
        book = tp.build_index("x.txt", text, "utf-8")
        self.assertEqual([c["no"] for c in book["chapters"]], [1, 2, 3])

    def test_fallback_blocks(self):
        text = "无章节标记的长文。" + "正文段落。" * 2000
        starts = tp.line_starts(text)
        blocks = tp.fallback_blocks(text, starts)
        self.assertGreater(len(blocks), 1)
        self.assertEqual(blocks[0]["title"], "块1")
        book = tp.build_index("y.txt", text, "utf-8")
        self.assertTrue(book["fallback_blocks"])
        self.assertTrue(all(c["no"] is None for c in book["chapters"]))

    def test_lore_top_present(self):
        book = tp.build_index(self.utf8, self.text, "utf-8")
        self.assertTrue(book["lore_top"])
        hits = [c["hits"] for c in book["lore_top"]]
        self.assertEqual(hits, sorted(hits, reverse=True))


class TestRoles(Base):
    def test_main_role_first_and_no_tail_verbs(self):
        book = tp.build_index(self.utf8, self.text, "utf-8")
        names = [r["name"] for r in book["roles"]]
        self.assertEqual(names[0], "林战")           # 主角命中次数最高
        for bad in ("林战说", "林战道", "周管事答", "吴天沉声"):
            self.assertNotIn(bad, names)
        self.assertGreaterEqual(len(names), 5)
        self.assertEqual(book["roles"][0]["first_ch"], 1)

    def test_stopwords_filtered(self):
        book = tp.build_index(self.utf8, self.text, "utf-8")
        for stop in tp.STOP_NAMES:
            self.assertNotIn(stop, [r["name"] for r in book["roles"]])


class TestScan(Base):
    def test_writes_index_and_card(self):
        code, out, _ = self.run_cli(["scan", self.utf8, "--out", self.dir])
        self.assertEqual(code, 0)
        self.assertIn("📖 已接入原著《示例长篇》", out)
        self.assertIn("角色候选：林战", out)
        idx = os.path.join(self.dir, tp.INDEX_NAME)
        toc = os.path.join(self.dir, tp.TOC_NAME)
        self.assertTrue(os.path.isfile(idx) and os.path.isfile(toc))
        book = json.load(open(idx, encoding="utf-8"))
        self.assertEqual(book["file"], "示例长篇.txt")
        self.assertEqual(len(book["chapters"]), 12)
        self.assertEqual(book["chars"], len(self.text))
        self.assertEqual(book["encoding"], "utf-8")
        with open(toc, encoding="utf-8") as f:
            body = f.read()
        self.assertIn("【第二卷 风起云涌】", body)
        self.assertIn("第十二章", body)          # 中文数字章节名原样保留

    def test_idempotent(self):
        self.run_cli(["scan", self.utf8, "--out", self.dir])
        p1 = open(os.path.join(self.dir, tp.INDEX_NAME), "rb").read()
        self.run_cli(["scan", self.utf8, "--out", self.dir])
        p2 = open(os.path.join(self.dir, tp.INDEX_NAME), "rb").read()
        self.assertEqual(p1, p2)

    def test_json_mode(self):
        _, out, _ = self.run_cli(["scan", self.utf8, "--out", self.dir, "--json"])
        book = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(book["generated_by"], "txt_prep.py")

    def test_gbk_scan_card(self):
        p = os.path.join(self.dir, "gbk原.txt")
        with open(p, "w", encoding="gb18030") as f:
            f.write(self.text)
        _, out, _ = self.run_cli(["scan", p, "--out", self.dir])
        self.assertIn("GB18030", out)


class TestSlice(Base):
    def test_by_chapter(self):
        code, out, _ = self.run_cli(["slice", self.utf8, "--ch", "3"])
        self.assertEqual(code, 0)
        self.assertIn("第三章", out)
        self.assertIn("转章3", out)
        self.assertIn("林战", out)

    def test_by_chapter_chinese_number(self):
        _, out, _ = self.run_cli(["slice", self.utf8, "--ch", "12"])
        self.assertIn("第十二章", out)

    def test_missing_chapter(self):
        code, _, err = self.run_cli(["slice", self.utf8, "--ch", "999"])
        self.assertEqual(code, 1)
        self.assertIn("不存在", err)

    def test_by_lines(self):
        _, out, _ = self.run_cli(["slice", self.utf8,
                                  "--from-line", "2", "--to-line", "4"])
        self.assertIn("行 2-4", out)
        self.assertIn("作者：某某", out)

    def test_grep_context_and_windows(self):
        _, out, _ = self.run_cli(["slice", self.utf8, "--grep", "孙长老",
                                  "-C", "2", "--windows", "1"])
        self.assertIn("命中", out)
        self.assertIn("孙长老", out)
        self.assertEqual(out.count("--- 行"), 1)

    def test_grep_picks_densest_window(self):
        # 稀疏命中在开头，密集命中在后段 → --windows 1 应取密集窗口
        text = ("第1章 稀疏\n" + "无关内容。\n" * 8 + "林战出现一次。\n"
                + "无关内容。\n" * 30
                + "第2章 密集\n" + ("林战在此。\n" * 6) + "无关内容。\n" * 5)
        p = os.path.join(self.dir, "dense.txt")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        _, out, _ = self.run_cli(["slice", p, "--grep", "林战",
                                  "-C", "2", "--windows", "1"])
        self.assertIn("（第2章 密集）", out)      # 章节标注取窗口内首个命中所在章
        self.assertNotIn("（第1章 稀疏）", out)
        self.assertIn("命中 6 处", out)

    def test_grep_miss(self):
        code, _, err = self.run_cli(["slice", self.utf8, "--grep", "不存在的词"])
        self.assertEqual(code, 1)
        self.assertIn("未命中", err)

    def test_truncation(self):
        _, out, err = self.run_cli(["slice", self.utf8, "--ch", "1",
                                    "--max-chars", "30"])
        self.assertIn("…（已截断）", out)
        self.assertIn("已截断至 30 字", err)

    def test_works_without_index(self):
        # 不跑 scan，直接 slice（索引缺失 → 现场重扫）
        self.assertFalse(os.path.isfile(os.path.join(self.dir, tp.INDEX_NAME)))
        code, out, _ = self.run_cli(["slice", self.utf8, "--ch", "1"])
        self.assertEqual(code, 0)
        self.assertIn("第1章", out)

    def test_uses_written_index(self):
        self.run_cli(["scan", self.utf8, "--out", self.dir])
        _, out, _ = self.run_cli(["slice", self.utf8, "--ch", "5"])
        self.assertIn("第 5 章", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
