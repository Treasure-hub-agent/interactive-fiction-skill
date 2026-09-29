#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""test_schema.py — novel_runtime.schema.json 合规测试（v10.1.0 新增）。

用法：
    python3 -m unittest scripts.test_schema -v
或：
    python3 scripts/test_schema.py

依赖：jsonschema（pip install jsonschema）；缺失时跳过并提示。
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    import jsonschema
    HAVE_JS = True
    from jsonschema import ValidationError  # noqa: F401
except ImportError:
    jsonschema = None  # type: ignore[assignment]
    HAVE_JS = False


def load_json(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


class TestSchema(unittest.TestCase):
    """核心字段 + 合法样本（含 v10.1.0 新增字段）+ 非法样本拦截。"""

    @classmethod
    def setUpClass(cls):
        cls.schema = load_json("schema/novel_runtime.schema.json")

    def test_required_fields_present(self):
        for field in ["v", "ua", "nm", "rn", "md", "vw", "ch", "sc", "wc", "choices", "st"]:
            self.assertIn(field, self.schema["required"], f"required 缺 {field}")

    def test_v101_new_fields_present(self):
        # v10.1.0 新增 chapter_summary / volumes
        self.assertIn("chapter_summary", self.schema["properties"])
        self.assertIn("volumes", self.schema["properties"])

    def test_choices_schema_reasonable(self):
        items = self.schema["properties"]["choices"]["items"]
        self.assertIn("seg", items["required"])
        self.assertIn("surface_by", items["required"])

    @unittest.skipUnless(HAVE_JS, "jsonschema 未安装：pip install jsonschema")
    def test_legal_sample_passes(self):
        sample = {
            "v": "10.1.0", "ua": "2026-08-30T10:00:00+08:00", "nm": "测试",
            "rn": "自创角色", "md": "主线", "vw": 1, "ch": 6, "sc": "城镇",
            "wc": 30000, "choices": [
                {"seg": 10, "picked": "A", "type": "consequence", "detail": "x",
                 "tier": "短期", "surface_by": 15}
            ],
            "st": {"位置": "城镇", "目标": "继续探索"},
            "chapter_summary": {"ch": 5, "summary": "本章摘要", "generated_by": "LLM",
                                "created_at": "2026-08-30T10:00:00+08:00"},
            "volumes": [{"ch_end": 5, "summary": "卷总结", "generated_by": "LLM",
                         "created_at": "2026-08-30T10:00:00+08:00"}],
        }
        if jsonschema is None:
            self.skipTest("jsonschema 未安装")
        jsonschema.validate(sample, self.schema)

    @unittest.skipUnless(HAVE_JS, "jsonschema 未安装：pip install jsonschema")
    def test_illegal_sample_rejected(self):
        bad = {"v": "10.1.0", "ua": "x", "nm": "x", "rn": "x", "md": "x",
               "vw": 99, "ch": 1, "sc": "x", "wc": 0, "choices": [], "st": {}}
        if jsonschema is None:
            self.skipTest("jsonschema 未安装")
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(bad, self.schema)


if __name__ == "__main__":
    unittest.main()