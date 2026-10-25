"""主管线：加载 → 摘词 → 筛选 → 排序 → 导出。

只做编排，不含业务口径（口径全在 config/default.yaml）。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Config, load_config
from .corpus import iter_corpus
from .export import to_csv, to_json
from .extract import extract
from .filter import FilterStats, apply_filters
from .lexicon import Lexicon
from .models import Candidate
from .phonology import Radicals, RhymeBook
from .rank import rank


@dataclass
class RunResult:
    candidates: list[Candidate]
    stats: dict[str, Any] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.candidates)

    def top(self, n: int = 20) -> list[Candidate]:
        return self.candidates[:n]


def run(
    *,
    config: Config | None = None,
    surname: str | None = None,
    sex: str | None = None,
    books: list[str] | None = None,
    keep_same_radical: bool = False,
    out_json: Path | str | None = None,
    out_csv: Path | str | None = None,
    progress: bool = True,
) -> RunResult:
    """跑完整条管线。

    参数
    ----
    config              配置对象；None 则读 config/default.yaml
    surname             姓氏（用于排除同声母/同韵母/同字）；None 则不过滤
    sex                 "男" / "女" / None
    books               覆盖配置里的语料范围
    keep_same_radical   True = 不剔除同部首
    out_json / out_csv  导出路径；None 则只返回内存结果
    """
    t0 = time.time()
    cfg = config or load_config()
    book_list = books or cfg.books
    book_rank = cfg.book_rank

    def log(msg: str):
        if progress:
            print(msg, flush=True)

    log(f"[1/5] 加载姓名库 …")
    lexicon = Lexicon.load(cfg.path("paths.corpus_root") / "Chinese_Names.dat")
    log(f"      2 字名 {len(lexicon)} 个")

    log(f"[2/5] 加载韵书 + 部首 …")
    rhyme = RhymeBook.load(cfg.path("paths.rhyme"), cfg.get("phonology.rhyme_book", "平水韵"))
    radicals = Radicals.load(cfg.path("paths.radical"))
    log(f"      韵书 {rhyme.book}，部首表 {len(radicals._m)} 字")

    log(f"[3/5] 加载语料 {book_list} …")
    passages = list(iter_corpus(cfg.path("paths.corpus_root"), book_list))
    log(f"      {len(passages)} 段")

    log(f"[4/5] 摘词（{cfg.get('extract.length', 2)}-gram + 姓名/语料双通道校验）…")
    hits = extract(
        passages,
        lexicon,
        split_pattern=cfg.split_pattern,
        length=cfg.get("extract.length", 2),
        min_population_freq=cfg.get("extract.min_population_freq", 3),
        min_corpus_freq=cfg.get("extract.min_corpus_freq", 0),
        corpus_channel=cfg.get("extract.corpus_channel", "全部"),
        max_sources=cfg.get("extract.max_sources", 3),
    )
    log(f"      命中 {len(hits)} 个")

    log(f"[5/5] 筛选 + 排序 …")
    candidates, fstats = apply_filters(
        hits,
        stopwords=cfg.stopwords,
        radicals=radicals,
        rhyme=rhyme,
        book_rank=book_rank,
        surname=surname,
        sex=sex,
        gender_ratio=cfg.get("filter.gender_ratio", 0.75),
        use_stopwords=cfg.get("filter.use_stopwords", True),
        drop_same_radical=cfg.get("filter.drop_same_radical", True) and not keep_same_radical,
        numeral_chars=cfg.numeral_chars,
        famous_sources=cfg.famous_sources,
        place_context_chars=cfg.place_context_chars,
        place_names=cfg.place_names,
    )
    # 出处按书目优先级排序（诗经/楚辞等先秦经典优先展示）
    for c in candidates:
        c.sources.sort(key=lambda s: book_rank.get(s.book, 99))

    ranked = rank(
        candidates,
        order=cfg.get("rank.order"),
    )
    log(f"      候选 {len(ranked)} 个")

    stats = {
        "books": book_list,
        "passages": len(passages),
        "hits": len(hits),
        "filters": fstats.as_dict(),
        "final": len(ranked),
        "surname": surname,
        "sex": sex,
        "elapsed_sec": round(time.time() - t0, 1),
    }

    if out_json:
        to_json(ranked, Path(out_json))
    if out_csv:
        to_csv(
            ranked, Path(out_csv),
            surname=surname or "",
            columns=cfg.get("export.columns"),
            encoding=cfg.get("export.csv_encoding", "utf-8-sig"),
        )

    return RunResult(candidates=ranked, stats=stats)
