"""筛选：停用字 → 同部首 → 姓氏冲突 → 性别倾向。

每一步都是**独立可关闭**的，方便做消融对比（见 tests/test_pipeline.py 的计数断言）。
"""
from __future__ import annotations

from dataclasses import dataclass

from .extract import Hit
from .phonology import Radicals, final, initial, is_open as _is_open
from .models import Candidate


@dataclass
class FilterStats:
    """每一步砍掉多少，用于回归测试与报告。"""
    input: int = 0
    dropped_stopword: int = 0
    dropped_radical: int = 0
    dropped_gender: int = 0
    dropped_surname: int = 0
    output: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "input": self.input,
            "dropped_stopword": self.dropped_stopword,
            "dropped_radical": self.dropped_radical,
            "dropped_gender": self.dropped_gender,
            "dropped_surname": self.dropped_surname,
            "output": self.output,
        }


def place_context_flag(right_chars, suffixes: set[str]) -> bool:
    """语境证据的**严格**判定（D-011）：非句末右邻全部是行政区划后缀、
    且后缀出现 ≥2 次（证据下限，防小样本偶然共现）。
    武强 右邻={縣:1,县:1} → True；乔木 31 种右邻含 1 个「都」→ False。"""
    if not right_chars:
        return False
    total = sum(right_chars.values())
    suffix_count = sum(n for ch, n in right_chars.items() if ch in suffixes)
    return total >= 2 and suffix_count == total


def surname_conflict(name: str, surname: str) -> str | None:
    """名字与姓氏的连读冲突：同字 / 同声母 / 同韵母。"""
    if surname in name:
        return "与姓同字"
    if initial(name[0]) and initial(name[0]) == initial(surname):
        return "与姓同声母"
    if final(name[0]) == final(surname):
        return "与姓同韵母"
    return None


def junction_liasion(name: str, surname: str | None) -> bool:
    """姓的韵尾是鼻音（-n/-ng）且名首字零声母 → 连读吞音（D-009）。
    例：「陈恩」chén-ēn 连读成一个半音节，「王安世」同理。只降权不剔除。"""
    if not surname or initial(name[0]):
        return False
    return final(surname).endswith(("n", "ng"))


def _famous_matcher(famous: set[str]):
    """预分组名篇目录。三种命中：
    整书行「诗经」（对 hit.books 判定）；精确行「唐诗\\t山居秋暝」；
    篇组前缀「楚辞\\t九歌」→「九歌·湘夫人」。对 hit.titles（全量出处坐标）判定。"""
    whole: set[str] = set()
    exact: set[str] = set()
    prefix: dict[str, list[str]] = {}
    for entry in famous:
        if "\t" not in entry:
            whole.add(entry)
            continue
        book, _, seg = entry.partition("\t")
        exact.add(entry)
        prefix.setdefault(book, []).append(seg)

    def is_famous(books: set[str], titles: set[str]) -> bool:
        if books & whole:
            return True
        for t in titles:
            if t in exact:
                return True
            book, _, title = t.partition("\t")
            for seg in prefix.get(book, ()):
                if title == seg or title.startswith(seg + "·"):
                    return True
        return False

    return is_famous


def apply_filters(
    hits: dict[str, Hit],
    *,
    stopwords: set[str],
    radicals: Radicals,
    rhyme,
    book_rank: dict[str, int],
    surname: str | None = None,
    sex: str | None = None,
    gender_ratio: float = 0.75,
    use_stopwords: bool = True,
    drop_same_radical: bool = True,
    numeral_chars: set[str] | None = None,
    famous_sources: set[str] | None = None,
    place_context_chars: set[str] | None = None,
    place_names: set[str] | None = None,
) -> tuple[list[Candidate], FilterStats]:
    stats = FilterStats(input=len(hits))
    out: list[Candidate] = []
    is_famous = _famous_matcher(famous_sources or set())

    for name, hit in hits.items():
        # ① 停用字
        if use_stopwords and (name[0] in stopwords or name[1] in stopwords):
            stats.dropped_stopword += 1
            continue

        r0, r1 = radicals.get(name[0]), radicals.get(name[1])
        # 叠字名（呦呦/关关/肃肃）是《诗经》修辞典故，不算「两个不同字的同义堆叠」，
        # 豁免同部首剔除；该规则只针对 桢柏/楷桐 这类两字同指一类事物。
        same_rad = bool(r0) and r0 == r1 and name[0] != name[1]

        # ② 同部首（同义堆叠：桢柏、楷桐）
        if drop_same_radical and same_rad:
            stats.dropped_radical += 1
            continue

        # ③ 性别倾向
        total = hit.male + hit.female
        if sex == "男" and total and hit.male / total < gender_ratio:
            stats.dropped_gender += 1
            continue
        if sex == "女" and total and hit.female / total < gender_ratio:
            stats.dropped_gender += 1
            continue

        # ④ 姓氏冲突
        if surname and surname_conflict(name, surname):
            stats.dropped_surname += 1
            continue

        pz = "".join(rhyme.pingze(c) for c in name)
        tones = [_tone4(c) for c in name]
        full_tones = ([_tone4(surname)] + tones) if surname else tones
        cand = Candidate(
            name=name,
            sources=hit.sources,
            corpus_freq=hit.corpus_freq,
            population_freq=hit.population_freq,
            book_count=len(hit.books),
            male=hit.male,
            female=hit.female,
            pingze=pz,
            tones=tones,
            full_tones=full_tones,
            tone_variety=len(set(full_tones)) if surname else 3,   # 无姓时中性，不惩罚
            junction_liasion=junction_liasion(name, surname),
            tail_open=_is_open(name[-1]),
            initials=[initial(c) for c in name],
            finals=[final(c) for c in name],
            places=[_place(c) for c in name],
            radicals=[r0, r1],
            pingze_interleave=(set(pz) == {"平", "仄"}),
            same_initial=bool(initial(name[0])) and initial(name[0]) == initial(name[1]),
            same_final=final(name[0]) == final(name[1]),
            same_radical=same_rad,
            has_numeral=bool(numeral_chars) and (name[0] in numeral_chars or name[1] in numeral_chars),
            # 地名碎片（D-011）：语境严格判定（每次非句末出现都接后缀）或地名志命中。
            # 降权不剔除——跨界词（观清都 之 观清）读感尚可，硬剔会误伤。
            place_flag=place_context_flag(hit.right_chars, place_context_chars or set())
                      or name in (place_names or set()),
            best_book_rank=min((book_rank.get(b, 99) for b in hit.books), default=99),
            source_famous=is_famous(hit.books, hit.titles),
        )
        if hit.male + hit.female == 0:
            cand.gender = "未知"
        elif hit.male > hit.female:
            cand.gender = "男"
        elif hit.female > hit.male:
            cand.gender = "女"
        else:
            cand.gender = "均"
        out.append(cand)

    stats.output = len(out)
    return out, stats


# 局部导入避免循环
def _tone4(ch: str) -> int:
    from .phonology import tone4
    return tone4(ch)


def _place(ch: str) -> str:
    from .phonology import place
    return place(ch)
