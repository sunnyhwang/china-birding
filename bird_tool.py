#!/usr/bin/env python3
"""
中国观鸟小工具 · China Birding Tool

Usage:
  python bird_tool.py                  # 静态知识库 + 热点攻略
  python bird_tool.py live             # 实时鸟讯（eBird + 中国观鸟记录中心）
  python bird_tool.py live --rare      # 仅显示稀有鸟种警报
  python bird_tool.py live --hotspot 沙河水库  # 指定热点最新记录
  python bird_tool.py live --geo 39.9 116.3 --dist 5  # 指定坐标周边鸟况
  python bird_tool.py hotspots         # 列出所有热点

默认区域为北京（CN-11），通过环境变量 BIRDING_REGION 切换其他省份。
"""

import os
import argparse
import json
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

# ═══════════════════════════════════════════════
# Static Knowledge Base
# ═══════════════════════════════════════════════

TITLE = r"""
╔══════════════════════════════════════════╗
║      🐦 中国观鸟指南 · China Birding       ║
║      让你的每次出行都有所收获                ║
╚══════════════════════════════════════════╝
"""

# ── Hotspots ─────────────────────────────────

HOTSPOTS = [
    {
        "name": "奥林匹克森林公园 (Olympic Forest Park)",
        "rating": "★★★★★",
        "best": "4-5月, 9-10月",
        "description": "北京最佳城市观鸟点。南区有大片水域，北区更自然。春秋迁徙季鸟类极多。",
        "birds": "蓝歌鸲、红喉歌鸲、黄腰柳莺、各种鹟类、鸲类",
        "tips": "建议早7点前到，北园人少鸟多。南园湿地有翠鸟和苇莺。",
    },
    {
        "name": "天坛公园 (Temple of Heaven)",
        "rating": "★★★★★",
        "best": "4-5月, 10-11月",
        "description": "二环内的鸟类天堂，古柏林区吸引了大量林鸟。近年记录过多种稀有鹟类。",
        "birds": "乌鹟、白眉姬鹟、黄眉姬鹟、红胁蓝尾鸲、戴菊",
        "tips": "游客区外的苗圃和西北角林区最好。长耳鸮冬季会在固定位置栖息。",
    },
    {
        "name": "颐和园 (Summer Palace)",
        "rating": "★★★★☆",
        "best": "全年",
        "description": "昆明湖冬季有大量水鸟，后山区域林鸟丰富。西堤是秋季观鸟黄金段。",
        "birds": "凤头鸊鷉、鸳鸯、各种鸭、白眉鸫、斑鸫",
        "tips": "冬季来湖面看潜鸭和秋沙鸭。春秋沿西堤走有惊喜。",
    },
    {
        "name": "沙河水库 (Shahe Reservoir)",
        "rating": "★★★★★",
        "best": "3-5月, 9-11月",
        "description": "北京最著名的水鸟观测点，春秋迁徙季能见到大量鹬鸻类和多种稀有水鸟。",
        "birds": "反嘴鹬、黑翅长脚鹬、斑尾塍鹬、卷羽鹈鹕、各种鸻鹬",
        "tips": "北岸比南岸好。去年有卷羽鹈鹕记录，震惊国内鸟圈。建议带单筒。",
    },
    {
        "name": "野鸭湖湿地保护区 (Wild Duck Lake)",
        "rating": "★★★★★",
        "best": "10-11月, 3-4月",
        "description": "北京最大的湿地，位于延庆。秋季数万只雁鸭类在此停歇。国家级自然保护区。",
        "birds": "灰鹤、白枕鹤、鸿雁、豆雁、针尾鸭、赤麻鸭",
        "tips": "距市区较远，建议包车或自驾。春秋迁徙季壮观。冬天有灰鹤群。",
    },
    {
        "name": "百望山森林公园 (Baiwangshan Forest Park)",
        "rating": "★★★★☆",
        "best": "4-5月, 9-10月",
        "description": "北京西山的一部分，猛禽迁徙通道。秋季可观猛禽迁徙。",
        "birds": "普通鵟、凤头蜂鹰、雀鹰、燕隼、红脚隼",
        "tips": "秋季9月中-10月中蹲山顶看猛禽过境，天气好时一小时可见上百只。",
    },
    {
        "name": "圆明园 (Yuanmingyuan / Old Summer Palace)",
        "rating": "★★★★☆",
        "best": "4月, 10月",
        "description": "水域丰富，芦苇丛生。春秋迁徙季鸣鸟密度高。",
        "birds": "东方大苇莺、黑眉苇莺、棕头鸦雀、翠鸟、白胸苦恶鸟",
        "tips": "后湖和福海区域最好。春天苇莺多，注意听鸣声。",
    },
    {
        "name": "北京植物园 (Beijing Botanical Garden)",
        "rating": "★★★★☆",
        "best": "4-6月, 9-10月",
        "description": "植物种类丰富，昆虫多，鸟类食物来源充足。适合春季观花观鸟。",
        "birds": "黄腹山雀、银喉长尾山雀、红嘴蓝鹊、斑姬啄木鸟、星头啄木鸟",
        "tips": "樱桃沟和温室周边。春季花鸟同赏。",
    },
    {
        "name": "国家植物园 (樱桃沟) (National Botanical Garden)",
        "rating": "★★★★☆",
        "best": "4-6月",
        "description": "樱桃沟有水杉林，阴湿环境吸引多种鹟科和鸫科鸟类。",
        "birds": "棕腹啄木鸟、白眉鸫、红胁蓝尾鸲、各种柳莺",
        "tips": "早上6-8点最佳，沿溪流走。",
    },
    {
        "name": "龙潭湖公园 (Longtan Lake Park)",
        "rating": "★★★☆☆",
        "best": "4-5月, 10月",
        "description": "东南二环的城中湖公园，春秋有迁徙林鸟过境。",
        "birds": "白眉鸫、斑鸫、黄喉鹀、田鹀",
        "tips": "东门附近的树林和湖心岛周边。",
    },
    {
        "name": "南海子湿地公园 (Nanhaizi Wetland Park)",
        "rating": "★★★★☆",
        "best": "3-5月, 10-11月",
        "description": "南城最大的湿地公园，有大片芦苇和开阔水面。鹿苑附近有麋鹿。",
        "birds": "震旦鸦雀、文须雀、大麻鳽、各种鹭、䴙䴘",
        "tips": "麋鹿苑附近有震旦鸦雀稳定记录。冬季可能有短耳鸮。",
    },
    {
        "name": "温榆河公园 (Wenyuhe Park)",
        "rating": "★★★★☆",
        "best": "4-5月, 9-10月",
        "description": "新建的大型城市公园，生境多样，近年鸟类记录快速增加。",
        "birds": "黑枕黄鹂、黑卷尾、棕腹啄木鸟、灰头绿啄木鸟",
        "tips": "东园的森林区域最值得探索。",
    },
]

