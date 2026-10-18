#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""属性测试 · txt_prep.py（dev 侧，不进发布包、不进 MANIFEST）

对症的已修 bug：**非 UTF-8 文本读取崩溃**。
原文 txt 来源极杂（简体 GB18030 / 繁体 Big5 / UTF-16 / 带 BOM / 半截文件被截断 /
混入二进制垃圾），任何一类字节序列都不该让 `detect_read` 抛异常——
这是「原著智能读取」入口的第一道关。

断言的性质（不是「某个样例能过」，而是「任意字节都能过」）：
  1. 任意字节串 → detect_read 必须返回 (str, 编码标签)，绝不抛异常；
  2. 返回的编码标签必须落在已知白名单内（下游要按标签写进 book_map.json）；
  3. 能完整解码的合法编码文本，必须被原样读出（不得丢字、不得换字符）；
  4. 任意文本 → build_index 必须产出可 JSON 序列化的索引，且章号/行号自洽；
  5. 任意文本 → find_marks/line_starts/line_of 的偏移与行号映射自洽。

运行：python3 -m unittest discover -s tests -p "test_*.py" -v
"""
import json
import os
import sys
import tempfile
import unittest

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
sys.path.insert(0, SCRIPTS)

import txt_prep as tp  # noqa: E402

FAST = settings(max_examples=200, deadline=None,
                suppress_health_check=[HealthCheck.too_slow])

# detect_read 允许出现的编码标签（下游 book_map.json 会写入该字段）
KNOWN_LABELS = {"utf-8-sig", "utf-16", "utf-8", "gb18030", "utf-8(replace)"}

# 文本策略：避开孤立代理区字符（Python 字符串层面非法），其余全放开，含换行与章节标记
TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=400)


def write_bytes(data: bytes) -> str:
    """把原始字节落盘，返回路径（调用方负责清理临时目录）。"""
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    return path


class TestDetectReadNeverCrashes(unittest.TestCase):
    """bug 3 防线：任意字节序列都不得让编码探测抛异常。"""

    @FAST
    @given(data=st.binary(max_size=600))
    def test_any_bytes_survives(self, data: bytes):
        """任意字节（含半截多字节序列、二进制垃圾）都必须安全返回。"""
        path = write_bytes(data)
        try:
            text, label = tp.detect_read(path)
        except SystemExit as e:                      # die() 路径只允许留给「文件打不开」
            self.fail(f"detect_read 对字节序列意外退出（code={e.code}）")
        except UnicodeDecodeError as e:
            self.fail(f"detect_read 抛 UnicodeDecodeError（未兜底）：{e}｜data={data[:60]!r}")
        except Exception as e:                       # noqa: BLE001 —— 属性测试要抓住一切异常
            self.fail(f"detect_read 抛未预期异常 {type(e).__name__}: {e}｜data={data[:60]!r}")
        else:
            self.assertIsInstance(text, str)
            self.assertIn(label, KNOWN_LABELS,
                          f"编码标签 {label!r} 不在白名单 {sorted(KNOWN_LABELS)}")
        finally:
            os.unlink(path)

    @FAST
    @given(text=st.text(alphabet=st.characters(blacklist_categories=("Cs",)),
                        min_size=40, max_size=400),
           enc=st.sampled_from(["utf-8", "utf-8-sig", "utf-16"]))
    def test_roundtrip_preserves_text_unambiguous(self, text: str, enc: str):
        """无 BOM 歧义的编码：读回必须一字不差。"""
        try:
            data = text.encode(enc)
        except UnicodeEncodeError:
            self.skipTest(f"{enc} 无法表示该文本")
        path = write_bytes(data)
        try:
            got, label = tp.detect_read(path)
        finally:
            os.unlink(path)
        self.assertEqual(got, text, f"{enc} 读回内容不一致（label={label}）")

    @FAST
    @given(text=st.text(alphabet=st.characters(blacklist_categories=("Cs",)),
                        min_size=40, max_size=400))
    def test_roundtrip_gb18030_realistic_length(self, text: str):
        """GB18030 文本在**真实长度**下必须读回原样。

        为什么加长度下限：GB18030 双字节汉字里约 7.4% 的字节对**恰好也是合法
        UTF-8**（如 '十' = CA AE → 'ʮ'）。纯字节探测无法区分，只有在
        「整个文件的每个字节都恰好是合法 UTF-8」时才会误判——该概率随长度
        指数衰减（0.074^N；N=40 时约 1e-46），而真实原著 txt 都是几十 KB 起。
        单字/极短样本的歧义是启发式的固有边界，见 test_short_gb18030_ambiguity_is_known_limit。
        """
        try:
            data = text.encode("gb18030")
        except UnicodeEncodeError:
            self.skipTest("gb18030 无法表示该文本")
        path = write_bytes(data)
        try:
            got, label = tp.detect_read(path)
        finally:
            os.unlink(path)
        self.assertEqual(got, text, f"gb18030 读回内容不一致（label={label}）")

    def test_short_gb18030_ambiguity_is_known_limit(self):
        """固化已知边界：极短 GB18030 文本可能被判定为 UTF-8。

        本用例不判「对错」，而是**把这个边界钉住**：一旦有人改进探测算法
        （如引入 CJK 占比打分），本用例会失败并提醒同步更新文档口径。
        """
        path = write_bytes("十".encode("gb18030"))
        try:
            got, label = tp.detect_read(path)
        finally:
            os.unlink(path)
        # 当前实现：UTF-8 优先 → 单字 '十' 被读作 'ʮ'
        self.assertEqual(got, "ʮ",
                         "极短样本的探测行为已变化——若探测算法升级，请同步更新本节文档说明")
        self.assertEqual(label, "utf-8")

    @FAST
    @given(prefix=st.binary(min_size=1, max_size=8))
    def test_truncated_multibyte_does_not_crash(self, prefix: bytes):
        """半截 UTF-8/UTF-16 序列（文件被截断的典型形态）不得崩溃。"""
        for tail in (b"\xe4\xb8", b"\xe4", b"\xff\xfe\x41", b"\xef\xbb"):
            path = write_bytes(prefix + tail)
            try:
                text, label = tp.detect_read(path)
                self.assertIn(label, KNOWN_LABELS)
                self.assertIsInstance(text, str)
            except SystemExit:
                self.fail("detect_read 对截断序列意外退出")
            finally:
                os.unlink(path)


class TestIndexProperties(unittest.TestCase):
    """索引不变量：可序列化、章号自洽、偏移与行号映射自洽。"""

    @FAST
    @given(text=TEXT)
    def test_build_index_serializable(self, text: str):
        path = write_bytes(text.encode("utf-8"))
        try:
            book = tp.build_index(path, text, "utf-8")
            json.dumps(book, ensure_ascii=False)   # 下游要写 book_map.json
        finally:
            os.unlink(path)
        self.assertIsInstance(book["chapters"], list)
        self.assertEqual(book["chars"], len(text))
        for i, ch in enumerate(book["chapters"], start=1):
            self.assertEqual(ch["idx"], i, "章序号应为连续 1..N")
            self.assertLessEqual(ch["start_line"], ch["end_line"],
                                 f"第{i}章起止行倒挂")
            self.assertGreaterEqual(ch["chars"], 0)
            if i > 1:
                prev = book["chapters"][i - 2]
                self.assertLessEqual(prev["start_line"], ch["start_line"],
                                     "章起始行应单调不减")

    @FAST
    @given(text=TEXT)
    def test_line_starts_and_line_of_consistent(self, text: str):
        starts = tp.line_starts(text)
        self.assertEqual(starts[0], 0, "首行偏移应为 0")
        self.assertEqual(len(starts), len(text.split("\n")) + 1)
        # 每个偏移落在 [0, len(text)] 内时，行号必须落在合法区间
        for pos in range(0, len(text) + 1, max(1, len(text) // 26 or 1)):
            ln = tp.line_of(starts, pos)
            self.assertGreaterEqual(ln, 1)
            self.assertLessEqual(ln, len(text.split("\n")),
                                 f"pos={pos} 推出行号 {ln} 超出总行数")

    @FAST
    @given(text=TEXT)
    def test_marks_within_text_bounds(self, text: str):
        chapters, volumes, starts = tp.find_marks(text)
        for mk in chapters + volumes:
            self.assertGreaterEqual(mk["pos"], 0)
            self.assertLessEqual(mk["pos"], len(text), "标记偏移越界")
            self.assertGreaterEqual(mk["line"], 1)
            self.assertTrue(mk["title"], "标记标题不应为空")

    @FAST
    @given(blocks=st.integers(min_value=1, max_value=4),
           filler=st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc")),
                          min_size=1, max_size=tp.BLOCK_CHARS * 4))
    def test_fallback_blocks_cover_text(self, blocks, filler):
        """无章节标记时，兜底切块必须覆盖全文（不得有正文落在块之外）。"""
        text = filler * blocks
        starts = tp.line_starts(text)
        got = tp.fallback_blocks(text, starts)
        if not text:
            return
        self.assertTrue(got, "非空文本应有兜底块")
        self.assertEqual(got[0]["pos"], 0, "首块须从 0 开始")
        for i, b in enumerate(got, start=1):
            self.assertEqual(b["title"], f"块{i}")
        if len(got) > 1:
            for a, b in zip(got, got[1:]):
                self.assertLess(a["pos"], b["pos"], "块偏移应严格递增")
        # 末块起点须小于文本长度，保证尾部正文被覆盖
        self.assertLess(got[-1]["pos"], len(text) or 1)


class TestCnNumProperties(unittest.TestCase):
    """中文数字解析：不得抛异常；能解析出的值必须与阿拉伯数字一致。"""

    @FAST
    @given(n=st.integers(min_value=0, max_value=9999))
    def test_arabic_digits_parse_to_self(self, n: int):
        self.assertEqual(tp.cn_num(str(n)), n)

    @FAST
    @given(s=st.text(max_size=8))
    def test_any_input_is_safe(self, s: str):
        """任意文本输入都不得让 cn_num 抛异常（章节标题千奇百怪）。"""
        try:
            got = tp.cn_num(s)
        except Exception as e:                       # noqa: BLE001
            self.fail(f"cn_num({s!r}) 抛 {type(e).__name__}: {e}")
        self.assertTrue(got is None or isinstance(got, int),
                        f"cn_num 应返回 int 或 None，实际 {type(got).__name__}")


if __name__ == "__main__":
    unittest.main()
