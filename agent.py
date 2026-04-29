#!/usr/bin/env python3
"""
中国观鸟智能体 · China Birding Agent

自然语言查询 → 自动分类意图 → 查询数据 → 格式化响应

默认查询北京地区（可通过环境变量 BIRDING_REGION 切换省份）。
eBird 区域代码: CN-11 = 北京, CN-31 = 上海, CN-44 = 广东 ...

用法:
  from agent import query_birds
  result = query_birds("卷羽鹈鹕最近在哪出现？")
  print(result)
"""
import json, os, re, sys
from datetime import datetime, timezone
from typing import Optional

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

from sources.ebird_source import EBirdSource
from sources.birdrecord_source import BirdRecordSource

# ══════════════════════════════════════════════════════════════
# API 密钥 — 必须设置环境变量 EBIRD_API_KEY
# 免费申请: https://ebird.org/api/keygen
# ══════════════════════════════════════════════════════════════

EBIRD_KEY = os.environ.get("EBIRD_API_KEY")
if not EBIRD_KEY:
    raise RuntimeError(
        "❌ 请设置环境变量 EBIRD_API_KEY\n"
        "   免费申请: https://ebird.org/api/keygen\n"
        "   或写入 .env 文件: EBIRD_API_KEY=你的密钥"
    )

# 区域设置 — 通过环境变量 BIRDING_REGION 切换省份
#   默认 CN-11 (北京), 可改为 CN-31 (上海), CN-44 (广东) 等
#   GB/T 2260 行政区域代码
BIRDING_REGION = os.environ.get("BIRDING_REGION", "CN-11")

# BirdRecord.cn 省份名 — 通过环境变量 BIRDING_PROVINCE 切换
#   默认 "北京", 可改为 "上海", "广东" 等
BIRDING_PROVINCE = os.environ.get("BIRDING_PROVINCE", "北京")

# ══════════════════════════════════════════════════════════════
# 数据源初始化
# ══════════════════════════════════════════════════════════════

_ebird: Optional[EBirdSource] = None
_birdrecord: Optional[BirdRecordSource] = None

def get_ebird():
    global _ebird
    if _ebird is None:
        _ebird = EBirdSource(EBIRD_KEY)
    return _ebird

def get_birdrecord():
    global _birdrecord
    if _birdrecord is None:
        _birdrecord = BirdRecordSource(province=BIRDING_PROVINCE)
    return _birdrecord

# ══════════════════════════════════════════════════════════════
# 意图分类
# ══════════════════════════════════════════════════════════════

# 默认观鸟热点别名（基于北京数据）
# 切换到其他省份时请替换此字典或通过配置文件自定义
HOTSPOT_ALIAS = {
    "奥林匹克": "奥林匹克森林公园",
    "奥森": "奥林匹克森林公园",
    "天坛": "天坛公园",
    "沙河": "沙河水库",
    "沙河水库": "沙河水库",
    "野鸭湖": "野鸭湖湿地保护区",
    "颐和园": "颐和园",
    "百望山": "百望山森林公园",
    "圆明园": "圆明园",
    "植物园": "北京植物园",
    "南海子": "南海子湿地公园",
    "温榆河": "温榆河公园",
    "十渡": "十渡",
}

