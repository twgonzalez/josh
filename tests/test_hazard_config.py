# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Unit tests for agents/scenarios/hazard_config.HazardConfig.

Covers:
  - YAML loading + DataSourceSpec unpacking
  - Mobilization floor enforcement (locked decision #4)
  - Dispositive vs. non-dispositive zone-table requirements
  - Degradation range / safe_egress_window positivity
  - load_all_hazard_configs duplicate detection
  - to_js_payload strips data_source

Run:
  uv run python -m unittest tests.test_hazard_config -v
"""
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents.scenarios.hazard_config import (
    DataSourceSpec,
    HazardConfig,
    load_all_hazard_configs,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WILDFIRE_YAML = REPO_ROOT / "config" / "hazards" / "wildfire.yaml"


def _write_yaml(tmp: Path, body: str, name: str = "test.yaml") -> Path:
    """Write a dedented YAML body to a tmp file; return the path."""
    p = tmp / name
    p.write_text(textwrap.dedent(body).lstrip())
    return p


class TestWildfireYamlLoads(unittest.TestCase):
    """The canonical wildfire.yaml loads and parses correctly end-to-end."""

    def test_loads_canonical_file(self):
        cfg = HazardConfig.from_yaml(WILDFIRE_YAML)
        self.assertEqual(cfg.hazard_id, "wildfire")
        self.assertEqual(cfg.mobilization, 0.90)
        self.assertFalse(cfg.dispositive_at_standard_3)
        self.assertEqual(cfg.zone_attribute, "HAZ_CLASS")
        self.assertEqual(cfg.classify_strategy, "most_severe")

    def test_degradation_values(self):
        cfg = HazardConfig.from_yaml(WILDFIRE_YAML)
        self.assertEqual(cfg.degradation["vhfhsz"], 0.35)
        self.assertEqual(cfg.degradation["high_fhsz"], 0.50)
        self.assertEqual(cfg.degradation["moderate_fhsz"], 0.75)
        self.assertEqual(cfg.degradation["non_fhsz"], 1.00)

    def test_safe_egress_windows(self):
        cfg = HazardConfig.from_yaml(WILDFIRE_YAML)
        self.assertEqual(cfg.safe_egress_window["vhfhsz"], 45)
        self.assertEqual(cfg.safe_egress_window["high_fhsz"], 90)
        self.assertEqual(cfg.safe_egress_window["moderate_fhsz"], 120)
        self.assertEqual(cfg.safe_egress_window["non_fhsz"], 120)

    def test_no_hooks_registered(self):
        cfg = HazardConfig.from_yaml(WILDFIRE_YAML)
        self.assertEqual(cfg.hooks, {})

    def test_data_source_loaded_as_spec(self):
        cfg = HazardConfig.from_yaml(WILDFIRE_YAML)
        self.assertIsInstance(cfg.data_source, DataSourceSpec)
        self.assertEqual(cfg.data_source.type, "arcgis_rest")
        self.assertEqual(cfg.data_source.cache_key, "fhsz.geojson")
        self.assertIn("FHSZ", cfg.data_source.url)


class TestMobilizationFloor(unittest.TestCase):
    """Locked decision #4: mobilization must be in [0.90, 1.00]."""

    def _make_cfg(self, mobilization):
        return HazardConfig(
            hazard_id="wildfire",
            data_source=DataSourceSpec(type="arcgis_rest", url="x", cache_key="x"),
            mobilization=mobilization,
            degradation={"non_fhsz": 1.0},
            safe_egress_window={"non_fhsz": 120},
        )

    def test_exact_floor_accepted(self):
        cfg = self._make_cfg(0.90)
        self.assertEqual(cfg.mobilization, 0.90)

    def test_above_floor_accepted(self):
        cfg = self._make_cfg(0.95)
        self.assertEqual(cfg.mobilization, 0.95)

    def test_unity_accepted(self):
        cfg = self._make_cfg(1.00)
        self.assertEqual(cfg.mobilization, 1.00)

    def test_below_floor_rejected(self):
        with self.assertRaises(ValueError) as cm:
            self._make_cfg(0.89)
        self.assertIn("NFPA 101", str(cm.exception))
        self.assertIn("0.89", str(cm.exception))

    def test_above_unity_rejected(self):
        with self.assertRaises(ValueError):
            self._make_cfg(1.01)


class TestDispositiveSemantics(unittest.TestCase):
    """Tsunami-style dispositive hazards must not carry zone tables."""

    def test_dispositive_with_empty_tables_accepted(self):
        cfg = HazardConfig(
            hazard_id="tsunami",
            data_source=DataSourceSpec(type="arcgis_rest", url="x", cache_key="x"),
            mobilization=1.00,
            dispositive_at_standard_3=True,
            # degradation and safe_egress_window intentionally empty
        )
        self.assertTrue(cfg.dispositive_at_standard_3)

    def test_dispositive_with_degradation_rejected(self):
        with self.assertRaises(ValueError) as cm:
            HazardConfig(
                hazard_id="tsunami",
                data_source=DataSourceSpec(type="arcgis_rest", url="x", cache_key="x"),
                mobilization=1.00,
                dispositive_at_standard_3=True,
                degradation={"in_zone": 0.0},   # non-empty → should fail
            )
        self.assertIn("dispositive", str(cm.exception))

    def test_non_dispositive_requires_degradation(self):
        with self.assertRaises(ValueError) as cm:
            HazardConfig(
                hazard_id="wildfire",
                data_source=DataSourceSpec(type="arcgis_rest", url="x", cache_key="x"),
                mobilization=0.90,
                # degradation missing
                safe_egress_window={"non_fhsz": 120},
            )
        self.assertIn("degradation", str(cm.exception))

    def test_non_dispositive_requires_safe_egress_window(self):
        with self.assertRaises(ValueError) as cm:
            HazardConfig(
                hazard_id="wildfire",
                data_source=DataSourceSpec(type="arcgis_rest", url="x", cache_key="x"),
                mobilization=0.90,
                degradation={"non_fhsz": 1.0},
                # safe_egress_window missing
            )
        self.assertIn("safe_egress_window", str(cm.exception))


class TestNumericRangeValidation(unittest.TestCase):
    def _kwargs(self, **overrides):
        base = dict(
            hazard_id="wildfire",
            data_source=DataSourceSpec(type="arcgis_rest", url="x", cache_key="x"),
            mobilization=0.90,
            degradation={"non_fhsz": 1.0},
            safe_egress_window={"non_fhsz": 120},
        )
        base.update(overrides)
        return base

    def test_degradation_above_one_rejected(self):
        with self.assertRaises(ValueError):
            HazardConfig(**self._kwargs(degradation={"non_fhsz": 1.5}))

    def test_degradation_negative_rejected(self):
        with self.assertRaises(ValueError):
            HazardConfig(**self._kwargs(degradation={"non_fhsz": -0.1}))

    def test_egress_window_zero_rejected(self):
        with self.assertRaises(ValueError):
            HazardConfig(**self._kwargs(safe_egress_window={"non_fhsz": 0}))

    def test_egress_window_negative_rejected(self):
        with self.assertRaises(ValueError):
            HazardConfig(**self._kwargs(safe_egress_window={"non_fhsz": -10}))


class TestDataSourceSpec(unittest.TestCase):
    def test_composite_requires_sources(self):
        with self.assertRaises(ValueError):
            DataSourceSpec(type="composite", cache_key="x")

    def test_geojson_file_requires_file(self):
        with self.assertRaises(ValueError):
            DataSourceSpec(type="geojson_file", cache_key="x")

    def test_arcgis_rest_requires_url(self):
        with self.assertRaises(ValueError):
            DataSourceSpec(type="arcgis_rest", cache_key="x")


class TestJsPayloadProjection(unittest.TestCase):
    """to_js_payload strips data_source; runtime fields ship as-is."""

    def test_data_source_stripped(self):
        cfg = HazardConfig.from_yaml(WILDFIRE_YAML)
        payload = cfg.to_js_payload()
        self.assertNotIn("data_source", payload)

    def test_runtime_fields_preserved(self):
        cfg = HazardConfig.from_yaml(WILDFIRE_YAML)
        payload = cfg.to_js_payload()
        self.assertEqual(payload["hazard_id"], "wildfire")
        self.assertEqual(payload["mobilization"], 0.90)
        self.assertFalse(payload["dispositive_at_standard_3"])
        self.assertEqual(payload["classify_strategy"], "most_severe")
        self.assertEqual(payload["degradation"]["vhfhsz"], 0.35)
        self.assertEqual(payload["palette"]["vhfhsz"], "#d7301f")

    def test_payload_is_json_serializable(self):
        import json
        cfg = HazardConfig.from_yaml(WILDFIRE_YAML)
        payload = cfg.to_js_payload()
        # Should not raise
        round_trip = json.loads(json.dumps(payload))
        self.assertEqual(round_trip["hazard_id"], "wildfire")


class TestLoadAllHazardConfigs(unittest.TestCase):
    def test_loads_real_config_directory(self):
        configs = load_all_hazard_configs(REPO_ROOT / "config" / "hazards")
        self.assertIn("wildfire", configs)
        self.assertEqual(configs["wildfire"].hazard_id, "wildfire")

    def test_duplicate_hazard_id_rejected(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            yaml_body = """
                hazard_id: wildfire
                data_source: {type: arcgis_rest, url: x, cache_key: x}
                mobilization: 0.90
                degradation: {non_fhsz: 1.0}
                safe_egress_window: {non_fhsz: 120}
            """
            _write_yaml(tmp, yaml_body, "a.yaml")
            _write_yaml(tmp, yaml_body, "b.yaml")
            with self.assertRaises(ValueError) as cm:
                load_all_hazard_configs(tmp)
            self.assertIn("Duplicate hazard_id", str(cm.exception))

    def test_underscore_prefix_skipped(self):
        with tempfile.TemporaryDirectory() as tmp_str:
            tmp = Path(tmp_str)
            valid_body = """
                hazard_id: wildfire
                data_source: {type: arcgis_rest, url: x, cache_key: x}
                mobilization: 0.90
                degradation: {non_fhsz: 1.0}
                safe_egress_window: {non_fhsz: 120}
            """
            # _template.yaml should be skipped, not parsed
            _write_yaml(tmp, "not: even: valid: yaml", "_template.yaml")
            _write_yaml(tmp, valid_body, "wildfire.yaml")
            configs = load_all_hazard_configs(tmp)
            self.assertEqual(set(configs.keys()), {"wildfire"})

    def test_missing_directory_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_all_hazard_configs("/nonexistent/path/xyz")


class TestResultExtrasValidation(unittest.TestCase):
    """Validate the declarative result_extras DSL — see hazard_config.py
    __post_init__ and docs/plan-multihazard-stage-1-hooks.md §5."""

    def _kwargs(self, result_extras):
        return dict(
            hazard_id="wildfire",
            data_source=DataSourceSpec(type="arcgis_rest", url="x", cache_key="x"),
            mobilization=0.90,
            degradation={"non_fhsz": 1.0},
            safe_egress_window={"non_fhsz": 120},
            result_extras=result_extras,
        )

    def test_wildfire_yaml_has_result_extras(self):
        cfg = HazardConfig.from_yaml(WILDFIRE_YAML)
        self.assertIn("fhsz_haz_class", cfg.result_extras)
        spec = cfg.result_extras["fhsz_haz_class"]
        self.assertEqual(spec["from"], "zone_lookup")
        self.assertEqual(spec["table"]["vhfhsz"], 3)
        self.assertEqual(spec["table"]["non_fhsz"], 0)

    def test_zone_lookup_requires_table(self):
        with self.assertRaises(ValueError) as cm:
            HazardConfig(**self._kwargs({"x": {"from": "zone_lookup"}}))
        self.assertIn("table", str(cm.exception))

    def test_containing_feature_attribute_requires_attribute(self):
        with self.assertRaises(ValueError) as cm:
            HazardConfig(**self._kwargs({"x": {"from": "containing_feature_attribute"}}))
        self.assertIn("attribute", str(cm.exception))

    def test_all_containing_features_requires_project(self):
        with self.assertRaises(ValueError) as cm:
            HazardConfig(**self._kwargs({"x": {"from": "all_containing_features"}}))
        self.assertIn("project", str(cm.exception))

    def test_literal_requires_value(self):
        with self.assertRaises(ValueError) as cm:
            HazardConfig(**self._kwargs({"x": {"from": "literal"}}))
        self.assertIn("value", str(cm.exception))

    def test_runtime_extras_requires_key(self):
        with self.assertRaises(ValueError) as cm:
            HazardConfig(**self._kwargs({"x": {"from": "runtime_extras"}}))
        self.assertIn("key", str(cm.exception))

    def test_unknown_from_type_rejected(self):
        with self.assertRaises(ValueError) as cm:
            HazardConfig(**self._kwargs({"x": {"from": "make_it_up"}}))
        self.assertIn("make_it_up", str(cm.exception))
        self.assertIn("not in", str(cm.exception))

    def test_non_dict_spec_rejected(self):
        with self.assertRaises(ValueError):
            HazardConfig(**self._kwargs({"x": "not_a_dict"}))

    def test_in_zone_no_extras_required(self):
        # in_zone is just a boolean derivation — no extra fields needed
        cfg = HazardConfig(**self._kwargs({"x": {"from": "in_zone"}}))
        self.assertEqual(cfg.result_extras["x"]["from"], "in_zone")

    def test_engine_telemetry_requires_key(self):
        with self.assertRaises(ValueError) as cm:
            HazardConfig(**self._kwargs({"x": {"from": "engine_telemetry"}}))
        self.assertIn("key", str(cm.exception))

    def test_valid_full_wildfire_zone_lookup_round_trips_through_json(self):
        cfg = HazardConfig.from_yaml(WILDFIRE_YAML)
        payload = cfg.to_js_payload()
        import json
        # Should survive JSON round-trip and still validate the same way
        roundtrip = json.loads(json.dumps(payload))
        self.assertEqual(
            roundtrip["result_extras"]["fhsz_haz_class"]["table"]["vhfhsz"], 3
        )


class TestHookRegistration(unittest.TestCase):
    """Verify the hooks_py registry handles register/call/has/clear correctly."""

    def setUp(self):
        # Each test gets a clean registry
        from agents.scenarios import hooks_py
        hooks_py.clear()

    def test_register_and_call(self):
        from agents.scenarios.hooks_py import register, call, has

        @register("post_fetch.identity")
        def identity(features, params):
            return features

        self.assertTrue(has("post_fetch.identity"))
        self.assertEqual(call("post_fetch.identity", "X", {}), "X")

    def test_idempotent_same_function(self):
        from agents.scenarios.hooks_py import register

        def fn(features, params):
            return features

        register("post_fetch.test")(fn)
        # Re-register same function — should not raise
        register("post_fetch.test")(fn)

    def test_different_function_same_name_rejected(self):
        from agents.scenarios.hooks_py import register

        @register("post_fetch.test")
        def fn1(features, params):
            return features

        with self.assertRaises(ValueError) as cm:
            @register("post_fetch.test")
            def fn2(features, params):
                return features
        self.assertIn("already registered", str(cm.exception))

    def test_wrong_arity_rejected(self):
        from agents.scenarios.hooks_py import register

        with self.assertRaises(ValueError) as cm:
            @register("post_fetch.bad")
            def bad(features):  # only 1 arg, post_fetch expects 2
                return features
        self.assertIn("arity", str(cm.exception))

    def test_call_missing_raises(self):
        from agents.scenarios.hooks_py import call
        with self.assertRaises(KeyError):
            call("post_fetch.never_registered", {}, {})

    def test_clear_empties_registry(self):
        from agents.scenarios.hooks_py import register, has, clear

        @register("post_fetch.test")
        def fn(features, params):
            return features

        self.assertTrue(has("post_fetch.test"))
        clear()
        self.assertFalse(has("post_fetch.test"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
