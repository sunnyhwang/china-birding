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
import json, logging, os, re, sys
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(__file__))

from config import load_local_config
from sources.ebird_source import EBirdSource
from sources.birdrecord_source import BirdRecordSource

# ══════════════════════════════════════════════════════════════
# API 密钥 — 必须设置环境变量 EBIRD_API_KEY
# 免费申请: https://ebird.org/api/keygen
# ══════════════════════════════════════════════════════════════

logger = logging.getLogger(__name__)
load_local_config()

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
    key = os.environ.get("EBIRD_API_KEY")
    if not key:
        raise RuntimeError(
            "请设置 EBIRD_API_KEY，或在 config.local.yaml 中填写 ebird.api_key。"
            "免费申请: https://ebird.org/api/keygen"
        )
    if _ebird is None or getattr(_ebird, "_api_key", None) != key:
        _ebird = EBirdSource(key)
    return _ebird

def get_birdrecord():
    global _birdrecord
    province = os.environ.get("BIRDING_PROVINCE", BIRDING_PROVINCE)
    if _birdrecord is None or getattr(_birdrecord, "province", None) != province:
        _birdrecord = BirdRecordSource(province=province)
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

REGION_ALIASES: dict[str, tuple[str, str]] = {
    "北京": ("CN-11", "北京"),
    "beijing": ("CN-11", "北京"),
    "上海": ("CN-31", "上海"),
    "shanghai": ("CN-31", "上海"),
    "广东": ("CN-44", "广东"),
    "guangdong": ("CN-44", "广东"),
    "浙江": ("CN-33", "浙江"),
    "zhejiang": ("CN-33", "浙江"),
    "江苏": ("CN-32", "江苏"),
    "jiangsu": ("CN-32", "江苏"),
    "四川": ("CN-51", "四川"),
    "sichuan": ("CN-51", "四川"),
    "云南": ("CN-53", "云南"),
    "yunnan": ("CN-53", "云南"),
}