# 常见物种中英文名映射（eBird 物种编码，已从官方 taxonomy 校正）
COMMON_SPECIES = {
    "卷羽鹈鹕": ("dalpel1", "Dalmatian Pelican"),
    "铜蓝鹟": ("verfly4", "Verditer Flycatcher"),
    "赭红尾鸲": ("blared1", "Black Redstart"),
    "震旦鸦雀": ("reedp1", "Reed Parrotbill"),
    "文须雀": ("beared1", "Bearded Reedling"),
    "黑枕黄鹂": ("blnori1", "Black-naped Oriole"),
    "大麻鳽": ("grebir1", "Great Bittern"),
    "蓝歌鸲": ("sibrob1", "Siberian Blue Robin"),
    "红喉歌鸲": ("sibrub1", "Siberian Rubythroat"),
    "白眉姬鹟": ("yelbrf1", "Yellow-rumped Flycatcher"),
    "黄眉姬鹟": ("narfly2", "Narcissus Flycatcher"),
    "普通翠鸟": ("comkin1", "Common Kingfisher"),
    "灰鹤": ("comcra1", "Common Crane"),
    "白枕鹤": ("whncra1", "White-naped Crane"),
    "反嘴鹬": ("pieavo1", "Pied Avocet"),
    "黑翅长脚鹬": ("bkwsti1", "Black-winged Stilt"),
    "凤头蜂鹰": ("crehon1", "Crested Honey Buzzard"),
    "雀鹰": ("eurspa1", "Eurasian Sparrowhawk"),
    "红脚隼": ("amufal1", "Amur Falcon"),
    "燕隼": ("eurkes1", "Eurasian Hobby"),
    "斑尾塍鹬": ("bartgo1", "Bar-tailed Godwit"),
    "东方大苇莺": ("orirwa1", "Oriental Reed Warbler"),
    "黑眉苇莺": ("blcwar1", "Black-browed Reed Warbler"),
    "红胁蓝尾鸲": ("refblu1", "Red-flanked Bluetail"),
    "戴菊": ("goldcr1", "Goldcrest"),
    "白眉鸫": ("eyethr1", "Eye-browed Thrush"),
    "斑鸫": ("dusthr1", "Dusky Thrush"),
    "黄喉鹀": ("yelbun1", "Yellow-throated Bunting"),
    "田鹀": ("rustbu1", "Rustic Bunting"),
    "芦鹀": ("pallb1", "Pallas's Bunting"),
    "苇鹀": ("pallb1", "Pallas's Bunting"),
    "黑鹳": ("blasto1", "Black Stork"),
    "白琵鹭": ("eurspo1", "Eurasian Spoonbill"),
    "赤颈䴙䴘": ("renegr1", "Red-necked Grebe"),
    "角鸊鷉": ("horogr1", "Horned Grebe"),
    "白腰杓鹬": ("eurcur1", "Eurasian Curlew"),
    "大杓鹬": ("farcur1", "Far Eastern Curlew"),
    "红颈瓣蹼鹬": ("renpha1", "Red-necked Phalarope"),
    "灰斑鸻": ("bkcplo1", "Black-bellied Plover"),
    "金斑鸻": ("pacgol1", "Pacific Golden-Plover"),
    "长尾鸭": ("lotduc1", "Long-tailed Duck"),
    "红胸秋沙鸭": ("rebmer1", "Red-breasted Merganser"),
    "小天鹅": ("tunswn1", "Tundra Swan"),
    "大天鹅": ("whoswn1", "Whooper Swan"),
    "白额雁": ("gwfgoo1", "Greater White-fronted Goose"),
    "小白额雁": ("lwfgoo1", "Lesser White-fronted Goose"),
    "鸿雁": ("swagoo1", "Swan Goose"),
    "斑头秋沙鸭": ("smamer1", "Smew"),
    "花脸鸭": ("baitea1", "Baikal Teal"),
    "罗纹鸭": ("falduc1", "Falcated Duck"),
    "青头潜鸭": ("baepoc1", "Baer's Pochard"),
    "白眼潜鸭": ("ferepo1", "Ferruginous Duck"),
}

# 中文物种名 → eBird species code 的反向查找
CN_TO_CODE = {}
for cn, (code, en) in COMMON_SPECIES.items():
    CN_TO_CODE[cn] = code

# ── 科级查询支持 ──────────────────────────────────────
# 中文科名 → 科拉丁名映射
# 用于处理 "鹎科鸟类有多少种" 这类查询
CN_FAMILY_MAP: dict[str, str] = {
    "鸭科": "Anatidae",
    "雉科": "Phasianidae",
    "鹭科": "Ardeidae",
    "鹮科": "Threskiornithidae",
    "鹳科": "Ciconiidae",
    "鹰科": "Accipitridae",
    "隼科": "Falconidae",
    "鹤科": "Gruidae",
    "鸻科": "Charadriidae",
    "鹬科": "Scolopacidae",
    "鸥科": "Laridae",
    "鸬鹚科": "Phalacrocoracidae",
    "䴙䴘科": "Podicipedidae",
    "鸠鸽科": "Columbidae",
    "杜鹃科": "Cuculidae",
    "鸱鸮科": "Strigidae",
    "雨燕科": "Apodidae",
    "翠鸟科": "Alcedinidae",
    "啄木鸟科": "Picidae",
    "伯劳科": "Laniidae",
    "鸦科": "Corvidae",
    "山雀科": "Paridae",
    "燕科": "Hirundinidae",
    "莺科": "Cettiidae",
    "柳莺科": "Phylloscopidae",
    "苇莺科": "Acrocephalidae",
    "鹟科": "Muscicapidae",
    "鸫科": "Turdidae",
    "画眉科": "Leiothrichidae",
    "噪鹛科": "Leiothrichidae",
    "鹎科": "Pycnonotidae",
    "椋鸟科": "Sturnidae",
    "绣眼鸟科": "Zosteropidae",
    "雀科": "Passeridae",
    "燕雀科": "Fringillidae",
    "鹀科": "Emberizidae",
    "梅花雀科": "Estrildidae",
    "鹪鹩科": "Troglodytidae",
    "攀雀科": "Remizidae",
    "花蜜鸟科": "Nectariniidae",
    "鹡鸰科": "Motacillidae",
    "太平鸟科": "Bombycillidae",
    "黄鹂科": "Oriolidae",
    "卷尾科": "Dicruridae",
    "王鹟科": "Monarchidae",
    "扇尾鹟科": "Rhipiduridae",
    "百灵科": "Alaudidae",
    "岩鹨科": "Prunellidae",
    "旋木雀科": "Certhiidae",
    "鳾科": "Sittidae",
    "太阳鸟科": "Nectariniidae",
    "啄花鸟科": "Dicaeidae",
    "鹛科": "Timaliidae",
    "幽鹛科": "Pellorneidae",
    "鸲科": "Muscicapidae",
    "地鸫科": "Turdidae",
}


