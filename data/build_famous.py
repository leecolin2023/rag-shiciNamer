"""重建 config/famous_sources.txt（名篇目录，D-007 的口径数据）。

    python data/build_famous.py

输入（data/upstream/，缺哪个就跳过哪种）：
    tangshi300.json     蘅塘退士《唐诗三百首》320 首目录（holynova/gushi_namer）
    songci300_src.json  朱祖谋《宋词三百首》选目 222 首（同上，标题格式「词牌·首句」）
    STCharacters.txt    OpenCC 简→繁单字映射（byvoid/opencc）

唐诗语料（chinese-poetry 全唐诗）标题是**繁体**，三百首目录是简体，
所以唐三百条目繁简各写一行；宋词语料没有 title 字段，corpus.py 把
标题统一成「词牌·首句」，与 gushi_namer 目录格式对齐。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / "data" / "upstream"
OUT = ROOT / "config" / "famous_sources.txt"


def load_t2s_map() -> dict[str, str]:
    """OpenCC STCharacters：简 → 该字首个繁体映射（标题场景够用，
    一简多繁选错只是少命中一首，不会误命中）。"""
    m: dict[str, str] = {}
    p = UP / "STCharacters.txt"
    if not p.exists():
        return m
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "\t" not in line:
            continue
        simp, trads = line.split("\t", 1)
        first = trads.split(" ")[0]
        if simp and first:
            m[simp] = first
    return m


def to_traditional(title: str, t2s: dict[str, str]) -> str:
    return "".join(t2s.get(ch, ch) for ch in title)


def main() -> None:
    lines = [
        "# 名篇目录：两种行式——",
        "#   `书名`（无 TAB）         整书皆为经典出处",
        "#   `书名<TAB>篇名`          指定篇目（或篇组）为经典出处",
        "# 命中任一出处的候选标 source_famous，排序键 source_fame 将其排前（D-007）。",
        "# 本文件由 data/build_famous.py 生成，手改会被覆盖。",
        "# 依据（可核对）：",
        "#   诗经/论语/周易  整书即经典（五经/四书，无需分级）",
        "#   楚辞  王逸《楚辞章句》核心篇目（离骚/九歌/天问/九章/远游/卜居/渔父）",
        "#   唐诗  蘅塘退士《唐诗三百首》320 首目录；语料标题为繁体，故繁简各一行",
        "#   宋词  朱祖谋《宋词三百首》选目 222 首；标题格式「词牌·首句」与语料对齐",
        "# 楚辞条目按篇组名匹配，如「九歌」命中「九歌·湘夫人」。",
        "",
        "诗经",
        "论语",
        "周易",
        "",
    ]
    lines += [f"楚辞\t{s}" for s in ("离骚", "九歌", "天问", "九章", "远游", "卜居", "渔父")]

    t2s = load_t2s_map()
    tang = json.loads((UP / "tangshi300.json").read_text(encoding="utf-8"))
    n_t = 0
    for p in tang:
        title = p["title"].strip()
        lines.append(f"唐诗\t{title}")
        trad = to_traditional(title, t2s)
        if trad != title:
            lines.append(f"唐诗\t{trad}")
        n_t += 1

    song = json.loads((UP / "songci300_src.json").read_text(encoding="utf-8"))
    for p in song:
        title = p["title"].strip()
        lines.append(f"宋词\t{title}")
        trad = to_traditional(title, t2s)
        if trad != title:
            lines.append(f"宋词\t{trad}")   # 宋词语料简繁混排，双份收录

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{OUT}: 唐三百 {n_t} 首（含繁体变体共 {sum(1 for l in lines if l.startswith('唐诗'))} 行），"
          f"宋词 {len(song)} 首，合计 {sum(1 for l in lines if l and not l.startswith('#'))} 行")


if __name__ == "__main__":
    main()
