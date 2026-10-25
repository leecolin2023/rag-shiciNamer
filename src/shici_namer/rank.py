"""排序。

**刻意不提供综合加权分。**
「0.4×音韵 + 0.3×出处 + 0.3×罕见度」这类分数无法验证，最后会变成另一种「编出来的数字」。
这里只做**多键字典序排序**，每一维都是可独立核对的客观量，用户可以自己改顺序。

排序项支持方向后缀 `key:asc` / `key:desc`（覆盖该键的默认方向），
让 config 里的排序口径自文档化，如 `corpus_freq:asc` = 语料越稀有越前。
"""
from __future__ import annotations

from typing import Callable

from .models import Candidate

# 字段名 → (取值函数, 默认方向)。'asc' = 值小者前；'desc' = 值大者前。
# 频次类默认降序（常见优先）；标记类与经典度默认升序（false / 诗经=0 优先）。
_FIELDS: dict[str, tuple[Callable[[Candidate], int], str]] = {
    "pingze_interleave": (lambda c: 0 if c.pingze_interleave else 1, "asc"),
    "same_initial":      (lambda c: 1 if c.same_initial else 0, "asc"),
    "same_final":        (lambda c: 1 if c.same_final else 0, "asc"),
    "has_numeral":       (lambda c: 1 if c.has_numeral else 0, "asc"),
    # 地名碎片（D-011）：右邻=行政区划后缀或命中地名志（武强/建平/长安）
    "place_flag":        (lambda c: 1 if c.place_flag else 0, "asc"),
    # 名篇出处（唐诗三百首/楚辞核心等，见 config/famous_sources.txt）优先
    "source_fame":       (lambda c: 0 if c.source_famous else 1, "asc"),
    "best_book_rank":    (lambda c: c.best_book_rank, "asc"),
    # 双界稀有度：语料与人口两个计数里较小者（可用键，但默认序不采用：
    # 全量语料下「一生」min=5 会压过「清扬」min=7，见 D-007 的探索记录）。
    "dual_rarity":       (lambda c: min(c.corpus_freq, c.population_freq), "asc"),
    # ---- 全名听感（D-009）。王维(2-2)/徽音(1-1) 是同调好名，只降权不剔除 ----
    # 全名声调去重数（聂趯趯 4-4-4 = 1 最单调；无姓时记 3 = 中性不惩罚）
    "tone_variety":      (lambda c: c.tone_variety, "desc"),
    # 姓鼻音韵尾 + 名首字零声母（陈恩型连读吞音）
    "junction_liasion":  (lambda c: 1 if c.junction_liasion else 0, "asc"),
    # 尾字洪音收尾（ang/ao 系响亮；i/ü 系扁窄）。放最末：徽音(in)/清泉(üan)
    # 这类细音收尾的好名不应被压制
    "tail_open":         (lambda c: 0 if c.tail_open else 1, "asc"),
    "corpus_freq":       (lambda c: c.corpus_freq, "desc"),
    "population_freq":   (lambda c: c.population_freq, "desc"),
    "book_count":        (lambda c: c.book_count, "desc"),
}

SUPPORTED = tuple(_FIELDS)


def _parse(spec: str) -> tuple[str, str]:
    """`key` / `key:asc` / `key:desc` → (字段名, 方向)。后缀覆盖默认方向。"""
    if ":" in spec:
        key, direction = spec.rsplit(":", 1)
        if direction not in ("asc", "desc"):
            raise ValueError(f"排序方向只能是 asc/desc：{spec}")
        return key, direction
    key = spec
    return key, _FIELDS[key][1]


def rank(
    candidates: list[Candidate],
    *,
    order: list[str] | None = None,
) -> list[Candidate]:
    """按 order 里的键做字典序排序。"""
    order = order or ["has_numeral", "place_flag", "source_fame", "same_final",
                      "dual_rarity", "tone_variety", "junction_liasion", "tail_open",
                      "population_freq:asc", "corpus_freq:asc"]
    try:
        parsed = [_parse(k) for k in order]
    except KeyError:
        unknown = [k for k in order if k.split(":")[0] not in _FIELDS]
        raise ValueError(f"不支持的排序键：{unknown}；可用：{SUPPORTED}")

    keyfuncs: list[Callable[[Candidate], int]] = []
    for key, direction in parsed:
        getter, default_dir = _FIELDS[key]
        negate = (direction == "desc")
        keyfuncs.append((lambda c, f=getter: -f(c)) if negate else getter)

    def key(c: Candidate):
        return tuple(f(c) for f in keyfuncs)

    return sorted(candidates, key=key)
