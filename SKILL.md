# China Birding — 中国观鸟工具

全国通用观鸟智能工具。整合 eBird + 中国观鸟记录中心，提供稀有鸟种警报、鸟种频率分析、热点查询、观鸟识图。

默认区域为北京，通过环境变量 BIRDING_REGION 切换其他省份。

## 用法示例

```
python bird_tool.py live --rare    # 稀有鸟种实时警报
python bird_tool.py live           # 实时鸟况
python bird_tool.py hotspots       # 热点排名
```

环境变量:
- `EBIRD_API_KEY` — eBird API 密钥
- `BIRDING_REGION` — eBird 区域代码 (默认 CN-11)
- `BIRDING_PROVINCE` — 观鸟记录中心省份 (默认 北京)
