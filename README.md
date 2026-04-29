

<p align="center">
  <img src="https://img.shields.io/badge/status-active-success" alt="Status">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
</p>

<p align="center">
  🐦 <strong>China Birding</strong> — 中国观鸟智能工具
  <br>
  <em>全国通用 · 多数据源融合 · 智能问答</em>
</p>

> ⚠️ **本工具面向 AI Agent（如 Nanobot）设计**，通过 Python API 调用实现复杂的观鸟数据查询。
> 如果你不熟悉命令行和代码运行，这款工具可能用起来不太顺手。

---

## 简介

**China Birding** 是一个融合多数据源的观鸟智能工具，覆盖全国各省份。

它整合了 **eBird** 和 **中国观鸟记录中心 (birdrecord.cn)** 两大数据源，提供：

| 功能 | 说明 | 示例 |
|------|------|------|
| 🚨 稀有警报 | 实时发现区域内罕见鸟种 | `最近有什么稀有鸟?` |
| 🐦 物种查询 | 特定鸟种近期出现记录 | `卷羽鹈鹕在哪?` |
| 🗺️ 热点排名 | 按物种数/观测活跃度排名 | `最热的观鸟点?` |
| 🌿 科级分析 | 某一科鸟类的种类与分布 | `鹎科有多少种，分布如何?` |
| 📊 月度鸟情 | 当季鸟类动态 | `现在能看到什么鸟?` |
| 🎯 新手攻略 | 观鸟地点推荐 | `新手去哪观鸟?` |

## 快速开始

### 1. 安装

```bash
pip install -r requirements.txt
```

### 2. 配置

复制 `.env.example` 为 `.env`，填写配置：

```bash
cp .env.example .env
```

**必填项：**
- `EBIRD_API_KEY` — eBird API 密钥（[免费申请](https://ebird.org/api/keygen)，几分钟即可获得）

**区域设置（按需修改）：**

```ini
# 默认区域：北京 (CN-11)
# 上海用户改为：BIRDING_REGION=CN-31, BIRDING_PROVINCE=上海
# 广东用户改为：BIRDING_REGION=CN-44, BIRDING_PROVINCE=广东
BIRDING_REGION=CN-11
BIRDING_PROVINCE=北京
```

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

#### 智能问答模式（适合集成 Nanobot / 自动化）

```python
from agent import query_birds

# 🚨 稀有鸟种警报
result = query_birds("最近有什么稀有鸟种？")

# 🐦 特定物种查询
result = query_birds("卷羽鹈鹕还在吗？")
result = query_birds("白尾海雕最近哪出现？")

# 🌿 科级分析（支持所有常见科名）
result = query_birds("北京目前有观测记录的鹎科鸟类有多少种，各自主要分布在什么区域？")
# → 自动识别 "鹎科"，查询 Pycnonotidae 下所有物种
# → 从 eBird 获取物种列表，从 birdrecord.cn 获取各区分布
# → 输出如：白头鹎 — 45次报告  📍 海淀45次 | 朝阳38次 | 东城29次

result = query_birds("鸭科在北京有多少种？")
result = query_birds("鹰科的鸟有哪些常见种？")

# 🗺️ 热点查询
result = query_birds("最热的鸟点是哪？")
result = query_birds("沙河水库最近怎么样？")
```

## 支持的查询模式

| 查询类型 | 关键词触发 | 示例 |
|---------|-----------|------|
| 稀有鸟讯 | `稀有/罕见/少见/important/notable` | `最近有什么稀有鸟` |
| 物种查询 | 中文鸟名 / 部分名称 | `卷羽鹈鹕`, `白尾海雕` |
| 科级查询 | `XX科` | `鹎科有多少种`, `鸭科分布` |
| 热点排名 | `热点/排名/鸟点/最热` | `最热的鸟点是哪` |
| 新手攻略 | `新手/攻略/推荐/去哪` | `新手去哪观鸟` |
| 月度鸟情 | `几月/季节/现在/月度` | `现在能看到什么` |
| 热门地点 | 热点别名 | `沙河水库怎么样` |

## 数据源

- **[eBird](https://ebird.org/)** — 全球最大的鸟类观测数据库，实时 API 访问
- **[中国观鸟记录中心](https://www.birdreport.cn/)** — 国内观鸟记录平台

## 支持的区域

通过设置环境变量切换省份，已内置各区/县数据的省份：

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
├── sources/
│   ├── ebird_source.py         # eBird API 封装
│   ├── birdrecord_source.py    # 观鸟记录中心封装
│   ├── cn_species_map.json     # 全物种分类数据（11,167 种）
│   └── __init__.py
├── .env.example                # 环境变量模板
├── requirements.txt            # Python 依赖
├── README.md                   # 本文件
└── SKILL.md                    # Nanobot 技能描述
```

## 隐私声明

- 本工具**不会收集任何用户数据**
- eBird API 调用由你的密钥直接发起
- 所有配置仅存于本地 `.env` 文件

## License

MIT
