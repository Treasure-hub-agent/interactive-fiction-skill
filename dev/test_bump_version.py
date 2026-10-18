#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""bump_version 边界测试（dev 侧，纯标准库）

为什么必须测：版本号替换是**不可逆的发布动作**，一旦误伤（如把 `10.2.10`
改成 `10.3.00`、或把正文里的数字改掉），会把错误版本号带进 tag / npm / Release。
本文件把「只替换真正的版本号出现」这一性质钉死。

运行：python3 -m unittest discover -s dev -p "test_*.py" -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bump_version as B  # noqa: E402


class TestReplaceVersionNumber(unittest.TestCase):
    def test_common_forms_are_replaced(self):
        cases = [
            "version-10.2.1-orange.svg",
            "v10.2.1 原著 txt 智能读取",
            '"version": "10.2.1"',
            "10.2.1",
            "## 当前版本：10.2.1",
        ]
        for text in cases:
            out, n = B.replace_version_number(text, "10.2.1", "10.3.0")
            self.assertEqual(n, 1, f"{text!r} 应替换 1 处")
            self.assertIn("10.3.0", out)

    def test_does_not_touch_longer_version(self):
        """10.2.10 / 110.2.1 不得被前缀命中（否则版本号会被改坏）。"""
        for text in ["10.2.10 不应被改", "v110.2.1x", "10.2.11", "9.10.2.1"]:
            out, n = B.replace_version_number(text, "10.2.1", "10.3.0")
            self.assertEqual(n, 0, f"{text!r} 不应被替换，实际 {n} 处 → {out!r}")

    def test_replaces_all_occurrences(self):
        text = "a v10.2.1 b 10.2.1-orange c 10.2.1"
        out, n = B.replace_version_number(text, "10.2.1", "10.3.0")
        self.assertEqual(n, 3)
        self.assertNotIn("10.2.1", out)

    def test_idempotent_on_new_version(self):
        """已是目标版本时不得再改（防重复 bump 改坏）。"""
        out, n = B.replace_version_number("v10.3.0 ok", "10.3.0", "10.3.0")
        self.assertEqual(n, 1)   # 自身仍会匹配，但内容不变
        self.assertEqual(out, "v10.3.0 ok")


class TestAutoTargetsSafety(unittest.TestCase):
    def test_targets_are_text_files_only(self):
        """自动替换列表里不得出现二进制（如 assets/*.png）。"""
        for rel, _desc in B.AUTO_TARGETS:
            self.assertTrue(rel.endswith((".md", ".json")) or rel == "VERSION",
                            f"{rel} 不是可安全替换的文本文件")

    def test_manual_hints_cover_semantic_locations(self):
        """带语义的位置必须在人工清单里（否则会被静默改坏）。"""
        rels = {rel for rel, _rx, _d in B.MANUAL_HINTS}
        for expect in ("README.md", "README.en.md", "CHANGELOG.md"):
            self.assertIn(expect, rels, f"{expect} 的语义段落须纳入人工清单")

    def test_no_overlap_between_auto_and_manual_files(self):
        """同一文件可同时出现在两清单（README 有自动段 + 人工段），
        但人工清单的正则不得匹配纯版本号行，否则会与自动替换冲突。"""
        for rel, rx, _d in B.MANUAL_HINTS:
            if rel in {r for r, _ in B.AUTO_TARGETS}:
                for sample in ["10.2.1", '"version": "10.2.1"', "version-10.2.1-orange.svg"]:
                    self.assertIsNone(rx.search(sample),
                                      f"{rel} 的人工正则误匹配纯版本号 {sample!r}")


class TestCurrentVersionReadable(unittest.TestCase):
    def test_reads_repo_version(self):
        v = B.read_current()
        self.assertRegex(v, r"^\d+\.\d+\.\d+$", f"VERSION 内容异常：{v!r}")


if __name__ == "__main__":
    unittest.main()
