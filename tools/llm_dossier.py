"""生成供大模型评审的候选档案（D-011 的 L3 层输入）。

    python tools/llm_dossier.py outputs/nie_male_l3.json --top 100

产出一个紧凑的 Markdown 档案：名次、全名（含姓，供谐音判断）、声调、
洪细、人口性别、名篇标记、全部出处的原句。配合 docs/LLM_JUDGE.md 的
提示词模板使用——大模型只做语义/谐音/碎片的审美判断，所有事实必须
来自本档案，不得编造。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pool", help="榜单 JSON（pipeline --json 产物）")
    ap.add_argument("--top", type=int, default=100)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    pool = json.loads(Path(args.pool).read_text(encoding="utf-8"))
    rows = []
    for i, c in enumerate(pool[: args.top], 1):
        srcs = "<br>".join(
            f"{s['book']}·{s['title'][:12]}「{s['sentence'][:20]}」" for s in c["sources"]
        )
        full = f"聂{c['name']}" if "聂" in args.pool else c["name"]
        warn = " ⚠地名" if c.get("place_flag") else ""
        rows.append(
            f"| {i} | {c['name']} | {full} | {'-'.join(map(str, c['full_tones']))} "
            f"| {'洪' if c['tail_open'] else '细'} | {c['male']}/{c['female']} "
            f"| {'✓' if c['source_famous'] else ''}{warn} | {srcs} |"
        )

    title = Path(args.pool).stem
    md = (
        f"# LLM 评审档案 · {title} · 前 {len(rows)} 名\n\n"
        "字段均为程序实测，可直接核对：名次（管线口径 D-007~D-011）｜名｜全名｜"
        "全名声调（姓+名）｜尾字洪细｜真实人口（男/女，0/0=库中无记录的通用名）｜"
        "名篇✓｜出处与原句（节选）。\n\n"
        "| # | 名 | 全名 | 声调 | 尾 | 人口(男/女) | 标记 | 出处·原句 |\n"
        "|---|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n"
    )
    out = Path(args.out or f"outputs/llm_dossier_{title}.md")
    out.write_text(md, encoding="utf-8")
    print(f"{out}: {len(rows)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
