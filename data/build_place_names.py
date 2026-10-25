"""重建 config/place_names.txt（地名志，D-011 的口径数据）。

    python data/build_place_names.py

输入：data/upstream/pcas-code.json —— 民政部行政区划名录镜像
（modood/Administrative-divisions-of-China，省/市/县三级）。

产出：一行一个**词干**（剥掉 省/市/县/区 等行政后缀，长度 ≥2）。
用于把候选里的地名碎片（武强/建平/长安）标记降权——
「这是个县名」是可引用、可核对的事实（D-011）。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "upstream" / "pcas-code.json"
OUT = ROOT / "config" / "place_names.txt"

# 剥掉的行政后缀（从长到短匹配一次）
_SUFFIXES = (
    "壮族自治区", "回族自治区", "维吾尔自治区", "自治县", "自治州",
    "林区", "特区", "地区", "矿区", "新区", "城区", "郊区",
    "省", "市", "县", "区", "旗", "盟",
)
# 不入志的通名条目
_GENERIC = {"市辖区", "县", "省直辖县级行政区划", "自治区", "直辖市", "直辖县"}


def stem(name: str) -> str:
    for suf in _SUFFIXES:
        if name.endswith(suf) and len(name) > len(suf):
            name = name[: -len(suf)]
            break
    return name


def main() -> None:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    names: set[str] = set()
    for prov in data:
        for city in [prov, *prov.get("children", [])]:
            for area in [city, *city.get("children", [])]:
                nm = area.get("name", "")
                if not nm or nm in _GENERIC:
                    continue
                s = stem(nm)
                if len(s) >= 2 and s not in _GENERIC:
                    names.add(s)

    lines = [
        "# 地名志：一行一个行政区词干（已剥 省/市/县/区 等后缀）。",
        "# 候选命中任一条 → place_flag=true，排序垫后（D-011：地名碎片武强/建平/长安）。",
        "# 由 data/build_place_names.py 从民政区划名录镜像生成，手改会被覆盖。",
        "# 依据：modood/Administrative-divisions-of-China（pcas-code.json，省/市/县三级）。",
        "",
        *sorted(names),
    ]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{OUT}: {len(names)} 个词干")


if __name__ == "__main__":
    main()
