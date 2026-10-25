"""手足名配对挖掘：从两份（或一份）榜单 JSON 里找互相关联的名字对。

    python tools/sibling_pairs.py outputs/nie_boy.json outputs/nie_girl.json
    python tools/sibling_pairs.py outputs/nie_boy.json            # 同池两两配对

关联类型（按证据强度排序）：
    同句        两个名摘自**同一句原文**（如「既明且哲」→ 明哲/保身 式）
    同字·同位   共用一个字且位置相同（怀永/怀瑾：伯仲式排行感最强）
    同字        共用一个字
    同篇        出处篇目相同（诗篇内部的呼应）

每对的质量由两人的榜单名次保证（名次之和排序）；词义接近/互补没有客观
度量，属主观层——本工具只出客观关联，语义判断由用户看表完成（D-003）。
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

TYPE_ORDER = ("同句", "同字·同位", "同字", "同篇")


def load(path: str) -> list[dict]:
    pool = json.loads(Path(path).read_text(encoding="utf-8"))
    for i, c in enumerate(pool):
        c["_rank"] = i + 1
        c["_pool"] = Path(path).stem
    return pool


def index(pool: list[dict]) -> tuple[dict, dict, dict]:
    by_char: dict[str, list] = defaultdict(list)
    by_title: dict[tuple, list] = defaultdict(list)
    by_sentence: dict[str, list] = defaultdict(list)
    for c in pool:
        for ch in set(c["name"]):
            by_char[ch].append(c)
        for s in c["sources"]:
            by_title[(s["book"], s["title"])].append(c)
            by_sentence[s["sentence"]].append(c)
    return by_char, by_title, by_sentence


def collect(by_a, by_b, cross: bool, kind: str) -> list:
    """桶内/桶间两两配对（倒排索引，避免 O(N²)）。"""
    seen: set = set()
    out = []
    for key in set(by_a) & set(by_b):
        bucket_a, bucket_b = by_a[key], by_b[key]
        it = ((x, y) for x in bucket_a for y in bucket_b) if cross else combinations(by_b[key], 2)
        for x, y in it:
            if x["name"] == y["name"]:
                continue
            k = (kind, *sorted((x["name"], y["name"])))
            if k in seen:
                continue
            seen.add(k)
            shared = set(x["name"]) & set(y["name"])
            if kind == "句" and shared:
                continue                     # 同句且同字 → 归同字类，不重复计
            if kind == "字":
                if not shared:
                    continue
                same_pos = any(x["name"][i] == ch == y["name"][i] for i, ch in enumerate(x["name"]))
                out.append(("同字·同位" if same_pos else "同字", x, y))
            elif kind == "篇" and not shared:
                out.append(("同篇", x, y))
            elif kind == "句" and not shared:
                out.append(("同句", x, y))
    return out


def mine(pool_a: list[dict], pool_b: list[dict] | None) -> list:
    cross = pool_b is not None
    b = pool_b or pool_a
    ca, ta, sa = index(pool_a)
    cb, tb, sb = index(b)
    out = collect(sa, sb, cross, "句")
    out += collect(ca, cb, cross, "字")
    out += collect(ta, tb, cross, "篇")
    # 类型去重：一对若已有更强关联，保留最强的
    best: dict[tuple, tuple] = {}
    for t, x, y in out:
        k = tuple(sorted((x["name"], y["name"])))
        if k not in best or TYPE_ORDER.index(t) < TYPE_ORDER.index(best[k][0]):
            best[k] = (t, x, y)
    return sorted(best.values(), key=lambda p: p[1]["_rank"] + p[2]["_rank"])


def render(pairs: list, top: int = 12, rank_cap: int = 1500) -> str:
    lines = []
    for typ in TYPE_ORDER:
        sub = [p for p in pairs if p[0] == typ
               and p[1]["_rank"] <= rank_cap and p[2]["_rank"] <= rank_cap][:top]
        if not sub:
            continue
        lines.append(f"\n## {typ}（前 {len(sub)}，按名次之和；双方均在前 {rank_cap} 名）\n")
        lines.append("| 组合 | 名次 | 出处 |")
        lines.append("|---|---|---|")
        for _, x, y in sub:
            if typ == "同句":
                shared = ({s["sentence"] for s in x["sources"]}
                          & {s["sentence"] for s in y["sources"]})
                sent = sorted(shared, key=len)[-1] if shared else ""
                src = next(s for s in x["sources"] if s["sentence"] == sent)
                line = f"「{sent[:16]}」{src['book']}·{src['title'][:8]}"
            else:
                s1, s2 = x["sources"][0], y["sources"][0]
                line = (f"「{s1['sentence'][:14]}」{s1['book']}·{s1['title'][:8]}<br>"
                        f"「{s2['sentence'][:14]}」{s2['book']}·{s2['title'][:8]}")
            lines.append(f"| **{x['name']} × {y['name']}** "
                         f"| #{x['_rank']} × #{y['_rank']} | {line} |")
    return "\n".join(lines)


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        return 2
    pool_a = load(sys.argv[1])
    pool_b = load(sys.argv[2]) if len(sys.argv) == 3 else None
    label = f"{pool_a[0]['_pool']} × {pool_b[0]['_pool']}" if pool_b else f"{pool_a[0]['_pool']} 同池"
    pairs = mine(pool_a, pool_b)
    print(f"{label}：候选对 {len(pairs)} 个")
    report = f"# 手足名配对 · {label}\n{render(pairs)}\n"
    out = Path("outputs") / f"sibling_{label.replace(' ', '_').replace('×', 'x')}.md"
    out.write_text(report, encoding="utf-8")
    print(f"报告 → {out}")
    print(report[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
