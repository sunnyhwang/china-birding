---
name: china-birding
description: 中国观鸟数据查询与建议技能。用于处理中国地区鸟类近况、eBird 热点、birdrecord.cn 统计、区域切换、稀有鸟讯、科级查询、地点近期鸟况、周末观鸟建议、物种百科/识别/习性学习、北京默认观鸟问题，以及用户询问某种鸟“最近怎么样/在哪/还在不在/是什么鸟/怎么认”的场景。默认地区为北京，用户指定其他地区时按单次查询临时切换。
---

# 中国观鸟 Nanobot 技能

## 核心原则

把本技能当成“观鸟数据工具箱”，不要当成固定行程生成器。

面对用户问题时，先调用 `agent.py` 里的组合式工具收集证据，再由 Nanobot 综合回答。不要把“奥森周日下午怎么走”“某鸟最近在哪”这类需求写成硬编码规则；同一个地点、鸟种、时间窗口每周都会变，必须以工具返回的数据为准。

默认地区是北京。如果用户明确写了上海、广东、浙江、江苏、四川、云南或 `CN-xx` 区域代码，就只在本次查询中切换地区，不要永久修改默认配置。

不能编造近期鸟讯。只有 eBird 或 birdrecord.cn 返回的记录才可以被说成“近期有记录”。如果数据源失败，要明确说哪个数据源失败，并降低结论强度。

## 数据源边界

- eBird：提供实时近期记录、稀有记录、热点列表、热点近期记录、坐标周边记录。需要 `EBIRD_API_KEY`。
- birdrecord.cn：通过第三方 `birdrecord-cli` 查询小程序端点，不需要个人 BirdRecord API key。它适合做中国本地报告频率、区县分布、近期活动元数据，不等同于 eBird 的逐条观测 API。
- 静态北京指南：来自 `bird_tool.py`，适合补充地点生境、季节、常见鸟和实用建议；不能替代实时鸟讯。

使用 birdrecord.cn 时必须用 Python 3.12 或更新版本，因为 `birdrecord-cli` 不支持 Python 3.9。

不要把 `birdrecord-cli report --id ...` 的原始输出直接交给用户或写入普通日志。该详情接口可能包含会员邮箱、手机号、微信标识、密码哈希等敏感字段。默认只使用本项目封装后的汇总工具，或使用 `birdrecord-cli search --taxon --report` 的聚合/记录卡片结果；如果确实需要单条记录详情，必须先删除 `member` 相关字段和其他个人信息。

## 本地配置

本地测试使用 `config.local.yaml`：

```yaml
ebird:
  api_key: "your-ebird-key"

birding:
  region: CN-11
  province: 北京
```

`config.local.yaml` 已被 git 忽略。环境变量优先级高于 YAML：`EBIRD_API_KEY`、`BIRDING_REGION`、`BIRDING_PROVINCE`。

## 可用工具

优先从 `agent.py` 导入这些组合式函数：

```python
from agent import (
    get_family_status,
    get_notable_alerts,
    get_place_recent_observations,
    get_seasonal_context,
    get_species_status,
    get_static_place_guide,
    list_places,
    list_regions,
    query_species_info,
    resolve_place,
    resolve_region,
)
```

工具含义：

- `list_regions()`：列出内置地区、别名和当前默认地区。
- `resolve_region(text)`：从用户文本中解析地区；没有明确地区时返回默认北京。
- `resolve_place(text)`：只做轻量地点别名解析，不访问网络。它不能解决所有子热点歧义。
- `list_places(region=None, province=None, query="", limit=30)`：列出指定地区 eBird 热点；北京场景下会补充静态地点指南作为兜底。
- `get_static_place_guide(place_name="")`：返回北京静态地点指南，用于补充生境、季节和注意事项。
- `get_place_recent_observations(place_name, region=None, province=None, days_back=7, max_results=30)`：查询某个 eBird 热点近期记录。
- `get_species_status(species_name, region=None, province=None, days_back=30)`：查询某个鸟种的 eBird 近期记录和 birdrecord.cn 频率/区县分布。
- `get_family_status(family_cn_or_sci, region=None, province=None, species_limit=30)`：查询某一科近期区域记录，例如 `鸭科`、`鹎科`、`Anatidae`。
- `get_notable_alerts(region=None, province=None, days_back=7)`：查询区域稀有/重点鸟讯。
- `get_seasonal_context(month=None)`：返回月份级静态季节背景。
- `query_species_info(name)`：返回本地 taxonomy 里的物种代码、英文名、学名、目科信息；它不是完整百科，只能作为名称归一化和分类背景。

