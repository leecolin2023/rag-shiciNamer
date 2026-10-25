"""命令行入口。

用法见 AGENTS.md「快速开始」，或 `python -m shici_namer --help`。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import PROJECT_ROOT, load_config
from .export import to_markdown_table
from .pipeline import run


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="shici-namer",
        description="从古典诗词里摘词取名（2-gram 摘词 + 真实姓名库校验）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例
----
# 全量候选
python -m shici_namer --top 40

# 聂姓男孩（排除与姓连读拗口的）
python -m shici_namer --xing 聂 --sex 男 --top 30 --csv 聂.csv

# 只要平仄交错的（注意：杜甫「仄仄」不符合此条件，但它仍是好名字）
python -m shici_namer --require-pingze --top 30
""",
    )
    p.add_argument("--config", type=Path, default=None, help="配置文件，默认 config/default.yaml")
    p.add_argument("--xing", default=None, help="姓氏，用于排除同声母/同韵母/同字")
    p.add_argument("--sex", choices=["男", "女"], default=None, help="性别倾向筛选")
    p.add_argument("--books", default=None, help="逗号分隔的语料范围，如 诗经,楚辞,唐诗")
    p.add_argument("--top", type=int, default=30, help="终端展示条数（不影响导出）")
    p.add_argument("--require-pingze", action="store_true", help="只保留平仄交错的")
    p.add_argument("--keep-same-radical", action="store_true", help="不剔除同部首（同义堆叠）")
    p.add_argument("--json", dest="out_json", default=None, help="导出 JSON 路径")
    p.add_argument("--csv", dest="out_csv", default=None, help="导出 CSV 路径")
    p.add_argument("--quiet", action="store_true", help="不打印进度")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    books = [b.strip() for b in args.books.split(",")] if args.books else None

    result = run(
        config=cfg,
        surname=args.xing,
        sex=args.sex,
        books=books,
        keep_same_radical=args.keep_same_radical,
        out_json=args.out_json,
        out_csv=args.out_csv,
        progress=not args.quiet,
    )

    cands = result.candidates
    if args.require_pingze:
        cands = [c for c in cands if c.pingze_interleave]

    print()
    print(f"统计：{result.stats}")
    print()
    print(to_markdown_table(cands, top=args.top, surname=args.xing or ""))
    if args.out_json:
        print(f"\nJSON → {args.out_json}")
    if args.out_csv:
        print(f"CSV  → {args.out_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
