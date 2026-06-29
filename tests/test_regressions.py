import argparse
import contextlib
import io
import os
import tempfile
import unittest

import agent
import bird_tool
import config as local_config


class ClassificationTests(unittest.TestCase):
    def test_newbie_birding_question_is_guide_not_species(self):
        self.assertEqual(agent.classify_query("新手去哪观鸟")["intent"], "guide")

    def test_hotspot_weekend_question_is_hotspot_data_request(self):
        classified = agent.classify_query("奥森 birds on a sunday afternoon")

        self.assertEqual(classified["intent"], "hotspot")
        self.assertEqual(classified["params"]["hotspot"], "奥林匹克森林公园")

    def test_region_prefixed_family_query_is_not_species(self):
        classified = agent.classify_query("广东鸭科最近有哪些记录")

        self.assertEqual(classified["intent"], "family")
        self.assertEqual(classified["params"]["region"], "CN-44")
        self.assertEqual(classified["params"]["family_cn"], "鸭科")

    def test_static_guide_does_not_require_live_credentials(self):
        old_key = os.environ.pop("EBIRD_API_KEY", None)
        try:
            output = agent.query_birds("新手去哪观鸟")
        finally:
            if old_key is not None:
                os.environ["EBIRD_API_KEY"] = old_key

        self.assertIn("观鸟攻略速览", output)

    def test_query_scoped_region_does_not_leak(self):
        class FakeEBird:
            def notable_observations(self, **kwargs):
                return [
                    {
                        "comName": os.environ.get("BIRDING_REGION", ""),
                        "locName": "region-marker",
                        "obsDt": "2026-06-29",
                    }
                ]

        class FakeBirdRecord:
            def get_notable_species(self, **kwargs):
                return []

        old_region = os.environ.get("BIRDING_REGION")
        old_province = os.environ.get("BIRDING_PROVINCE")
        old_get_ebird = agent.get_ebird
        old_get_birdrecord = agent.get_birdrecord
        try:
            os.environ["BIRDING_REGION"] = "CN-11"
            os.environ["BIRDING_PROVINCE"] = "北京"
            agent.get_ebird = lambda: FakeEBird()
            agent.get_birdrecord = lambda: FakeBirdRecord()

            output = agent.query_birds("上海最近有什么稀有鸟")
        finally:
            agent.get_ebird = old_get_ebird
            agent.get_birdrecord = old_get_birdrecord
            if old_region is None:
                os.environ.pop("BIRDING_REGION", None)
            else:
                os.environ["BIRDING_REGION"] = old_region
            if old_province is None:
                os.environ.pop("BIRDING_PROVINCE", None)
            else:
                os.environ["BIRDING_PROVINCE"] = old_province

        self.assertIn("CN-31", output)
        self.assertEqual(os.environ.get("BIRDING_REGION"), old_region)


