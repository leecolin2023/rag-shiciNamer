"""音韵与字形分析。

三件事，都是上一版（qiming/）踩过坑之后改的：

1. **平仄用平水韵，不用普通话四声。**
   入声字（石/白/轼/陆/牧/若/疾）在现代普通话里散入四声，用四声判平仄会失真。
   例：王安石 — 普通话「平平平」，平水韵「平平仄」。

2. **声母用 Style.INITIALS，韵母用 Style.FINALS。**
   上一版拿拼音字符串的末位字母冒充韵母，「李li/白bai」被判成同韵母（实际 i/ai）。

3. **同声母/同韵母只是特征，不是缺陷。**
   双声（参差、清泉）、叠韵（窈窕）是汉语的修辞美，不能当噪声删掉。
"""
from __future__ import annotations

import json
from pathlib import Path

from pypinyin import Style, lazy_pinyin

# 声母 → 发音部位（用于判断连读是否拗口）
PLACE: dict[str, str] = {}
for _chars, _place in [
    ("bpmf", "唇"), ("dtnl", "舌尖中"), ("gkh", "舌根"),
    ("jqx", "舌面"), ("zhchshr", "翘舌"), ("zcs", "平舌"),
]:
    for _c in _chars:
        PLACE[_c] = _place
PLACE[""] = "零"


def initial(ch: str) -> str:
    """真·声母；零声母返回空串。"""
    return lazy_pinyin(ch, style=Style.INITIALS, strict=True)[0]


def final(ch: str) -> str:
    """真·韵母。"""
    return lazy_pinyin(ch, style=Style.FINALS, strict=True)[0]


def tone4(ch: str) -> int:
    """普通话四声（1-4），无法判定返回 0。"""
    s = lazy_pinyin(ch, style=Style.TONE3, neutral_tone_with_five=True)[0]
    digits = [c for c in s if c.isdigit()]
    return int(digits[-1]) if digits else 0


def place(ch: str) -> str:
    return PLACE.get(initial(ch), "?")


# 舌尖元音字（zhi/chi/shi/ri/zi/ci/si）：韵母串写作 i，但音韵学上属开口呼（洪音）
_APICAL_INITIALS = {"zh", "ch", "sh", "r", "z", "c", "s"}


def is_open(ch: str) -> bool:
    """尾字韵母洪细（D-009）。按**韵腹**判（介音不算）：洪 = 韵腹为
    a/o/e/u（如 ang/iang/uan/üan/ao/u，收音响亮），细 = 韵腹为 i/ü
    （如 in/ing/ün，收音扁窄）。舌尖元音 -i（石/之/思）按开口呼归洪。
    依据：元音响度 a>o>e>u>ü>i（四呼中介音不改变响度，故 泉 üan 判洪）。
    用于「名的尾字收音是否响亮」。"""
    f = final(ch)
    if f == "i" and initial(ch) in _APICAL_INITIALS:
        return True
    # 去介音：i/u/ü 后跟其他元音时是介音（iang→ang，van→an，ue→e）
    core = f
    if len(f) >= 2 and f[0] in "iuv" and f[1] in "aoe":
        core = f[1:]
    return core[0] in "aoeu"


class RhymeBook:
    """平水韵 / 中华新韵 / 广韵。提供中古平仄判定。"""

    def __init__(self, mapping: dict[str, str], book: str):
        self._m = mapping
        self.book = book

    def pingze(self, ch: str) -> str:
        """返回单字标签：'平' | '仄' | '通'（两读）| '?'
        刻意用单字，保证 len(pingze_string) == len(name)，便于逐位对齐。"""
        return self._m.get(ch, "?")

    def pattern(self, name: str) -> str:
        return "".join(self.pingze(c) for c in name)

    @classmethod
    def load(cls, path: Path, book: str = "平水韵") -> "RhymeBook":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"找不到韵书 {path}。运行 `python data/fetch.py` 下载 rhymebooks.json。"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        if book not in data:
            raise KeyError(f"韵书里没有「{book}」，可选：{list(data)}")
        ping_groups, ze_groups = data[book][0], data[book][1]
        ping: set[str] = set()
        ze: set[str] = set()
        for g in ping_groups:
            ping.update(g)
        for g in ze_groups:
            ze.update(g)
        mapping: dict[str, str] = {}
        for ch in ping | ze:
            if ch in ping and ch in ze:
                mapping[ch] = "通"      # 两读通用，不参与平仄交错判定
            elif ch in ping:
                mapping[ch] = "平"
            else:
                mapping[ch] = "仄"
        return cls(mapping, book)


class Radicals:
    """康熙字典数据的部首字段。只用于「同部首 → 同义堆叠」检测。"""

    def __init__(self, mapping: dict[str, str]):
        self._m = mapping

    def get(self, ch: str) -> str:
        return self._m.get(ch, "")

    @classmethod
    def load(cls, path: Path) -> "Radicals":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"找不到康熙字典数据 {path}。运行 `python data/fetch.py` 下载。"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls({r["character"]: r.get("radical", "") for r in data.get("data", [])})