REGION_CODE_TO_PROVINCE = {
    region: province for region, province in REGION_ALIASES.values()
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


def extract_region(text: str) -> dict:
    """Extract a query-scoped region override from natural language."""
    text_lower = text.lower()
    for alias, (region, province) in REGION_ALIASES.items():
        if alias in text_lower or alias in text:
            return {"region": region, "province": province}

    code_match = re.search(r"\bCN-\d{2}\b", text, flags=re.IGNORECASE)
    if code_match:
        region = code_match.group(0).upper()
        return {"region": region, "province": REGION_CODE_TO_PROVINCE.get(region)}

    return {}


@contextmanager
def scoped_region(params: dict):
    """Temporarily apply a query-specific eBird/BirdRecord region."""
    old_region = os.environ.get("BIRDING_REGION")
    old_province = os.environ.get("BIRDING_PROVINCE")

    region = params.get("region")
    province = params.get("province")
    try:
        if region:
            os.environ["BIRDING_REGION"] = region
        if province:
            os.environ["BIRDING_PROVINCE"] = province
        yield
    finally:
        if old_region is None:
            os.environ.pop("BIRDING_REGION", None)
        else:
            os.environ["BIRDING_REGION"] = old_region

        if old_province is None:
            os.environ.pop("BIRDING_PROVINCE", None)
        else:
            os.environ["BIRDING_PROVINCE"] = old_province


def current_region_label() -> str:
    region = os.environ.get("BIRDING_REGION", BIRDING_REGION)
    province = os.environ.get("BIRDING_PROVINCE", BIRDING_PROVINCE)
    return f"{province} ({region})" if province else region


def extract_visit_window(text: str) -> str:
    text_lower = text.lower()
    day = ""
    if any(kw in text for kw in ["周六", "星期六"]) or "saturday" in text_lower:
        day = "周六"
    elif any(kw in text for kw in ["周日", "星期日", "星期天"]) or "sunday" in text_lower:
        day = "周日"
    elif "周末" in text or "weekend" in text_lower:
        day = "周末"

    time_of_day = ""
    if any(kw in text for kw in ["早上", "上午"]) or "morning" in text_lower:
        time_of_day = "上午"
    elif "下午" in text or "afternoon" in text_lower:
        time_of_day = "下午"
    elif "傍晚" in text or "evening" in text_lower:
        time_of_day = "傍晚"

    return f"{day}{time_of_day}" or day or time_of_day or "周末"

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
    region_params = extract_region(text)

    def result(intent: str, params: Optional[dict] = None) -> dict:
        merged = dict(region_params)
        if params:
            merged.update(params)
        return {"intent": intent, "params": merged}

    # ── 检测稀有鸟讯（优先级高于物种匹配） ──
    is_notable = any(kw in text for kw in ["稀有", "罕见", "重要鸟讯", "警报", "稀罕", "特殊", "最近有什么"])
    if is_notable:
        return result("notable")

    # ── 检测热点排行 ──
    if any(kw in text for kw in ["热点排名", "热点排行", "最热的鸟点", "鸟点排名", "排名"]):
        return result("rankings")

    # ── 检测明确的新手/攻略意图，避免把“去哪观鸟”误识别成鸟名 ──
    if any(kw in text for kw in ["新手", "攻略", "指南"]):
        return result("guide")

    # ── 检测科级查询（如"鹎科鸟类有多少种"） ──
    for family_cn, family_sci in sorted(CN_FAMILY_MAP.items(), key=lambda x: -len(x[0])):
        if family_cn in text:
            return result("family", {"family_cn": family_cn, "family_sci": family_sci})

    family_match = re.search(r'([\u4e00-\u9fff]{1,6})科', text)
    if family_match:
        family_cn = family_match.group(0)  # e.g. "鹎科"
        # Unknown family — still return as species query attempt
        return result("species", {"species": family_cn})

    # ── 检测物种查询 ──
    # 模式: "XX鸟还在北京吗" "最近XX在哪" "XX是什么鸟" "XX的记录"
    species_keywords = list(CN_TO_CODE.keys())
    found_species = None
    for cn_name in species_keywords:
        if cn_name in text:
            found_species = cn_name
            break
    if not found_species:
        # 尝试正则匹配：常见鸟名后缀（排除"鸟点"、"观鸟"这类通用词）
        text_no_spot = text.replace("鸟点", "XX").replace("观鸟", "XX")
        cn_pattern = re.findall(r'[\u4e00-\u9fff]{2,6}(?:鸟|鹀|鹟|鸲|鸻|鹬|鸭|雁|鹤|鹭|鹰|隼|鸮|鹃|莺|鸫|雀|鸦|鹎|鸲|鸰)', text_no_spot)
        if cn_pattern:
            found_species = cn_pattern[0]

    if found_species:
        is_info_query = any(kw in text for kw in ["是什么", "是什么鸟", "介绍", "百科", "特征", "长什么样"])
        return result(
            "species_info" if is_info_query else "species",
            {"species": found_species, "species_code": CN_TO_CODE.get(found_species)},
        )

    # ── 检测稀有鸟讯（通用） ──
    if any(kw in text for kw in ["稀有", "罕见", "重要", "稀罕", " notable", "特殊", "最近"]):
        return result("notable")
    
    # ── 检测热点查询 ──
    for alias, full_name in sorted(HOTSPOT_ALIAS.items(), key=lambda x: -len(x[0])):
        if alias in text:
            return result("hotspot", {"hotspot": full_name})
    
    # ── 检测地理查询 ──
    geo_match = re.search(r'(\d+\.?\d*)\s*[°度,，\s]\s*(\d+\.?\d*)', text)
    if geo_match:
        return result("geo", {"lat": float(geo_match.group(1)), "lng": float(geo_match.group(2))})
    
    # ── 检测热点排行 ──
    if any(kw in text for kw in ["热点", "排名", "排行", "最热", "鸟点", "去哪"]):
        return result("rankings")
    
    # ── 检测当前季节 ──
    if any(kw in text for kw in ["这个月", "本月", "季节", "迁徙", "现在看什么"]):
        return result("seasonal")
    
    # ── 检测攻略 ──
    if any(kw in text for kw in ["攻略", "指南", "推荐", "建议", "新手"]):
        return result("guide")
    
    # ── 默认：返回近期概览 ──
    return result("notable")


# ══════════════════════════════════════════════════════════════
# 查询执行
# ══════════════════════════════════════════════════════════════

def query_notable(days_back: int = 7) -> list[dict]:
    """查询近期稀有/重要鸟讯（融合 eBird + birdrecord.cn，使用已配置的区域）。"""
    results = []

    # 1. eBird 稀有鸟讯
    try:
        eb = get_ebird()
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
    except Exception as e:
        logger.info("eBird notable query failed: %s", e, exc_info=True)
        results.append({"source": "eBird", "error": str(e)})

    # 2. birdrecord.cn 低频率物种（reportCount ≤ 3 的物种）
    try:
        br = get_birdrecord()
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
    except Exception as e:
        logger.info("BirdRecord notable query failed: %s", e, exc_info=True)
        results.append({"source": "birdrecord.cn", "error": str(e)})

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
    errors = []

    # 1. eBird
    ebird_results = []
    code = CN_TO_CODE.get(species_name)
    try:
        eb = get_ebird()
        if code:
            raw = eb.recent_observations(species_code=code, days_back=days_back, max_results=20)
            ebird_results = _normalize_ebird_obs(raw)
        else:
            all_obs = eb.recent_observations(days_back=days_back, max_results=100)
            raw = [o for o in all_obs if species_name in o.get("comName", "") or species_name in o.get("sciName", "")]
            ebird_results = _normalize_ebird_obs(raw)
    except Exception as e:
        logger.info(
            "eBird species query failed for %s: %s",
            species_name,
            e,
            exc_info=True,
        )
        errors.append({"source": "eBird", "message": str(e)})

    # 2. birdrecord.cn — 报告频率（该物种在 birdrecord.cn 上的报告次数）
    birdrecord_result = {"total_reports": 0, "districts": []}
    try:
        br = get_birdrecord()
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
    except Exception as e:
        logger.info(
            "BirdRecord species query failed for %s: %s",
            species_name,
            e,
            exc_info=True,
        )
        errors.append({"source": "birdrecord.cn", "message": str(e)})

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
        "errors": errors,
    }


