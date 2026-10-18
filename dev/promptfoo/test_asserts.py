#!/usr/bin/env python3
# © 2026 Treasure-hub-agent · interactive-fiction skill · MIT License
# https://github.com/Treasure-hub-agent/interactive-fiction-skill
"""断言自测（dev 侧，纯标准库，不依赖 hypothesis）

为什么必须有这个文件：promptfoo 断言是「评测模型输出的尺子」，尺子本身若不
准确，评测结论就是假信号。本文件用**构造的正例/反例**逐条校准每个断言，
确保：合规样本全过、违规样本全被抓到。

运行：python3 -m unittest discover -s dev/promptfoo -p "test_*.py" -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asserts as A  # noqa: E402

# ---------- 构造样本 ----------
STATUS = "🔖 原著 · 第3章 · 1.2万字"
BODY_OK = (
    "雨还没停。林战站在檐下，指节上还留着方才交手时的红痕。\n"
    "（他把袖口拢了拢，遮住那道红）\n"
    "〔她方才那句话，究竟是什么意思〕\n"
    "「走吧。」他说。短促，像把话折断了丢出去。\n"
    "她没有动，只是看着他，像在等一个更完整的句子。\n"
) * 6   # 重复到主区间字数内
OPTS_OK = "\n".join([
    "A · [进攻] 追出门往左拐，沿街堵她问清票的来路",
    "B · [探索] 留在厅里核票根笔迹，先弄清票的来路",
    "C · [套话] 不碰票的事，先向那人套昨晚谁进过厅",
    "D · [主角] 把票收进内袋不声张，先按票上地名走一趟",
    "E · [跳过] 快进到天亮后头班车的站台",
])
HINT = "> 💡 输入「选项降级」可切两分支；输入「进度」查看剧情仪表盘"


def sample(body=BODY_OK, status=STATUS, opts=OPTS_OK, hint=HINT):
    return f"{status}\n\n{body}\n\n{opts}\n{hint}"


class TestLocateSections(unittest.TestCase):
    """分区定位是所有断言的地基，先校准它。"""

    def test_splits_four_sections(self):
        s = sample()
        got = A.locate_sections(s)
        self.assertEqual(got["status"], STATUS)
        self.assertIn("林战" if False else "雨还没停", got["body"])
        self.assertEqual([l for l, _ in got["options"]], ["A", "B", "C", "D", "E"])
        self.assertIn("💡", got["hint"])

    def test_status_and_options_excluded_from_body(self):
        s = sample()
        body = A.locate_sections(s)["body"]
        self.assertNotIn("🔖", body, "状态条不得计入正文")
        self.assertNotIn("A.", body, "选项行不得计入正文")
        self.assertNotIn("💡", body, "提示行不得计入正文")

    def test_count_body_chars_ignores_markup_whitespace(self):
        n1 = A.count_body_chars(sample())
        n2 = A.count_body_chars(sample(body=BODY_OK.replace("\n", "")))
        # 换行/空白不计入
        self.assertLess(abs(n1 - n2), 30, "净字数应基本不受换行影响")


class TestFiveOptions(unittest.TestCase):
    def test_pass_on_canonical(self):
        self.assertTrue(A.has_five_options(sample())["pass"])

    def test_fail_when_missing_e(self):
        opts = "\n".join(OPTS_OK.splitlines()[:4])
        r = A.has_five_options(sample(opts=opts))
        self.assertFalse(r["pass"], "缺 E 选项必须判违规")
        self.assertIn("A", r["reason"])

    def test_fail_when_out_of_order(self):
        opts = "\n".join(["B. 二", "A. 一", "C. 三", "D. 四", "E. 五"])
        self.assertFalse(A.has_five_options(sample(opts=opts))["pass"], "顺序错须判违规")

    def test_fail_when_duplicated(self):
        opts = "\n".join(["A. 一", "B. 二", "C. 三", "D. 四", "A. 又一"])
        self.assertFalse(A.has_five_options(sample(opts=opts))["pass"], "重复字母须判违规")

    def test_exempt_on_gather_marker(self):
        s = sample(body=BODY_OK + "\n[集]\n")
        self.assertTrue(A.has_five_options(s)["pass"], "[集] 为合法豁免")

    def test_accepts_list_and_bold_markup(self):
        opts = "\n".join([f"- **{l}.** 选项{l}" for l in "ABCDE"])
        self.assertTrue(A.has_five_options(sample(opts=opts))["pass"],
                        "列表符号/加粗不应影响识别")

    def test_accepts_compact_dot_separator(self):
        """SKILL.md §紧凑选项格式 的默认形式 `A · [标签] 摘要` 必须被识别。

        回归背景：OPTION_RE 的分隔符类若漏掉 `·`，规范默认格式会被判「无选项」，
        且选项行会落进 body 使字数虚高——两个断言同时假阳性/假阴性。
        """
        opts = "\n".join([f"{l} · [标签] 摘要{l}" for l in "ABCDE"])
        s = sample(opts=opts)
        self.assertEqual([l for l, _ in A.locate_sections(s)["options"]], list("ABCDE"),
                         "紧凑格式 A · 选项行应被识别")
        self.assertTrue(A.has_five_options(s)["pass"], "紧凑格式五选项须判通过")
        self.assertNotIn("A ·", A.locate_sections(s)["body"], "选项行不得落进正文")


class TestWordcount(unittest.TestCase):
    def test_pass_on_main_range(self):
        r = A.wordcount_in_range(sample())
        self.assertTrue(r["pass"], r["reason"])

    def test_fail_when_too_short(self):
        r = A.wordcount_in_range(sample(body="太短了。"))
        self.assertFalse(r["pass"], "过短须判违规")

    def test_fail_when_too_long(self):
        r = A.wordcount_in_range(sample(body=BODY_OK * 6))
        self.assertFalse(r["pass"], "过长须判违规")

    def test_scene_override(self):
        ctx = {"vars": {"scene": "对话快速交换"}}
        # 造到 250-400 净字数区间（对话快速交换档）
        short = ("「走？」他说。\n「不走。」她答，声音很轻。\n（他把手松开）\n"
                 "〔她是不是在等我先动〕\n") * 8
        r = A.wordcount_in_range(sample(body=short), ctx)
        self.assertTrue(r["pass"], f"场景档应放宽区间：{r['reason']}")


class TestSymbolDiscipline(unittest.TestCase):
    def test_pass_on_canonical(self):
        self.assertTrue(A.symbol_discipline(sample())["pass"])

    def test_fail_when_dialogue_in_action(self):
        body = BODY_OK + "\n（他说：「我记住了」）\n"
        r = A.symbol_discipline(sample(body=body))
        self.assertFalse(r["pass"], "台词塞进动作括号须判违规")

    def test_fail_when_dialogue_in_inner_thought(self):
        body = BODY_OK + "\n〔她想：「他终究还是来了」〕\n"
        self.assertFalse(A.symbol_discipline(sample(body=body))["pass"],
                         "台词塞进心理括号须判违规")


class TestStatusBar(unittest.TestCase):
    def test_pass_on_canonical(self):
        self.assertTrue(A.status_bar_format(sample())["pass"])

    def test_fail_when_missing(self):
        r = A.status_bar_format(sample(status=""))
        self.assertFalse(r["pass"], "缺状态条须判违规")

    def test_fail_when_no_wordcount(self):
        r = A.status_bar_format(sample(status="🔖 原著 · 第3章"))
        self.assertFalse(r["pass"], "缺字数位须判违规")

    def test_fail_when_no_chapter(self):
        r = A.status_bar_format(sample(status="🔖 原著 · 1.2万字"))
        self.assertFalse(r["pass"], "缺章节位须判违规")

    def test_pass_on_prologue(self):
        r = A.status_bar_format(sample(status="🔖 自创 · 序章 · 0.1万字"))
        self.assertTrue(r["pass"], "序章应合法")


class TestNoEmDash(unittest.TestCase):
    def test_pass_on_clean(self):
        self.assertTrue(A.no_em_dash(sample())["pass"])

    def test_fail_on_chinese_em_dash(self):
        self.assertFalse(A.no_em_dash(sample(body=BODY_OK + "\n他停了下——然后走了。"))["pass"])

    def test_fail_on_double_hyphen(self):
        self.assertFalse(A.no_em_dash(sample(body=BODY_OK + "\n他停了下--然后走了。"))["pass"])


class TestNoAiTone(unittest.TestCase):
    def test_pass_on_clean(self):
        self.assertTrue(A.no_ai_tone(sample())["pass"])

    def test_fail_on_catchphrase(self):
        self.assertFalse(A.no_ai_tone(sample(body=BODY_OK + "\n总而言之，他明白了。"))["pass"])

    def test_multiple_hits_reported(self):
        r = A.no_ai_tone(sample(body=BODY_OK + "\n总而言之，值得注意的是，他走了。"))
        self.assertFalse(r["pass"])
        self.assertGreaterEqual(len(r["reason"]), 5)


class TestNotClosedLoop(unittest.TestCase):
    def test_pass_on_open_ending(self):
        self.assertTrue(A.not_closed_loop(sample())["pass"])

    def test_fail_on_closed_loop(self):
        body = BODY_OK + "\n事情终于解决了，一切归于平静。"
        r = A.not_closed_loop(sample(body=body))
        self.assertFalse(r["pass"], "闭环结论须判违规")

    def test_only_inspects_tail(self):
        """闭环词出现在正文中段（未收尾）不应误伤。"""
        body = "事情终于解决了。但新的消息又来了。\n" + BODY_OK
        r = A.not_closed_loop(sample(body=body))
        self.assertTrue(r["pass"], f"中段的闭环词不应被判为收尾闭环：{r['reason']}")


class TestOptionConstraints(unittest.TestCase):
    def test_e_key_decision_detected(self):
        opts = OPTS_OK.replace("E · [跳过] 快进到天亮后头班车的站台",
                               "E · [跳过] 快进到他向你表白的那一刻")
        self.assertFalse(A.e_option_not_key_decision(sample(opts=opts))["pass"])

    def test_e_clean_passes(self):
        self.assertTrue(A.e_option_not_key_decision(sample())["pass"])

    def test_d_user_voice_detected(self):
        opts = OPTS_OK.replace("D · [主角] 把票收进内袋不声张，先按票上地名走一趟",
                               "D · [主角] 你来决定要不要追出门")
        self.assertFalse(A.d_option_is_protagonist_inference(sample(opts=opts))["pass"])

    def test_d_protagonist_inference_passes(self):
        self.assertTrue(A.d_option_is_protagonist_inference(sample())["pass"])


class TestAggregate(unittest.TestCase):
    def test_all_pass_on_good_sample(self):
        r = A.assert_all(sample())
        self.assertTrue(r["pass"], r.get("reason"))
        self.assertEqual(len(r["details"]), 10, "应覆盖 10 项契约")

    def test_all_fails_and_reports_each(self):
        bad = sample(body="太短——总而言之。", status="无状态条", opts="A. 只有一项")
        r = A.assert_all(bad)
        self.assertFalse(r["pass"])
        failed = [k for k, v in r["details"].items() if not v["pass"]]
        self.assertGreaterEqual(len(failed), 5,
                                f"坏样本应触发多项失败，实际 {failed}")
        for k in failed:
            self.assertTrue(r["details"][k]["reason"], f"{k} 失败须带原因")

    def test_details_always_present(self):
        for s in (sample(), "随手一段话"):
            r = A.assert_all(s)
            self.assertEqual(set(r["details"]), {
                "five_options", "wordcount", "symbols", "status_bar", "no_em_dash",
                "no_ai_tone", "not_closed_loop", "e_option", "d_option", "opt_separator"})


class TestOptionSeparator(unittest.TestCase):
    """分隔符合规断言：宽松解析不得掩盖格式偏差。"""

    def test_canonical_separator_passes(self):
        opts = "\n".join([f"{l} · [标签] 摘要{l}" for l in "ABCDE"])
        self.assertTrue(A.option_separator_canonical(sample(opts=opts))["pass"])

    def test_ideographic_comma_rejected(self):
        """顿号是实测中最常见的偏差（子代理自创写法），必须报出。"""
        opts = "\n".join([f"{l}、[标签] 摘要{l}" for l in "ABCDE"])
        r = A.option_separator_canonical(sample(opts=opts))
        self.assertFalse(r["pass"], "顿号分隔符须判不合规")
        self.assertIn("、", r["reason"])

    def test_ascii_dot_rejected(self):
        opts = "\n".join([f"{l}. [标签] 摘要{l}" for l in "ABCDE"])
        self.assertFalse(A.option_separator_canonical(sample(opts=opts))["pass"])

    def test_loose_parsing_still_finds_options(self):
        """宽松解析（locate_sections）仍应定位到选项，保证字数不被污染。"""
        opts = "\n".join([f"{l}、[标签] 摘要{l}" for l in "ABCDE"])
        got = A.locate_sections(sample(opts=opts))
        self.assertEqual([l for l, _ in got["options"]], list("ABCDE"))
        self.assertNotIn("、[标签]", got["body"], "选项行不得被吃进正文")


if __name__ == "__main__":
    unittest.main()
