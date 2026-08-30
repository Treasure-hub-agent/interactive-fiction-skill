#!/usr/bin/env python3
"""test_data.py — 数据文件约束单元测试（v10.1.0 新增）。

用法：
    python3 -m unittest scripts.test_data -v
或：
    python3 scripts/test_data.py
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACE = {"快", "慢", "迂回"}


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


class TestTags(unittest.TestCase):
    """tags.json：general 7 类 × 5 词 = 35 词去重；emotion 7 项去重；节奏覆盖。"""

    @classmethod
    def setUpClass(cls):
        cls.tags = load_json("data/tags.json")

    def test_general_7_types(self):
        self.assertEqual(len(self.tags["general"]), 7)

    def test_general_35_words_unique(self):
        words = [w for t in self.tags["general"] for w in t["tags"]]
        self.assertEqual(len(words), 35)
        self.assertEqual(len(set(words)), 35)

    def test_general_pace_valid(self):
        for t in self.tags["general"]:
            self.assertIn(t["pace"], PACE, f"{t['type']} pace 非法")

    def test_general_covers_all_pace(self):
        paces = {t["pace"] for t in self.tags["general"]}
        self.assertEqual(paces, PACE)

    def test_emotion_7_unique(self):
        self.assertEqual(len(self.tags["emotion"]), 7)
        etags = [e["tag"] for e in self.tags["emotion"]]
        self.assertEqual(len(set(etags)), 7)

    def test_emotion_pace_valid(self):
        for e in self.tags["emotion"]:
            self.assertIn(e["pace"], PACE)


class TestEmotionDaily(unittest.TestCase):
    """emotion_daily.json（v10.1.0）：4 档 × 5 词 = 20 词去重；节奏覆盖；触发词。"""

    @classmethod
    def setUpClass(cls):
        cls.ed = load_json("data/emotion_daily.json")

    def test_4_scenes(self):
        self.assertEqual(set(self.ed["scenes"].keys()), {"日常亲密", "共同决策", "冲突", "和解"})

    def test_20_words_unique(self):
        words = [w for s in self.ed["scenes"].values() for w in s["tags"]]
        self.assertEqual(len(words), 20)
        self.assertEqual(len(set(words)), 20)

    def test_pace_valid_and_covers_all(self):
        paces = []
        for name, sc in self.ed["scenes"].items():
            self.assertIn(sc["pace"], PACE, f"{name} pace 非法")
            paces.append(sc["pace"])
        self.assertEqual(set(paces), PACE)

    def test_trigger_keywords(self):
        self.assertGreaterEqual(len(self.ed["trigger"]["keywords"]), 5)
        self.assertEqual(self.ed["trigger"]["stage"], "定情")


class TestWordcount(unittest.TestCase):
    """wordcount.json：main + scenes 区间合法。"""

    @classmethod
    def setUpClass(cls):
        cls.wc = load_json("data/wordcount.json")

    def test_main_range(self):
        self.assertLessEqual(self.wc["main"]["min"], self.wc["main"]["max"])

    def test_scenes_ranges(self):
        self.assertIn("情感场景", self.wc["scenes"])
        for name, rng in self.wc["scenes"].items():
            self.assertLessEqual(rng["min"], rng["max"], f"{name} 区间非法")


class TestCommands(unittest.TestCase):
    """commands.json：域不重复；回顾域含 v10.1.0 新增指令。"""

    @classmethod
    def setUpClass(cls):
        cls.cmds = load_json("data/commands.json")

    def test_domains_unique(self):
        domains = [c["domain"] for c in self.cmds]
        self.assertEqual(len(set(domains)), len(domains))

    def test_review_aliases_v101(self):
        review = next(c for c in self.cmds if c["domain"] == "回顾")
        for alias in ("回顾", "章回顾", "卷回顾", "第N章讲了什么"):
            self.assertIn(alias, review["aliases"])


if __name__ == "__main__":
    unittest.main()