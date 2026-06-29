

<p align="center">
  <img src="https://img.shields.io/badge/status-active-success" alt="Status">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
</p>

<p align="center">
  🐦 <strong>China Birding</strong> — 中国观鸟智能工具
  <br>
  <em>区域可配置 · 多数据源融合 · Nanobot 工具 API</em>
</p>

> ⚠️ **本工具面向 AI Agent（如 Nanobot）设计**，通过 Python API 调用实现复杂的观鸟数据查询。
> 如果你不熟悉命令行和代码运行，这款工具可能用起来不太顺手。

---

## 简介

**China Birding** 是一个融合多数据源的观鸟工具 API。默认面向北京，实时 eBird 查询可通过区域代码切换，birdrecord.cn 区县统计目前内置若干省市。

这个仓库不应该把复杂用户需求硬编码成单个「行程生成器」。更合理的用法是：Nanobot 调用这里提供的区域、地点、物种、热点、季节工具收集证据，然后由 Nanobot 自己组织最终回答。

它整合了 **eBird** 和 **中国观鸟记录中心 (birdrecord.cn)** 两大数据源，提供：

| 功能 | 说明 | 示例 |
|------|------|------|
| 🚨 稀有警报 | 实时发现区域内罕见鸟种 | `最近有什么稀有鸟?` |
| 🐦 物种查询 | 内置常见中文鸟名的近期出现记录 | `卷羽鹈鹕在哪?` |
| 🗺️ 热点排名 | 按物种数/观测活跃度排名 | `最热的观鸟点?` |
| 🌿 科级分析 | 某一科近期区域记录与分布 | `鹎科有多少种，分布如何?` |
| 🧭 地点素材 | 提供地点列表、近期热点记录、静态地点指南，供智能体生成建议 | `奥森周日下午观鸟` |
| 📊 月度鸟情 | 当季鸟类动态 | `现在能看到什么鸟?` |
| 🎯 新手攻略 | 观鸟地点推荐 | `新手去哪观鸟?` |

## 快速开始

### 1. 安装

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

`birdrecord-cli` 需要 Python 3.12 或更新版本。如果系统默认 `python3` 版本较旧，请明确使用 Python 3.12 创建虚拟环境。

### 2. 配置

推荐使用本地 YAML。`config.local.yaml` 已被 `.gitignore` 忽略，可以安全填写本机密钥：

```bash
cp config.example.yaml config.local.yaml
```

**必填项：**
- `ebird.api_key` — eBird API 密钥（[免费申请](https://ebird.org/api/keygen)，几分钟即可获得）

**区域设置（按需修改）：**

```yaml
ebird:
  api_key: "your-ebird-key"

birding:
  region: CN-11
  province: 北京
```

环境变量仍然可用，并且优先级高于 YAML：`EBIRD_API_KEY`、`BIRDING_REGION`、`BIRDING_PROVINCE`。

### 3. 使用

#### 命令行模式

```bash
# 查看静态攻略
python bird_tool.py

# 实时鸟况
python bird_tool.py live
python bird_tool.py live --rare          # 仅看稀有警报
python bird_tool.py live --hotspot 沙河水库  # 指定热点
python bird_tool.py hotspots             # 列出热点排名
```

#### Nanobot 工具 API（推荐）

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

# 列出和解析地区。
regions = list_regions()
resolved = resolve_region("上海最近有什么稀有鸟？")

# 鸟种近况：Nanobot 应综合返回记录、错误和不确定性。
status = get_species_status("卷羽鹈鹕", region=resolved["region"], province=resolved["province"])

# 物种基础信息：只提供本地分类/命名背景；完整百科应结合外部搜索。
info = query_species_info("普通翠鸟")

# 区域稀有鸟讯。
alerts = get_notable_alerts(region="CN-11", province="北京")

# 科级近况。
ducks = get_family_status("鸭科", region="CN-44", province="广东")

# 地点/周末建议：保留用户原文查候选，再由 Nanobot 选择合适热点。
request = "奥森周日下午观鸟"
beijing = resolve_region(request)
places = list_places(query=request, region=beijing["region"], province=beijing["province"])
recent = get_place_recent_observations("奥林匹克森林公园南园", region="CN-11", province="北京")
guide = get_static_place_guide("奥林匹克森林公园")
season = get_seasonal_context()
```

`query_birds(text)` 仍然保留为旧的便利格式化入口，适合简单命令行式问题。Nanobot 集成应优先使用上面的组合式函数。

## 支持的查询模式

| 查询类型 | 关键词触发 | 示例 |
|---------|-----------|------|
| 稀有鸟讯 | `稀有/罕见/少见/important/notable` | `最近有什么稀有鸟` |
| 物种查询 | 内置中文鸟名 / 鸟名后缀猜测（非完整中文名库） | `卷羽鹈鹕`, `白尾海雕` |
| 科级查询 | `XX科` | `鹎科有多少种`, `鸭科分布` |
| 热点排名 | `热点/排名/鸟点/最热` | `最热的鸟点是哪` |
| 地点素材 | 热点别名 / 地点名 / `where/place/hotspot` | `奥森 sunday afternoon birds` |
| 新手攻略 | `新手/攻略/推荐/去哪` | `新手去哪观鸟` |
| 月度鸟情 | `几月/季节/现在/月度` | `现在能看到什么` |
| 热门地点 | 热点别名 | `沙河水库怎么样` |

## 数据源

- **[eBird](https://ebird.org/)** — 全球最大的鸟类观测数据库，实时 API 访问
- **[中国观鸟记录中心](https://www.birdreport.cn/)** — 国内观鸟记录平台；当前通过第三方 `birdrecord-cli` 包访问小程序端点，不需要个人 API key，但不是 eBird 这种公开开发者 API

## 支持的区域

默认区域可通过 `BIRDING_REGION` / `BIRDING_PROVINCE` 设置。智能问答也支持在单次问题中直接写省市名，例如 `上海最近有什么稀有鸟？`，该次查询会临时使用上海，不会污染后续北京默认查询。

eBird 实时查询可通过 `BIRDING_REGION` 切换区域；birdrecord.cn 区县统计目前内置以下省市：

| 省份 | eBird 代码 | 内置区县数 |
|------|-----------|-----------|
| 北京 🌟 | CN-11 | 16 区 |
| 上海 | CN-31 | 16 区 |
| 广东 | CN-44 | 21 市 |
| 浙江 | CN-33 | 11 市 |
| 江苏 | CN-32 | 13 市 |
| 四川 | CN-51 | 18 市州 |
| 云南 | CN-53 | 16 市州 |

> 设置 `BIRDING_REGION` 和 `BIRDING_PROVINCE` 即可切换。
> 如需新增省份区县数据，编辑 `birdrecord_source.py` 中的 `PROVINCE_DISTRICTS` 字典即可。

## 项目结构

```
china-birding/
├── agent.py                    # 智能问答主入口
├── bird_tool.py                # 命令行工具
├── config.py                   # 本地 YAML 配置加载
├── config.example.yaml         # 可提交的配置模板
├── sources/
│   ├── ebird_source.py         # eBird API 封装
│   ├── birdrecord_source.py    # 观鸟记录中心封装
│   ├── cn_species_map.json     # 全物种分类数据（11,167 种）
│   └── __init__.py
├── requirements.txt            # Python 依赖
├── README.md                   # 本文件
└── SKILL.md                    # Nanobot 技能描述
```

## 隐私声明

- 本工具**不会收集任何用户数据**
- eBird API 调用由你的密钥直接发起
- 所有配置仅存于本地 `config.local.yaml` 文件

## 许可

MIT