def _load_family_species() -> dict[str, list[str]]:
    """Build familySciName → list of (cn_name, code) from taxonomy cache."""
    taxonomy = _load_taxonomy()
    family_species: dict[str, list[tuple[str, str]]] = {}
    # taxonomy is keyed by English name, each value has code, familySciName, etc.
    # We need Chinese names too — they're buried in the map values? No — the keys are EN names.
    # We'll store by code → (en_name, family_sci_name)
    code_family: dict[str, str] = {}
    for en_name, info in taxonomy.items():
        code = info.get("code", "")
        family = info.get("familySciName", "")
        if code and family:
            code_family[code] = family

    # Also build reverse: family → list of codes
    for code, family in code_family.items():
        family_species.setdefault(family, []).append(code)

    return code_family, family_species


_FAMILY_CODE_CACHE: Optional[dict[str, str]] = None
_FAMILY_SPECIES_CACHE: Optional[dict[str, list[str]]] = None

def get_family_data():
    global _FAMILY_CODE_CACHE, _FAMILY_SPECIES_CACHE
    if _FAMILY_CODE_CACHE is not None:
        return _FAMILY_CODE_CACHE, _FAMILY_SPECIES_CACHE
    _FAMILY_CODE_CACHE, _FAMILY_SPECIES_CACHE = _load_family_species()
    return _FAMILY_CODE_CACHE, _FAMILY_SPECIES_CACHE

# 热门热点坐标（用于 geo 查询）
HOTSPOT_COORDS = {
    "奥林匹克森林公园": (39.99, 116.39),
    "天坛公园": (39.88, 116.41),
    "沙河水库": (40.13, 116.29),
    "野鸭湖湿地保护区": (40.41, 115.84),
    "颐和园": (39.99, 116.27),
    "百望山森林公园": (40.02, 116.27),
    "圆明园": (40.00, 116.30),
    "北京植物园": (39.99, 116.21),
    "国家植物园": (39.99, 116.21),
    "南海子湿地公园": (39.77, 116.47),
    "温榆河公园": (40.03, 116.47),
    "龙潭湖公园": (39.87, 116.45),
    "十渡": (39.63, 115.59),
}

def classify_query(text: str) -> dict:
    """
    分析用户自然语言查询，返回意图和参数。
    
    返回:
      {
        "intent": "species" | "notable" | "hotspot" | "geo" | "rankings" | "seasonal" | "guide" | "species_info",
        "params": { ... }
      }
    """
    text_clean = text.strip().lower()
    
    # ── 检测稀有鸟讯（优先级高于物种匹配） ──
    is_notable = any(kw in text for kw in ["稀有", "罕见", "重要鸟讯", "警报", "稀罕", "特殊", "最近有什么"])
    if is_notable:
        return {"intent": "notable", "params": {}}

    # ── 检测热点排行 ──
    if any(kw in text for kw in ["热点排名", "热点排行", "最热的鸟点", "鸟点排名", "排名"]):
        return {"intent": "rankings", "params": {}}

    # ── 检测物种查询 ──
    # 模式: "XX鸟还在北京吗" "最近XX在哪" "XX是什么鸟" "XX的记录"
    species_keywords = list(CN_TO_CODE.keys())
    found_species = None
    for cn_name in species_keywords:
        if cn_name in text:
            found_species = cn_name
            break
    if not found_species:
        # 尝试正则匹配：常见鸟名后缀（排除"鸟点"这类组合）
        # 先剔除 "鸟点"
        text_no_spot = text.replace("鸟点", "XX")
        cn_pattern = re.findall(r'[\u4e00-\u9fff]{2,6}(?:鸟|鹀|鹟|鸲|鸻|鹬|鸭|雁|鹤|鹭|鹰|隼|鸮|鹃|莺|鸫|雀|鸦|鹎|鸲|鸰)', text_no_spot)
        if cn_pattern:
            found_species = cn_pattern[0]

    if found_species:
        is_info_query = any(kw in text for kw in ["是什么", "是什么鸟", "介绍", "百科", "特征", "长什么样"])
        return {
            "intent": "species_info" if is_info_query else "species",
            "params": {"species": found_species, "species_code": CN_TO_CODE.get(found_species)}
        }

    # ── 检测科级查询（如"鹎科鸟类有多少种"） ──
    family_match = re.search(r'([\u4e00-\u9fff]{1,6})科', text)
    if family_match:
        family_cn = family_match.group(0)  # e.g. "鹎科"
        family_sci = CN_FAMILY_MAP.get(family_cn)
        if family_sci:
            return {"intent": "family", "params": {"family_cn": family_cn, "family_sci": family_sci}}
        # Unknown family — still return as species query attempt
        return {"intent": "species", "params": {"species": family_cn}}

    # ── 检测稀有鸟讯（通用） ──
    if any(kw in text for kw in ["稀有", "罕见", "重要", "稀罕", " notable", "特殊", "最近"]):
        return {"intent": "notable", "params": {}}
    
    # ── 检测热点查询 ──
    for alias, full_name in sorted(HOTSPOT_ALIAS.items(), key=lambda x: -len(x[0])):
        if alias in text:
            return {"intent": "hotspot", "params": {"hotspot": full_name}}
    
    # ── 检测地理查询 ──
    geo_match = re.search(r'(\d+\.?\d*)\s*[°度,，\s]\s*(\d+\.?\d*)', text)
    if geo_match:
        return {"intent": "geo", "params": {"lat": float(geo_match.group(1)), "lng": float(geo_match.group(2))}}
    
    # ── 检测热点排行 ──
    if any(kw in text for kw in ["热点", "排名", "排行", "最热", "鸟点", "去哪"]):
        return {"intent": "rankings", "params": {}}
    
    # ── 检测当前季节 ──
    if any(kw in text for kw in ["这个月", "本月", "季节", "迁徙", "现在看什么"]):
        return {"intent": "seasonal", "params": {}}
    
    # ── 检测攻略 ──
    if any(kw in text for kw in ["攻略", "指南", "推荐", "建议", "新手"]):
        return {"intent": "guide", "params": {}}
    
    # ── 默认：返回近期概览 ──
    return {"intent": "notable", "params": {}}