class ToolApiTests(unittest.TestCase):
    def test_list_regions_exposes_default_and_aliases(self):
        rows = agent.list_regions()
        beijing = next(row for row in rows if row["region"] == "CN-11")

        self.assertEqual(beijing["province"], "北京")
        self.assertIn("北京", beijing["aliases"])
        self.assertIn("beijing", beijing["aliases"])

    def test_resolve_region_supports_query_override_and_default(self):
        shanghai = agent.resolve_region("上海最近有什么稀有鸟")
        default = agent.resolve_region()

        self.assertEqual(shanghai["region"], "CN-31")
        self.assertEqual(shanghai["province"], "上海")
        self.assertEqual(default["source"], "default")

    def test_list_places_uses_static_beijing_fallback_without_live_key(self):
        old_key = os.environ.pop("EBIRD_API_KEY", None)
        try:
            result = agent.list_places(query="奥森", limit=5)
        finally:
            if old_key is not None:
                os.environ["EBIRD_API_KEY"] = old_key

        self.assertEqual(result["region"]["region"], "CN-11")
        self.assertTrue(result["source_errors"])
        self.assertTrue(any("奥林匹克森林公园" in place["name"] for place in result["places"]))

    def test_get_static_place_guide_resolves_alias(self):
        guide = agent.get_static_place_guide("奥森")

        self.assertEqual(guide["region"], "北京 (CN-11)")
        self.assertTrue(any("Olympic Forest Park" in place["name"] for place in guide["places"]))

    def test_get_place_recent_observations_scopes_region_and_restores_env(self):
        calls = []
        old_region = os.environ.get("BIRDING_REGION")
        old_province = os.environ.get("BIRDING_PROVINCE")
        old_query_hotspot = agent.query_hotspot
        try:
            os.environ["BIRDING_REGION"] = "CN-11"
            os.environ["BIRDING_PROVINCE"] = "北京"

            def fake_query_hotspot(hotspot, days_back=7, max_results=20):
                calls.append({
                    "hotspot": hotspot,
                    "days_back": days_back,
                    "max_results": max_results,
                    "region": os.environ.get("BIRDING_REGION"),
                })
                return {
                    "hotspot": {"locName": hotspot},
                    "observations": [{"comName": "Great Spotted Woodpecker"}],
                }

            agent.query_hotspot = fake_query_hotspot
            result = agent.get_place_recent_observations(
                "奥森",
                region="上海",
                days_back=3,
                max_results=7,
            )
        finally:
            agent.query_hotspot = old_query_hotspot
            if old_region is None:
                os.environ.pop("BIRDING_REGION", None)
            else:
                os.environ["BIRDING_REGION"] = old_region
            if old_province is None:
                os.environ.pop("BIRDING_PROVINCE", None)
            else:
                os.environ["BIRDING_PROVINCE"] = old_province

        self.assertEqual(result["resolved_place"], "奥林匹克森林公园")
        self.assertEqual(result["region"]["region"], "CN-31")
        self.assertEqual(calls[0]["region"], "CN-31")
        self.assertEqual(calls[0]["days_back"], 3)
        self.assertEqual(calls[0]["max_results"], 7)
        self.assertEqual(os.environ.get("BIRDING_REGION"), old_region)

    def test_query_hotspot_prefers_active_related_hotspot(self):
        class FakeEBird:
            def hotspot_list(self):
                return [
                    {
                        "locId": "general",
                        "locName": "奥林匹克森林公园 (Olympic Forest Park)",
                        "lastDate": "2026-06-19 06:56",
                        "numSpecies": "252",
                    },
                    {
                        "locId": "south",
                        "locName": "奥林匹克森林公园南园 (Olympic Forest Park South)",
                        "lastDate": "2026-06-26 18:10",
                        "numSpecies": "268",
                    },
                ]

            def hotspot_observations(self, loc_id, **kwargs):
                if loc_id == "general":
                    return []
                return [{"comName": "Chinese Blackbird", "obsDt": "2026-06-26 18:10"}]

        old_get_ebird = agent.get_ebird
        try:
            agent.get_ebird = lambda: FakeEBird()
            result = agent.query_hotspot("奥林匹克森林公园", days_back=7)
        finally:
            agent.get_ebird = old_get_ebird

        self.assertEqual(result["hotspot"]["locId"], "south")
        self.assertEqual(result["observations"][0]["comName"], "Chinese Blackbird")


class ConfigTests(unittest.TestCase):
    def test_local_yaml_sets_missing_env_without_overwriting_existing_values(self):
        old_key = os.environ.get("EBIRD_API_KEY")
        old_region = os.environ.get("BIRDING_REGION")
        old_province = os.environ.get("BIRDING_PROVINCE")
        parsed = {}
        try:
            os.environ.pop("EBIRD_API_KEY", None)
            os.environ["BIRDING_REGION"] = "CN-31"
            os.environ.pop("BIRDING_PROVINCE", None)

            with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=True) as f:
                f.write(
                    "ebird:\n"
                    "  api_key: test-key\n"
                    "birding:\n"
                    "  region: CN-11\n"
                    "  province: 北京\n"
                )
                f.flush()

                parsed = local_config.load_local_config(f.name)

            self.assertEqual(parsed["ebird"]["api_key"], "test-key")
            self.assertEqual(os.environ.get("EBIRD_API_KEY"), "test-key")
            self.assertEqual(os.environ.get("BIRDING_REGION"), "CN-31")
            self.assertEqual(os.environ.get("BIRDING_PROVINCE"), "北京")
        finally:
            if old_key is None:
                os.environ.pop("EBIRD_API_KEY", None)
            else:
                os.environ["EBIRD_API_KEY"] = old_key
            if old_region is None:
                os.environ.pop("BIRDING_REGION", None)
            else:
                os.environ["BIRDING_REGION"] = old_region
            if old_province is None:
                os.environ.pop("BIRDING_PROVINCE", None)
            else:
                os.environ["BIRDING_PROVINCE"] = old_province


