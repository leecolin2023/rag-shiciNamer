"""一致性断言：平水韵、声韵、部首。

这些测试是**口径契约**。任何智能体改代码后如果这些挂了，
说明它动了不该动的东西（或者动完没更新口径文档）。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from shici_namer.config import load_config
from shici_namer.phonology import Radicals, RhymeBook, final, initial, tone4


class TestRhymeBook(unittest.TestCase):
    """平水韵必须能正确识别入声。这是本项目相对旧方案最关键的一处升级。"""

    @classmethod
    def setUpClass(cls):
        cfg = load_config()
        cls.rhyme = RhymeBook.load(cfg.path("paths.rhyme"), "平水韵")

    def test_入声字判仄(self):
        """石/白/轼/陆/牧/若/疾/勃/骆 都是入声字，现代普通话读平声。"""
        for ch in "石白轼陆牧若疾勃骆":
            with self.subTest(ch=ch):
                self.assertEqual(self.rhyme.pingze(ch), "仄", f"{ch} 应为入声（仄）")

    def test_王安石是平平仄(self):
        """普通话是「平平平」，平水韵是「平平仄」。这是判据，不能变。"""
        self.assertEqual(self.rhyme.pattern("王安石"), "平平仄")

    def test_白居易是仄平仄(self):
        """白是入声 → 仄。普通话会误判成「平平仄」。"""
        self.assertEqual(self.rhyme.pattern("白居易"), "仄平仄")

    def test_李清照是仄平仄(self):
        self.assertEqual(self.rhyme.pattern("李清照"), "仄平仄")

    def test_两读字标为通(self):
        """平声组与仄声组都出现的字标为「通」，不应被当成「平」或「仄」。"""
        mapping = self.rhyme._m
        ambiguous = [c for c, v in mapping.items() if v == "通"]
        self.assertGreater(len(ambiguous), 100, "两读字数量异常，韵书可能读错了")
        for ch in ambiguous[:5]:
            self.assertEqual(self.rhyme.pingze(ch), "通")

    def test_平仄串与名字等长(self):
        """单字标签的意义：pingze 串长度必须等于名字长度。"""
        for nm in ("王安石", "白居易", "清泉", "明月"):
            self.assertEqual(len(self.rhyme.pattern(nm)), len(nm))


class TestSoundFields(unittest.TestCase):
    """声母/韵母必须取自 pypinyin 的 INITIALS / FINALS，不能拿字符串末位字母凑。"""

    def test_李白的韵母不同(self):
        """李 li / 白 bai → i / ai。旧实现比较末位字母 'i'=='i'，误判为同韵母。"""
        self.assertEqual(final("李"), "i")
        self.assertEqual(final("白"), "ai")
        self.assertNotEqual(final("李"), final("白"))

    def test_韩信的韵母不同(self):
        """韩 han / 信 xin → an / in。末位字母都是 n，不能据此判同韵母。"""
        self.assertEqual(final("韩"), "an")
        self.assertEqual(final("信"), "in")
        self.assertNotEqual(final("韩"), final("信"))

    def test_零声母不算同声母(self):
        """「安」是零声母，不应与任何字构成「同声母」。"""
        self.assertEqual(initial("安"), "")
        self.assertEqual(initial("王"), "")

    def test_四声(self):
        self.assertEqual(tone4("清"), 1)
        self.assertEqual(tone4("照"), 4)


class TestOpenness(unittest.TestCase):
    """尾字洪细（D-009）：依据四呼分类，舌尖元音 -i 归洪。"""

    def test_洪细分类(self):
        from shici_namer.phonology import is_open
        # 洪：韵腹 a/o/e/u（含带介音的 iang/üan——介音不改变响度）
        for ch in "扬安昌高波路舒泉远":
            self.assertTrue(is_open(ch), f"{ch} 应为洪音")
        # 细：韵腹 i/ü（in/ing 类收音扁窄）
        for ch in "音心金定君":
            self.assertFalse(is_open(ch), f"{ch} 应为细音")

    def test_舌尖元音归洪(self):
        """石/之/思 的韵母串写作 i（齐齿形），但音韵学上是舌尖元音，属开口呼。"""
        from shici_namer.phonology import is_open
        for ch in "石之思志字":
            self.assertTrue(is_open(ch), f"{ch}（舌尖元音）应为洪音")


class TestRadicals(unittest.TestCase):
    def test_同部首可检出(self):
        """桢/柏 都是木部 → 同义堆叠，应被识别。"""
        cfg = load_config()
        rad = Radicals.load(cfg.path("paths.radical"))
        self.assertEqual(rad.get("桢"), rad.get("柏"))
        self.assertEqual(rad.get("楷"), rad.get("桐"))
        self.assertNotEqual(rad.get("江"), rad.get("山"))


if __name__ == "__main__":
    unittest.main()
