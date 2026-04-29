#!/usr/bin/env python3
"""
BirdRecord.cn (中国观鸟记录中心) data source.

Uses the birdrecord-cli library (v0.1.3) to query the official API.
Uses a share-level token — no user login required.

Available data:
  - Species lists for a region (not individual observations)
  - Activity/survey metadata (location, date, species count — no species list)
  - Aggregate species frequency (report counts per species in a region/date)

Beijing: province="北京"
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from birdrecord_cli.client import BirdrecordClient
from birdrecord_cli.models.client import (
    CommonPageActivityRequest,
    CommonListActivityTaxonRequest,
    ChartStatisticsTaxonRequest,
)

# ----------------------------------------------------------------
# Constants — override via env var BIRDING_PROVINCE (e.g. "上海", "广东")
# ----------------------------------------------------------------
DEFAULT_PROVINCE = os.environ.get("BIRDING_PROVINCE", "北京")

BEIJING_DISTRICTS = [
    "东城区", "西城区", "朝阳区", "丰台区", "石景山区",
    "海淀区", "门头沟区", "房山区", "通州区", "顺义区",
    "昌平区", "大兴区", "怀柔区", "平谷区", "密云区",
    "延庆区",
]

TZ = timezone(timedelta(hours=8))


# ----------------------------------------------------------------
# BirdRecord source
# ----------------------------------------------------------------
class BirdRecordSource:
    """Query birdrecord.cn for bird data. Configurable per province.

    Set env BIRDING_PROVINCE to change region (default: 北京).
    Set env BIRDRECORD_SHARE_TOKEN for authenticated access (optional).
    """

    def __init__(self, province: str = None):
        self._client = BirdrecordClient()
        self.province = province or DEFAULT_PROVINCE

    # ----------------------------------------------------------
    # Species frequency (report counts per species)
    # ----------------------------------------------------------

    def get_species_frequency(
        self,
        species_name: Optional[str] = None,
        days_back: int = 14,
        district: Optional[str] = None,
    ) -> list[dict]:
        """Get how many reports each species appeared in.

        Args:
            species_name: filter for a specific species
            days_back: lookback window
            district: filter by district (e.g. "海淀区")

        Returns list of {species, englishName, latinName, reportCount, source}
        """
        now = datetime.now(TZ)
        start = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")

        req = CommonListActivityTaxonRequest(
            province=self.province,
            startTime=start,
            endTime=end,
        )
        if species_name:
            req.taxonname = species_name
        if district:
            req.district = district

        # Increase limit to get all species
        req.limit = 500
        req.start = 1

        try:
            resp = self._client.common_list_activity_taxon(req)
            results = []
            for t in resp.payload:
                results.append({
                    "species": t.taxonname,
                    "englishName": t.englishname or "",
                    "latinName": t.latinname or "",
                    "reportCount": t.recordcount,
                    "taxonOrder": t.taxonordername or "",
                    "taxonFamily": t.taxonfamilyname or "",
                    "source": "birdrecord",
                })
            # Sort by reportCount descending
            results.sort(key=lambda x: -x["reportCount"])
            return results
        except Exception:
            return []  # silent fail — some districts have no data

    def get_species_frequency_by_district(
        self, species_name: str, days_back: int = 14
    ) -> list[dict]:
        """Get a species' report count in each Beijing district.

        Returns list of {district, reportCount}
        """
        results = []
        for d in BEIJING_DISTRICTS:
            try:
                freq = self.get_species_frequency(
                    species_name=species_name, days_back=days_back, district=d
                )
                if freq:
                    results.append({
                        "district": d,
                        "reportCount": freq[0]["reportCount"],
                    })
            except Exception:
                pass  # skip districts with no data
        return results

    # ----------------------------------------------------------
    # Monthly statistics
    # ----------------------------------------------------------

    def get_monthly_statistics(
        self,
        species_name: str = "",
        days_back: int = 30,
    ) -> list[dict]:
        """Get monthly statistics for a species in Beijing.

        Returns list of {month, reportCount, observationCount}
        """
        now = datetime.now(TZ)
        start = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")

        req = ChartStatisticsTaxonRequest(
            province=self.province,
            startTime=start,
            endTime=end,
            taxonname=species_name,
        )
        try:
            resp = self._client.chart_record_statistics_taxon(req)
            results = []
            for r in resp.payload:
                results.append({
                    "month": r.taxon_month,
                    "reportCount": r.taxon_num,
                    "observationCount": r.taxon_count,
                })
            return results
        except Exception as e:
            print(f"[birdrecord] get_monthly_statistics error: {e}", file=sys.stderr)
            return []

    # ----------------------------------------------------------
    # Recent activities (metadata only — location, date, species count)
    # ----------------------------------------------------------

    def get_recent_activities(
        self,
        days_back: int = 14,
        limit: int = 20,
        page: int = 1,
        district: Optional[str] = None,
    ) -> list[dict]:
        """Get recent birding survey activities in Beijing.

        Returns basic metadata: location, date, observer, total species count.
        (The API does not expose which species were observed.)
        """
        now = datetime.now(TZ)
        start = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")

        req = CommonPageActivityRequest(
            province=self.province,
            startTime=start,
            endTime=end,
            start=page,
            limit=limit,
        )
        if district:
            req.district = district

        try:
            resp = self._client.common_page_activity(req)
            activities = []
            for a in resp.payload:
                activities.append({
                    "id": str(a.id),
                    "name": a.name,
                    "location": a.point_name,
                    "address": a.address,
                    "district": a.district_name,
                    "date": a.start_time,
                    "observer": a.username,
                    "speciesCount": a.taxoncount,
                    "source": "birdrecord",
                })
            return activities
        except Exception as e:
            print(f"[birdrecord] get_recent_activities error: {e}", file=sys.stderr)
            return []

    # ----------------------------------------------------------
    # Notable / rare species detection
    # ----------------------------------------------------------

    def get_notable_species(
        self,
        days_back: int = 14,
        max_reports: int = 3,
    ) -> list[dict]:
        """Find species with low report counts (= potentially rare/notable).

        Returns list of species sorted by reportCount ascending.
        """
        all_species = self.get_species_frequency(days_back=days_back)
        rare = [s for s in all_species if s["reportCount"] <= max_reports]
        return rare


# -------------------------------------------------
# Module-level convenience instance
# -------------------------------------------------
_source: Optional[BirdRecordSource] = None


def get_source() -> BirdRecordSource:
    global _source
    if _source is None:
        _source = BirdRecordSource()
    return _source


# -------------------------------------------------
# Self-test
# -------------------------------------------------
if __name__ == "__main__":
    import locale
    locale.setlocale(locale.LC_ALL, '')
    sys.stdout.reconfigure(encoding="utf-8")

    src = get_source()

    print("=== 普通翠鸟 30天报告频率 ===")
    freq = src.get_species_frequency("普通翠鸟", days_back=30)
    for f in freq:
        print(f"  {f['species']} ({f['englishName']}) — {f['reportCount']}次报告")

    print("\n=== 普通翠鸟 各区分布 (30天) ===")
    by_dist = src.get_species_frequency_by_district("普通翠鸟", days_back=30)
    for d in sorted(by_dist, key=lambda x: -x['reportCount'])[:8]:
        print(f"  {d['district']}: {d['reportCount']}次报告")

    print("\n=== 海淀区最近活动 (14天) ===")
    acts = src.get_recent_activities(days_back=14, limit=10, district="海淀区")
    for a in acts:
        print(f"  [{a['date']}] {a['location']} — {a['observer']} ({a['speciesCount']}种)")

    print("\n=== 近30天低频鸟种 (≤3次报告) ===")
    rare = src.get_notable_species(days_back=30, max_reports=3)
    for r in rare[:15]:
        print(f"  {r['species']} ({r['englishName']}) — {r['reportCount']}次报告")
