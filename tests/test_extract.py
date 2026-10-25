"""摘词层断言：2-gram 必须能捞回分词器漏掉的词，且停用字过滤必须生效。

不用全量语料跑（太慢）。这里用构造的小语料，验证算法行为本身。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shici_namer.corpus import Passage, split_sentences
from shici_namer.extract import extract
from shici_namer.lexicon import Lexicon, NameStat


def make_lexicon(names: dict[str, int]) -> Lexicon:
    return Lexicon({k: NameStat(n=v, m=v, f=0) for k, v in names.items()})


class TestSplit(unittest.TestCase):
    def test_逗号也切句(self):
        """2-gram 只需要相邻两字，逗号也必须切，否则会跨句取字。"""
        got = split_sentences("明月松间照，清泉石上流。", r"[！。？；!?\n\r，、：,]+")
        self.assertEqual(got, ["明月松间照", "清泉石上流"])

    def test_单字句被丢弃(self):
        self.assertEqual(split_sentences("春。", r"[。]+"), [])


class TestCorpusFormats(unittest.TestCase):
    """语料格式适配（2026-10 全量语料恢复后新增的两种形态）。"""

    def test_宋词标题为词牌首句(self):
        """宋词（chinese-poetry ci 系）没有 title，词牌在 rhythmic 且不唯一；
        标题必须是「词牌·首句片段」，否则名篇目录（宋词三百首）无法匹配。"""
        import json
        import tempfile
        from shici_namer.corpus import iter_corpus
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / "宋词"
            d.mkdir()
            (d / "ci.test.json").write_text(json.dumps([
                {"description": "作者简介，无 paragraphs，应被跳过", "name": "苏轼"},
                {"author": "苏轼", "rhythmic": "水调歌头", "paragraphs": ["明月几时有，把酒问青天。"]},
            ], ensure_ascii=False), encoding="utf-8")
            psgs = list(iter_corpus(Path(td), ["宋词"]))
        self.assertEqual(len(psgs), 1)
        self.assertEqual(psgs[0].title, "水调歌头·明月几时有")
        self.assertEqual(psgs[0].author, "苏轼")


class TestExtract(unittest.TestCase):
    def test_能捞回_jieba_切错的清泉(self):
        """jieba 把「清泉石上流」切成 清泉石/上流，漏掉「清泉」。
        2-gram 必须能拿到「清泉」。
        """
        lex = make_lexicon({"清泉": 95})
        passages = [Passage("唐诗", "测试", "清泉石上流")]
        hits = extract(passages, lex, split_pattern=r"[。，]+", min_population_freq=1)
        self.assertIn("清泉", hits)
        self.assertEqual(hits["清泉"].population_freq, 95)

    def test_语料词频按出现次数累加(self):
        lex = make_lexicon({"千里": 61})
        passages = [
            Passage("诗经", "玄鸟", "邦畿千里"),
            Passage("楚辞", "", "宁昂昂若千里之驹乎"),
        ]
        hits = extract(passages, lex, split_pattern=r"[。，]+", min_population_freq=1)
        self.assertEqual(hits["千里"].corpus_freq, 2)
        self.assertEqual(hits["千里"].books, {"诗经", "楚辞"})

    def test_人口频次不足的丢弃(self):
        lex = make_lexicon({"清泉": 2})
        hits = extract([Passage("唐诗", "", "清泉石上流")], lex,
                       split_pattern=r"[。，]+", min_population_freq=3)
        self.assertNotIn("清泉", hits)

    def test_叠字语料通道(self):
        """人口 0 的叠字词，语料出现 ≥2 次即可进入（呦呦 靠它活下来）；
        非叠字的同类组合仍被拒（言告/顷筐 这类诗法套语）。"""
        lex = make_lexicon({})   # 姓名库里完全没有
        psgs = [Passage("诗经", "鹿鸣", "呦呦鹿鸣"), Passage("诗经", "鹿鸣", "呦呦鹿鸣食野之蒿"),
                Passage("诗经", "草虫", "喓喓草虫"), Passage("诗经", "草虫", "喓喓草虫趯趯阜螽"),
                Passage("诗经", "葛覃", "言告师氏"), Passage("诗经", "卷耳", "言告夫人")]
        hits = extract(psgs, lex, split_pattern=r"[。，]+",
                       min_population_freq=1, min_corpus_freq=2, corpus_channel="叠字")
        self.assertIn("呦呦", hits)
        self.assertIn("喓喓", hits)
        self.assertNotIn("言告", hits, "非叠字的人口 0 词不应经语料通道进入")

    def test_语料通道关闭时叠字也进不来(self):
        lex = make_lexicon({})
        hits = extract([Passage("诗经", "鹿鸣", "呦呦鹿鸣")] * 3, lex,
                       split_pattern=r"[。，]+",
                       min_population_freq=1, min_corpus_freq=0)
        self.assertEqual(hits, {})

    def test_右邻字被记录(self):
        """语境证据（D-011）：武强的右邻是縣/县，清泉的右邻是石——
        前者是地名词干，后者是独立的词。句末出现则无右邻。"""
        lex = make_lexicon({"武强": 33, "清泉": 95, "乔木": 4})
        psgs = [
            Passage("唐诗", "某", "官武强縣尉"),
            Passage("唐诗", "某", "知武强县事"),
            Passage("唐诗", "山居秋暝", "清泉石上流"),
            Passage("诗经", "汉广", "南有乔木"),
        ]
        hits = extract(psgs, lex, split_pattern=r"[。，]+", min_population_freq=1)
        self.assertEqual(dict(hits["武强"].right_chars), {"縣": 1, "县": 1})
        self.assertEqual(dict(hits["清泉"].right_chars), {"石": 1})
        self.assertEqual(dict(hits["乔木"].right_chars), {})   # 句末，无右邻

    def test_不在姓名库的丢弃(self):
        lex = make_lexicon({"清泉": 95})
        hits = extract([Passage("唐诗", "", "松间月照")], lex,
                       split_pattern=r"[。，]+", min_population_freq=1)
        self.assertEqual(hits, {})

    def test_出处最多保留_max_sources(self):
        lex = make_lexicon({"千里": 61})
        passages = [Passage("诗经", f"篇{i}", "邦畿千里") for i in range(10)]
        hits = extract(passages, lex, split_pattern=r"[。，]+",
                       min_population_freq=1, max_sources=3)
        self.assertEqual(len(hits["千里"].sources), 3)
        self.assertEqual(hits["千里"].corpus_freq, 10)


if __name__ == "__main__":
    unittest.main()
