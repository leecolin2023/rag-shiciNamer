"""导出：JSON（全字段）与 CSV（人读）。"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import Candidate

DEFAULT_COLUMNS = [
    "姓名", "名", "平仄", "今调", "全名声调", "声母", "韵母", "部首", "同部首",
    "性别倾向", "男女比", "语料词频", "真实人口频次", "出处跨书数",
    "首选出处", "首选原句", "全部出处", "尾字洪细",
]


def _row(c: Candidate, surname: str) -> list[str]:
    first = c.sources[0] if c.sources else None
    all_src = " ｜ ".join(f"{s.label()}：「{s.sentence}」" for s in c.sources)
    return [
        f"{surname}{c.name}" if surname else c.name,
        c.name,
        c.pingze,
        "/".join(map(str, c.tones)),
        "/".join(map(str, c.full_tones)),
        "/".join(c.initials),
        "/".join(c.finals),
        "/".join(c.radicals),
        "是" if c.same_radical else "否",
        c.gender,
        f"{c.male}/{c.female}",
        str(c.corpus_freq),
        str(c.population_freq),
        str(c.book_count),
        first.label() if first else "",
        first.sentence if first else "",
        all_src,
        "洪" if c.tail_open else "细",
    ]


def to_json(candidates: list[Candidate], path: Path) -> Path:
    """紧凑序列化：全量候选数万条，带缩进会撑爆内存（人读格式是 CSV/表格）。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [c.to_dict() for c in candidates]
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return path


def to_csv(
    candidates: list[Candidate],
    path: Path,
    *,
    surname: str = "",
    columns: list[str] | None = None,
    encoding: str = "utf-8-sig",
) -> Path:
    columns = columns or DEFAULT_COLUMNS
    if columns != DEFAULT_COLUMNS:
        # 列顺序改了但没改 _row → 直接报错，避免导出错位的 CSV
        raise ValueError(
            "自定义 columns 需要同步修改 export._row()；"
            "若只是想改顺序，请改 DEFAULT_COLUMNS 并同步 tests/test_pipeline.py"
        )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=encoding, newline="") as f:
        w = csv.writer(f)
        w.writerow(columns)
        for c in candidates:
            w.writerow(_row(c, surname))
    return path


def to_markdown_table(candidates: list[Candidate], top: int = 20, surname: str = "") -> str:
    """生成用于报告/对话的紧凑表格。"""
    lines = ["| 名 | 平仄 | 词频 | 人口 | 跨书 | 出处 | 原句 |",
             "|---|---|---|---|---|---|---|"]
    for c in candidates[:top]:
        s = c.sources[0] if c.sources else None
        lines.append(
            f"| {surname}{c.name} | {c.pingze} | {c.corpus_freq} | {c.population_freq} | "
            f"{c.book_count} | {s.label() if s else ''} | {s.sentence[:24] if s else ''} |"
        )
    return "\n".join(lines)
