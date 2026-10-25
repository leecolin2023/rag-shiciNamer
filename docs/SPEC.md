# SPEC · 算法规格与不变量

> 本文件描述「系统怎么算」。口径参数在 `config/default.yaml`，不在这里重复。
> 若两者冲突，以配置为准，并来修本文件。

---

## 1. 数据契约

### 1.1 语料（`corpus.py`）

所有语料最终摊平为 `Passage(book, title, text, author, dynasty)` 流。

| 文件 | 结构 | 说明 |
|---|---|---|
| `诗经.json` | `[{title, chapter, section, content: [line, …]}]` | 305 篇 |
| `楚辞.json` | `[{title, section, author, content: [line, …]}]` | 优先；篇名用于名篇分级（D-007） |
| `楚辞.txt` | 纯文本，一行一段 | 退化格式（无篇名，名篇匹配失效） |
| `论语.json` | `[{chapter, paragraphs: [line, …]}]` | |
| `周易.txt` | 纯文本 | |
| `唐诗/*.json` | `[{title, author, paragraphs: […]}]` | 排除 `authors.*.json` |
| `宋诗/*.json` | 同上（部分用 `content` 而非 `paragraphs`） | |
| `宋词/*.json` | 同上 | |

**容错**：单个 JSON 解析失败即跳过，不中断。语料里确实有少量损坏文件。

### 1.2 姓名库（`lexicon.py`）

`Chinese_Names.dat`，每行 `姓名,性别`，性别 ∈ {男, 女, 未知}。

```
张伟明,男    →  given = "伟明"   (去掉首字姓氏)
阿安,男      →  given = "安"     (单字名，不进索引)
```

只索引**恰好 2 个汉字**的名。产出 `{名: {n: 总频次, m: 男, f: 女}}`。

**这是本项目替代「笔画吉凶」的量化依据。**

### 1.3 韵书（`phonology.RhymeBook`）

`rhymebooks.json`，结构 `{韵书名: [平声组列表, 仄声组列表]}`，每组是一个字符串（同韵部的字）。

```
平声组里的字 → "平"
仄声组里的字 → "仄"
两组都有的字  → "通"   （两读，不参与平仄交错判定）
都没有        → "?"
```

**入声字天然落在仄声组**，所以「石/白/轼/陆/牧/若/疾」都判仄。

**不变量**：`len(pingze(name)) == len(name)`（单字标签，逐位对齐）。

### 1.4 部首（`phonology.Radicals`）

来自康熙字典数据的 `radical` 字段，仅用于同部首检测。

---

## 2. 管线

```
Passage 流
   │
   ├─ split_sentences(text)         按 split_pattern 切；逗号也切
   │
   ├─ 枚举相邻 length-gram          当前 length = 2
   │
   ├─ 成词证据双通道（取或，D-007）
   │     ① 姓名库频次 >= min_population_freq（默认 1：有人叫过）
   │     ② 叠字且语料频次 >= min_corpus_freq（默认 2：叠音是构词法）
   │
   ▼
Hit{name, corpus_freq, population_freq, sources, books, titles}
   │
   ├─ 停用字剔除                      name 任一字符 ∈ stopwords
   ├─ 同部首剔除                      radical(a) == radical(b)；叠字豁免
   ├─ 性别倾向                        指定性别占比 >= gender_ratio
   ├─ 姓氏冲突                        同字 / 同声母 / 同韵母
   ├─ 地名碎片标注 place_flag          语境全称判定 + 地名志（D-011，只降权不剔除）
   │
   ▼
Candidate{…全维标注 + has_numeral/source_famous/best_book_rank/place_flag…}
   │
   ├─ rank(order)                    多键字典序，支持 key:asc/:desc 方向后缀
   │
   ▼
JSON / CSV / Markdown
```

### 2.1 为什么是 2-gram 而不是分词

**实测**：

```
「清泉石上流」
  jieba          → 清泉石 / 上流        「清泉」丢失
  2-gram         → 清泉 / 泉石 / 石上 / 上流
  + 姓名库校验    → 清泉（人口 95）保留 ✅
```

**代价**：会产生伪词。因为「其道」「国之」「以成」「有明」确实出现在姓名库里（有人叫过这些名字），
词表校验拦不住。必须靠停用字表。

### 2.2 corpus_freq 的语义

`corpus_freq` = 该 2-gram 在**本次加载的语料**中作为相邻二字出现的总次数。

⚠️ **它是相对量，不同 `--books` 之间不可比**。只跑诗经时「四方」= 35，全量时 = 969。

它的用途是**成词性代理**：真词在语料里反复出现；偶然相邻只出现一两次
（「建平」只在「況復建平家」出现一次，其实是地名）。

### 2.3 排序

字典序多键，**无加权综合分**。默认键序（D-007 选定骨架，D-008 退音韵键，
D-009 加听感键，D-010 用户偏好，D-011 加地名键；键名支持 `:asc`/`:desc`
后缀覆盖默认方向）：

```
has_numeral(数词垫后) → place_flag(地名碎片垫后，D-011) → source_fame(名篇优先)
→ same_final(叠字压后，D-010) → dual_rarity(名篇层内双界稀有)
→ tone_variety(全名声调多样性) → junction_liasion(连读吞音垫后)
→ tail_open(尾字洪音优先，D-010) → population_freq:asc → corpus_freq:asc
```

