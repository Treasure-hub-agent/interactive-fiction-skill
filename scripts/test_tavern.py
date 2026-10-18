#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""tavern_prep / 酒馆卡注入 单元测试（纯标准库）

覆盖：
  1. 解析器对真实卡（PNG / JSON）+ 构造卡的各种形态
  2. 宏替换、字段归一、entries 两种形态（list / dict）
  3. 落盘结构与源卡只读（sha256 前后一致）
  4. novel.py 的酒馆语义注入：constant 必入 / keys 命中 / 预算硬约束 /
     常驻配额（防全量常驻）/ position 与 recursive 降级

运行：python3 -m unittest discover -s scripts -p "test_tavern*.py" -v
"""
import base64
import json
import os
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import novel  # noqa: E402
import tavern_prep as tp  # noqa: E402

REAL_PNG = os.path.expanduser(
    "~/novels/参考卡研究/chub-cn-cards-20260927/修仙世界系统_joyful_dad_3845.png")
REAL_JSON = os.path.expanduser(
    "~/novels/参考卡研究/chub-hot-20260925/MADLAD_FROM_HEAVEN_aemeath-ee69d666a27c.json")


# ---------- 测试素材构造 ----------
def make_png_card(card: dict, key: str = "chara") -> bytes:
    """构造一张内嵌 chara tEXt chunk 的最小合法 PNG。"""
    def chunk(typ: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + typ + data
                + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\xff\xff"                      # 1x1 像素
    payload = key.encode() + b"\x00" + base64.b64encode(
        json.dumps(card, ensure_ascii=False).encode("utf-8"))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"tEXt", payload) + chunk(b"IEND", b""))


def sample_card(name="测试角色", extra=None) -> dict:
    card = {
        "name": name,
        "description": "一位来自 {{char}} 世界的旅人，与 {{user}} 相识于雨夜。",
        "personality": "沉默但可靠",
        "mes_example": "{{char}}：「走吧。」",
        "first_mes": "{{char}} 抬头看了 {{user}} 一眼。",
        "alternate_greetings": ["备选一", "备选二"],
        "system_prompt": "你是叙事者，遵守既定规则。",
        "post_history_instructions": "保持第二人称。",
        "creator": "tester",
        "character_version": "1.0",
        "tags": ["测试"],
        "character_book": {
            "name": "测试世界书",
            "scan_depth": 50,
            "token_budget": 500,
            "recursive_scanning": True,
            "entries": [
                {"keys": ["雨夜", "夜雨"], "content": "雨下得很大。", "constant": False,
                 "extensions": {"probability": 80}, "insertion_order": 200,
                 "position": "before_char", "id": 1},
                {"keys": ["旧伤"], "content": "左臂有一道旧疤。", "constant": True,
                 "extensions": {"probability": 100}, "insertion_order": 100,
                 "position": "after_char", "id": 2},
                {"keys": [], "content": "无关键词条目。", "constant": False, "id": 3},
            ],
        },
    }
    if extra:
        card.update(extra)
    return card


def make_novel(tmp: str, name="测试小说") -> str:
    ndir = os.path.join(tmp, name)
    os.makedirs(os.path.join(ndir, "meta"), exist_ok=True)
    with open(os.path.join(ndir, "meta", "novel_runtime.json"), "w", encoding="utf-8") as f:
        json.dump({"v": 1, "ua": "t", "nm": name, "rn": "自创", "md": "爽文", "vw": "v",
                   "ch": 1, "sc": "日常过渡", "wc": 0, "choices": [], "st": {},
                   "seg_count": 1, "cp": {"旧友": {}}, "npcs": []}, f, ensure_ascii=False)
    with open(os.path.join(ndir, "meta", "novel_assist.json"), "w", encoding="utf-8") as f:
        json.dump({"turn": 0, "notes": [], "changes": [], "closed_choices": []},
                  f, ensure_ascii=False)
    return ndir


class Args:
    def __init__(self, inp=None, full=False, card=None, novel=None, root=None, dry_run=False):
        self.input = inp
        self.full = full
        self.card = card
        self.novel = novel
        self.root = root
        self.dry_run = dry_run
        self.json = False


# ---------- 载体解析 ----------
class TestCarriers(unittest.TestCase):
    def test_png_chara_roundtrip(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "a.png")
            with open(p, "wb") as f:
                f.write(make_png_card(sample_card()))
            card, desc, err = tp.load_card(p)
            self.assertIsNone(err, err)
            self.assertEqual(card["name"], "测试角色")
            self.assertIn("PNG", desc)
            self.assertIn("chara", desc)

    def test_png_ccv3_key_also_supported(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "b.png")
            with open(p, "wb") as f:
                f.write(make_png_card({"data": sample_card(), "spec": "chara_card_v3"}, key="ccv3"))
            card, desc, err = tp.load_card(p)
            self.assertIsNone(err, err)
            self.assertEqual(card["name"], "测试角色")
            self.assertIn("ccv3", desc)

    def test_json_bare_and_wrapped(self):
        with tempfile.TemporaryDirectory() as t:
            p1 = os.path.join(t, "bare.json")
            with open(p1, "w", encoding="utf-8") as f:
                json.dump(sample_card(), f, ensure_ascii=False)
            c1, d1, e1 = tp.load_card(p1)
            self.assertIsNone(e1)
            self.assertEqual(c1["name"], "测试角色")
            self.assertIn("裸 V2", d1)

            p2 = os.path.join(t, "spec.json")
            with open(p2, "w", encoding="utf-8") as f:
                json.dump({"spec": "chara_card_v2", "data": sample_card()}, f, ensure_ascii=False)
            c2, d2, e2 = tp.load_card(p2)
            self.assertIsNone(e2)
            self.assertIn("spec", d2)

    def test_charx_zip(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "c.charx")
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("card.json", json.dumps(
                    {"spec": "chara_card_v3", "data": sample_card()}, ensure_ascii=False))
                z.writestr("assets/icon.png", b"fake")
            card, desc, err = tp.load_card(p)
            self.assertIsNone(err, err)
            self.assertEqual(card["name"], "测试角色")
            self.assertIn("CHARX", desc)

    def test_unsupported_and_missing(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "x.txt")
            open(p, "w").close()
            _, _, err = tp.load_card(p)
            self.assertIn("不支持的格式", err)
            _, _, err2 = tp.load_card(os.path.join(t, "nope.png"))
            self.assertIn("不存在", err2)

    def test_broken_png_without_card(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "plain.png")
            with open(p, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)
            card, desc, err = tp.load_card(p)
            self.assertIsNone(card)
            self.assertIn("未找到", err)

    @unittest.skipUnless(os.path.isfile(REAL_PNG), "缺真实 PNG 样本")
    def test_real_png_card(self):
        card, desc, err = tp.load_card(REAL_PNG)
        self.assertIsNone(err, err)
        entries = tp.normalize_entries(card.get("character_book"))
        self.assertGreater(len(entries), 0, "真实卡应有世界书条目")

    @unittest.skipUnless(os.path.isfile(REAL_JSON), "缺真实 JSON 样本")
    def test_real_json_card_48_entries(self):
        card, desc, err = tp.load_card(REAL_JSON)
        self.assertIsNone(err, err)
        entries = tp.normalize_entries(card.get("character_book"))
        self.assertEqual(len(entries), 48, "该样本含 48 条世界书条目")


# ---------- 字段归一 ----------
class TestNormalize(unittest.TestCase):
    def test_macro_replacement(self):
        got = tp.clean_macro("{{char}} 对 {{user}} 说：{{未知宏}}", "阿离")
        self.assertIn("阿离", got)
        self.assertIn("你", got)
        self.assertNotIn("{{", got, "未知宏不应残留花括号")

    def test_entries_list_form(self):
        ents = tp.normalize_entries(sample_card()["character_book"])
        self.assertEqual(len(ents), 3)
        self.assertEqual(ents[0]["keys"], ["雨夜", "夜雨"])
        self.assertEqual(ents[0]["probability"], 80)
        self.assertEqual(ents[0]["order"], 200)
        self.assertFalse(ents[0]["constant"])
        self.assertTrue(ents[1]["constant"])

    def test_entries_dict_form(self):
        cb = {"entries": {"0": {"keys": ["甲"], "content": "一", "enabled": True},
                          "1": {"keys": ["乙"], "content": "二", "enabled": True}}}
        ents = tp.normalize_entries(cb)
        self.assertEqual(len(ents), 2)
        self.assertEqual({e["keys"][0] for e in ents}, {"甲", "乙"})

    def test_disabled_and_empty_filtered(self):
        cb = {"entries": [
            {"keys": ["甲"], "content": "一", "enabled": False},
            {"keys": [], "content": "", "enabled": True},
            {"keys": ["乙"], "content": "二", "enabled": True},
        ]}
        ents = tp.normalize_entries(cb)
        self.assertEqual([e["keys"][0] for e in ents], ["乙"])

    def test_keys_as_string(self):
        cb = {"entries": [{"keys": "甲,乙、丙 丁", "content": "x", "enabled": True}]}
        ents = tp.normalize_entries(cb)
        self.assertEqual(ents[0]["keys"], ["甲", "乙", "丙", "丁"])

    def test_bad_types_do_not_crash(self):
        cb = {"entries": ["不是字典", None, 42, {"keys": 5, "content": 7, "enabled": True}]}
        ents = tp.normalize_entries(cb)      # 不得抛异常
        self.assertIsInstance(ents, list)

    def test_stats(self):
        card = sample_card()
        ents = tp.normalize_entries(card["character_book"])
        st = tp.card_stats(card, ents)
        self.assertEqual(st["name"], "测试角色")
        self.assertEqual(st["entries_total"], 3)
        self.assertEqual(st["entries_constant"], 1)
        self.assertEqual(st["alternate_greetings"], 2)
        self.assertTrue(st["has_system_prompt"])

    def test_slugify_safe(self):
        self.assertNotIn("/", tp.slugify("a/b:c*d?e"))
        self.assertEqual(tp.slugify(""), "未命名")
        self.assertTrue(tp.slugify("练好长的" * 40))


# ---------- 导入落盘 ----------
class TestImport(unittest.TestCase):
    def test_import_writes_expected_structure_and_keeps_source_readonly(self):
        with tempfile.TemporaryDirectory() as t:
            ndir = make_novel(t)
            p = os.path.join(t, "card.png")
            with open(p, "wb") as f:
                f.write(make_png_card(sample_card("阿离")))
            before = tp.file_sha256(p)
            rc = tp.cmd_import(Args(card=p, novel="测试小说", root=t))
            self.assertEqual(rc, 0)
            after = tp.file_sha256(p)
            self.assertEqual(before, after, "源卡必须只读（sha256 前后一致）")

            cdir = os.path.join(ndir, "characters", "阿离")
            for fn in ("profile.md", "personality.md", "interaction.md", "openings.md"):
                self.assertTrue(os.path.isfile(os.path.join(cdir, fn)), f"缺 {fn}")
            ldir = os.path.join(ndir, "lorebook", "阿离")
            files = sorted(os.listdir(ldir))
            self.assertEqual(len(files), 3, "三条条目应各落一份文件")
            sdir = os.path.join(ndir, "source", "tavern", "阿离")
            self.assertTrue(os.path.isfile(os.path.join(sdir, "card.png")), "源卡应留档")
            self.assertTrue(os.path.isfile(os.path.join(sdir, "卡信息.json")))
            with open(os.path.join(sdir, "卡信息.json"), encoding="utf-8") as f:
                meta = json.load(f)
            self.assertIn("system_prompt", meta["留档"])
            self.assertIn("不注入", meta["留档"]["备注"])
            self.assertEqual(meta["源文件sha256"], before)

    def test_import_reads_are_idempotent(self):
        """两次导入应产出相同内容（幂等，不叠加）。"""
        with tempfile.TemporaryDirectory() as t:
            ndir = make_novel(t)
            p = os.path.join(t, "c.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(sample_card("幂等"), f, ensure_ascii=False)
            tp.cmd_import(Args(card=p, novel="测试小说", root=t))
            d1 = sorted(os.listdir(os.path.join(ndir, "lorebook", "幂等")))
            tp.cmd_import(Args(card=p, novel="测试小说", root=t))
            d2 = sorted(os.listdir(os.path.join(ndir, "lorebook", "幂等")))
            self.assertEqual(d1, d2, "重复导入不应产生重复条目文件")

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            ndir = make_novel(t)
            p = os.path.join(t, "c.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(sample_card("预演"), f, ensure_ascii=False)
            rc = tp.cmd_import(Args(card=p, novel="测试小说", root=t, dry_run=True))
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.isdir(os.path.join(ndir, "lorebook")), "预演不得写盘")

    def test_missing_novel_reports_error(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "c.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(sample_card(), f, ensure_ascii=False)
            rc = tp.cmd_import(Args(card=p, novel="不存在的小说", root=t))
            self.assertEqual(rc, 1)


# ---------- 酒馆语义注入（novel.py） ----------
class TestTavernInjection(unittest.TestCase):
    def _setup(self, t, entries):
        make_novel(t)          # 只需目录副作用，返回值不再使用
        card = sample_card("注入角色")
        card["character_book"]["entries"] = entries
        p = os.path.join(t, "card.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(card, f, ensure_ascii=False)
        tp.cmd_import(Args(card=p, novel="测试小说", root=t))
        return novel.Novel(t, "测试小说")

    def test_constant_always_injected(self):
        with tempfile.TemporaryDirectory() as t:
            n = self._setup(t, [
                {"keys": ["常驻项"], "content": "常驻内容。", "constant": True, "id": 1},
                {"keys": ["关键词"], "content": "命中内容。", "constant": False, "id": 2},
            ])
            hits = novel.tavern_hits(n, n.runtime, Args(inp="这句话没有关键词"), budget=4)
            titles = [h[0] for h in hits]
            self.assertTrue(any("常驻项" in x for x in titles), f"常驻项必入：{titles}")

    def test_keyword_hit_and_miss(self):
        with tempfile.TemporaryDirectory() as t:
            n = self._setup(t, [
                {"keys": ["雨夜"], "content": "雨下得很大。", "constant": False, "id": 1},
                {"keys": ["沙漠"], "content": "沙子很烫。", "constant": False, "id": 2},
            ])
            hit = novel.tavern_hits(n, n.runtime, Args(inp="今夜是雨夜"), budget=4)
            titles = [h[0] for h in hit]
            self.assertTrue(any("雨夜" in x for x in titles), titles)
            self.assertFalse(any("沙漠" in x for x in titles), "未命中不得注入")

    def test_budget_hard_cap(self):
        """预算硬约束：无论多少条常驻，注入数不得超过 budget（防爆窗）。"""
        with tempfile.TemporaryDirectory() as t:
            entries = [{"keys": [f"常驻{i}"], "content": f"内容{i}。", "constant": True, "id": i}
                       for i in range(1, 21)]
            entries += [{"keys": ["目标"], "content": "目标内容。", "constant": False, "id": 99}]
            n = self._setup(t, entries)
            for budget in (1, 2, 4, 8):
                hits = novel.tavern_hits(n, n.runtime, Args(inp="目标"), budget=budget)
                self.assertLessEqual(len(hits), budget,
                                     f"budget={budget} 时注入 {len(hits)} 条，超预算")

    def test_constant_quota_leaves_room_for_keywords(self):
        """常驻配额：多条 constant 不得吃光预算，须给关键词命中留名额。"""
        with tempfile.TemporaryDirectory() as t:
            entries = [{"keys": [f"常驻{i}"], "content": f"c{i}", "constant": True, "id": i}
                       for i in range(1, 11)]
            entries.append({"keys": ["目标"], "content": "命中内容。", "constant": False, "id": 99})
            n = self._setup(t, entries)
            hits = novel.tavern_hits(n, n.runtime, Args(inp="目标"), budget=4)
            titles = [h[0] for h in hits]
            self.assertTrue(any("目标" in x for x in titles),
                            f"关键词命中须能在常驻挤压下入选：{titles}")
            const_n = sum(1 for x in titles if "常驻" in x)
            self.assertLessEqual(const_n, max(1, 4 // novel.LORE_CONST_RATIO),
                                 f"常驻条数超出配额：{titles}")

    def test_order_priority_within_same_weight(self):
        """order 值小者优先（与酒馆习惯一致）。"""
        with tempfile.TemporaryDirectory() as t:
            n = self._setup(t, [
                {"keys": ["甲"], "content": "后置", "constant": False,
                 "insertion_order": 900, "id": 1},
                {"keys": ["甲"], "content": "前置", "constant": False,
                 "insertion_order": 100, "id": 2},
            ])
            hits = novel.tavern_hits(n, n.runtime, Args(inp="甲"), budget=4)
            self.assertGreaterEqual(len(hits), 2)
            self.assertIn("前置", hits[0][1], f"order 小者应排前：{[h[1][:12] for h in hits]}")

    def test_long_content_truncated(self):
        with tempfile.TemporaryDirectory() as t:
            long_text = "很长。" * 800
            n = self._setup(t, [{"keys": ["长文"], "content": long_text,
                                 "constant": True, "id": 1}])
            hits = novel.tavern_hits(n, n.runtime, Args(inp="长文"), budget=4)
            self.assertTrue(hits)
            self.assertLessEqual(len(hits[0][1]), novel.LORE_ENTRY_INJECT_MAX + 20,
                                 "单条注入须截断到上限附近")
            self.assertIn("lorebook 原文", hits[0][1], "截断处应指向原文")

    def test_no_lorebook_dir_is_safe(self):
        with tempfile.TemporaryDirectory() as t:
            make_novel(t)      # 只需目录副作用
            n = novel.Novel(t, "测试小说")
            self.assertEqual(novel.tavern_entries(n), [], "无 lorebook 目录应返回空")
            self.assertEqual(novel.tavern_hits(n, n.runtime, Args(inp="x")), [])

    def test_broken_entry_files_skipped(self):
        """损坏条目文件不得让注入崩溃。"""
        with tempfile.TemporaryDirectory() as t:
            ndir = make_novel(t)
            ldir = os.path.join(ndir, "lorebook", "坏卡")
            os.makedirs(ldir)
            with open(os.path.join(ldir, "bad.md"), "wb") as f:
                f.write(b"\xff\xfe\x00\x00 not utf8 \x80\x81")
            open(os.path.join(ldir, "empty.md"), "w").close()
            with open(os.path.join(ldir, "nohead.md"), "w", encoding="utf-8") as f:
                f.write("## 普通设定\n\n内容")
            n = novel.Novel(t, "测试小说")
            self.assertEqual(novel.tavern_entries(n), [], "非酒馆格式文件应被跳过")

    def test_position_and_recursive_are_downgraded(self):
        """position=depth 类与 recursive 卡：一律并入 [设定] 段，不影响 P0 顺序。"""
        with tempfile.TemporaryDirectory() as t:
            n = self._setup(t, [
                {"keys": ["深插"], "content": "深度注入内容。", "constant": True,
                 "position": 4, "id": 1},
            ])
            hits = novel.tavern_hits(n, n.runtime, Args(inp="深插"), budget=4)
            self.assertTrue(hits, "depth 类条目应仍能被注入（降级为 [设定] 段）")
            self.assertEqual(hits[0][2], "酒馆卡·注入角色", "来源应标注酒馆卡")

    def test_brief_integration_shows_tavern_source(self):
        """端到端：brief 的 [设定] 段应出现酒馆卡来源标注，且总条数受预算约束。"""
        with tempfile.TemporaryDirectory() as t:
            self._setup(t, [
                {"keys": ["关键词甲"], "content": "甲内容。", "constant": False, "id": 1},
            ])
            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                novel.cmd_brief(Args(inp="关键词甲", root=t, novel="测试小说"))
            out = buf.getvalue()
            self.assertIn("[设定]", out)
            self.assertIn("酒馆卡·注入角色", out)
            seg = out.split("[设定]")[1].split("\n[")[0]
            self.assertLessEqual(seg.count("  · "), novel.LORE_MAX, "超预算注入")

    def test_cross_source_dedup_same_title(self):
        """跨源去重：既有世界书与酒馆卡出现**同名条目**时，只注入一条。

        回归背景：原实现只用既有世界书的标题初始化 `seen`，导致酒馆卡的同名条目
        被加进 merged 后又被 `tv + [...]` 拼回一次 → 「功法」注入两遍（实测复现）。
        """
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as t:
            ndir = make_novel(t)
            # 既有世界书：与酒馆卡同名「功法」
            wb = os.path.join(ndir, "worldbuilding")
            os.makedirs(wb, exist_ok=True)
            with open(os.path.join(wb, "世界观.md"), "w", encoding="utf-8") as f:
                f.write("# 功法\n\n既有的功法设定。\n\n# 宗门\n\n既有宗门设定。\n")
            # 酒馆卡：同名「功法」+ 独有「妖兽」
            card = sample_card("去重卡")
            card["character_book"]["entries"] = [
                {"keys": ["功法"], "content": "酒馆的功法设定。", "id": 1},
                {"keys": ["妖兽"], "content": "酒馆的妖兽设定。", "id": 2},
            ]
            p = os.path.join(t, "c.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(card, f, ensure_ascii=False)
            tp.cmd_import(Args(card=p, novel="测试小说", root=t))

            buf = io.StringIO()
            with redirect_stdout(buf):
                novel.cmd_brief(Args(inp="我想修炼功法，还想了解宗门", root=t, novel="测试小说"))
            out = buf.getvalue()
            seg = out.split("[设定]")[1].split("\n[")[0]
            rows = [ln.strip() for ln in seg.split("\n") if ln.strip().startswith("·")]
            titles = [r.split("—")[0].replace("·", "").strip() for r in rows]
            dup = [x for x in set(titles) if titles.count(x) > 1]
            self.assertEqual(dup, [], f"跨源同名条目不得重复注入：{rows}")
            # 同名时酒馆卡版本优先（更贴本轮输入）
            self.assertTrue(any("酒馆卡" in r for r in rows),
                            f"同名条目应保留酒馆卡版本：{rows}")


class TestSafetyBoundaries(unittest.TestCase):
    """安全边界：不可信输入（用户下载的卡）不得撑爆内存或刷屏失控。"""

    def test_charx_zip_bomb_rejected_by_declared_size(self):
        """高压缩比大文件的 CHARX 必须被拒（不解压）——zip 炸弹防护。"""
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "bomb.charx")
            # 造 20MB 全零数据（压缩后极小 → 压缩比极高）
            payload = json.dumps({"name": "炸弹", "blob": "0" * (20 * 1024 * 1024)})
            with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("card.json", payload)
            card, desc, err = tp.load_card(p)
            self.assertIsNone(card, "超大 CHARX 应被拒绝")
            self.assertIn("zip 炸弹", err, f"应提示 zip 炸弹防护，实际：{err}")

    def test_charx_normal_size_still_works(self):
        """防护不得误伤正常卡。"""
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "ok.charx")
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("card.json", json.dumps(sample_card("正常"), ensure_ascii=False))
            card, desc, err = tp.load_card(p)
            self.assertIsNone(err, f"正常 CHARX 不应被拒：{err}")
            self.assertEqual(card["name"], "正常")

    def test_charx_candidate_limit(self):
        """候选 JSON 过多时不得遍历全部（防卡在解析循环）。"""
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "many.charx")
            with zipfile.ZipFile(p, "w") as z:
                for i in range(50):
                    z.writestr(f"junk{i:03d}.json", "{}")
                z.writestr("card.json", json.dumps(sample_card("目标"), ensure_ascii=False))
            card, desc, err = tp.load_card(p)
            self.assertIsNone(err, err)
            self.assertEqual(card["name"], "目标", "应优先命中 card.json")

    def test_full_mode_hard_cap(self):
        """--full 不设常规预算，但须有硬上限（防 60 条 constant 全量刷屏）。"""
        with tempfile.TemporaryDirectory() as t:
            entries = [{"keys": [f"常驻{i}"], "content": f"c{i}", "constant": True, "id": i}
                       for i in range(1, 61)]
            make_novel(t)
            card = sample_card("满量")
            card["character_book"]["entries"] = entries
            p = os.path.join(t, "c.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(card, f, ensure_ascii=False)
            tp.cmd_import(Args(card=p, novel="测试小说", root=t))
            n = novel.Novel(t, "测试小说")
            hits = novel.tavern_hits(n, n.runtime, Args(inp="无命中词"), budget=None)
            self.assertLessEqual(len(hits), novel.LORE_FULL_HARD_CAP,
                                 f"--full 注入 {len(hits)} 条，超出硬上限 "
                                 f"{novel.LORE_FULL_HARD_CAP}")



class TestFieldCoercion(unittest.TestCase):
    """布尔字段归一：卡片来自多平台导出，布尔常写成字符串（"false"/"0"）。"""

    def test_string_false_is_not_truthy(self):
        """字符串 'false'/'0' 必须判为假——否则「本应禁用」的条目会被启用/常驻。"""
        cb = {"entries": [
            {"keys": ["甲"], "content": "甲。", "enabled": "false", "id": 1},
            {"keys": ["乙"], "content": "乙。", "constant": "false", "id": 2},
            {"keys": ["丙"], "content": "丙。", "constant": "0", "id": 3},
            {"keys": ["丁"], "content": "丁。", "constant": "true", "id": 4},
        ]}
        ents = tp.normalize_entries(cb)
        keys = {e["keys"][0]: e for e in ents}
        self.assertNotIn("甲", keys, "enabled='false' 字符串应被判为禁用")
        self.assertFalse(keys["乙"]["constant"], "constant='false' 应判为非常驻")
        self.assertFalse(keys["丙"]["constant"], "constant='0' 应判为非常驻")
        self.assertTrue(keys["丁"]["constant"], "constant='true' 应判为常驻")

    def test_real_bools_and_missing_defaults(self):
        """真布尔与缺省语义不得被破坏（enabled 缺省=True，constant 缺省=False）。"""
        cb = {"entries": [
            {"keys": ["甲"], "content": "甲。", "id": 1},                    # 都缺省
            {"keys": ["乙"], "content": "乙。", "enabled": False, "id": 2},   # 真布尔禁用
            {"keys": ["丙"], "content": "丙。", "constant": True, "id": 3},   # 真布尔常驻
        ]}
        ents = tp.normalize_entries(cb)
        keys = {e["keys"][0]: e for e in ents}
        self.assertIn("甲", keys, "enabled 缺省应为启用")
        self.assertFalse(keys["甲"]["constant"], "constant 缺省应为非常驻")
        self.assertNotIn("乙", keys, "enabled=False 应被过滤")
        self.assertTrue(keys["丙"]["constant"])

    def test_truthy_helper_directly(self):
        for v, exp in [("false", False), ("FALSE", False), ("0", False), ("no", False),
                       ("", False), (None, False), (0, False), (False, False),
                       ("true", True), ("1", True), ("yes", True), (1, True), (True, True)]:
            self.assertEqual(tp._truthy(v, default=False), exp, f"_truthy({v!r})")


class TestReimportCleanup(unittest.TestCase):
    """换版导入：条目变少/重排时不得残留旧条目文件（残留会被继续注入）。"""

    def test_reimport_removes_stale_entries(self):
        with tempfile.TemporaryDirectory() as t:
            ndir = make_novel(t)
            card = sample_card("换代卡")
            card["character_book"]["entries"] = [
                {"keys": ["甲"], "content": "甲。", "id": 1},
                {"keys": ["乙"], "content": "乙。", "id": 2},
                {"keys": ["丙"], "content": "丙。", "id": 3},
            ]
            p = os.path.join(t, "v1.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(card, f, ensure_ascii=False)
            tp.cmd_import(Args(card=p, novel="测试小说", root=t))
            ldir = os.path.join(ndir, "lorebook", "换代卡")
            self.assertEqual(len(os.listdir(ldir)), 3)

            # 换版：只剩 2 条
            card["character_book"]["entries"] = [
                {"keys": ["新甲"], "content": "新甲。", "id": 1},
                {"keys": ["新乙"], "content": "新乙。", "id": 2},
            ]
            p2 = os.path.join(t, "v2.json")
            with open(p2, "w", encoding="utf-8") as f:
                json.dump(card, f, ensure_ascii=False)
            tp.cmd_import(Args(card=p2, novel="测试小说", root=t))

            files = sorted(os.listdir(ldir))
            self.assertEqual(len(files), 2, f"旧条目应被清理，实际残留：{files}")
            self.assertFalse([f for f in files if "丙" in f], "已移除的条目不得残留")

    def test_reimport_keeps_other_packs(self):
        """清理只针对本卡目录，不得误伤其它酒馆卡。"""
        with tempfile.TemporaryDirectory() as t:
            ndir = make_novel(t)
            for nm in ("卡A", "卡B"):
                card = sample_card(nm)
                card["character_book"]["entries"] = [{"keys": [nm], "content": nm, "id": 1}]
                p = os.path.join(t, f"{nm}.json")
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(card, f, ensure_ascii=False)
                tp.cmd_import(Args(card=p, novel="测试小说", root=t))
            # 重导卡A
            card = sample_card("卡A")
            card["character_book"]["entries"] = [{"keys": ["卡A新"], "content": "新", "id": 1}]
            p = os.path.join(t, "卡A2.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(card, f, ensure_ascii=False)
            tp.cmd_import(Args(card=p, novel="测试小说", root=t))
            base = os.path.join(ndir, "lorebook")
            self.assertEqual(sorted(os.listdir(base)), ["卡A", "卡B"], "其它卡目录不得被删")
            self.assertEqual(len(os.listdir(os.path.join(base, "卡B"))), 1, "卡B 条目不得受影响")


if __name__ == "__main__":
    unittest.main()
