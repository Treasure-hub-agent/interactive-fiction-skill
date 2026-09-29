#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""test_validate.py — validate.py 主流程 + 坏数据拦截测试（v10.1.0 新增）。

用法：
    python3 -m unittest scripts.test_validate -v
或：
    python3 scripts/test_validate.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_validate(fake_root):
    """在 fake_root 下运行 validate.py，返回 (exit_code, output)。"""
    proc = subprocess.run(
        [sys.executable, os.path.join(fake_root, "scripts", "validate.py")],
        capture_output=True, text=True, cwd=fake_root, timeout=60,
    )
    return proc.returncode, proc.stdout + proc.stderr


class FakeRepoMixin:
    """复制整个源目录到临时位置，构造可改装的独立副本（保证 MANIFEST 一致）。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="if-repo-")
        for entry in os.listdir(ROOT):
            src = os.path.join(ROOT, entry)
            dst = os.path.join(self.tmp, entry)
            if os.path.isdir(src):
                if entry == ".git":
                    continue
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            elif os.path.isfile(src):
                shutil.copy2(src, dst)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TestValidateMain(FakeRepoMixin, unittest.TestCase):
    """主流程：完整副本应通过。"""

    def test_clean_repo_passes(self):
        code, out = run_validate(self.tmp)
        self.assertEqual(code, 0, f"干净副本应通过 validate.py\n{out}")
        self.assertIn("全部检查通过", out)


class TestValidateBroken(FakeRepoMixin, unittest.TestCase):
    """故意构造坏数据：应返回非零。"""

    def test_bad_version_mismatch(self):
        with open(os.path.join(self.tmp, "VERSION"), "w", encoding="utf-8") as f:
            f.write("99.0.0")
        code, out = run_validate(self.tmp)
        self.assertNotEqual(code, 0)
        self.assertIn("version", out.lower())

    def test_bad_tag_duplicate(self):
        p = os.path.join(self.tmp, "data", "tags.json")
        with open(p, encoding="utf-8") as f:
            tags = json.load(f)
        tags["general"][0]["tags"][1] = tags["general"][0]["tags"][0]  # 制造重复
        with open(p, "w", encoding="utf-8") as f:
            json.dump(tags, f, ensure_ascii=False)
        code, out = run_validate(self.tmp)
        self.assertNotEqual(code, 0)

    def test_broken_link(self):
        # 在 command_nav.md 里引用一个不存在的文件
        p = os.path.join(self.tmp, "references", "command_nav.md")
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n见 [不存在](../extended/not-exist.md)\n")
        code, out = run_validate(self.tmp)
        self.assertNotEqual(code, 0)
        self.assertIn("引用不存在", out)

    def test_missing_emotion_daily(self):
        os.remove(os.path.join(self.tmp, "data", "emotion_daily.json"))
        code, out = run_validate(self.tmp)
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()