class FamilyQueryTests(unittest.TestCase):
    def test_family_query_counts_all_recent_family_records_not_first_page_slice(self):
        taxonomy = {
            f"Duck {i}": {
                "code": f"duck{i}",
                "sciName": f"Anas test{i}",
                "enName": f"Duck {i}",
                "order": "Anseriformes",
                "familyComName": "Ducks, Geese, and Waterfowl",
                "familySciName": "Anatidae",
            }
            for i in range(40)
        }
        taxonomy["Baikal Teal"] = {
            "code": "baitea1",
            "sciName": "Sibirionetta formosa",
            "enName": "Baikal Teal",
            "order": "Anseriformes",
            "familyComName": "Ducks, Geese, and Waterfowl",
            "familySciName": "Anatidae",
        }

        class FakeEBird:
            def recent_observations(self, **kwargs):
                return [
                    {"speciesCode": "duck35", "comName": "Duck 35", "locName": "Late Taxonomy Marsh"},
                    {"speciesCode": "notduck", "comName": "Other Bird", "locName": "Elsewhere"},
                ]

        class FakeBirdRecord:
            def get_species_frequency(self, days_back=30):
                return [
                    {
                        "species": "花脸鸭",
                        "englishName": "Baikal Teal",
                        "reportCount": 7,
                        "taxonFamily": "鸭科",
                    },
                    {
                        "species": "苍鹭",
                        "englishName": "Grey Heron",
                        "reportCount": 99,
                        "taxonFamily": "鹭科",
                    },
                ]

            def get_species_frequency_by_district(self, species_name, days_back=30):
                return [{"district": "海淀区", "reportCount": 3}]

        old_taxonomy = agent._TAXONOMY_CACHE
        old_family_code_cache = agent._FAMILY_CODE_CACHE
        old_family_species_cache = agent._FAMILY_SPECIES_CACHE
        old_get_ebird = agent.get_ebird
        old_get_birdrecord = agent.get_birdrecord
        try:
            agent._TAXONOMY_CACHE = taxonomy
            agent._FAMILY_CODE_CACHE = None
            agent._FAMILY_SPECIES_CACHE = None
            agent.get_ebird = lambda: FakeEBird()
            agent.get_birdrecord = lambda: FakeBirdRecord()

            result = agent.query_family("Anatidae", species_limit=5)
        finally:
            agent._TAXONOMY_CACHE = old_taxonomy
            agent._FAMILY_CODE_CACHE = old_family_code_cache
            agent._FAMILY_SPECIES_CACHE = old_family_species_cache
            agent.get_ebird = old_get_ebird
            agent.get_birdrecord = old_get_birdrecord

        self.assertEqual(result["total_codes"], 41)
        self.assertEqual(result["ebird_species_count"], 1)
        self.assertEqual(result["birdrecord_species_count"], 1)
        self.assertEqual(result["recorded_species_count"], 2)
        self.assertTrue(any(s["code"] == "duck35" for s in result["species_list"]))


class BirdToolTests(unittest.TestCase):
    def test_hotspots_cli_handles_source_errors(self):
        class FakeEBird:
            def hotspot_list(self):
                raise RuntimeError("missing key")

        old_get_ebird = bird_tool.get_ebird_source
        try:
            bird_tool.get_ebird_source = lambda: FakeEBird()
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                bird_tool.cmd_hotspots(argparse.Namespace())
        finally:
            bird_tool.get_ebird_source = old_get_ebird

        self.assertIn("missing key", out.getvalue())

    def test_live_cli_uses_get_recent_activities(self):
        class FakeEBird:
            def notable_observations(self, **kwargs):
                return []

            def recent_observations(self, **kwargs):
                return []

        class FakeBirdRecord:
            def get_recent_activities(self, **kwargs):
                return [{"location": "测试点", "date": "2026-06-29", "speciesCount": 12}]

            def recent_activities(self, **kwargs):
                raise AssertionError("cmd_live should use get_recent_activities")

            def format_activity(self, activity):
                return "  activity-ok"

        old_get_ebird = bird_tool.get_ebird_source
        old_get_birdrecord = bird_tool.get_birdrecord_source
        try:
            bird_tool.get_ebird_source = lambda: FakeEBird()
            bird_tool.get_birdrecord_source = lambda: FakeBirdRecord()
            out = io.StringIO()
            args = argparse.Namespace(hotspot=None, geo=None, rare=False, dist=10)
            with contextlib.redirect_stdout(out):
                bird_tool.cmd_live(args)
        finally:
            bird_tool.get_ebird_source = old_get_ebird
            bird_tool.get_birdrecord_source = old_get_birdrecord

        self.assertIn("activity-ok", out.getvalue())


if __name__ == "__main__":
    unittest.main()
