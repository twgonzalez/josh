# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
HazardConfig — declarative hazard parameters loaded from YAML at build time.

Per `docs/plan-multihazard-stage-1-hooks.md` §5. One YAML file per hazard in
`config/hazards/{hazard_id}.yaml`; Python loads and validates them; emits the
runtime-relevant subset as JSON into `JOSH_DATA.hazard_configs[hazard_id]` for
the JS engine to consume.

Locked decisions referenced:
  #2  (tsunami dispositive_at_standard_3=True)
  #3  (gas pir_constant=0.69)
  #4  (mobilization >= 0.90 design floor — enforced here)
  #6  (superseded — 4-fn HazardAdapter ABC retired in favor of this config)
  #11 (tagged-union HazardResult — unchanged; this config drives engine
       behavior but the per-hazard variant shape lives in JS)
  #12 (this is the config side of the architecture; see status doc)

Design notes:
  - Plain dataclass + __post_init__ validator (NOT Pydantic). Architect review
    on 2026-05-24 rejected Pydantic as a new dependency in a geopandas/shapely
    project to avoid version conflicts with pydantic-core's Rust extensions.
  - `to_js_payload()` strips Python-only fields (data_source URLs are
    pipeline-internal; JS only needs the runtime parameters).
"""
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal, Any
import yaml

# Type aliases mirroring the JS-side schema in docs/josh-data-schema-v2.md §1
HazardId = Literal[
    'wildfire', 'flood', 'tsunami', 'dam_failure', 'gas_hazmat', 'landslide',
]
ClassifyStrategy = Literal['most_severe', 'first_hit', 'all']
DataSourceType = Literal[
    'arcgis_rest', 'geojson_file', 'composite', 'npms', 'dsod',
]


@dataclass
class DataSourceSpec:
    """How to acquire the polygon data for this hazard at pipeline time.

    Build-time only — does NOT ship in JOSH_DATA (stripped by to_js_payload()).
    """
    type:           DataSourceType
    cache_key:      str
    url:            str | None = None
    file:           str | None = None
    sources:        list = field(default_factory=list)   # list[DataSourceSpec] for composite
    cache_ttl_days: int = 90

    def __post_init__(self) -> None:
        # composite must have sources; geojson_file must have file; others must have url
        if self.type == 'composite' and not self.sources:
            raise ValueError(
                f"DataSourceSpec(type='composite') requires non-empty `sources` list"
            )
        if self.type == 'geojson_file' and not self.file:
            raise ValueError(
                f"DataSourceSpec(type='geojson_file') requires `file` field"
            )
        if self.type in ('arcgis_rest', 'npms', 'dsod') and not self.url:
            raise ValueError(
                f"DataSourceSpec(type={self.type!r}) requires `url` field"
            )


@dataclass
class HazardConfig:
    """Declarative per-hazard parameters.

    Loaded from config/hazards/{hazard_id}.yaml at pipeline time. The JS-payload
    projection (to_js_payload) is inlined into JOSH_DATA.hazard_configs and
    consumed by static/hazard_engine.js.
    """
    hazard_id:                 HazardId
    data_source:               DataSourceSpec
    mobilization:              float
    dispositive_at_standard_3: bool = False

    # Zone-keyed parameter tables (empty when dispositive or single-zone)
    zone_attribute:     str | None        = None
    zone_map:           dict[str, str]    = field(default_factory=dict)
    degradation:        dict[str, float]  = field(default_factory=dict)
    safe_egress_window: dict[str, float]  = field(default_factory=dict)

    # Classify strategy — wildfire today uses max(HAZ_CLASS) when point falls in
    # overlapping polygons; default 'most_severe' replicates that behavior.
    classify_strategy: ClassifyStrategy = 'most_severe'

    # Zone returned by default classify when no polygon contains the project.
    # Wildfire: 'non_fhsz'. Flood: 'x'. Tsunami: 'outside'. Dam: 'outside'.
    # If not set, engine returns the literal string 'outside'.
    default_zone:       str | None       = None

    # UI vocab. `labels` is long-form tooltip text for the polygon layer;
    # `zone_labels` is short-form text for HazardResult.zone_label in the brief.
    # Both consumed downstream — labels by themes.py + hazard_polygon_layer.js;
    # zone_labels by static/hazard_engine.js when building results.
    palette:            dict[str, str]   = field(default_factory=dict)
    labels:             dict[str, str]   = field(default_factory=dict)
    zone_labels:        dict[str, str]   = field(default_factory=dict)
    legend_label:       str              = ''

    # Hook overrides — map phase name to registered hook name. 5 hookable phases:
    # post_fetch, augment_graph (Python pipeline-time); classify, degradation,
    # egress_window (JS runtime). `build_result` is NOT hookable — variant-
    # specific fields are declared via `result_extras` (declarative DSL below).
    # Phases not listed use the engine's default implementation.
    hooks:              dict[str, str]   = field(default_factory=dict)

    # Hazard-specific extras passed to hook functions as `params`
    runtime_extras:     dict             = field(default_factory=dict)

    # Variant-specific fields added to HazardResult by the engine's internal
    # _buildResult. Each key is a field name to populate on the result; each
    # value is a {from: <type>, ...spec} describing how to derive it.
    #
    # Supported `from:` types (interpreted by hazard_engine.js _resolveResultExtra):
    #   zone_lookup                  — table[zone] (constant per-zone integer/string)
    #   containing_feature_attribute — read attr from polygon containing the project
    #   all_containing_features      — iterate all polygons containing the project,
    #                                  project specified attributes into array
    #   nearest_feature_attribute    — read attr from nearest polyline/polygon (gas)
    #   in_zone                      — boolean: true iff zone != 'outside'
    #   literal                      — static constant value
    #   runtime_extras               — pull from cfg.runtime_extras[key]
    #   engine_telemetry             — pull from engine's per-phase telemetry dict
    #
    # See docs/plan-multihazard-stage-1-hooks.md §5 for the full DSL spec.
    result_extras:      dict             = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Locked decision #4 — mobilization >= 0.90 design floor (NFPA 101)
        if not (0.90 <= self.mobilization <= 1.0):
            raise ValueError(
                f"hazard {self.hazard_id!r}: mobilization {self.mobilization} "
                f"outside [0.90, 1.00] — violates NFPA 101 design floor "
                f"(see docs/multihazard_status.md locked decision #4)"
            )
        # Dispositive hazards must not define zone tables (they're not consulted)
        if self.dispositive_at_standard_3:
            if self.degradation or self.safe_egress_window:
                raise ValueError(
                    f"hazard {self.hazard_id!r}: dispositive_at_standard_3=True "
                    f"but degradation/safe_egress_window tables are non-empty — "
                    f"these are never consulted for dispositive hazards"
                )
        # Non-dispositive hazards must define the zone tables (engine reads them)
        else:
            if not self.degradation:
                raise ValueError(
                    f"hazard {self.hazard_id!r}: non-dispositive hazards must "
                    f"define `degradation` zone table"
                )
            if not self.safe_egress_window:
                raise ValueError(
                    f"hazard {self.hazard_id!r}: non-dispositive hazards must "
                    f"define `safe_egress_window` zone table"
                )
        # Degradation factors must all be in [0, 1]
        for zone, factor in self.degradation.items():
            if not (0.0 <= factor <= 1.0):
                raise ValueError(
                    f"hazard {self.hazard_id!r}: degradation[{zone!r}]={factor} "
                    f"outside [0, 1]"
                )
        # safe_egress_window minutes must be positive
        for zone, mins in self.safe_egress_window.items():
            if mins <= 0:
                raise ValueError(
                    f"hazard {self.hazard_id!r}: safe_egress_window[{zone!r}]"
                    f"={mins} must be positive"
                )
        # result_extras: each entry must be a {from: <type>, ...} dict
        _VALID_FROM_TYPES = frozenset([
            'zone_lookup', 'containing_feature_attribute', 'all_containing_features',
            'nearest_feature_attribute', 'in_zone', 'literal',
            'runtime_extras', 'engine_telemetry',
        ])
        for field_name, spec in self.result_extras.items():
            if not isinstance(spec, dict):
                raise ValueError(
                    f"hazard {self.hazard_id!r}: result_extras[{field_name!r}] "
                    f"must be a dict (got {type(spec).__name__})"
                )
            from_type = spec.get('from')
            if from_type not in _VALID_FROM_TYPES:
                raise ValueError(
                    f"hazard {self.hazard_id!r}: result_extras[{field_name!r}].from"
                    f"={from_type!r} not in {sorted(_VALID_FROM_TYPES)!r}"
                )
            # Type-specific required fields
            if from_type == 'zone_lookup' and 'table' not in spec:
                raise ValueError(
                    f"hazard {self.hazard_id!r}: result_extras[{field_name!r}] "
                    f"with from=zone_lookup requires `table` mapping"
                )
            if from_type in ('containing_feature_attribute', 'nearest_feature_attribute') \
                    and 'attribute' not in spec:
                raise ValueError(
                    f"hazard {self.hazard_id!r}: result_extras[{field_name!r}] "
                    f"with from={from_type} requires `attribute` name"
                )
            if from_type == 'all_containing_features' and 'project' not in spec:
                raise ValueError(
                    f"hazard {self.hazard_id!r}: result_extras[{field_name!r}] "
                    f"with from=all_containing_features requires `project` attr map"
                )
            if from_type == 'literal' and 'value' not in spec:
                raise ValueError(
                    f"hazard {self.hazard_id!r}: result_extras[{field_name!r}] "
                    f"with from=literal requires `value`"
                )
            if from_type in ('runtime_extras', 'engine_telemetry') and 'key' not in spec:
                raise ValueError(
                    f"hazard {self.hazard_id!r}: result_extras[{field_name!r}] "
                    f"with from={from_type} requires `key` name"
                )

    @classmethod
    def from_yaml(cls, path: str | Path) -> 'HazardConfig':
        """Load a HazardConfig from a YAML file.

        Unpacks nested data_source dict into DataSourceSpec.
        """
        with open(path) as f:
            raw = yaml.safe_load(f)
        if not isinstance(raw, dict):
            raise ValueError(
                f"HazardConfig.from_yaml({path}): expected top-level mapping, "
                f"got {type(raw).__name__}"
            )
        ds_raw = raw.get('data_source')
        if not isinstance(ds_raw, dict):
            raise ValueError(
                f"HazardConfig.from_yaml({path}): missing or invalid `data_source` "
                f"(expected mapping, got {type(ds_raw).__name__})"
            )
        raw['data_source'] = DataSourceSpec(**ds_raw)
        return cls(**raw)

    def to_js_payload(self) -> dict[str, Any]:
        """Project to the runtime shape consumed by static/hazard_engine.js.

        Strips `data_source` (build-time only). All other fields ship as-is.
        """
        d = asdict(self)
        d.pop('data_source', None)
        return d


def load_all_hazard_configs(config_dir: str | Path) -> dict[str, HazardConfig]:
    """Load every config/hazards/*.yaml under `config_dir`.

    Returns dict keyed by hazard_id. Skips files starting with '_' (template/example).
    """
    config_dir = Path(config_dir)
    if not config_dir.exists():
        raise FileNotFoundError(
            f"load_all_hazard_configs: directory not found: {config_dir}"
        )
    configs: dict[str, HazardConfig] = {}
    for yaml_path in sorted(config_dir.glob("*.yaml")):
        if yaml_path.name.startswith("_"):
            continue
        cfg = HazardConfig.from_yaml(yaml_path)
        if cfg.hazard_id in configs:
            raise ValueError(
                f"Duplicate hazard_id {cfg.hazard_id!r} "
                f"(seen in {yaml_path} and prior file)"
            )
        configs[cfg.hazard_id] = cfg
    return configs