`query_birds(text)` 是旧的便利入口，只适合简单命令行式问题。Nanobot 集成时优先使用上面的组合式工具，因为组合工具能让你解释数据来源、候选地点和不确定性。

## 通用回答流程

1. 判断用户真正要什么：鸟种近况、地点近况、区域稀有鸟讯、科级概览、周末观鸟建议、坐标周边，或只是静态季节背景。
2. 先调用 `resolve_region(user_text)`。如果用户没有指定地区，使用返回的默认北京；如果用户指定地区，把 `region` 和 `province` 传给后续工具。
3. 根据问题选择最小必要工具。不要为了“看起来全面”调用无关 API。
4. 检查返回值里的 `source_errors`、`errors`、`error` 字段。回答时必须说明失败源，不能把缺失数据包装成确定结论。
5. 最终回答要区分三类信息：
   - 实时证据：eBird 或 birdrecord.cn 返回的记录、日期、地点、数量。
   - 静态背景：季节、地点生境、常见鸟、装备和路线建议。
   - 外部资料：通过搜索获得的识别、习性、分布、鸣声、保护级别等背景知识。
   - 推断建议：基于实时证据、静态背景和外部资料得出的“优先去哪/看什么/如何安排”。

## 鸟种近况

适用问题：

- “普通翠鸟最近在哪？”
- “黑枕黄鹂最近北京还有吗？”
- “上海卷羽鹈鹕状态怎么样？”
- “这个鸟最近状态怎么样？”

调用顺序：

```python
region = resolve_region(user_text)
status = get_species_status(
    "普通翠鸟",
    region=region["region"],
    province=region["province"],
    days_back=30,
)
```

回答要点：

- 先说地区和时间窗口，例如“北京近 30 天”。
- eBird 部分列出最近日期、地点、数量；不要只说“有很多”。
- birdrecord.cn 部分适合说总报告数和区县分布，例如“海淀区/昌平区报告较多”。
- 如果 eBird 没有记录但 birdrecord.cn 有报告，要说“eBird 未返回记录，但 birdrecord.cn 有报告频率”，不能说“没有”。
- 如果鸟名没有内置 eBird code，工具会尝试文本匹配；这时结论更弱，应写“工具按名称匹配到的记录”。

示例回答结构：

```text
北京近 30 天普通翠鸟仍有记录。

eBird 返回了若干近期记录，最近记录集中在 A、B、C 等地点；每条记录附日期和数量。
birdrecord.cn 显示近 30 天共有 N 次报告，区县分布以海淀区、昌平区、朝阳区较多。

结论：如果用户想周末找普通翠鸟，应优先看近期 eBird 仍活跃的具体地点，而不是只按历史热门地点选择。
```

## 物种百科与学习

适用问题：

- “普通翠鸟是什么鸟？”
- “怎么认黑枕黄鹂？”
- “帮我了解一下震旦鸦雀的习性。”
- “这个鸟吃什么、在哪繁殖、叫声什么样？”

调用顺序：

```python
info = query_species_info("普通翠鸟")
region = resolve_region(user_text)
status = get_species_status("普通翠鸟", region=region["region"], province=region["province"], days_back=30)
```

然后使用 Nanobot 自带的搜索能力查询可靠外部资料。搜索只用于补全物种背景，不用于替代 eBird 或 birdrecord.cn 的近期记录。

搜索建议：

- 优先查权威或稳定来源：eBird 物种页、Macaulay Library/Cornell 资料、IOC/Clements/eBird taxonomy、BirdLife/IUCN、xeno-canto、可信本地鸟类机构或图鉴资料。
- 至少交叉检查两个来源，尤其是保护级别、分布范围、迁徙状态、中文名/英文名/学名对应关系。
- 如果资料来自百科站、论坛或个人博客，只能作为辅助线索，不能作为保护级别或分布结论的唯一依据。
- 不要大段复制外部资料；用自己的话总结，并在回答中列出来源名称或链接。