def query_hotspot(hotspot_name: str, days_back: int = 7, max_results: int = 20) -> dict:
    """查询某个热点的近期记录，返回热点信息和观察列表。"""
    try:
        eb = get_ebird()
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
        if not scored:
            return {"error": f"未找到热点 '{hotspot_name}'"}

        def _last_date_value(hotspot: dict) -> float:
            raw = hotspot.get("lastDate", "")
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    return datetime.strptime(raw[:16] if "%H" in fmt else raw[:10], fmt).timestamp()
                except (TypeError, ValueError):
                    continue
            return 0

        def _num_species(hotspot: dict) -> int:
            try:
                return int(hotspot.get("numSpecies", 0))
            except (TypeError, ValueError):
                return 0

        scored.sort(key=lambda x: (x[0], -_last_date_value(x[1]), -_num_species(x[1])))
        primary = scored[0]
        related = sorted(
            scored[1:],
            key=lambda x: (-_last_date_value(x[1]), x[0], -_num_species(x[1])),
        )

        match = primary[1]
        obs = []
        fallback_used = False
        candidates = [primary] + related
        for index, (_, candidate) in enumerate(candidates):
            candidate_obs = eb.hotspot_observations(
                candidate["locId"],
                days_back=days_back,
                max_results=max_results,
            )
            if candidate_obs or index == len(candidates) - 1:
                match = candidate
                obs = candidate_obs
                fallback_used = index > 0
                break

        return {
            "hotspot": match,
            "observations": obs,
            "matched_hotspots": [
                {
                    "locName": h.get("locName", ""),
                    "locId": h.get("locId", ""),
                    "lastDate": h.get("lastDate", ""),
                    "numSpecies": h.get("numSpecies", ""),
                }
                for _, h in scored[:10]
            ],
            "fallback_used": fallback_used,
        }
    except Exception as e:
        logger.info("Hotspot query failed for %s: %s", hotspot_name, e, exc_info=True)
        return {"error": str(e)}