# ══════════════════════════════════════════════════════════════
# 查询执行
# ══════════════════════════════════════════════════════════════

def query_notable(days_back: int = 7) -> list[dict]:
    """查询近期稀有/重要鸟讯（融合 eBird + birdrecord.cn，使用已配置的区域）。"""
    results = []

    # 1. eBird 稀有鸟讯
    eb = get_ebird()
    try:
        eb_data = eb.notable_observations(days_back=days_back, max_results=20)
        for o in eb_data:
            results.append({
                "species": o.get("comName", "?"),
                "sciName": o.get("sciName", ""),
                "location": o.get("locName", "?"),
                "date": o.get("obsDt", "?"),
                "count": o.get("howMany", 1),
                "source": "eBird",
            })
    except Exception:
        pass

    # 2. birdrecord.cn 低频率物种（reportCount ≤ 3 的物种）
    br = get_birdrecord()
    try:
        br_rare = br.get_notable_species(days_back=max(days_back * 2, 14), max_reports=3)
        for o in br_rare:
            results.append({
                "species": o["species"],
                "sciName": o.get("latinName", ""),
                "location": "",
                "date": "",
                "count": o.get("reportCount", 1),
                "source": "birdrecord.cn",
                "note": f"近{max(days_back * 2, 14)}天仅{o.get('reportCount', 1)}次报告",
            })
    except Exception:
        pass

    return results


def _normalize_ebird_obs(obs: list[dict]) -> list[dict]:
    """将 eBird 格式转为统一格式。"""
    normalized = []
    for o in obs:
        if "error" in o:
            continue
        normalized.append({
            "species": o.get("comName", "?"),
            "sciName": o.get("sciName", ""),
            "location": o.get("locName", "?"),
            "date": o.get("obsDt", "?"),
            "count": o.get("howMany", 1),
            "source": "eBird",
        })
    return normalized


def query_species_recent(species_name: str, days_back: int = 30) -> dict:
    """查询某个物种在配置区域的近期记录（融合 eBird + birdrecord.cn）。

    Returns:
        {
            "ebird": [...],       # eBird 观测记录（统一格式）
            "birdrecord": {...},  # birdrecord.cn 汇总
            "summary": str,       # 融合后的文字摘要
        }
    """
    eb = get_ebird()
    br = get_birdrecord()

    # 1. eBird
    ebird_results = []
    code = CN_TO_CODE.get(species_name)
    if code:
        try:
            raw = eb.recent_observations(species_code=code, days_back=days_back, max_results=20)
            ebird_results = _normalize_ebird_obs(raw)
        except Exception:
            pass
    else:
        try:
            all_obs = eb.recent_observations(days_back=days_back, max_results=100)
            raw = [o for o in all_obs if species_name in o.get("comName", "") or species_name in o.get("sciName", "")]
            ebird_results = _normalize_ebird_obs(raw)
        except Exception:
            pass

    # 2. birdrecord.cn — 报告频率（该物种在 birdrecord.cn 上的报告次数）
    birdrecord_result = {}
    try:
        br_freq = br.get_species_frequency(
            species_name=species_name, days_back=days_back
        )
        br_count = br_freq[0]["reportCount"] if br_freq else 0

        # 各区分布
        br_districts = br.get_species_frequency_by_district(
            species_name=species_name, days_back=days_back
        )

        birdrecord_result = {
            "total_reports": br_count,
            "districts": br_districts,
        }
    except Exception:
        birdrecord_result = {"total_reports": 0, "districts": []}

    # 3. 物种百科信息
    info = query_species_info(species_name)
    en_name = info.get("en_name", "")

    # 4. 构建摘要
    total_ebird = len(ebird_results)
    br_reports = birdrecord_result.get("total_reports", 0)

    summary_parts = []
    if total_ebird > 0:
        # 按地点聚合 eBird 数据
        by_loc = {}
        for o in ebird_results:
            loc = o["location"]
            by_loc.setdefault(loc, []).append(o)
        loc_summary = []
        for loc, obs in sorted(by_loc.items(), key=lambda x: -len(x[1]))[:5]:
            recent_dates = [o["date"] for o in obs[:3]]
            loc_summary.append(f"📍{loc} ({len(obs)}次, 最近{recent_dates[0]})")
        summary_parts.append(f"【eBird】{total_ebird}条记录，{len(by_loc)}个地点：\n" + "\n".join(loc_summary))

    if br_reports > 0:
        summary_parts.append(f"\n【birdrecord.cn】近{days_back}天共{br_reports}次报告")

    return {
        "ebird": ebird_results,
        "birdrecord": birdrecord_result,
        "summary": "\n".join(summary_parts) if summary_parts else "暂无记录",
        "species_info": info,
    }


