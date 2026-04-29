

<p align="center">
  <img src="https://img.shields.io/badge/status-active-success" alt="Status">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
</p>

<p align="center">
  🐦 <strong>China Birding</strong> — 中国观鸟智能工具
  <br>
  <em>全国通用 · 多数据源融合 · 智能问答</em>
</p>

---

## 简介

**China Birding** 是一个融合多数据源的观鸟智能工具，覆盖全国各省份。

它整合了 **eBird** 和 **中国观鸟记录中心 (birdrecord.cn)** 两大数据源，提供：
- 🚨 **稀有鸟种实时警报** — 第一时间发现身边的罕见鸟讯
- 🗺️ **热点查询与排名** — 找到你附近的最佳观鸟点
- 🐦 **物种检索** — 查询某个鸟种在你区域的近期记录
- 📊 **月度鸟情** — 了解当季的鸟类动态
- 🤖 **智能问答** — 自然语言查询，无需记忆命令

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
# 默认：北京 (CN-11)
# 上海用户改为：BIRDING_REGION=CN-31, BIRDING_PROVINCE=上海
# 广东用户改为：BIRDING_REGION=CN-44, BIRDING_PROVINCE=广东
BIRDING_REGION=CN-11
BIRDING_PROVINCE=北京
```

### 3. 使用

**命令行工具：**

```bash
# 查看静态攻略（热点推荐、月度鸟种、新手指南）
python bird_tool.py

# 实时鸟况（稀有警报 + 近期记录）
python bird_tool.py live
python bird_tool.py live --rare          # 仅看稀有警报
python bird_tool.py live --hotspot 沙河水库  # 指定热点
python bird_tool.py hotspots             # 列出所有热点排名
```

**Python 调用（适合集成）：**

```python
from agent import query_birds

# 智能自然语言查询
result = query_birds("最近有什么稀有鸟？")
print(result)

result = query_birds("卷羽鹈鹕还在吗？")
print(result)
```

## 支持的区域

| 省份 | eBird 代码 | birdrecord.cn 省份名 |
|------|-----------|---------------------|
| 北京 | CN-11 | 北京 |
| 上海 | CN-31 | 上海 |
| 天津 | CN-12 | 天津 |
| 重庆 | CN-50 | 重庆 |
| 广东 | CN-44 | 广东 |
| 浙江 | CN-33 | 浙江 |
| 江苏 | CN-32 | 江苏 |
| 四川 | CN-51 | 四川 |
| 云南 | CN-53 | 云南 |
| 更多... | CN-XX | 省份名 |

> 设置 `BIRDING_REGION` 和 `BIRDING_PROVINCE` 即可切换区域。热点攻略目前基于北京数据，欢迎贡献其他省份的内容！

## 数据源

- **[eBird](https://ebird.org/)** — 全球最大的鸟类观测数据库，实时 API 访问
- **[中国观鸟记录中心](https://www.birdreport.cn/)** — 国内观鸟记录平台，覆盖本土数据

## 项目结构

```
china-birding/
├── agent.py                    # 智能问答主入口
├── bird_tool.py                # 命令行工具
├── sources/
│   ├── ebird_source.py         # eBird API 封装
│   ├── birdrecord_source.py    # 观鸟记录中心封装
│   └── cn_species_map.json     # 中文-英文物种名映射
├── .env.example                # 环境变量模板
├── requirements.txt            # Python 依赖
└── README.md
```

## 隐私声明

- 本工具**不会收集任何用户数据**
- eBird API 调用由你的密钥直接发起
- 所有配置仅存于本地 `.env` 文件

## License

MIT