def _region_params(region: Optional[str] = None, province: Optional[str] = None) -> dict:
    """Normalize explicit region/province arguments into scoped-region params."""
    params = {}

    if region:
        extracted = extract_region(region)
        if extracted:
            params.update(extracted)
        elif re.fullmatch(r"CN-\d{2}", region, flags=re.IGNORECASE):
            code = region.upper()
            params["region"] = code
            params["province"] = REGION_CODE_TO_PROVINCE.get(code)
        else:
            params["region"] = region

    if province:
        extracted = extract_region(province)
        if extracted:
            params.update(extracted)
        else:
            params["province"] = province
            for known_region, known_province in REGION_CODE_TO_PROVINCE.items():
                if known_province == province:
                    params.setdefault("region", known_region)
                    break

    return params


def resolve_region(query_or_region: str = "") -> dict:
    """Resolve a query-scoped birding region, defaulting to the configured Beijing region."""
    explicit = extract_region(query_or_region) if query_or_region else {}
    if explicit:
        return {
            "region": explicit.get("region"),
            "province": explicit.get("province"),
            "label": (
                f"{explicit.get('province')} ({explicit.get('region')})"
                if explicit.get("province") else explicit.get("region")
            ),
            "source": "query",
        }

    region = os.environ.get("BIRDING_REGION", BIRDING_REGION)
    province = os.environ.get("BIRDING_PROVINCE", REGION_CODE_TO_PROVINCE.get(region, BIRDING_PROVINCE))
    return {
        "region": region,
        "province": province,
        "label": f"{province} ({region})" if province else region,
        "source": "default",
    }


def list_regions() -> list[dict]:
    """List built-in region aliases that the Nanobot layer can offer or resolve."""
    by_region = {}
    for alias, (region, province) in REGION_ALIASES.items():
        entry = by_region.setdefault(
            region,
            {"region": region, "province": province, "aliases": []},
        )
        entry["aliases"].append(alias)

    default_region = os.environ.get("BIRDING_REGION", BIRDING_REGION)
    rows = []
    for entry in by_region.values():
        rows.append({
            **entry,
            "label": f"{entry['province']} ({entry['region']})",
            "is_default": entry["region"] == default_region,
        })
    return sorted(rows, key=lambda item: (not item["is_default"], item["province"]))


def resolve_place(query_or_place: str) -> dict:
    """Resolve a known Beijing hotspot alias without making live API calls."""
    text = query_or_place or ""
    for alias, full_name in sorted(HOTSPOT_ALIAS.items(), key=lambda x: -len(x[0])):
        if alias in text:
            return {"place": full_name, "alias": alias, "source": "alias"}
    return {"place": text.strip(), "alias": "", "source": "literal"}


def _static_hotspot_guides(query: str = "") -> list[dict]:
    """Return static Beijing guide entries, optionally filtered by alias/name."""
    try:
        from bird_tool import HOTSPOTS
    except Exception as e:
        logger.info("Failed to load static hotspot guide: %s", e, exc_info=True)
        return []

    place = resolve_place(query).get("place", "") if query else ""
    text = query.lower()
    matches = []
    for item in HOTSPOTS:
        name = item.get("name", "")
        haystack = name.lower()
        if place and place not in name and text not in haystack:
            continue
        matches.append({
            "name": name,
            "rating": item.get("rating", ""),
            "best": item.get("best", ""),
            "description": item.get("description", ""),
            "birds": item.get("birds", ""),
            "tips": item.get("tips", ""),
            "source": "static-beijing-guide",
        })
    return matches