# ── Key Species by Month ──────────────────────

SPECIES_BY_MONTH = [
    ("1月 越冬水鸟", "冰面鸭类（绿头鸭、针尾鸭、赤麻鸭）、䴙䴘、白骨顶、灰鹤、短耳鸮"),
    ("2月 早春萌芽", "北朱雀、锡嘴雀、田鹀、芦鹀、苇鹀、戴菊、白腰朱顶雀"),
    ("3月 春迁开始", "豆雁、鸿雁、白额雁、鸻鹬类开始过境、凤头麦鸡、云雀"),
    ("4月 春迁高峰", "极多柳莺、鹟类、鸫类过境；蓝歌鸲、红喉歌鸲、白眉姬鹟、普通夜鹰"),
    ("5月 夏候鸟抵达", "大杜鹃、四声杜鹃、黑枕黄鹂、黑卷尾、黄眉柳莺、厚嘴苇莺"),
    ("6月 繁殖季", "黑眉苇莺、东方大苇莺、棕头鸦雀、白胸苦恶鸟、斑嘴鸭带崽"),
    ("7月 林鸟活跃", "家燕、金腰燕育雏、池鹭、夜鹭、黄苇鳽"),
    ("8月 迁徙前奏", "幼鸟独立、猛禽开始迁徙、红脚隼、燕隼"),
    ("9月 秋迁高峰", "各种鹟、鸫、柳莺、鹀类；猛禽迁徙高峰（百望山）、多种鸻鹬"),
    ("10月 秋迁尾期", "斑鸫、白眉鸫大量过境、灰鹤南迁、短耳鸮出现"),
    ("11月 冬候鸟到", "针尾鸭、赤麻鸭、大天鹅、小天鹅、鸿雁、苇鹀"),
    ("12月 冬季稳定", "北朱雀、戴菊、旋木雀、䴓类、各种越冬鸫、鹀"),
]

# ── Beginner Recommendations ──────────────────

BEGINNER_GUIDE = [
    ("推荐路线（新手友好）", "奥林匹克森林公园南园 → 天坛公园"),
    ("推荐季节", "4月中-5月初（春季迁徙高峰期）"),
    ("必备装备", "双筒望远镜（8×42最佳）、观鸟手册/小程序、水、午餐"),
    ("怎么找鸟", "先听声音！安静站立2-3分钟，观察灌丛中层和树冠层"),
    ("推荐图书", "《中国鸟类野外手册》（马敬能）"),
    ("记录工具", "eBird App / 中国观鸟记录中心小程序"),
    ("注意事项", "不穿亮色衣服，不大声喧哗，不追鸟不扰鸟，不公布繁殖地点"),
]


