#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""check_pack 规则自测（dev 侧，纯标准库）

为什么必须测：`check_pack.py` 是「发布包边界」的尺子——它若失灵，.pyc/泄露会再次
漏进发布包。本文件用构造样本校准它的**禁入规则**与**必需清单**判定逻辑（纯逻辑，
不需真打包）。

运行：python3 -m unittest discover -s dev -p "test_*.py" -v
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_pack as C  # noqa: E402


def matches_any(path: str) -> str:
    """返回命中的禁入规则原因；无命中返回空串。"""
    for pat, why in C.FORBIDDEN:
        if re.search(pat, path):
            return why
    return ""


class TestForbiddenRules(unittest.TestCase):
    def test_cache_and_bytecode_flagged(self):
        for p in ("scripts/__pycache__/novel.cpython-312.pyc",
                  "scripts/x.pyc", "a/b.pyo",
                  ".ruff_cache/foo", ".mypy_cache/bar", ".pytest_cache/baz", ".hypothesis/x"):
            self.assertTrue(matches_any(p), f"{p} 应被禁入规则命中")

    def test_dev_side_flagged(self):
        for p in ("dev/check_pack.py", "dev/promptfoo/asserts.py",
                  "tests/test_novel_props.py", "eval/run.py",
                  ".github/workflows/ci.yml",
                  ".pre-commit-config.yaml", "ruff.toml", "cliff.toml",
                  "promptfooconfig.yaml"):
            self.assertTrue(matches_any(p), f"{p} 应被禁入规则命中")

    def test_runtime_files_not_flagged(self):
        """发布包内**应当存在**的文件不得被误判为禁入。"""
        for p in ("SKILL.md", "VERSION", "MANIFEST.json", "package.json",
                  "scripts/novel.py", "scripts/tavern_prep.py",
                  "scripts/test_tavern.py",  # 测试随包分发是既有约定
                  "extended/tavern_import.md", "references/command_nav.md",
                  "data/commands.json", "schema/novel_runtime.schema.json",
                  "assets/banner.svg", "modes/immersion.md"):
            self.assertFalse(matches_any(p), f"{p} 不应被判为禁入：{matches_any(p)}")

    def test_log_and_output_flagged(self):
        for p in ("build.log", "output/tmp.json"):
            self.assertTrue(matches_any(p), f"{p} 应被禁入规则命中")


class TestRequiredList(unittest.TestCase):
    def test_required_are_runtime_files(self):
        """必需清单里的文件都必须是随包分发的（不得混入 dev 侧文件）。"""
        for p in C.REQUIRED:
            self.assertFalse(matches_any(p),
                             f"必需清单含 dev 侧文件 {p}（自相矛盾，会让检查永远失败）")

    def test_required_covers_new_feature(self):
        """本版新增的酒馆卡功能文件必须在必需清单里（防白名单写窄漏发）。"""
        joined = " ".join(C.REQUIRED)
        for must in ("tavern_prep.py", "tavern_import.md"):
            self.assertIn(must, joined, f"必需清单应包含 {must}")

    def test_required_nonempty_unique(self):
        self.assertTrue(C.REQUIRED)
        self.assertEqual(len(C.REQUIRED), len(set(C.REQUIRED)), "必需清单不应有重复项")


class TestRepoWiring(unittest.TestCase):
    """确认检查脚本已挂进本地 CI（否则等于没接）。"""

    def test_hooked_into_local_ci(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p = os.path.join(root, "dev", "run_ci_local.sh")
        with open(p, encoding="utf-8") as f:
            body = f.read()
        self.assertIn("check_pack.py", body, "run_ci_local.sh 应调用 check_pack.py")

    def test_hooked_into_workflow(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p = os.path.join(root, ".github", "workflows", "ci.yml")
        if not os.path.isfile(p):
            self.skipTest("无 workflow 文件")
        with open(p, encoding="utf-8") as f:
            body = f.read()
        self.assertIn("check_pack.py", body, "CI workflow 应调用 check_pack.py")


if __name__ == "__main__":
    unittest.main()