平仄交错/同声母保留为可用键，默认序不含（D-008）；`same_final` 因 D-010
「压叠字层」进入默认序（叠字必然同韵母），代价是窈窕类非叠字叠韵词一并压后。
全名听感键（D-009）在未指定姓氏时取中性值（tone_variety=3、
junction_liasion=False），即无姓运行不惩罚。
名篇目录见 `config/famous_sources.txt`（诗经/论语/周易整书 + 楚辞核心 +
唐诗三百首 + 宋词三百首，出处可核对）。

**不变量**：前 N 个候选中，若某位出现 `has_numeral=True`，其后不得再有 `False`。

---

## 3. 输出契约

### 3.1 JSON

`Candidate.to_dict()`，字段见 `models.py`。`sources` 是按 `book_rank` 排序的出处列表，最多 `max_sources` 条。

### 3.2 CSV

18 列（D-009 新增「全名声调」「尾字洪细」），顺序由 `config.export.columns`
定义，**必须与 `export.DEFAULT_COLUMNS` 一致**
（`tests/test_pipeline.py::test_csv列与配置一致` 会检查）。

改列顺序必须同时改：`config` → `export.DEFAULT_COLUMNS` → `export._row()` → 测试。

---

## 4. 不变量清单

| # | 不变量 | 由谁保证 |
|---|---|---|
| I1 | 每个候选至少 1 条出处，且出处有原句 | `extract` 收集 + `test_每个候选都有出处` |
| I2 | 通过任一成词通道：人口 ≥ min_population_freq 或（叠字且语料 ≥ min_corpus_freq） | `extract` + `test_每个候选都有平仄与统计` |
| I3 | `len(pingze) == len(name)` | `RhymeBook.pingze` 单字标签 |
| I4 | 默认配置下候选无同部首（叠字豁免：叠音是修辞典故） | `filter` + `test_没有同部首` |
| I5 | 默认配置下候选无停用字 | `filter` + `test_没有停用字` |
| I6 | 排序满足首键 has_numeral；前 50 无数词短语 | `rank` + `test_排序满足首键` |
| I7 | CSV 列与配置一致 | `test_csv列与配置一致` |
| I8 | 漏斗计数单调递减 | `test_统计字段完整` |
| I9 | 配置真的驱动行为（非硬编码） | `test_提高最小人口频次会减少候选` 等 8 条 |
| I10 | 公认好名靠前（呦呦前 100、徽音前 250；旧榜首垫底） | `TestAcceptance`（验收回归，D-007） |
| I11 | 全名声调参与排序：聂绳绳(4-2-2) 排在 趎趯(4-4-4) 之前；无姓运行不惩罚 | `test_聂姓全名声调参与排序`（D-009） |
| I12 | 洪细按韵腹判（介音不算）：泉/扬=洪，音/心=细；舌尖元音归洪 | `test_洪细分类`/`test_舌尖元音归洪` |
| I13 | 地名碎片标记：右邻全称为后缀（武强）或命中地名志（建平）→ place_flag 垫后；偶然共现（乔木式）不标记 | `test_place_flag两种证据`/`test_右邻字被记录`/`test_地名碎片被垫后` |

---

## 5. 未实现 / 已知缺口

| 缺口 | 影响 | 备注 |
|---|---|---|
| 单字名 | 只支持 2 字名 | `length=1` 需同时改姓名库索引逻辑 |
| 词性/语义判断 | 叙事碎片（利维/锡爵）与时代名（文刚）仍不可客观识别；地名碎片已由 D-011 处理 | HanLP/LTP 已否决（现代模型不适用先秦文本 + GB 级依赖）；若做应为默认关闭插件 |
| 谐音检测 | 「毛泊涵 ≈ 毛伯涵」查不出 | 需拼音 + 音近字表 |
| 多音字分级 | 只能标、不能判 | `heteronym` 含罕读，硬拒会误杀 |
| 名篇目录覆盖 | 诗经无篇目级分级（整书同级）；宋诗无选本 | 唐三百/宋三百/楚辞核心已覆盖；见 D-007 残留 |
| 繁简混排 | 输出里偶见「詠燭」「關山月」 | 语料问题，换 `chtxt` 精校版可解 |
| 方位词 | 「东南」「西南」等可进名篇层中游 | 未像数字字那样垫后，待积累反例再定 |

---

## 6. 性能

| 场景 | 耗时 | 内存 |
|---|---|---|
| 全量 7 部书（153 万段，2026-10 恢复后实测） | ~74 s | — |
| 诗经+楚辞（3.6k 段） | ~3 s | — |
| 仅诗经（305 篇） | ~2.5 s | — |

`extract` 为两遍扫描（语料通道开启时先全量计数），约为单遍的 1.3 倍。
语料通道限定叠字时第一遍只计叠字 gram，内存增量可忽略。
瓶颈仍在 `iter_corpus` 的 JSON 解析与逐字枚举。
若需提速：把 `hits` 序列化缓存，改语料时增量更新。