# ═══════════════════════════════════════════════
# Live Data Sources
# ═══════════════════════════════════════════════

def get_ebird_source():
    """Initialize eBird source with API key (from env)."""
    from sources.ebird_source import EBirdSource
    key = os.environ.get("EBIRD_API_KEY")
    if not key:
        print("⚠️  请设置环境变量 EBIRD_API_KEY (免费申请: https://ebird.org/api/keygen)")
        key = ""
    return EBirdSource(key)


def get_birdrecord_source():
    """Initialize BirdRecord source (uses env BIRDING_PROVINCE)."""
    from sources.birdrecord_source import BirdRecordSource
    import os
    province = os.environ.get("BIRDING_PROVINCE", "北京")
    return BirdRecordSource(province=province)


# ── Live reporters ─────────────────────────────

def cmd_live(args):
    """Fetch and display live bird data."""
    eb = get_ebird_source()

    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"  🐦 实时鸟况 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"{'='*60}")

    # ── Section 1: Rare/Notable sightings ──
    if not args.hotspot and not args.geo:
        lines.append(f"\n📡 稀有/重点鸟种警报 (eBird Notable)")
        try:
            notable = eb.notable_observations(days_back=7, max_results=15)
            if notable:
                for o in notable:
                    lines.append(f"  ★ {o.get('comName','?')} ({o.get('sciName','?')})")
                    lines.append(f"    @ {o.get('locName','?')} [{o.get('obsDt','?')}] ×{o.get('howMany','1')}")
            else:
                lines.append("  （暂无稀有鸟种记录）")
        except Exception as e:
            lines.append(f"  ⚠️ {e}")

    # ── Section 2: Recent observations ──
    if args.hotspot:
        # Get observations for a specific hotspot
        hs_name = args.hotspot
        # Find hotspot locId from name
        try:
            hotspots = eb.hotspot_list()
            q = hs_name.lower()
            # Score matches: exact > starts with > contains
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
            match = scored[0][1] if scored else None
            if match:
                lines.append(f"\n📍 热点: {match['locName']}")
                obs = eb.hotspot_observations(match["locId"], days_back=3, max_results=20)
                lines.append(f"  最近3天观测记录: {len(obs)} 条")
                for o in obs[:15]:
                    lines.append(eb.format_observation(o))
            else:
                lines.append(f"\n⚠️ 未找到匹配热点 '{hs_name}'")
                lines.append("  提示: 试试 'python bird_tool.py hotspots' 查看所有热点")
        except Exception as e:
            lines.append(f"  ⚠️ {e}")

    elif args.geo:
        # Observations near coordinates
        lat, lng = args.geo
        dist = args.dist or 10
        lines.append(f"\n📍 坐标周边 ({lat}, {lng}) 半径 {dist}km")
        try:
            obs = eb.geo_recent(lat, lng, dist_km=dist, days_back=7, max_results=30)
            lines.append(f"  最近7天: {len(obs)} 条记录")
            for o in obs[:15]:
                lines.append(eb.format_observation(o))
            # Also check notable near geo
            notable = eb.geo_notable(lat, lng, dist_km=dist, days_back=14, max_results=10)
            if notable:
                lines.append(f"\n  ★ 周边稀有记录:")
                for o in notable[:5]:
                    lines.append(f"    {o.get('comName','?')} @ {o.get('locName','?')} [{o.get('obsDt','?')}]")
        except Exception as e:
            lines.append(f"  ⚠️ {e}")

    else:
        # General recent observations for Beijing (skip if --rare)
        if not args.rare:
            try:
                obs = eb.recent_observations(days_back=7, max_results=15)
                if obs:
                    lines.append(f"\n📋 近期观测 (eBird) — {len(obs)} 条最新记录")
                    # Group by location
                    by_loc = {}
                    for o in obs:
                        loc = o.get("locName", "未知")
                        by_loc.setdefault(loc, []).append(o)
                    for loc, loc_obs in list(by_loc.items())[:8]:
                        lines.append(f"  📍 {loc}")
                        for o in loc_obs[:5]:
                            lines.append(f"    {o.get('comName','?')} ×{o.get('howMany','?')} [{o.get('obsDt','?')}]")
                        if len(loc_obs) > 5:
                            lines.append(f"    ... 及另外 {len(loc_obs)-5} 种")
            except Exception as e:
                lines.append(f"  ⚠️ 获取eBird数据失败: {e}")

        # ── Section 3: BirdRecord China ──
        lines.append(f"\n🇨🇳 中国观鸟记录中心 · 近期记录")
        try:
            br = get_birdrecord_source()
            activities = br.recent_activities(limit=10)
            if activities:
                for act in activities:
                    lines.append(br.format_activity(act))
            else:
                lines.append("  （暂无该地区记录）")
        except Exception as e:
            lines.append(f"  ⚠️ {e}")

    # Summary
    lines.append(f"\n{'─'*60}")
    lines.append(f"  数据来源: eBird · 中国观鸟记录中心")
    lines.append(f"  更新于: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"{'─'*60}\n")

    print("\n".join(lines))


def cmd_hotspots(args):
    """List all Beijing hotspots from eBird."""
    eb = get_ebird_source()
    print(f"\n📌 观鸟热点 (eBird) — {len(eb.hotspot_list())} 个")
    print(f"{'='*60}")

    try:
        hotspots = eb.hotspot_list()
        # Sort by numSpecies descending
        def _sp(h):
            try:
                return int(h.get("numSpecies", 0))
            except:
                return 0
        hotspots.sort(key=_sp, reverse=True)

        for h in hotspots[:30]:
            name = h.get("locName", "?")
            sp = h.get("numSpecies", "?")
            last = h.get("lastDate", "?")
            print(f"  {name:45s} | {str(sp):>4s} 种 | 最近: {last}")
    except Exception as e:
        print(f"  ⚠️ {e}")
    print()


def cmd_month(args):
    """Show what's in season this month."""
    now = datetime.now()
    month = args.month or now.month

    print(f"\n📅 {now.year}年{month}月 观鸟看点")
    print(f"{'='*60}")

    for m_name, species in SPECIES_BY_MONTH:
        m_num = int(m_name.split("月")[0].split()[-1])
        if m_num == month:
            print(f"\n📌 {m_name}")
            print(f"  {species}")
            break
    else:
        print(f"\n  (暂未收录{month}月数据)")

    print()


# ── Original static commands ───────────────────

def cmd_guide(args):
    """Show the static knowledge base / hotspot guide."""
    print(TITLE)

    # Hotspots
    print(f"\n📌 观鸟热点推荐\n{'='*60}")
    for h in HOTSPOTS:
        print(f"\n{h['name']}  {h['rating']}  最佳: {h['best']}")
        print(f"  {h['description']}")
        print(f"  常见鸟种: {h['birds']}")
        print(f"  建议: {h['tips']}")

    # Species by month
    print(f"\n\n📅 各月重点鸟种\n{'='*60}")
    for m_name, sp in SPECIES_BY_MONTH:
        print(f"\n  {m_name}")
        print(f"    {sp}")

    # Beginner guide
    print(f"\n\n🎯 新手入门\n{'='*60}")
    for title, content in BEGINNER_GUIDE:
        print(f"\n  {title}:")
        print(f"    {content}")

    print()
    print(f"  ⚡ 试试 'python bird_tool.py live' 获取实时鸟况")
    print()


# ═══════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="中国观鸟指南 · China Birding Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python bird_tool.py                  静态指南
  python bird_tool.py live             实时鸟况（eBird + 中国观鸟记录中心）
  python bird_tool.py live --rare      只看稀有鸟种
  python bird_tool.py live --hotspot 沙河水库  指定热点
  python bird_tool.py live --geo 39.9 116.3 --dist 5  坐标周边
  python bird_tool.py hotspots         列出观鸟热点
  python bird_tool.py month --month 4  查看某月鸟种
        """,
    )
    parser.add_argument(
        "command", nargs="?",
        choices=["live", "hotspots", "month"],
        help="子命令: guide(默认), live(实时), hotspots(热点), month(月份)",
    )

    # live mode options
    parser.add_argument("--rare", action="store_true", help="仅显示稀有鸟种")
    parser.add_argument("--hotspot", type=str, help="指定热点名称查看记录")
    parser.add_argument("--geo", type=float, nargs=2, metavar=("LAT", "LNG"), help="指定坐标")
    parser.add_argument("--dist", type=int, default=10, help="坐标搜索半径(km)")
    parser.add_argument("--month", type=int, help="指定月份(1-12)")

    args = parser.parse_args()

    cmd = args.command or "guide"

    if cmd == "live":
        cmd_live(args)
    elif cmd == "hotspots":
        cmd_hotspots(args)
    elif cmd == "month":
        cmd_month(args)
    else:
        cmd_guide(args)


if __name__ == "__main__":
    main()