def query_hotspot(hotspot_name: str, days_back: int = 7) -> dict:
    """查询某个热点的近期记录，返回热点信息和观察列表。"""
    eb = get_ebird()
    try:
        hotspots = eb.hotspot_list()
        q = hotspot_name.lower()
        scored = []
        for h in hotspots:
            name = h.get("locName", "").lower()
            if q == name:
                scored.append((0, h))
            elif name.startswith(q):
                scored.append((1, h))
            elif q in name:
                scored.append((2, h))
        scored.sort(key=lambda x: x[0])
        if not scored:
            return {"error": f"未找到热点 '{hotspot_name}'"}
        match = scored[0][1]
        obs = eb.hotspot_observations(match["locId"], days_back=days_back, max_results=20)
        return {
            "hotspot": match,
            "observations": obs,
        }
    except Exception as e:
        return {"error": str(e)}


def query_hotspot_rankings() -> list[dict]:
    """获取热点排名（按物种数，使用已配置的区域）。"""
    eb = get_ebird()
    try:
        hotspots = eb.hotspot_list()
        def _sp(h):
            try:
                return int(h.get("numSpecies", 0))
            except:
                return 0
        hotspots.sort(key=_sp, reverse=True)
        return hotspots
    except Exception as e:
        return [{"error": str(e)}]


def query_geo(lat: float, lng: float, dist_km: int = 10, days_back: int = 7) -> dict:
    """查询坐标周边鸟况。"""
    eb = get_ebird()
    try:
        obs = eb.geo_recent(lat, lng, dist_km=dist_km, days_back=days_back, max_results=30)
        notable = eb.geo_notable(lat, lng, dist_km=dist_km, days_back=days_back*2, max_results=10)
        return {"observations": obs, "notable": notable}
    except Exception as e:
        return {"error": str(e)}


def query_seasonal(month: int = None) -> str:
    """获取本月或指定月的观鸟看点。"""
    from bird_tool import SPECIES_BY_MONTH
    now = datetime.now()
    if month is None:
        month = now.month
    for m_name, species in SPECIES_BY_MONTH:
        m_num = int(m_name.split("月")[0].split()[-1])
        if m_num == month:
            return f"{m_name}\n{species}"
    return f"暂未收录{month}月数据"


_TAXONOMY_CACHE = None

def _load_taxonomy() -> dict:
    """从本地缓存加载完整的 eBird 物种分类（CN name → info）。"""
    global _TAXONOMY_CACHE
    if _TAXONOMY_CACHE is not None:
        return _TAXONOMY_CACHE
    map_path = os.path.join(os.path.dirname(__file__), "sources", "cn_species_map.json")
    if os.path.exists(map_path):
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                _TAXONOMY_CACHE = json.load(f)
                return _TAXONOMY_CACHE
        except:
            pass
    _TAXONOMY_CACHE = {}
    return _TAXONOMY_CACHE


def query_species_info(name: str) -> dict:
    """获取物种百科信息，从本地 taxonomy 缓存查找。"""
    code = CN_TO_CODE.get(name)
    en_name = COMMON_SPECIES.get(name, (None, None))[1]

    # 从 taxonomy 缓存查找（按英文名，需处理后匹配）
    taxonomy = _load_taxonomy()
    info = {}

    if code:
        # 通过 code 反查（taxonomy 以英文名为 key）
        for en, t in taxonomy.items():
            if t.get("code") == code:
                info = t
                info["comName_zh"] = name
                info["comName_en"] = en
                break

    if not info and en_name:
        # 通过英文名查
        if en_name in taxonomy:
            info = taxonomy[en_name]
            info["comName_zh"] = name
            info["comName_en"] = en_name

    return {
        "name": name,
        "code": code,
        "species_info": info,
        "en_name": en_name,
    }


# ══════════════════════════════════════════════════════════════
# 响应格式化（小红书风格）
# ══════════════════════════════════════════════════════════════