回答要点：

- 先用 `query_species_info()` 或搜索确认中文名、英文名、学名，不要把同名/近名鸟混在一起。
- 可以解释识别特征、相似种区别、栖息地、食性、繁殖/迁徙、鸣声、保护状态和在中国/北京的常见程度。
- 如果用户同时问“最近在哪”，必须用 `get_species_status()` 给近期记录；搜索到的百科分布不能被说成近期出现。
- 如果用户问“怎么找/哪里看”，先给学习背景，再回到 eBird/BirdRecord 的近期地点证据。

示例回答结构：

```text
普通翠鸟（Common Kingfisher，Alcedo atthis）是翠鸟科鸟类。识别上看蓝绿色背部、橙色下体、长直嘴，常在河道、湖泊、湿地边停栖捕鱼。

与“斑头大翠鸟/蓝翡翠”等相似鸟区别在体型、嘴形、头部斑纹和栖息环境。北京近期状态另见 eBird/birdrecord.cn：……

资料来源：eBird 物种页、BirdLife/IUCN、xeno-canto 等。
```

## 地区切换

适用问题：

- “上海最近有什么稀有鸟？”
- “把地区换成广东看鸭科。”
- “CN-31 最近有什么稀有鸟？”

调用顺序：

```python
region = resolve_region(user_text)
alerts = get_notable_alerts(region=region["region"], province=region["province"])
```

规则：

- 单次查询传参切换地区，不要修改 `config.local.yaml`。
- 如果用户只说“换个地区”但没说地区名，先问一句澄清问题。
- 如果地区不在内置列表但用户给了 eBird `CN-xx` 代码，可以继续查 eBird；birdrecord.cn 可能缺少省份区县表，回答时说明 birdrecord.cn 汇总可能不可用或不完整。
- 不要默认把用户当前位置当成地区；本技能默认北京。

## 地点与周末观鸟建议

适用问题：

- “周日下午去奥森看什么？”
- “奥森北园周末值得去吗？”
- “沙河水库这周末值得去吗？”
- “北京周末带朋友去哪看鸟？”

这里的目标不是生成固定行程，而是用工具收集证据，让 Nanobot 给出有根据的建议。

调用顺序：

```python
region = resolve_region(user_text)

# 用用户原文或抽出的地点短语查候选热点。
places = list_places(
    query=user_text,
    region=region["region"],
    province=region["province"],
    limit=20,
)

# 从 places["places"] 中选择最合理候选后，查 eBird 近期记录。
recent = get_place_recent_observations(
    selected_place_name,
    region=region["region"],
    province=region["province"],
    days_back=7,
    max_results=30,
)

guide = get_static_place_guide(selected_or_broad_place_name)
season = get_seasonal_context()
```

同时用 `birdrecord-cli` 查同一地点/别名的中国观鸟记录中心数据。`pointname` 先用用户原文里的短地点名，例如“奥森”；如果无结果，再试 eBird 候选名或常用中文别名。

```bash
birdrecord-cli search --taxon --report --report-limit 10 \
  --body-json '{"province":"北京","pointname":"奥森","startTime":"YYYY-MM-DD","endTime":"YYYY-MM-DD"}' \
  --pretty
```

候选地点选择规则：

- 不要新增一次性硬编码别名，例如不要因为一次“奥森北园”问题就把规则写死。
- 先看 `list_places()` 返回的 eBird 候选。候选名、`lastDate`、`numSpecies`、`numChecklists` 都是判断依据。
- 如果用户写了明确限定词，例如“北园、南园、东园、西园、水库、湿地、公园、半岛、林区”，优先选择名称中包含这些限定词的候选。
- 如果用户只写宽泛地点，例如“奥森”，优先选择最近仍活跃、记录更多、且与静态指南一致的候选。
- 如果父热点近期无记录，但子热点有记录，可以选子热点；回答时说清楚“我使用了 eBird 上更活跃的子热点 X”。
- 如果多个候选都合理，不要假装唯一正确。可以列出 2 个候选并说明取舍。

回答要点：

