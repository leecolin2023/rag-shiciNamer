"""语料加载。

数据契约（每个语料文件的结构）见 data/README.md。
本模块只做「读文件 → 摊平成一维句子流」，不做任何筛选。

产出的 Sentence 流会被 extract.py 枚举 2-gram。
"""
from __future__ import annotations

import glob
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

CJK_RE = re.compile(r"^[\u4e00-\u9fff]+$")


@dataclass
class Passage:
    book: str
    title: str
    text: str
    author: str = ""
    dynasty: str = ""


def _read_json(path: Path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def iter_corpus(corpus_root: Path, books: list[str]) -> Iterator[Passage]:
    """按书目产出 Passage。缺失的书目文件会被静默跳过并计数（由调用方报告）。"""
    root = Path(corpus_root)

    # 诗经：list[{title, chapter, section, content: [line,...]}]
    if "诗经" in books:
        p = root / "诗经.json"
        if p.exists():
            for poem in _read_json(p):
                for line in poem.get("content", []):
                    yield Passage("诗经", poem.get("title", ""), line, dynasty="先秦")

    # 楚辞：优先读带篇名的 楚辞.json（[{title, section, author, content:[line,...]}]，
    # 篇名用于名篇分级）；退回纯文本 楚辞.txt（一行一句段，无篇名）
    if "楚辞" in books:
        p = root / "楚辞.json"
        if p.exists():
            for poem in _read_json(p):
                title = poem.get("title", "")
                section = poem.get("section", "")
                label = title if title == section or not section else f"{section}·{title}"
                for line in poem.get("content", []):
                    if len(line.strip()) >= 2:
                        yield Passage("楚辞", label, line,
                                      author=poem.get("author", ""), dynasty="先秦")
        else:
            p = root / "楚辞.txt"
            if p.exists():
                for line in p.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if len(line) >= 4:
                        yield Passage("楚辞", "", line, dynasty="先秦")

    # 论语：list[{chapter, paragraphs: [line,...]}]
    if "论语" in books:
        p = root / "论语.json"
        if p.exists():
            for ch in _read_json(p):
                for line in ch.get("paragraphs", []):
                    yield Passage("论语", ch.get("chapter", ""), line, author="孔子", dynasty="先秦")

    # 周易：纯文本
    if "周易" in books:
        p = root / "周易.txt"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if len(line) >= 4:
                    yield Passage("周易", "", line, dynasty="先秦")

    # 唐诗 / 宋诗 / 宋词：list[{title, author, paragraphs|content: [...]}]
    # 宋词（chinese-poetry ci 系）没有 title，词牌在 rhythmic 字段且不唯一——
    # 标题统一为「词牌·首句片段」以支持名篇匹配（与 gushi_namer 目录格式对齐）；
    # 文件里混有作者简介条目（无 paragraphs），自然跳过。
    for book in ("唐诗", "宋诗", "宋词"):
        if book not in books:
            continue
        for fp in sorted(glob.glob(str(root / book / "*.json"))):
            base = os.path.basename(fp)
            if "authors" in base or base.startswith("author"):
                continue
            try:
                data = _read_json(Path(fp))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue  # 语料里有少量损坏文件，跳过并计入统计
            if not isinstance(data, list):
                continue
            for poem in data:
                if not isinstance(poem, dict):
                    continue
                title = poem.get("title") or ""
                author = poem.get("author", "")
                lines = poem.get("paragraphs") or poem.get("content") or []
                if not title and poem.get("rhythmic") and lines:
                    head = re.split(r"[，。？！,、；;]", str(lines[0]))[0]
                    title = f"{poem['rhythmic']}·{head.strip()}"
                for line in lines:
                    yield Passage(book, title, line, author=author, dynasty=book[0])


def split_sentences(text: str, pattern: str) -> list[str]:
    """按标点切句。逗号也切——2-gram 只需要相邻两字，不需要完整句。"""
    return [s.strip() for s in re.split(pattern, text) if len(s.strip()) >= 2]


def is_cjk(s: str) -> bool:
    return bool(CJK_RE.match(s))