def fmt_notable(data: list[dict]) -> str:
    """格式化稀有鸟讯（融合 eBird + birdrecord.cn）。"""
    if not data:
        return f"📡 已配置区域近期暂无稀有鸟种记录"

    lines = ["━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             "  🚨 稀有鸟讯速递",
             "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    # 分离来源
    from_ebird = [o for o in data if o.get("source") == "eBird"]
    from_br = [o for o in data if o.get("source") == "birdrecord.cn"]

    if from_ebird:
        lines.append("\n  📡 eBird 稀有记录:")
        for o in from_ebird[:10]:
            lines.append(f"\n  ★ {o.get('species', '?')}")
            sci = o.get("sciName", "")
            if sci:
                lines.append(f"    {sci}")
            lines.append(f"    📍 {o.get('location', '?')}")
            lines.append(f"    🕐 {o.get('date', '?')}  ×{o.get('count', 1)}")

    if from_br:
        lines.append("\n  📗 birdrecord.cn 低频率记录:")
        for o in from_br[:10]:
            note = o.get("note", "")
            lines.append(f"\n  ★ {o.get('species', '?')}")
            lines.append(f"    {note}")
            if o.get("location"):
                lines.append(f"    📍 {o['location']}")

    total_ebird = len(from_ebird)
    total_br = len(from_br)
    lines.append(f"\n  📊 共 {total_ebird} 条 eBird 稀有记录 + {total_br} 条 birdrecord.cn 低频记录")
    lines.append(f"  更新于 {datetime.now().strftime('%m-%d %H:%M')}")
    return "\n".join(lines)


def fmt_species(data: dict, species_name: str) -> str:
    """格式化物种查询结果（融合 eBird + birdrecord.cn）。"""
    ebird_obs = data.get("ebird", [])
    br_data = data.get("birdrecord", {})
    summary = data.get("summary", "")

    if not ebird_obs and not br_data:
        return f"🐦 已配置区域近期未发现 **{species_name}** 的记录"

    lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             f"  🐦 {species_name} 近期区域记录",
             f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    # 百科信息
    info = data.get("species_info", {})
    en = info.get("en_name", "")
    code = info.get("code", "")
    if en:
        lines.append(f"  English: {en}")
    if code:
        lines.append(f"  eBird Code: {code}")

    lines.append("")

    # eBird 数据
    if ebird_obs:
        by_loc = {}
        for o in ebird_obs:
            loc = o["location"]
            by_loc.setdefault(loc, []).append(o)
        lines.append(f"  📡 eBird ({len(ebird_obs)}条, {len(by_loc)}个地点):")
        for loc, loc_obs in sorted(by_loc.items(), key=lambda x: -len(x[1]))[:5]:
            dates = [o["date"] for o in loc_obs[:3]]
            cnts = [str(o["count"]) for o in loc_obs[:3]]
            lines.append(f"    📍 {loc}")
            lines.append(f"       最近: {', '.join(dates)}")
            lines.append(f"       数量: {', '.join(cnts)}只")
            if len(loc_obs) > 3:
                lines.append(f"       还有 {len(loc_obs) - 3} 条记录")

    # birdrecord.cn 数据
    br_reports = br_data.get("total_reports", 0)
    br_districts = br_data.get("districts", [])
    if br_reports > 0:
        lines.append(f"\n  📗 birdrecord.cn ({br_reports}次报告):")
        if br_districts:
            top_dists = sorted(br_districts, key=lambda x: -x['reportCount'])[:6]
            dist_str = " | ".join(f"{d['district']} {d['reportCount']}次" for d in top_dists)
            lines.append(f"    📊 各区分布: {dist_str}")

    lines.append(f"\n  📊 数据: eBird + birdrecord.cn · {datetime.now().strftime('%m-%d %H:%M')}")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 科级查询（如"鹎科鸟类有多少种、分布如何"）
# ══════════════════════════════════════════════════════════════

def query_family(family_sci: str, species_limit: int = 30) -> dict:
    """
    查询某一科鸟类的物种列表及其在配置区域的分布情况。

    构建方式：
      - 从 cn_species_map.json（全物种分类数据）匹配 familySciName
      - 通过 COMMON_SPECIES 获取中文名（仅覆盖常见种，约 142 种）
      - 仅对有中文名的物种查询 birdrecord.cn 和 eBird
    """
    _, family_species = get_family_data()
    taxonomy = _load_taxonomy()

    codes = family_species.get(family_sci, [])
    if not codes:
        return {"error": f"未找到科 {family_sci} 的物种数据"}

    # Build code → cn_name from COMMON_SPECIES (reverse lookup)
    code_to_cn: dict[str, str] = {}
    for cn, (code, en) in COMMON_SPECIES.items():
        code_to_cn[code] = cn

    # Build code → en_name from taxonomy
    code_to_en: dict[str, str] = {}
    for en_name, info in taxonomy.items():
        code = info.get("code", "")
        if code:
            code_to_en[code] = en_name

    # Get family common English name
    family_en = ""
    for en_name, info in taxonomy.items():
        if info.get("familySciName") == family_sci:
            family_en = info.get("familyComName", "")
            break

    species_in_family = []
    for code in codes[:species_limit]:
        en_name = code_to_en.get(code, "")
        cn_name = code_to_cn.get(code, "")
        species_in_family.append({
            "cn_name": cn_name,          # may be empty if not in COMMON_SPECIES
            "en_name": en_name,
            "code": code,
        })

    # Query frequency & observations (only for species with Chinese names)
    br = get_birdrecord()
    eb = get_ebird()

    enriched = []
    for sp in species_in_family:
        cn_name = sp["cn_name"]
        code = sp["code"]

        # birdrecord.cn frequency (requires Chinese name)
        reports = 0
        top_districts = []
        if cn_name:
            try:
                freq = br.get_species_frequency_by_district(cn_name, days_back=30)
                reports = sum(f.get("reportCount", 0) for f in freq)
                top_districts = sorted(freq, key=lambda x: -x.get("reportCount", 0))[:5]
            except Exception:
                pass  # no birdrecord.cn data for this species

        # eBird recent observations
        recent_obs = []
        try:
            recent_obs = eb.recent_observations(days_back=14, species_code=code)[:5]
        except Exception:
            pass

        enriched.append({
            **sp,
            "frequency": {
                "total_reports": reports,
                "districts": top_districts,
            },
            "recent_obs": recent_obs,
        })

    # Find the Chinese family name
    family_cn = ""
    for cn_f, sci_f in CN_FAMILY_MAP.items():
        if sci_f == family_sci:
            family_cn = cn_f
            break

    return {
        "family_cn": family_cn,
        "family_sci": family_sci,
        "family_en": family_en,
        "total_codes": len(codes),
        "species_list": enriched,
    }


def _build_en_to_cn_map(taxonomy: dict) -> dict[str, str]:
    """Build English name → Chinese name lookup from taxonomy + COMMON_SPECIES."""
    en_to_cn = {en: cn for cn, (code, en) in COMMON_SPECIES.items()}
    return en_to_cn


def fmt_family(data: dict) -> str:
    """格式化科级查询结果。"""
    if "error" in data:
        return f"⚠️ {data['error']}"

    lines = ["━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]

    family_cn = data.get("family_cn", "")
    family_en = data.get("family_en", "")
    total_codes = data.get("total_codes", 0)
    species_list = data.get("species_list", [])

    title = f"{family_cn}({family_en})" if family_cn else f"{family_en or data.get('family_sci','')}"
    has_record = [s for s in species_list if s["frequency"]["total_reports"] > 0 or s["recent_obs"]]

    lines.append(f"  🌿 {title} — 该科 {total_codes} 种，区域内近期有记录 {len(has_record)} 种")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for sp in species_list:
        cn = sp.get("cn_name", "")
        en = sp.get("en_name", "?")
        code = sp.get("code", "")
        freq = sp.get("frequency", {})
        reports = freq.get("total_reports", 0)
        districts = freq.get("districts", [])
        recent = sp.get("recent_obs", [])

        # Skip species with zero data unless they have a Chinese name
        if reports == 0 and not recent:
            if not cn:
                continue  # skip unknown species with no records
            # For species without Chinese name, still show a minimal entry
            label = f"{en}" if not cn else f"{cn}({en})"
            label += f" — ❌ 暂无该区域记录"
            lines.append(f"  ▸ {label}")
            continue

        cn_name_missing = not cn
        label = f"{cn}({en})" if cn else en

        parts = [f"  ▸ {label}"]

        if reports > 0:
            parts[0] += f" — {reports}次报告"
            if districts:
                dist_str = " | ".join(f"{d['district']}{d['reportCount']}次" for d in districts[:3])
                parts.append(f"    📍 区域分布: {dist_str}")

        if recent:
            locs = set(o.get("locName", "?") for o in recent[:3])
            parts.append(f"    📡 eBird: {', '.join(locs)}")

        if cn_name_missing:
            parts.append(f"    ⚠️ 暂无中文匹配，仅显示英文名")

        lines.extend(parts)

    if not has_record:
        lines.append("  📭 区域内近期暂无该科鸟类记录")

    lines.append(f"\n  📊 数据: eBird + birdrecord.cn · {datetime.now().strftime('%m-%d %H:%M')}")
    return "\n".join(lines)


def fmt_hotspot(data: dict) -> str:
    """格式化热点查询结果。"""
    if "error" in data:
        return f"⚠️ {data['error']}"
    
    hs = data["hotspot"]
    obs = data.get("observations", [])
    name = hs.get("locName", "?")
    species_cnt = hs.get("numSpecies", "?")
    last_date = hs.get("lastDate", "?")
    
    lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             f"  📍 {name}",
             f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             f"  历史记录: {species_cnt} 种",
             f"  最近活跃: {last_date}", ""]
    
    if obs:
        # 按日期分组
        by_date = {}
        for o in obs:
            d = o.get("obsDt", "?").split(" ")[0]
            by_date.setdefault(d, []).append(o)
        for date, day_obs in sorted(by_date.items(), reverse=True)[:5]:
            lines.append(f"  📅 {date}")
            for o in day_obs[:8]:
                com = o.get("comName", "?")
                cnt = o.get("howMany", 1)
                lines.append(f"    {com} ×{cnt}")
            if len(day_obs) > 8:
                lines.append(f"    ... 及另外 {len(day_obs)-8} 种")
            lines.append("")
        lines.append(f"  📊 共 {len(obs)} 条近期记录")
    else:
        lines.append("  📊 近期待观测记录")
    
    lines.append(f"  数据: eBird · {datetime.now().strftime('%m-%d %H:%M')}")
    return "\n".join(lines)


def fmt_rankings(data: list[dict]) -> str:
    """格式化热点排名。"""
    if not data:
        return "暂无热点数据"
    if isinstance(data[0], dict) and "error" in data[0]:
        return f"⚠️ {data[0]['error']}"
    
    lines = ["━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             "  🏆 观鸟热点 TOP 15",
             "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    for i, h in enumerate(data[:15], 1):
        name = h.get("locName", "?")
        sp = h.get("numSpecies", "?")
        last = h.get("lastDate", "?")
        emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"  {i}."
        lines.append(f"\n{emoji} {name}")
        lines.append(f"      {sp} 种鸟 | 最近: {last}")
    
    lines.append(f"\n  数据: eBird · {datetime.now().strftime('%m-%d %H:%M')}")
    return "\n".join(lines)


def fmt_seasonal(text: str, month: int) -> str:
    """格式化月度鸟种信息。"""
    month_names = ["", "一月", "二月", "三月", "四月", "五月", "六月",
                   "七月", "八月", "九月", "十月", "十一月", "十二月"]
    return (f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"  📅 {datetime.now().year}年{month_names[month]}观鸟看点\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"  {text}")


def fmt_species_info(data: dict) -> str:
    """格式化物种百科。"""
    name = data["name"]
    en = data.get("en_name")
    info = data.get("species_info", {})
    code = data.get("code")

    lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             f"  🐦 {name}",
             f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    if en:
        lines.append(f"  English: {en}")
    if code:
        lines.append(f"  eBird Code: {code}")
    if info:
        lines.append(f"  学名: {info.get('sciName', '?')}")
        lines.append(f"  目: {info.get('order', '?')}")
        lines.append(f"  科: {info.get('familyComName', '?')} ({info.get('familySciName', '?')})")
    else:
        lines.append(f"  ⚠️ 暂未找到详细百科数据")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════

def query_birds(query: str) -> str:
    """
    主入口：自然语言查询 → 返回格式化响应。
    
    参数:
      query: 自然语言查询，如 "卷羽鹈鹕还在北京吗？"
    
    返回:
      格式化字符串，可直接发送给用户
    """
    classified = classify_query(query)
    intent = classified["intent"]
    params = classified["params"]
    
    if intent == "notable":
        data = query_notable(days_back=7)
        return fmt_notable(data)
    
    elif intent == "species":
        species = params.get("species", "")
        data = query_species_recent(species)
        return fmt_species(data, species)

    elif intent == "species_info":
        species = params.get("species", "")
        info = query_species_info(species)
        result = fmt_species_info(info)
        # 也查一下近期记录（融合）
        data = query_species_recent(species)
        ebird_obs = data.get("ebird", [])
        if ebird_obs:
            result += f"\n\n📡 近期 eBird 记录:\n"
            by_loc = {}
            for o in ebird_obs:
                loc = o["location"]
                by_loc.setdefault(loc, []).append(o)
            for loc, loc_obs in sorted(by_loc.items(), key=lambda x: -len(x[1]))[:3]:
                dates = [o["date"] for o in loc_obs[:2]]
                result += f"  📍 {loc}: {', '.join(dates)}\n"
        br_data = data.get("birdrecord", {})
        br_reports = br_data.get("total_reports", 0)
        if br_reports:
            result += f"\n📗 birdrecord.cn: 近30天{br_reports}次报告"
        return result
    
    elif intent == "hotspot":
        hotspot = params.get("hotspot", "")
        data = query_hotspot(hotspot)
        return fmt_hotspot(data)
    
    elif intent == "geo":
        lat = params.get("lat")
        lng = params.get("lng")
        dist = params.get("dist_km", 10)
        data = query_geo(lat, lng, dist)
        if "error" in data:
            return f"⚠️ {data['error']}"
        
        obs = data.get("observations", [])
        notable = data.get("notable", [])
        lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                 f"  📍 坐标 ({lat}, {lng}) 周边 {dist}km",
                 f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        if notable:
            lines.append(f"\n  ★ 周边稀有记录:")
            for o in notable[:5]:
                lines.append(f"    {o.get('comName','?')} @ {o.get('locName','?')} [{o.get('obsDt','?')}]")
        if obs:
            lines.append(f"\n  近期观测 ({len(obs)} 条):")
            for o in obs[:10]:
                lines.append(f"    {o.get('comName','?')} ×{o.get('howMany',1)} @ {o.get('locName','?')}")
        return "\n".join(lines)
    
    elif intent == "rankings":
        data = query_hotspot_rankings()
        return fmt_rankings(data)
    
    elif intent == "seasonal":
        month = params.get("month", datetime.now().month)
        text = query_seasonal(month)
        return fmt_seasonal(text, month)
    
    elif intent == "guide":
        return ("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "  🎯 观鸟攻略速览（以北京为例）\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "\n"
                "  🔹 最佳季节: 4-5月(春迁) 9-10月(秋迁)\n"
                "  🔹 新手推荐: 奥森 → 天坛\n"
                "  🔹 水鸟: 沙河水库、野鸭湖\n"
                "  🔹 猛禽: 百望山(9-10月)\n"
                "  🔹 林鸟: 植物园、圆明园\n"
                "  🔹 装备: 双筒望远镜 8×42\n"
                "\n"
                "  想要更详细的？告诉我具体想去哪！")

    elif intent == "family":
        family_sci = params.get("family_sci", "")
        family_cn = params.get("family_cn", "")
        data = query_family(family_sci)
        if "error" in data:
            return f"⚠️ 查询 {family_cn} 数据时出错: {data['error']}"
        return fmt_family(data)
    
    return "🐦 没太明白你问的是什么，试试：\n  • 「最近有什么稀有鸟？」\n  • 「卷羽鹈鹕还在吗？」\n  • 「沙河现在怎么样？」\n  • 「最热的鸟点是哪？」"


# ══════════════════════════════════════════════════════════════
# CLI 入口（方便测试）
# ══════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "最近有什么好看的？"
    
    result = query_birds(query)
    print(result)


if __name__ == "__main__":
    main()
