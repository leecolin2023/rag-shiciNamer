"""摘词：全量 2-gram + 真实姓名库校验。

为什么不用分词器（jieba / pypaddle）：
    「清泉石上流」jieba 切成 `清泉石 / 上流`，把「清泉」吞掉了。
    全量 2-gram 得到 `清泉 / 泉石 / 石上 / 上流`，再用姓名库校验，
    能把它捞回来。实测「清泉」在最终候选里（语料词频 568、人口 95）。

代价：会产生伪词（「其道」「国之」「以成」），因为它们确实出现在姓名库里
（有人叫过这些名字）。这一层由 filter.py 的停用字表处理。

成词证据是**双通道取或**（D-007）：
    ① 该词在真实姓名库中出现 ≥ min_population_freq 次（有人叫过）
    ② 该词在本语料中出现 ≥ min_corpus_freq 次（反复出现，非偶然相邻）
单靠通道① 会漏掉「呦呦」（姓名库频次 0，但《鹿鸣》里出现 3 次）；
单靠通道② 会漏掉只出现一次但确有人名的词。阈值在 config/default.yaml。
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Sequence

from .corpus import Passage, is_cjk, split_sentences
from .lexicon import Lexicon
from .models import Source


@dataclass
class Hit:
    name: str
    corpus_freq: int = 0                 # 语料中出现次数（成词性代理）
    population_freq: int = 0             # 真实姓名库频次
    male: int = 0
    female: int = 0
    sources: list[Source] = field(default_factory=list)
    books: set[str] = field(default_factory=set)
    # 全量出处坐标（"书\t篇"）。sources 只保留前 max_sources 条做展示，
    # 名篇判定（filter._famous_matcher）必须看全量，否则会漏掉
    # 未进前 3 的名篇出处（清泉 的 山居秋暝 就是这样漏掉的）。
    titles: set[str] = field(default_factory=set)
    # 每次出现位置紧随其后的字的计数（句末不记）。语境证据（D-011）：
    # 「武强」的非句末右邻**全部**是 縣/县——它是更长地名的词干，不是词。
    # 带计数是为了支持严格判定（全部右邻均为后缀且 ≥2 次），防偶然共现：
    # 「乔木」31 种右邻里只有 1 个「都」，不能算证据。
    right_chars: Counter[str] = field(default_factory=Counter)


def extract(
    passages: Sequence[Passage],
    lexicon: Lexicon,
    *,
    split_pattern: str,
    length: int = 2,
    min_population_freq: int = 3,
    min_corpus_freq: int = 0,
    corpus_channel: str = "全部",
    max_sources: int = 3,
) -> dict[str, Hit]:
    """枚举每句所有相邻 length-gram，保留通过成词证据双通道的。

    通道②（min_corpus_freq > 1 时启用）需要先知道每个 gram 的总出现次数，
    因此扫两遍：第一遍只计数，第二遍建 hit 收出处。
    corpus_channel 限定通道②的范围："叠字"（叠音词是《诗经》构词法，成词
    证据强）/ "全部" / "关"。返回 {name: Hit}。
    """
    redup_only = corpus_channel == "叠字"
    counts: Counter[str] | None = None
    if min_corpus_freq > 1:
        counts = Counter()
        for psg in passages:
            for sent in split_sentences(psg.text, split_pattern):
                n = len(sent)
                for i in range(n - length + 1):
                    w = sent[i:i + length]
                    if is_cjk(w) and not (redup_only and w[0] != w[-1]):
                        counts[w] += 1

    hits: dict[str, Hit] = {}

    for psg in passages:
        for sent in split_sentences(psg.text, split_pattern):
            n = len(sent)
            if n < length:
                continue
            for i in range(n - length + 1):
                w = sent[i:i + length]
                if not is_cjk(w):
                    continue
                stat = lexicon.get(w)
                pop_ok = stat is not None and stat.n >= min_population_freq
                corpus_ok = (counts is not None and counts.get(w, 0) >= min_corpus_freq
                             and not (redup_only and w[0] != w[-1]))
                if not (pop_ok or corpus_ok):
                    continue

                hit = hits.get(w)
                if hit is None:
                    hit = hits[w] = Hit(
                        name=w,
                        population_freq=stat.n if stat else 0,
                        male=stat.m if stat else 0,
                        female=stat.f if stat else 0,
                    )
                hit.corpus_freq += 1
                hit.books.add(psg.book)
                hit.titles.add(f"{psg.book}\t{psg.title}")
                if i + length < n:
                    hit.right_chars[sent[i + length]] += 1
                if len(hit.sources) < max_sources:
                    hit.sources.append(
                        Source(psg.book, psg.title, psg.author, psg.dynasty, sent)
                    )

    return hits


def sort_sources(hit: Hit, book_rank: dict[str, int]) -> None:
    """按书目优先级排序出处（诗经/楚辞等先秦经典优先）。"""
    hit.sources.sort(key=lambda s: book_rank.get(s.book, 99))
