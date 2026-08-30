#!/usr/bin/env python3
"""test_manifest.py — MANIFEST.json 哈希与集合一致性测试（v10.1.0 新增）。

用法：
    python3 -m unittest scripts.test_manifest -v
或：
    python3 scripts/test_manifest.py
"""
import hashlib
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class TestManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "MANIFEST.json"), encoding="utf-8") as f:
            cls.manifest = json.load(f)

    def test_files_match_disk(self):
        """清单中的每个文件应真实存在且哈希一致。"""
        files = self.manifest["files"]
        mismatches = []
        for rel, meta in files.items():
            p = os.path.join(ROOT, rel)
            if not os.path.isfile(p):
                mismatches.append(f"{rel}: 不存在")
                continue
            if sha256_file(p) != meta["sha256"]:
                mismatches.append(f"{rel}: 哈希不一致")
        self.assertEqual(mismatches, [])

    def test_every_deliverable_listed(self):
        """工具/数据/文档类可交付文件应尽数在清单中。"""
        counted = {
            "data/*.json": sum(1 for x in self.manifest["files"] if x.startswith("data/")),
            "schema/*.json": sum(1 for x in self.manifest["files"] if x.startswith("schema/")),
            "scripts/*.py": sum(1 for x in self.manifest["files"] if x.startswith("scripts/")),
        }
        self.assertGreaterEqual(counted["data/*.json"], 5, "data 文件应含 5+")
        self.assertGreaterEqual(counted["schema/*.json"], 1)
        self.assertGreaterEqual(counted["scripts/*.py"], 3, "scripts 应含 validate/gen_manifest + 测试")

    def test_root_files_listed(self):
        for root_file in ("SKILL.md", "VERSION", "package.json", "README.md"):
            self.assertIn(root_file, self.manifest["files"])


if __name__ == "__main__":
    unittest.main()