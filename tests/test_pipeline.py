"""端到端断言：只在「诗经」上跑（快），但检查的是整条链的契约。

包含三类检查：
  1. 结构契约   —— 每个候选都必须有出处、有平仄、有统计量
  2. 筛选契约   —— 停用字/同部首/姓氏冲突必须真的被剔除
  3. 排序契约   —— 平仄交错的必须排在前面
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shici_namer.config import load_config
from shici_namer.export import DEFAULT_COLUMNS
from shici_namer.filter import surname_conflict
from shici_namer.lexicon import Lexicon, NameStat
from shici_namer.models import Candidate
from shici_namer.phonology import Radicals, RhymeBook
from shici_namer.rank import rank


class TestSurnameConflict(unittest.TestCase):
    def test_同字(self):
        self.assertEqual(surname_conflict("聂聂", "聂"), "与姓同字")

    def test_同声母(self):
        # 聂 niè / 楠 nán → 都是 n
        self.assertEqual(surname_conflict("楠柏", "聂"), "与姓同声母")

    def test_同韵母(self):
        # 聂 nie / 月 yue → 韵母都是 e 系（FINALS 分别为 ie / ve，不同）
        # 这里用确定同韵母的组合：李 li / 溪 xi
        self.assertEqual(surname_conflict("溪月", "李"), "与姓同韵母")

    def test_无冲突(self):
        self.assertIsNone(surname_conflict("千里", "聂"))


class TestJunctionLiaison(unittest.TestCase):
    """连读吞音（D-009）：姓鼻音韵尾 + 名首字零声母。只降权不剔除。"""

    def test_鼻音韵尾加零声母(self):
        from shici_namer.filter import junction_liasion
        self.assertTrue(junction_liasion("安宁", "陈"))    # chén + ān
        self.assertTrue(junction_liasion("安然", "王"))    # wáng + ān

    def test_非鼻音韵尾不算(self):
        from shici_namer.filter import junction_liasion
        self.assertFalse(junction_liasion("安宁", "聂"))   # niè 韵尾 ie

    def test_名首非零声母不算(self):
        from shici_namer.filter import junction_liasion
        self.assertFalse(junction_liasion("明远", "陈"))   # míng 有声母

    def test_无姓不算(self):
        from shici_namer.filter import junction_liasion
        self.assertFalse(junction_liasion("安宁", None))


def _cand(name, pz, corpus_freq=10, pop=10, book_count=1, same_initial=False):
    return Candidate(
        name=name, pingze=pz, corpus_freq=corpus_freq, population_freq=pop,
        book_count=book_count, same_initial=same_initial,
        pingze_interleave=(set(pz) == {"平", "仄"}),
    )


class TestRank(unittest.TestCase):
    def test_平仄交错优先(self):
        cs = [
            _cand("平平", "平平", corpus_freq=9999),
            _cand("平仄", "平仄", corpus_freq=1),
        ]
        out = rank(cs, order=["pingze_interleave", "corpus_freq"])
        self.assertEqual(out[0].name, "平仄")

    def test_语料词频次高优先(self):
        cs = [_cand("甲乙", "平仄", corpus_freq=5), _cand("丙丁", "平仄", corpus_freq=500)]
        out = rank(cs, order=["pingze_interleave", "corpus_freq"])
        self.assertEqual(out[0].name, "丙丁")

    def test_方向后缀可覆盖默认方向(self):
        """corpus_freq 默认降序，:asc 后缀反转。方向语法是口径的一部分。"""
        cs = [_cand("甲乙", "平仄", corpus_freq=5), _cand("丙丁", "平仄", corpus_freq=500)]
        self.assertEqual(rank(cs, order=["corpus_freq"])[0].name, "丙丁")
        self.assertEqual(rank(cs, order=["corpus_freq:asc"])[0].name, "甲乙")

    def test_同声母键仍可用(self):
        """same_initial 键保留（可用），但默认序不再使用（D-004/D-008）。"""
        cs = [
            _cand("清泉", "平平", same_initial=True, corpus_freq=9999),
            _cand("明月", "平仄", same_initial=False, corpus_freq=1),
        ]
        out = rank(cs, order=["pingze_interleave", "same_initial", "corpus_freq"])
        self.assertEqual(out[0].name, "明月")

    def test_默认序数词垫后(self):
        """默认序首键 has_numeral：数词短语（一生/四方）必须排在无数词之后。"""
        cs = [
            _cand("一生", "仄平", corpus_freq=1557),
            _cand("徽音", "平平", corpus_freq=2),
        ]
        for c, has_num in ((cs[0], True), (cs[1], False)):
            c.has_numeral = has_num
        self.assertEqual(rank(cs)[0].name, "徽音")

    def test_默认序地名碎片垫后(self):
        """默认序第二键 place_flag（D-011）：武强必须排在同名篇层的干净词之后。"""
        cs = [
            _cand("武强", "仄平", corpus_freq=1, pop=33),
            _cand("孔阳", "仄平", corpus_freq=1, pop=2),
        ]
        cs[0].place_flag = True
        self.assertEqual(rank(cs)[0].name, "孔阳")

    def test_默认序声调多样性优先(self):
        """默认序在 dual 之后比 tone_variety（D-009）：三连同调垫后。
        王维(2-2)这类同调好名只是降权，仍在候选里。"""
        cs = [
            _cand("趯趯", "仄仄", corpus_freq=2, pop=0),   # 聂趯趯 4-4-4 → 调数1
            _cand("绳绳", "平平", corpus_freq=2, pop=0),   # 聂绳绳 4-2-2 → 调数2
        ]
        cs[0].tone_variety, cs[1].tone_variety = 1, 2
        self.assertEqual(rank(cs)[0].name, "绳绳")

    def test_默认序连读与洪细垫后(self):
        """junction_liasion（陈恩型）与细音收尾在默认序中降权。"""
        cs = [
            _cand("安宁", "平平", corpus_freq=2, pop=0),
            _cand("明远", "平仄", corpus_freq=2, pop=0),
        ]
        cs[0].junction_liasion, cs[0].tail_open = True, True
        cs[1].junction_liasion, cs[1].tail_open = False, True
        self.assertEqual(rank(cs)[0].name, "明远")
        cs[1].tail_open = False
        cs[1].junction_liasion = False
        cs[0].junction_liasion, cs[0].tail_open = False, True
        self.assertEqual(rank(cs)[0].name, "安宁")   # 尾字洪细是最末裁决

    def test_未知排序键报错(self):
        with self.assertRaises(ValueError):
            rank([_cand("甲乙", "平仄")], order=["不存在的键"])
        with self.assertRaises(ValueError):
            rank([_cand("甲乙", "平仄")], order=["corpus_freq:wrong"])


class TestPipelineContract(unittest.TestCase):
    """在真实语料上跑一遍（仅诗经），检查结构契约。"""

    @classmethod
    def setUpClass(cls):
        from shici_namer.pipeline import run
        cfg = load_config()
        # 只跑诗经：快，且足以覆盖全链路
        cls.result = run(config=cfg, books=["诗经"], progress=False)
        cls.cfg = cfg

    def test_有产出(self):
        """基线：仅「诗经」应产出 700± 候选（双通道门槛后当前实测 702）。
        这个下界是回归护栏，不是质量指标；语料或口径大改后需同步更新。"""
        self.assertGreater(len(self.result), 400, "诗经候选数骤降，链路可能断了")

    def test_每个候选都有出处(self):
        for c in self.result.candidates:
            with self.subTest(name=c.name):
                self.assertTrue(c.sources, "候选必须有出处")
                self.assertTrue(c.sources[0].sentence, "出处必须有原句")
                self.assertEqual(c.sources[0].book, "诗经")

    def test_每个候选都有平仄与统计(self):
        """双通道门槛不变量：人口 ≥ min_population_freq 或语料 ≥ min_corpus_freq。"""
        min_pop = self.cfg.get("extract.min_population_freq", 1)
        min_cor = self.cfg.get("extract.min_corpus_freq", 0)
        for c in self.result.candidates[:500]:
            with self.subTest(name=c.name):
                self.assertRegex(c.pingze, r"^[平仄通?]{2}$")
                self.assertTrue(
                    c.population_freq >= min_pop or c.corpus_freq >= min_cor,
                    f"{c.name} 未通过任何成词通道（pop={c.population_freq}, corpus={c.corpus_freq}）")
                self.assertGreaterEqual(c.corpus_freq, 1)
                self.assertEqual(len(c.initials), 2)
                self.assertEqual(len(c.finals), 2)

    def test_没有同部首(self):
        """默认配置下，同部首（同义堆叠）必须被剔除干净。"""
        bad = [c.name for c in self.result.candidates if c.same_radical]
        self.assertEqual(bad, [], f"仍有同部首候选：{bad[:10]}")

    def test_没有停用字(self):
        stop = self.cfg.stopwords
        self.assertGreater(len(stop), 150, "停用字表似乎没读到")
        bad = [c.name for c in self.result.candidates
               if c.name[0] in stop or c.name[1] in stop]
        self.assertEqual(bad, [], f"仍有含停用字的候选：{bad[:10]}")

    def test_虚拟词被停用字挡掉(self):
        """纯 2-gram 会产生「其道」「国之」这类语法组合，必须被停用字拦下。"""
        names = {c.name for c in self.result.candidates}
        for pseudo in ("其道", "国之", "以成", "有明"):
            with self.subTest(pseudo=pseudo):
                self.assertNotIn(pseudo, names)

    def test_排序满足首键(self):
        """默认序首键 has_numeral：前 300 个里，无数词的都排在含数词之前。"""
        head = self.result.candidates[:300]
        flags = [c.has_numeral for c in head]
        first_true = flags.index(True) if True in flags else len(flags)
        self.assertTrue(all(f for f in flags[first_true:]),
                        "排序违反首键 has_numeral")
        self.assertFalse(any(c.has_numeral for c in head[:50]),
                         "前 50 名不应出现数词短语")

    def test_统计字段完整(self):
        st = self.result.stats
        for key in ("passages", "hits", "filters", "final", "elapsed_sec"):
            self.assertIn(key, st)
        f = st["filters"]
        # 漏斗必须单调递减
        self.assertGreaterEqual(f["input"], f["output"])
        self.assertGreater(f["dropped_stopword"], 0, "停用字一步应砍掉一些")


class TestAcceptance(unittest.TestCase):
    """验收回归（D-007 + 2026-10 用户偏好 D-010）：好名靠前、平庸词垫底，
    且三条浏览偏好真实生效（人≥2 门槛 / 压叠字 / 响亮收尾优先）。

    历史：D-007 改造时 徽音/呦呦 曾被门槛杀死、思成 #357/713（诗经+楚辞）。
    2026-10 用户偏好（D-010）后：pop<2 非叠字词（含徽音）被挡、
    叠字层（含呦呦）被 same_final 压后——这是用户明确选择的取舍，
    两个历史断言改锁新行为。
    """

    @classmethod
    def setUpClass(cls):
        from shici_namer.pipeline import run
        cls.result = run(config=load_config(), books=["诗经"], progress=False)

    def test_人口门槛挡掉单源孤证(self):
        """min_population_freq=2：全库只有 1 人叫过的非叠字词（徽音 pop=1）
        不再进入候选；人口充足的（千里 pop=61）仍在。"""
        names = {c.name for c in self.result.candidates}
        self.assertNotIn("徽音", names, "pop=1 非叠字词应被门槛挡掉（D-010 取舍）")
        self.assertIn("千里", names)

    def test_叠字层被压后但通道仍通(self):
        """same_final 压叠字：前 50 无叠字；呦呦（叠字语料通道进入）仍在候选，
        但跌出前 200（被整体压到非叠字词之后）。"""
        idx = {c.name: i for i, c in enumerate(self.result.candidates)}
        self.assertIn("呦呦", idx, "叠字语料通道应仍放行 pop=0 叠字")
        self.assertGreater(idx["呦呦"], 200, "叠字应被 same_final 压后")
        self.assertFalse(any(c.name[0] == c.name[1] for c in self.result.candidates[:50]))

    def test_响亮收尾优先(self):
        """tail_open 提到频次键之前：前 50 名全部洪音收尾。"""
        self.assertTrue(all(c.tail_open for c in self.result.candidates[:50]),
                        "前 50 名应全部尾字洪音（D-010 偏好）")

    def test_叠字不受同部首剔除(self):
        """叠字（呦呦：口+口）是《诗经》修辞典故，豁免同部首规则。"""
        cand = next((c for c in self.result.candidates if c.name == "呦呦"), None)
        self.assertIsNotNone(cand)
        self.assertFalse(cand.same_radical)

    def test_地名碎片被垫后(self):
        """D-011：右邻=行政区划后缀的词（武强型）必须排在无此特征的词之后。
        诗经-only 语料里用「观清都」的 观清（楚辞，不在本榜）不行——
        改用 filter 单元级行为 + 榜单级无 place_flag 验证。"""
        # 榜单级：默认口径下前 200 名不应有 place_flag
        self.assertFalse(any(c.place_flag for c in self.result.candidates[:200]),
                          "前 200 名不应出现地名碎片")

    def test_place_flag两种证据(self):
        """语境严格判定（武强右邻全为縣/县）与地名志命中（建平）都置 place_flag；
        偶然共现（乔木 31 种右邻含 1 个「都」）不置。"""
        from collections import Counter
        from shici_namer.filter import apply_filters, place_context_flag
        from shici_namer.extract import Hit
        from shici_namer.phonology import RhymeBook, Radicals
        cfg = load_config()
        SUF = cfg.place_context_chars
        # 严格判定单元
        self.assertTrue(place_context_flag(Counter({"縣": 1, "县": 1}), SUF))       # 武强
        self.assertFalse(place_context_flag(Counter({"都": 1, "石": 30}), SUF))     # 乔木式偶然共现
        self.assertFalse(place_context_flag(Counter({"都": 1}), SUF))               # 单次证据不足
        self.assertFalse(place_context_flag(Counter(), SUF))                        # 全句末
        rhyme = RhymeBook.load(cfg.path("paths.rhyme"), "平水韵")
        radicals = Radicals.load(cfg.path("paths.radical"))
        hits = {
            "武强": Hit(name="武强", corpus_freq=2, population_freq=33,
                        right_chars=Counter({"縣": 1, "县": 1})),
            "建平": Hit(name="建平", corpus_freq=1, population_freq=8),
            "清泉": Hit(name="清泉", corpus_freq=1, population_freq=95, right_chars=Counter({"石": 1})),
        }
        cands, _ = apply_filters(
            hits, stopwords=set(), radicals=radicals, rhyme=rhyme, book_rank={"诗经": 0},
            place_context_chars=SUF, place_names=cfg.place_names,
        )
        flags = {c.name: c.place_flag for c in cands}
        self.assertTrue(flags["武强"], "右邻全为縣/县 应标记")
        self.assertTrue(flags["建平"], "地名志命中应标记")
        self.assertFalse(flags["清泉"], "右邻=石 不应标记")

    def test_旧榜首垫底(self):
        """改造前霸榜的数词短语必须跌到最后 10%。"""
        n = len(self.result.candidates)
        idx = {c.name: i for i, c in enumerate(self.result.candidates)}
        for w in ("千里", "四方"):
            self.assertGreater(idx[w], n * 0.9, f"{w} 应垫底")

    def test_聂姓全名声调参与排序(self):
        """D-009：三连同调（聂趯趯 4-4-4）必须排在有声调起伏的叠字之后，
        且前 30 名的 tone_variety >= 2（无姓时中性值 3 不惩罚）。"""
        from shici_namer.pipeline import run
        r = run(config=load_config(), surname="聂", books=["诗经"], progress=False)
        idx = {c.name: i for i, c in enumerate(r.candidates)}
        self.assertIn("绳绳", idx)
        self.assertIn("趯趯", idx)
        self.assertLess(idx["绳绳"], idx["趯趯"],
                        "聂绳绳(4-2-2) 应排在 趯趯(4-4-4) 之前")
        self.assertGreaterEqual(min(c.tone_variety for c in r.candidates[:30]), 2)
        # 无姓运行（setUpClass 的 result）不惩罚：全为中性 3
        self.assertEqual(min(c.tone_variety for c in self.result.candidates[:50]), 3)


class TestFamousMatcher(unittest.TestCase):
    """名篇目录三种命中方式（整书/精确/篇组前缀）。"""

    def test_三种命中(self):
        from shici_namer.filter import _famous_matcher
        m = _famous_matcher({"诗经", "楚辞\t九歌", "唐诗\t山居秋暝"})
        self.assertTrue(m({"诗经"}, {"诗经\t思齐"}))            # 整书
        self.assertTrue(m({"楚辞"}, {"楚辞\t九歌·湘夫人"}))    # 篇组前缀
        self.assertTrue(m({"唐诗", "宋诗"}, {"宋诗\t无题", "唐诗\t山居秋暝"}))  # 精确
        self.assertFalse(m({"宋诗"}, {"宋诗\t无题"}))          # 未命中
        self.assertFalse(m(set(), set()))


class TestExportContract(unittest.TestCase):
    def test_csv列与配置一致(self):
        cfg = load_config()
        self.assertEqual(cfg.get("export.columns"), DEFAULT_COLUMNS,
                         "config 里的 export.columns 与 export.DEFAULT_COLUMNS 不一致")

    def test_csv快速导出(self):
        import csv
        import tempfile
        from shici_namer.export import to_csv

        cs = [_cand("千里", "平仄", corpus_freq=7476, pop=61, book_count=6)]
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.csv"
            to_csv(cs, p, surname="聂")
            with open(p, encoding="utf-8-sig") as f:
                rows = list(csv.reader(f))
        self.assertEqual(rows[0], DEFAULT_COLUMNS)
        self.assertEqual(rows[1][0], "聂千里")
        self.assertEqual(len(rows[1]), len(DEFAULT_COLUMNS))


class TestConfigIsWired(unittest.TestCase):
    """证明 config/default.yaml 真的在驱动行为，不是摆设。

    做法：拿一份改过的配置跑同一批语料，断言结果按预期变化。
    如果哪天有人把阈值硬编码回代码里，这些测试会挂。
    """

    @classmethod
    def setUpClass(cls):
        import copy
        import yaml
        from shici_namer.config import Config, PROJECT_ROOT

        base = yaml.safe_load((PROJECT_ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
        cls.base = base
        cls.Config = Config
        cls.PROJECT_ROOT = PROJECT_ROOT

    _cache: dict = {}

    def _run_with(self, mutate, key: str = ""):
        """按 key 缓存，避免重复跑同一条管线（每条约 3 秒）。"""
        import copy
        from shici_namer.pipeline import run
        if key and key in self._cache:
            return self._cache[key]
        raw = copy.deepcopy(self.base)
        mutate(raw)
        out = run(config=self.Config(raw=raw), books=["诗经"], progress=False)
        if key:
            self._cache[key] = out
        return out

    def test_提高最小人口频次会减少候选(self):
        strict = self._run_with(lambda r: r["extract"].__setitem__("min_population_freq", 20), "strict")
        base = self._run_with(lambda r: None, "base")
        self.assertLess(len(strict), len(base),
                        "提高 min_population_freq 后候选应减少——配置可能没接上")

    def test_保留同部首会增加候选(self):
        keep = self._run_with(lambda r: r["filter"].__setitem__("drop_same_radical", False), "keep_rad")
        base = self._run_with(lambda r: None, "base")
        self.assertGreater(len(keep), len(base),
                           "关闭 drop_same_radical 后候选应增加")
        # 而且这些多出来的确实含同部首
        self.assertTrue(any(c.same_radical for c in keep.candidates))

    def test_停用字表可关闭(self):
        no_stop = self._run_with(lambda r: r["filter"].__setitem__("use_stopwords", False), "no_stop")
        base = self._run_with(lambda r: None, "base")
        self.assertGreater(len(no_stop), len(base),
                           "关闭停用字后候选应增加")
        # 关掉后应能出现含虚词的伪词
        names = {c.name for c in no_stop.candidates}
        self.assertTrue(any(n[0] in "其之以有" or n[1] in "其之以有" for n in names),
                        "关闭停用字后应出现含虚词的候选")

    def test_性别筛选确实生效(self):
        """有性别筛选应少于无筛选。
        （注意：不能拿 0.75 → 0.99 做对比——姓名库里大量名字的性别比本来就是 1.0，
         阈值提高不产生差别。这是数据的性质，不是配置没接上。）"""
        from shici_namer.pipeline import run
        no_sex = self._run_with(lambda r: None, "base")
        male = run(config=self.Config(raw=__import__("copy").deepcopy(self.base)),
                   books=["诗经"], sex="男", progress=False)
        self.assertLess(len(male), len(no_sex),
                        "加性别筛选后候选应减少——配置可能没接上")
        self.assertGreater(len(male), 0, "诗经里应有男性向名字")

    def test_关闭语料通道会失去叠字(self):
        """min_corpus_freq=0 时，呦呦（人口 0）应从候选里消失。"""
        no_ch = self._run_with(lambda r: r["extract"].__setitem__("min_corpus_freq", 0), "no_ch")
        names = {c.name for c in no_ch.candidates}
        self.assertNotIn("呦呦", names, "语料通道关闭后叠字名不应再进入候选")

    def test_清空数字字表会让数词回到前列(self):
        """numeral_chars 置空 → has_numeral 恒 False → 数词短语不再垫后。"""
        no_num = self._run_with(lambda r: r["rank"].__setitem__("numeral_chars", ""), "no_num")
        top100 = [c.name for c in no_num.candidates[:100]]
        self.assertTrue(any(c.has_numeral is False and any(
            ch in "一二三四五六七八九十百千万" for ch in c.name) for c in no_num.candidates[:100]),
            "清空数字表后前 100 应出现数词短语")
        self.assertFalse(top100 == [], "sanity")

    def test_名篇分级接线(self):
        """use_famous=false 时没有任何候选带 source_famous=True。"""
        cfg = self.Config(raw=__import__("copy").deepcopy(self.base))
        cfg.raw["rank"]["use_famous"] = False
        from shici_namer.pipeline import run
        out = run(config=cfg, books=["诗经"], progress=False)
        self.assertFalse(any(c.source_famous for c in out.candidates),
                         "关闭名篇分级后 source_famous 应全为 False")
        base = self._run_with(lambda r: None, "base")
        self.assertTrue(all(c.source_famous for c in base.candidates[:50]),
                        "诗经整书在名篇目录里，前 50 应全部 source_famous=True")


if __name__ == "__main__":
    unittest.main()
