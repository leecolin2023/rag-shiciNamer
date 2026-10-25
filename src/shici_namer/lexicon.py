"""真实姓名库（Chinese_Names.dat）。

数据格式：每行 `姓名,性别`，性别 ∈ {男, 女, 未知}。
本模块把 3 字姓名（单姓+双字名）切成「名」，统计频次与性别分布。

这是本项目**替代「笔画数吉凶」的量化依据**：
一个名字在 1930–2008 年的真实人口里出现过几次，是可核对的事实，
而「人格 31 是大吉」是 1918 年日本某系统的约定。
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

CJK_RE = re.compile(r"^[\u4e00-\u9fff]+$")


@dataclass
class NameStat:
    n: int = 0      # 总记录数
    m: int = 0      # 男
    f: int = 0      # 女

    @property
    def gender(self) -> str:
        if self.m + self.f == 0:
            return "未知"
        if self.m > self.f:
            return "男"
        if self.f > self.m:
            return "女"
        return "均"


class Lexicon:
    """2 字名 → NameStat。只索引双字名（单字名走另一条路径）。"""

    def __init__(self, stats: dict[str, NameStat]):
        self.stats = stats

    def __len__(self) -> int:
        return len(self.stats)

    def __contains__(self, name: str) -> bool:
        return name in self.stats

    def get(self, name: str, default: NameStat | None = None) -> NameStat | None:
        return self.stats.get(name, default)

    @classmethod
    def load(cls, path: Path) -> "Lexicon":
        counter: Counter[str] = Counter()
        gender: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(
                f"找不到姓名库 {path}。运行 `python data/fetch.py` 下载，"
                f"或修改 config/default.yaml 的 paths.corpus_root。"
            )
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) < 2 or len(parts[0]) < 2:
                    continue
                given = parts[0][1:]          # 去掉姓
                if len(given) != 2 or not CJK_RE.match(given):
                    continue
                counter[given] += 1
                if parts[1] == "男":
                    gender[given][0] += 1
                elif parts[1] == "女":
                    gender[given][1] += 1
        stats = {k: NameStat(n=v, m=gender[k][0], f=gender[k][1]) for k, v in counter.items()}
        return cls(stats)
