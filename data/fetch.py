"""数据准备：检查 / 复制 / 下载。

项目不打包数据（语料 + 姓名库约 300 MB）。二选一：
  A. 直接指向本机已有的数据目录（改 config 或设 SHICI_DATA_ROOT）
  B. 用本脚本把数据收集到 data/upstream/，成为自包含项目

常用：
    python data/fetch.py --check
    python data/fetch.py --link-to data/upstream --from ../research/repos/NanBox_PiPiName/data
    python data/fetch.py --download rhymebooks
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / "data" / "upstream"

# 文件名 → (是否必需, 最小字节数, 下载 URL)
# 路径相对于 corpus_root
REQUIRED: dict[str, tuple[bool, int, str | None]] = {
    "Chinese_Names.dat": (
        True, 1_000_000,
        "https://raw.githubusercontent.com/wrk226/get_chinese_name/master/data/Chinese_Names.dat",
    ),
    "诗经.json": (
        True, 100_000,
        "https://raw.githubusercontent.com/holynova/gushi_namer/master/public/json/shijing.json",
    ),
    "楚辞.txt": (False, 50_000, None),
    "论语.json": (False, 50_000, None),
    "周易.txt": (False, 50_000, None),
    "唐诗": (False, 1, None),
    "宋诗": (False, 1, None),
    "宋词": (False, 1, None),
}

SIDE_FILES: dict[str, tuple[str, str]] = {
    # 目标相对路径 → (用途, 下载 URL)
    "rhymebooks.json": (
        "平水韵韵书（LingDong-/cope）",
        "https://raw.githubusercontent.com/LingDong-/cope/master/data/rhymebooks.json",
    ),
    "kangxi.json": (
        "康熙字典数据（含部首），来自 hunterlau2020/bename（注意默认分支是 master）",
        "https://raw.githubusercontent.com/hunterlau2020/bename/master/data/kangxi.json",
    ),
    "诗经.json": (
        "诗经 305 篇（chinese-poetry 标准结构，含 chapter/section）",
        "https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/master/"
        "%E8%AF%97%E7%BB%8F/shijing.json",
    ),
    "楚辞.json": (
        "楚辞 65 篇（带篇名，名篇分级必需）",
        "https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/master/"
        "%E6%A5%9A%E8%BE%9E/chuci.json",
    ),
    "tangshi300.json": (
        "唐诗三百首目录（名篇分级，见 config/famous_sources.txt）",
        "https://raw.githubusercontent.com/holynova/gushi_namer/master/public/json/tangshi.json",
    ),
    "songci300_src.json": (
        "宋词三百首选目（名篇分级）",
        "https://raw.githubusercontent.com/holynova/gushi_namer/master/public/json/songci.json",
    ),
    "STCharacters.txt": (
        "OpenCC 简→繁单字映射（名篇目录繁简双份用，见 data/build_famous.py）",
        "https://raw.githubusercontent.com/byvoid/opencc/master/data/dictionary/STCharacters.txt",
    ),
    "pcas-code.json": (
        "行政区划名录镜像（地名志用，见 data/build_place_names.py）",
        "https://raw.githubusercontent.com/modood/Administrative-divisions-of-China/master/dist/pcas-code.json",
    ),
}


def check(corpus_root: Path, rhyme: Path, radical: Path) -> int:
    """返回缺失的必需项数量。"""
    missing = 0
    print(f"语料根目录：{corpus_root}")
    for name, (required, min_size, _url) in REQUIRED.items():
        p = corpus_root / name
        if not p.exists():
            flag = "必需" if required else "可选"
            print(f"  ✗ {name:<20} 缺失（{flag}）")
            missing += int(required)
            continue
        size = p.stat().st_size if p.is_file() else sum(
            f.stat().st_size for f in p.glob("*") if f.is_file()
        )
        ok = size >= min_size
        print(f"  {'✓' if ok else '!'} {name:<20} {size/1e6:.1f} MB")
        if not ok and required:
            missing += 1

    print("\n配套文件：")
    for label, p in (("韵书 rhymebooks.json", rhyme), ("康熙 kangxi.json", radical)):
        if p.exists():
            print(f"  ✓ {label:<28} {p.stat().st_size/1e3:.0f} KB")
        else:
            print(f"  ✗ {label:<28} 缺失")
            missing += 1
    return missing


def link_to(target: Path, source: Path | None, copy: bool) -> None:
    """把必需文件收集到 target（默认软链，Windows 无权限时自动退化为复制）。"""
    target.mkdir(parents=True, exist_ok=True)
    for name in list(REQUIRED) + list(SIDE_FILES):
        src = None
        if source:
            for cand in (source / name, source.parent / name):
                if cand.exists():
                    src = cand
                    break
        if src is None:
            print(f"  - {name}: 源目录里没有，跳过（可用 --download 获取）")
            continue
        dst = target / name
        if dst.exists() or dst.is_symlink():
            print(f"  = {name}: 已存在")
            continue
        if copy or os.name == "nt":
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
        else:
            dst.symlink_to(src.resolve())
        print(f"  ✓ {name}")


def download(name: str) -> None:
    UPSTREAM.mkdir(parents=True, exist_ok=True)
    if name in SIDE_FILES:
        url = SIDE_FILES[name][1]
    elif name in REQUIRED:
        url = REQUIRED[name][2]
        if not url:
            print(f"{name} 没有配置下载地址（语料目录需从 chinese-poetry 系列仓库获取）")
            return
    else:
        print(f"未知文件 {name}；可选：{[*REQUIRED, *SIDE_FILES]}")
        return
    dst = UPSTREAM / name
    print(f"下载 {url}\n  → {dst}")
    urllib.request.urlretrieve(url, dst)
    print(f"  完成，{dst.stat().st_size/1e6:.1f} MB")


def main() -> int:
    ap = argparse.ArgumentParser(description="数据准备工具")
    ap.add_argument("--check", action="store_true", help="检查数据是否齐全")
    ap.add_argument("--link-to", type=Path, default=None, help="收集到指定目录")
    ap.add_argument("--from", dest="source", type=Path, default=None, help="源数据目录")
    ap.add_argument("--copy", action="store_true", help="复制而非软链")
    ap.add_argument("--download", default=None, help="下载指定文件到 data/upstream/")
    args = ap.parse_args()

    if args.download:
        download(args.download)
        return 0

    if args.link_to:
        link_to(args.link_to, args.source, args.copy)
        return 0

    # 默认行为：按 config 检查
    import yaml
    cfg = yaml.safe_load((ROOT / "config" / "default.yaml").read_text(encoding="utf-8"))
    corpus_root = Path(cfg["paths"]["corpus_root"])
    if not corpus_root.is_absolute():
        corpus_root = (ROOT / corpus_root).resolve()
    if os.environ.get("SHICI_DATA_ROOT"):
        corpus_root = Path(os.environ["SHICI_DATA_ROOT"])
    rhyme = (ROOT / cfg["paths"]["rhyme"]).resolve()
    radical = (ROOT / cfg["paths"]["radical"]).resolve()

    missing = check(corpus_root, rhyme, radical)
    print()
    if missing:
        print(f"缺少 {missing} 项必需数据。解决方式见本文件顶部说明。")
        return 1
    print("数据齐全，可以运行：python -m shici_namer --top 20")
    return 0


if __name__ == "__main__":
    sys.exit(main())
