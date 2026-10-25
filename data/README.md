# 数据说明

项目不打包数据（约 300 MB）。两条路任选。

---

## 路线 A · 指向本机已有的数据（最快）

如果本机已经有 `chinese-poetry` 系语料和 `Chinese_Names.dat`，直接改
`config/default.yaml` 的 `paths.corpus_root`，或用环境变量：

```bash
export SHICI_DATA_ROOT=/path/to/data     # Windows: set SHICI_DATA_ROOT=...
python data/fetch.py --check
```

---

## 路线 B · 收集到 `data/upstream/`（自包含，当前默认）

```bash
# 从本地已有目录复制/软链
python data/fetch.py --link-to data/upstream --from /path/to/old/data

# 缺的单独下载（GitHub raw 较慢时可在浏览器下载后放进 data/upstream/）
python data/fetch.py --download Chinese_Names.dat
python data/fetch.py --download rhymebooks.json
python data/fetch.py --download kangxi.json
python data/fetch.py --download 诗经.json
python data/fetch.py --download 楚辞.json
python data/fetch.py --download tangshi300.json
python data/fetch.py --download songci300_src.json

# config/default.yaml 已默认指向 data/upstream，无需额外设置
```

`config/famous_sources.txt` 由 `tangshi300.json` / `songci300_src.json` /
楚辞核心篇目生成（生成依据写在文件头注释里）；重新生成需按文件头注释
拼装，或手改。

---

## 必需文件

目录结构必须是这样（`corpus_root` 指向根）：

```
<corpus_root>/
├── Chinese_Names.dat        ★必需  116 万条真实姓名（17 MB）
├── 诗经.json                ★必需  305 篇（chinese-poetry 标准结构，含 chapter/section）
├── 楚辞.json                        65 篇带篇名（名篇分级需要；缺失时退回 楚辞.txt）
├── 楚辞.txt                         纯文本退化格式，一行一段，无篇名
├── 论语.json
├── 周易.txt
├── 唐诗/*.json                      全唐诗，约 5.8 万首（**标题为繁体**）
├── 宋诗/*.json                      约 25 万首
└── 宋词/*.json                      ci.song.*.json；无 title，词牌在 rhythmic，
                                              标题统一为「词牌·首句」；混有作者简介条目
```

配套文件（路径在 `config.paths` 里单独配置）：

```
rhymebooks.json          平水韵/中华新韵/广韵     LingDong-/cope
kangxi.json              康熙字典数据（含部首）    hunterlau2020/bename
tangshi300.json          唐诗三百首目录            holynova/gushi_namer
songci300_src.json       宋词三百首选目            holynova/gushi_namer
STCharacters.txt         OpenCC 简→繁单字映射       byvoid/opencc
pcas-code.json           行政区划名录（省/市/县）    modood/Administrative-divisions-of-China
```

`config/famous_sources.txt` 由 `python data/build_famous.py` 从上述三个文件生成
（唐诗语料标题是繁体，目录繁简各一行；宋词按「词牌·首句」对齐）。
`config/place_names.txt` 由 `python data/build_place_names.py` 从 pcas-code.json 生成
（剥行政后缀取词干，D-011 地名碎片标记用）。

**最小可跑集**：`Chinese_Names.dat` + `诗经.json` + `rhymebooks.json` +
`kangxi.json`（约 18 MB，产出 531 个候选（2026-10 口径实测），足够验证链路与全部测试）。
加上 `楚辞.json` 后为 1,065 个候选。

---

## 数据来源

| 文件 | 上游 | 许可 |
|---|---|---|
| 唐诗/宋诗/宋词 | [chinese-poetry](https://github.com/chinese-poetry/chinese-poetry) | MIT |
| 诗经/楚辞/论语/周易 | 同上（转存）/ 国学经典公版 | — |
| Chinese_Names.dat | [wrk226/get_chinese_name](https://github.com/wrk226/get_chinese_name) | GPL-3.0 |
| rhymebooks.json | [LingDong-/cope](https://github.com/LingDong-/cope) | 见上游 |
| kangxi.json | [hunterlau2020/bename](https://github.com/hunterlau2020/bename) | 见上游 |

**注意许可差异**：姓名库来自 GPL-3.0 仓库。若本项目要商用或换许可，需先确认该数据的可用范围。

**2026-10 全量恢复记录**：`data/upstream/` 的 论语/周易/唐诗/宋诗/宋词 由
`python data/fetch.py --link-to data/upstream --from <NanBox_PiPiName>/data` 收集
（chinese-poetry 血统镜像）。恢复时核验：唐诗 57,612 首 / 宋诗 254,248 首 /
宋词 22,617 首，损坏文件 0；全量段数 1,531,539，与历史基线一致。

---

## 已知数据问题

| 问题 | 影响 | 缓解 |
|---|---|---|
| 繁简混排 | 唐诗 57/58、宋诗 255/255 个文件**正文以繁体为主**（2026-10 抽样核实，与 chinese-poetry 官方仓库逐文件比对一致，属上游血统而非转存事故）；宋词/周易为简体，论语为繁体。繁体正文的两字大多撞不上简体姓名库，唐诗/宋诗的实际产出因此打折 | 繁简同形字不受影响；根治需换 `JasonWade001/chtxt` 精校版或接入 OpenCC 正文转换（`STCharacters.txt` 已备，当前仅用于名篇目录繁简对齐），需重写 `corpus.py` 的解析 |
| 少量 JSON 损坏 | 解析失败 | `corpus.py` 已做 try/except 跳过 |
| OCR 噪声 | 个别诗句有误字 | 同上，换精校语料 |
| 姓名库只到 2008 年 | 性别倾向反映的是那个时代 | 属数据本身的局限，不是 bug |
| 姓名库 `${name}` 字段有「未知」9.7 万条 | 性别标注不全 | 已单独标为「未知」，不参与性别筛选 |

---

## 校验

```bash
python data/fetch.py --check
```

输出每项的大小与状态。返回码非 0 表示缺必需数据。