def find_static_hotspot_guide(hotspot_name: str) -> Optional[dict]:
    """Find one static Beijing guide entry for a known hotspot alias."""
    guides = _static_hotspot_guides(hotspot_name)
    return guides[0] if guides else None


def get_static_place_guide(place_name: str = "") -> dict:
    """Return static Beijing place-guide entries for agent-side planning synthesis."""
    return {
        "region": "北京 (CN-11)",
        "query": place_name,
        "places": _static_hotspot_guides(place_name),
    }


def list_places(
    region: Optional[str] = None,
    province: Optional[str] = None,
    query: str = "",
    limit: int = 30,
) -> dict:
    """List live eBird hotspots for a region, with static Beijing fallback guides."""
    params = _region_params(region, province)
    source_errors = []
    places = []
    query_text = query.lower()
    canonical_query = resolve_place(query).get("place", query).lower() if query else ""

    with scoped_region(params):
        active_region = resolve_region()
        try:
            hotspots = get_ebird().hotspot_list()
            for hotspot in hotspots:
                name = hotspot.get("locName", "")
                name_lower = name.lower()
                if canonical_query and canonical_query not in name_lower and query_text not in name_lower:
                    continue
                places.append({
                    "name": name,
                    "locId": hotspot.get("locId", ""),
                    "lat": hotspot.get("lat", ""),
                    "lng": hotspot.get("lng", ""),
                    "lastDate": hotspot.get("lastDate", ""),
                    "numSpecies": hotspot.get("numSpecies", ""),
                    "numChecklists": hotspot.get("numChecklists", ""),
                    "source": "eBird",
                })
        except Exception as e:
            logger.info("Place list query failed: %s", e, exc_info=True)
            source_errors.append({"source": "eBird", "message": str(e)})

        if active_region.get("region") == "CN-11":
            existing = {p.get("name") for p in places}
            for guide in _static_hotspot_guides(query):
                if guide["name"] not in existing:
                    places.append(guide)

        return {
            "region": active_region,
            "query": query,
            "places": places[:limit],
            "source_errors": source_errors,
        }


def get_place_recent_observations(
    place_name: str,
    region: Optional[str] = None,
    province: Optional[str] = None,
    days_back: int = 7,
    max_results: int = 30,
) -> dict:
    """Fetch recent eBird observations for a place/hotspot name in a scoped region."""
    params = _region_params(region, province)
    place = resolve_place(place_name).get("place", place_name)
    with scoped_region(params):
        data = query_hotspot(place, days_back=days_back, max_results=max_results)
        if isinstance(data, dict):
            return {**data, "region": resolve_region(), "query": place_name, "resolved_place": place}
        return {"error": "Unexpected hotspot query response", "region": resolve_region(), "query": place_name}


def get_species_status(
    species_name: str,
    region: Optional[str] = None,
    province: Optional[str] = None,
    days_back: int = 30,
) -> dict:
    """Fetch recent status for a species using eBird plus birdrecord.cn."""
    params = _region_params(region, province)
    with scoped_region(params):
        data = query_species_recent(species_name, days_back=days_back)
        return {**data, "region": resolve_region(), "query": species_name}


def get_notable_alerts(
    region: Optional[str] = None,
    province: Optional[str] = None,
    days_back: int = 7,
) -> dict:
    """Fetch notable/rare sightings for a scoped region."""
    params = _region_params(region, province)
    with scoped_region(params):
        return {
            "region": resolve_region(),
            "records": query_notable(days_back=days_back),
        }


def get_family_status(
    family_cn_or_sci: str,
    region: Optional[str] = None,
    province: Optional[str] = None,
    species_limit: int = 30,
) -> dict:
    """Fetch recent regional status for a bird family."""
    family_sci = CN_FAMILY_MAP.get(family_cn_or_sci, family_cn_or_sci)
    params = _region_params(region, province)
    with scoped_region(params):
        data = query_family(family_sci, species_limit=species_limit)
        return {**data, "region": resolve_region(), "query": family_cn_or_sci}


