"""配置加载。口径唯一来源是 config/default.yaml，本模块只负责读 + 补默认 + 解析路径。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as e:  # pragma: no cover
    raise ImportError("需要 PyYAML：pip install pyyaml") from e

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Config:
    raw: dict[str, Any]
    root: Path = PROJECT_ROOT

    # ---- 便捷访问 ----
    def get(self, dotted: str, default=None):
        cur: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def path(self, dotted: str) -> Path:
        """解析配置里的相对路径；环境变量 SHICI_DATA_ROOT 可覆盖 corpus_root。"""
        value = self.get(dotted)
        if value is None:
            raise KeyError(f"配置缺少 {dotted}")
        p = Path(value)
        if p.is_absolute():
            return p
        # corpus_root 允许被环境变量覆盖（便于换数据盘）
        if dotted == "paths.corpus_root" and os.environ.get("SHICI_DATA_ROOT"):
            return Path(os.environ["SHICI_DATA_ROOT"]).resolve()
        return (self.root / p).resolve()

    # ---- 常用字段 ----
    @property
    def books(self) -> list[str]:
        return list(self.get("corpus.books", []))

    @property
    def book_rank(self) -> dict[str, int]:
        return dict(self.get("corpus.book_rank", {}))

    @property
    def split_pattern(self) -> str:
        return self.get("corpus.split_pattern", r"[！。？；!?\n\r，、：,]+")

    @property
    def stopwords(self) -> set[str]:
        """从 config/stopwords.txt 读停用字。文件缺失时返回空集并警告。"""
        p = self.path("paths.stopwords")
        out: set[str] = set()
        if not p.exists():
            return out
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # 格式：分类<TAB>字符
            chars = line.split("\t")[-1]
            out.update(ch for ch in chars if "\u4e00" <= ch <= "\u9fff")
        return out

    @property
    def numeral_chars(self) -> set[str]:
        """数字字集（含任一数字字的候选标 has_numeral，排序垫后）。"""
        s = self.get("rank.numeral_chars", "") or ""
        return {ch for ch in s if "\u4e00" <= ch <= "\u9fff"}

    @property
    def place_names(self) -> set[str]:
        """地名志词干（config/place_names.txt，D-011）。文件缺失返回空集。"""
        p = self.path("paths.place_names")
        if not p.exists():
            return set()
        out: set[str] = set()
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                out.add(line)
        return out

    @property
    def place_context_chars(self) -> set[str]:
        """行政区划后缀表（右邻语境证据，D-011）。"""
        s = self.get("filter.place_context_chars", "") or ""
        return {ch for ch in s if "\u4e00" <= ch <= "\u9fff"}

    @property
    def famous_sources(self) -> set[str]:
        """名篇目录，元素为 "书名"（整书）或 "书名\\t篇名"（单篇）。
        文件缺失时返回空集（分级失效）。"""
        p = self.path("paths.famous")
        if not self.get("rank.use_famous", True) or not p.exists():
            return set()
        out: set[str] = set()
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.add(line)
        return out


def load_config(path: str | os.PathLike | None = None) -> Config:
    p = Path(path) if path else PROJECT_ROOT / "config" / "default.yaml"
    if not p.exists():
        raise FileNotFoundError(f"找不到配置文件：{p}")
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    return Config(raw=raw)