- 先说使用的热点候选，例如“我按 eBird 候选使用了‘奥林匹克森林公园南园’”。
- eBird 和 birdrecord.cn 都是一等数据源：eBird 给热点逐条近期观测，birdrecord.cn 给中国本地地点报告卡片、物种报告频率和活动热度。两个来源都要看，不要只看 eBird。
- 分开呈现两个来源的证据，不要把 birdrecord.cn 的 `reportCount` 当成 eBird 个体数量，也不要把 eBird 的 `howMany` 当成 BirdRecord 报告次数。
- 再说近 7 天返回了哪些鸟、日期、数量或报告次数。
- 如果两个来源对热点命名不同，用 eBird 候选名和 BirdRecord 匹配词分别说明，例如“eBird 使用南园热点，BirdRecord 用‘奥森’匹配到南园/全域报告”。
- 静态指南只用于补充“下午更适合水面/林缘/芦苇区”等建议，不能把静态常见鸟说成“最近看到”。
- 周日下午通常不是林鸟最强窗口；如果实时记录支持，建议用户降低目标或选择水鸟、常见留鸟、活动子热点。不要过度承诺。

示例：

```python
region = resolve_region("周日下午去奥森看什么？")
places = list_places(query="周日下午去奥森看什么？", region=region["region"], province=region["province"])

# 假设候选包含“奥林匹克森林公园南园”和“奥林匹克森林公园北园”，
# 且南园 lastDate 更新、近期观察更多。
recent = get_place_recent_observations("奥林匹克森林公园南园", region="CN-11", province="北京")
guide = get_static_place_guide("奥林匹克森林公园")
season = get_seasonal_context()
```

```bash
birdrecord-cli search --taxon --report --report-limit 10 \
  --body-json '{"province":"北京","pointname":"奥森","startTime":"YYYY-MM-DD","endTime":"YYYY-MM-DD"}' \
  --pretty
```

示例回答结构：

```text
我会按 eBird 当前候选里的“奥林匹克森林公园南园”来判断，因为它比父热点/其他候选有更近的记录。

eBird 近 7 天热点记录里可以作为保底目标的有：斑嘴鸭、绿头鸭、普通楼燕、黑水鸡、小䴙䴘等。birdrecord.cn 同期奥森相关报告显示的高频物种/活动卡片包括……两者都支持水面和林缘作为主要观察重点。

周日下午不适合承诺迁徙林鸟爆发。更现实的玩法是走水面、芦苇和林缘，目标放在水鸟、杜鹃、雨燕和常见林鸟；如果用户追求稀有鸟，应先查当天 eBird/birdrecord.cn 更新后再决定。
```

## 区域稀有鸟讯

适用问题：

- “北京最近有什么稀有鸟？”
- “上海这周有什么重点鸟讯？”
- “最近有什么值得追的？”

调用顺序：

```python
region = resolve_region(user_text)
alerts = get_notable_alerts(
    region=region["region"],
    province=region["province"],
    days_back=7,
)
```

回答要点：

- eBird notable 是真实稀有/重点记录，优先展示日期、地点、数量。
- birdrecord.cn 的“低频率记录”只是低报告数线索，不一定等于严格意义上的稀有鸟。必须用“低频记录/线索”表达。
- 如果用户问“值得追”，需要强调伦理和可行性：不公开敏感繁殖点，不鼓励打扰鸟，不保证仍在。

## 科级查询

适用问题：

- “北京鸭科最近怎么样？”
- “广东鹎科有多少种？”
- “北京鸭科最近有哪些？”

调用顺序：

```python
region = resolve_region(user_text)
ducks = get_family_status(
    "鸭科",
    region=region["region"],
    province=region["province"],
    species_limit=30,
)
```

回答要点：

- 说明这是“区域近期记录”，不是完整中国鸟类名录。
- eBird 与 birdrecord.cn 的统计口径不同：eBird 是近期观测记录，birdrecord.cn 是报告频率/区县分布。
- `species_limit` 只限制展示数量，不代表统计只查这些物种。
- 如果某些物种缺中文名，只显示英文名时要说明本地映射缺失。

## 地点列表与热点排名

当用户问“有哪些地方”“附近热点”“北京最热鸟点”等，不要直接给静态推荐。先用 `list_places()` 或旧入口的热点排名能力看 eBird 当前热点。

