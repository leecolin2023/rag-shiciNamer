"""数据模型。全部用 dataclass，便于序列化与类型提示。"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Source:
    """一条出处。"""
    book: str
    title: str = ""
    author: str = ""
    dynasty: str = ""
    sentence: str = ""

    def label(self) -> str:
        s = f"{self.book}·{self.title}" if self.title else self.book
        return f"{s}（{self.author}）" if self.author else s


@dataclass
class Candidate:
    """一个候选名（已通过全部筛选，带全维标注）。"""
    name: str                      # 两字名，不含姓
    sources: list[Source] = field(default_factory=list)
    # 统计
    corpus_freq: int = 0           # 该 2-gram 在语料中作为相邻二字出现的次数
    population_freq: int = 0       # 在真实姓名库中出现的次数
    book_count: int = 0            # 出处跨书数
    male: int = 0
    female: int = 0
    # 音韵
    pingze: str = ""               # 如「平仄」
    tones: list[int] = field(default_factory=list)      # 普通话四声（名内）
    initials: list[str] = field(default_factory=list)
    finals: list[str] = field(default_factory=list)
    places: list[str] = field(default_factory=list)     # 发音部位
    radicals: list[str] = field(default_factory=list)
    # 全名听感（D-009，姓 + 名一起念的维度；未指定姓氏时取中性值不参与降权）
    full_tones: list[int] = field(default_factory=list)  # 姓+名的声调序列
    tone_variety: int = 3            # 全名声调去重数（3=最多样；无姓时记 3 不惩罚）
    junction_liasion: bool = False   # 姓鼻音韵尾 + 名首字零声母 → 连读吞音（陈恩型）
    tail_open: bool = True           # 尾字韵母洪音（响亮收尾）；细音为 False
    # 派生标记
    pingze_interleave: bool = False
    same_initial: bool = False
    same_final: bool = False
    same_radical: bool = False
    has_numeral: bool = False      # 含数字字（数词短语，排序垫后，见 D-007）
    place_flag: bool = False       # 地名碎片（右邻=行政区划后缀，或命中地名志，见 D-011）
    best_book_rank: int = 99       # 最佳出处的经典度（越小越经典，来自 config book_rank）
    source_famous: bool = False    # 任一出处属于名篇目录（唐诗三百首等，见 config/famous_sources.txt）
    gender: str = "未知"           # 男 / 女 / 均 / 未知

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["sources"] = [asdict(s) for s in self.sources]
        return d