def get_seasonal_context(month: Optional[int] = None) -> dict:
    """Return static seasonal context the agent can combine with live data."""
    if month is None:
        month = datetime.now().month
    return {
        "month": month,
        "region": resolve_region(),
        "summary": query_seasonal(month),
    }


def query_hotspot_rankings() -> list[dict]:
    """获取热点排名（按物种数，使用已配置的区域）。"""
    try:
        eb = get_ebird()
        hotspots = eb.hotspot_list()
        def _sp(h):
            try:
                return int(h.get("numSpecies", 0))
            except (TypeError, ValueError):
                return 0
        hotspots.sort(key=_sp, reverse=True)
        return hotspots
    except Exception as e:
        logger.info("Hotspot ranking query failed: %s", e, exc_info=True)
        return [{"error": str(e)}]


def query_geo(lat: float, lng: float, dist_km: int = 10, days_back: int = 7) -> dict:
    """查询坐标周边鸟况。"""
    try:
        eb = get_ebird()
        obs = eb.geo_recent(lat, lng, dist_km=dist_km, days_back=days_back, max_results=30)
        notable = eb.geo_notable(lat, lng, dist_km=dist_km, days_back=days_back*2, max_results=10)
        return {"observations": obs, "notable": notable}
    except Exception as e:
        logger.info("Geo query failed for %s,%s: %s", lat, lng, e, exc_info=True)
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
    """从本地缓存加载完整的 eBird 物种分类（English name → info）。"""
    global _TAXONOMY_CACHE
    if _TAXONOMY_CACHE is not None:
        return _TAXONOMY_CACHE
    map_path = os.path.join(os.path.dirname(__file__), "sources", "cn_species_map.json")
    if os.path.exists(map_path):
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                _TAXONOMY_CACHE = json.load(f)
                return _TAXONOMY_CACHE
        except Exception as e:
            logger.info("Failed to load taxonomy cache %s: %s", map_path, e, exc_info=True)
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
    errors = [o for o in data if o.get("error")]
    records = [o for o in data if not o.get("error")]

    if not records and errors:
        lines = [f"⚠️ 暂时无法确认 {current_region_label()} 近期稀有鸟讯，因为数据源查询失败。"]
        for err in errors:
            lines.append(f"  - {err.get('source', 'unknown')}: {err.get('error', 'unknown error')}")
        return "\n".join(lines)

    if not records:
        return f"📡 已配置区域近期暂无稀有鸟种记录"

    lines = ["━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             "  🚨 稀有鸟讯速递",
             "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    lines.append(f"  区域: {current_region_label()}")

    # 分离来源
    from_ebird = [o for o in records if o.get("source") == "eBird"]
    from_br = [o for o in records if o.get("source") == "birdrecord.cn"]

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
    if errors:
        lines.append("\n  ⚠️ 部分数据源查询失败:")
        for err in errors:
            lines.append(f"    - {err.get('source', 'unknown')}: {err.get('error', 'unknown error')}")
    lines.append(f"  更新于 {datetime.now().strftime('%m-%d %H:%M')}")
    return "\n".join(lines)


def fmt_species(data: dict, species_name: str) -> str:
    """格式化物种查询结果（融合 eBird + birdrecord.cn）。"""
    ebird_obs = data.get("ebird", [])
    br_data = data.get("birdrecord", {})
    errors = data.get("errors", [])
    br_reports = br_data.get("total_reports", 0)

    if not ebird_obs and br_reports == 0 and errors:
        lines = [f"⚠️ 暂时无法确认 {current_region_label()} **{species_name}** 的近期记录，因为数据源查询失败。"]
        for err in errors:
            lines.append(f"  - {err.get('source', 'unknown')}: {err.get('message', 'unknown error')}")
        return "\n".join(lines)

    if not ebird_obs and br_reports == 0:
        return f"🐦 已配置区域近期未发现 **{species_name}** 的记录"

    lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
             f"  🐦 {species_name} 近期区域记录",
             f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    lines.append(f"  区域: {current_region_label()}")

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
    br_districts = br_data.get("districts", [])
    if br_reports > 0:
        lines.append(f"\n  📗 birdrecord.cn ({br_reports}次报告):")
        if br_districts:
            top_dists = sorted(br_districts, key=lambda x: -x['reportCount'])[:6]
            dist_str = " | ".join(f"{d['district']} {d['reportCount']}次" for d in top_dists)
            lines.append(f"    📊 各区分布: {dist_str}")

    if errors:
        lines.append("\n  ⚠️ 部分数据源查询失败:")
        for err in errors:
            lines.append(f"    - {err.get('source', 'unknown')}: {err.get('message', 'unknown error')}")

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
      - 一次性获取区域近期 eBird 记录，并按 familySciName 过滤
      - 一次性获取 birdrecord.cn 区域频率，并按中文科名过滤
      - species_limit 只限制展示数量，不限制统计范围
    """
    _, family_species = get_family_data()
    taxonomy = _load_taxonomy()

    codes = family_species.get(family_sci, [])
    if not codes:
        return {"error": f"未找到科 {family_sci} 的物种数据"}

    code_set = set(codes)

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

    # Find the Chinese family name
    family_cn_candidates = [cn_f for cn_f, sci_f in CN_FAMILY_MAP.items() if sci_f == family_sci]
    family_cn = family_cn_candidates[0] if family_cn_candidates else ""

    errors = []
    ebird_by_code: dict[str, list[dict]] = {}
    try:
        eb = get_ebird()
        recent_obs = eb.recent_observations(days_back=14, max_results=10000)
        for obs in recent_obs:
            code = obs.get("speciesCode", "")
            if code in code_set:
                ebird_by_code.setdefault(code, []).append(obs)
    except Exception as e:
        logger.info("eBird family query failed for %s: %s", family_sci, e, exc_info=True)
        errors.append({"source": "eBird", "message": str(e)})

    birdrecord_by_key: dict[str, dict] = {}
    try:
        br = get_birdrecord()
        br_species = br.get_species_frequency(days_back=30)
        if family_cn_candidates:
            br_species = [
                s for s in br_species
                if s.get("taxonFamily") in family_cn_candidates
            ]
        else:
            br_species = []

        for item in br_species:
            cn_name = item.get("species", "")
            code = CN_TO_CODE.get(cn_name)
            key = code or f"birdrecord:{cn_name}"
            birdrecord_by_key[key] = {
                "cn_name": cn_name,
                "en_name": item.get("englishName", ""),
                "code": code or "",
                "reportCount": item.get("reportCount", 0),
                "districts": [],
            }

        top_for_districts = sorted(
            birdrecord_by_key.values(),
            key=lambda x: -x.get("reportCount", 0),
        )[:min(species_limit, 10)]
        for item in top_for_districts:
            cn_name = item.get("cn_name", "")
            if cn_name:
                item["districts"] = sorted(
                    br.get_species_frequency_by_district(cn_name, days_back=30),
                    key=lambda x: -x.get("reportCount", 0),
                )[:5]
    except Exception as e:
        logger.info("BirdRecord family query failed for %s: %s", family_sci, e, exc_info=True)
        errors.append({"source": "birdrecord.cn", "message": str(e)})

    enriched_by_key: dict[str, dict] = {}
    for code, obs in ebird_by_code.items():
        enriched_by_key[code] = {
            "cn_name": code_to_cn.get(code, ""),
            "en_name": code_to_en.get(code, obs[0].get("comName", "")),
            "code": code,
            "frequency": {
                "total_reports": 0,
                "districts": [],
            },
            "recent_obs": obs[:5],
        }

    for key, item in birdrecord_by_key.items():
        code = item.get("code", "")
        target_key = code or key
        entry = enriched_by_key.setdefault(target_key, {
            "cn_name": item.get("cn_name", ""),
            "en_name": item.get("en_name", ""),
            "code": code,
            "frequency": {
                "total_reports": 0,
                "districts": [],
            },
            "recent_obs": [],
        })
        if item.get("cn_name") and not entry.get("cn_name"):
            entry["cn_name"] = item["cn_name"]
        if item.get("en_name") and not entry.get("en_name"):
            entry["en_name"] = item["en_name"]
        entry["frequency"] = {
            "total_reports": item.get("reportCount", 0),
            "districts": item.get("districts", []),
        }

    enriched = sorted(
        enriched_by_key.values(),
        key=lambda sp: (
            -sp.get("frequency", {}).get("total_reports", 0),
            -len(sp.get("recent_obs", [])),
            sp.get("cn_name") or sp.get("en_name") or "",
        ),
    )

    return {
        "family_cn": family_cn,
        "family_sci": family_sci,
        "family_en": family_en,
        "total_codes": len(codes),
        "recorded_species_count": len(enriched),
        "ebird_species_count": len(ebird_by_code),
        "birdrecord_species_count": len(birdrecord_by_key),
        "species_display_limit": species_limit,
        "species_list": enriched[:species_limit],
        "errors": errors,
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
    recorded_species_count = data.get("recorded_species_count", 0)
    ebird_species_count = data.get("ebird_species_count", 0)
    birdrecord_species_count = data.get("birdrecord_species_count", 0)
    display_limit = data.get("species_display_limit", 30)
    species_list = data.get("species_list", [])
    errors = data.get("errors", [])

    title = f"{family_cn}({family_en})" if family_cn else f"{family_en or data.get('family_sci','')}"

    if not species_list and errors:
        lines.append(f"  🌿 {title} — 分类库该科 {total_codes} 种")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"  区域: {current_region_label()}")
        lines.append("  ⚠️ 暂时无法确认该科的区域近期记录，因为数据源查询失败。")
        for err in errors:
            lines.append(f"    - {err.get('source', 'unknown')}: {err.get('message', 'unknown error')}")
        lines.append(f"\n  📊 数据: eBird + birdrecord.cn · {datetime.now().strftime('%m-%d %H:%M')}")
        return "\n".join(lines)

    lines.append(
        f"  🌿 {title} — 分类库该科 {total_codes} 种；"
        f"区域近期至少 {recorded_species_count} 种有记录"
    )
    lines.append(f"     区域: {current_region_label()}")
    lines.append(f"     eBird {ebird_species_count} 种 | birdrecord.cn {birdrecord_species_count} 种")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    for sp in species_list:
        cn = sp.get("cn_name", "")
        en = sp.get("en_name", "?")
        code = sp.get("code", "")
        freq = sp.get("frequency", {})
        reports = freq.get("total_reports", 0)
        districts = freq.get("districts", [])
        recent = sp.get("recent_obs", [])

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

    if recorded_species_count > len(species_list):
        lines.append(f"  ... 仅展示前 {display_limit} 种，另有 {recorded_species_count - len(species_list)} 种未展开")

    if not species_list and not errors:
        lines.append("  📭 区域内近期暂无该科鸟类记录")

    if errors:
        lines.append("\n  ⚠️ 部分数据源查询失败:")
        for err in errors:
            lines.append(f"    - {err.get('source', 'unknown')}: {err.get('message', 'unknown error')}")

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
             f"  区域: {current_region_label()}",
             f"  历史记录: {species_cnt} 种",
             f"  最近活跃: {last_date}", ""]
    if data.get("fallback_used"):
        lines.append("  注: 精确匹配热点近期无记录，已使用相关活跃子热点。")
        lines.append("")
    
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
    lines.append(f"  区域: {current_region_label()}")
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
    params = classified["params"]
    with scoped_region(params):
        return _dispatch_query(classified["intent"], params)


def _dispatch_query(intent: str, params: dict) -> str:
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