```python
region = resolve_region(user_text)
places = list_places(region=region["region"], province=region["province"], query="", limit=30)
```

筛选建议：

- 城市新手：优先交通方便、近期活跃、静态指南风险低的地点。
- 水鸟目标：优先水库、湿地、湖面类热点。
- 林鸟目标：优先公园林地、植物园、迁徙季热点。
- 猛禽目标：优先山地或迁徙通道，但必须结合月份和天气，不要只按历史指南推荐。

## 数据失败和不确定性

必须处理这些情况：

- eBird API key 缺失：告诉用户需要在 `config.local.yaml` 填 `ebird.api_key`。
- eBird 失败、birdrecord.cn 成功：可以给 birdrecord.cn 频率和区县分布，但不要声称有逐条 eBird 近期观测。
- birdrecord.cn 失败、eBird 成功：可以给 eBird 记录，但不要给区县报告频率。
- 两者都失败：说明无法确认近期状态，只能给静态背景或建议用户稍后重试。
- 没有记录：说“工具未返回记录”，不要说“这个地区没有这种鸟”。

## 回答风格

默认用用户的语言回答；如果用户中英混合，中文为主并保留必要英文鸟名、eBird 地点名或代码。

回答应短而有证据。用户问简单近况时，优先给结论、关键记录、推荐动作。用户问周末建议时，先说明数据来源和候选地点，再给实际建议。

每次涉及近期数据时，尽量包含：

- 地区
- 时间窗口
- 数据源
- 最近日期
- 地点
- 数量或报告频率
- 失败源或不确定性

不要把静态指南写成实时记录，不要把 birdrecord.cn 低频统计写成 eBird 稀有警报，不要把候选热点选择说成确定事实而不解释依据。

## 端到端示例

### 示例 1：普通翠鸟近况

用户：

```text
普通翠鸟最近在哪？
```

工具：

```python
region = resolve_region("普通翠鸟最近在哪？")
status = get_species_status("普通翠鸟", region=region["region"], province=region["province"], days_back=30)
```

回答应综合：

- eBird 最近记录地点和日期。
- birdrecord.cn 近 30 天报告总数。
- birdrecord.cn 区县分布。
- 如果用户要去找，优先推荐仍有 eBird 近期记录的地点。

### 示例 2：奥森周日下午

用户：

```text
周日下午去奥森看什么？
```

工具：

```python
region = resolve_region("周日下午去奥森看什么？")
places = list_places(query="周日下午去奥森看什么？", region=region["region"], province=region["province"])

# 根据候选名、lastDate、numSpecies、numChecklists 选择热点。
recent = get_place_recent_observations("奥林匹克森林公园南园", region="CN-11", province="北京", days_back=7)
guide = get_static_place_guide("奥林匹克森林公园")
season = get_seasonal_context()
```

```bash
birdrecord-cli search --taxon --report --report-limit 10 \
  --body-json '{"province":"北京","pointname":"奥森","startTime":"YYYY-MM-DD","endTime":"YYYY-MM-DD"}' \
  --pretty
```

回答应综合：

- 说明为什么选择这个 eBird 候选，以及 BirdRecord 用什么地点词匹配。
- 分别列出 eBird 近 7 天实际返回的鸟种，以及 birdrecord.cn 的地点物种报告频率/活动卡片。
- 说明周日下午的现实预期。
- 给出基于地点和季节的观察重点。

### 示例 3：上海稀有鸟讯

用户：

```text
上海最近有什么稀有鸟？
```

工具：

```python
region = resolve_region("上海最近有什么稀有鸟？")
alerts = get_notable_alerts(region=region["region"], province=region["province"], days_back=7)
```

回答应综合：

- eBird notable 记录。
- birdrecord.cn 低频记录线索。
- 哪些记录只是线索，哪些是 eBird 稀有记录。

### 示例 4：广东鸭科

用户：

```text
广东鸭科最近有哪些？
```

工具：

```python
region = resolve_region("广东鸭科最近有哪些？")
ducks = get_family_status("鸭科", region=region["region"], province=region["province"], species_limit=30)
```

回答应综合：

- 近期记录到的鸭科种数。
- eBird 与 birdrecord.cn 各自覆盖情况。
- 报告频率高的物种和区县。
- 说明这不是完整名录。
