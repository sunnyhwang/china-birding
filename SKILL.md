# China Birding — 中国观鸟工具

全国通用观鸟智能工具。整合 eBird + 中国观鸟记录中心，支持多数据源融合分析。

## 功能

- 🚨 **稀有鸟种实时警报** — 自动监控配置区域内的罕见鸟讯
- 🐦 **物种检索** — 按中文名查询单个鸟种近期分布
- 🌿 **科级分析** — 跨物种分析（如「鹎科鸟类有多少种、各自分布在哪些区域」）
- 🗺️ **热点排名** — 按物种数排列观鸟点
- 📊 **月度鸟情** — 了解当季鸟类动态
- 🎯 **新手攻略** — 观鸟地点推荐

## 环境变量

| 变量 | 必填 | 说明 | 默认值 |
|------|------|------|--------|
| `EBIRD_API_KEY` | ✅ | eBird API 密钥（[申请](https://ebird.org/api/keygen)） | — |
| `BIRDING_REGION` | | eBird 区域代码 | `CN-11`（北京） |
| `BIRDING_PROVINCE` | | 观鸟记录中心省份名 | `北京` |
| `BIRDRECORD_SHARE_TOKEN` | | 观鸟记录中心共享令牌（可选） | — |

## 用法示例

```bash
python bird_tool.py live --rare    # 稀有鸟种实时警报
python bird_tool.py live           # 实时鸟况
python bird_tool.py hotspots       # 热点排名
```

```python
from agent import query_birds
query_birds("鹎科鸟类有多少种，各自分布在哪？")  # 科级分析
query_birds("卷羽鹈鹕还在吗？")                    # 物种查询
query_birds("最近有什么稀有鸟？")                  # 稀有警报
```

## 全国切换

```ini
# .env — 上海
BIRDING_REGION=CN-31
BIRDING_PROVINCE=上海
```
