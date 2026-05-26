# Copyright (C) 2026 Thomas Gonzalez
# SPDX-License-Identifier: AGPL-3.0-or-later
# This file is part of JOSH (Jurisdictional Objective Standards for Housing).
# See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

"""
Hook Registry — Python side (build-time hazard transforms).

Per `docs/plan-multihazard-stage-1-hooks.md` §3. A vanilla decorator + dict
registry that lets per-hazard transform functions be referenced from YAML
config by name without the engine knowing about them at import time.

The JS-side equivalent lives in `static/hooks.js`. Both expose the same API
shape (register/call/has/clear) so YAML hook references like
`flood.augment_graph` resolve consistently across languages — the only
difference is which side runs which phase:

  Pipeline phases (Python):  post_fetch, augment_graph
  Runtime phases (JS):       classify, degradation, egress_window, build_result

Usage:

    from agents.scenarios.hooks_py import register

    @register("flood.augment_graph")
    def flood_augment_graph(graph, features, params):
        ...
        return graph

The engine calls `hooks.call("flood.augment_graph", graph, features, params)`
and never references the function directly. Hooks register at module import
time; `agents/scenarios/transforms/__init__.py` imports every submodule so
all hooks are available when the engine first runs.
"""
from typing import Callable, Any
import inspect

# Phase prefix → expected arity (positional parameters). Mirrors the JS
# EXPECTED_ARITY map in static/hooks.js. Used for register-time validation.
#
# FIVE hookable phases: post_fetch + augment_graph (Python pipeline-time);
# classify + degradation + egress_window (JS runtime). `build_result` is
# NOT a hook — it's engine-internal, driven by HazardConfig.result_extras.
_EXPECTED_ARITY = {
    "post_fetch":    2,   # (features, params)
    "augment_graph": 3,   # (graph, features, params)
    "classify":      3,   # (point, features, cfg)         — Python side rarely needed
    "degradation":   4,   # (edge, zone, features, params) — Python side rarely needed
    "egress_window": 4,   # (point, zone, features, params)
}

# Module-level registry. Keyed by `{phase}.{adapter_name}` (e.g. "flood.augment_graph").
_REGISTRY: dict[str, Callable] = {}
_SIGNATURES: dict[str, inspect.Signature] = {}


def register(name: str) -> Callable:
    """Decorator: register a callable under a string name.

    Idempotent: re-registering the SAME function object under the SAME name
    is a no-op (required so tests can re-import transform modules without
    raising). Re-registering a DIFFERENT function under an existing name
    raises ValueError.

    Validates the function's arity against the phase prefix (e.g. an
    `augment_graph.*` hook must accept exactly 3 positional args).
    """
    def decorator(fn: Callable) -> Callable:
        existing = _REGISTRY.get(name)
        if existing is fn:
            return fn  # idempotent — same function, same name → ok
        if existing is not None:
            raise ValueError(
                f"Hook {name!r} already registered by {existing!r}; "
                f"refusing to overwrite with {fn!r}"
            )

        # Phase-prefix arity check
        prefix = name.split(".", 1)[0]
        expected_arity = _EXPECTED_ARITY.get(prefix)
        if expected_arity is not None:
            sig = inspect.signature(fn)
            positional = [
                p for p in sig.parameters.values()
                if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                              inspect.Parameter.POSITIONAL_OR_KEYWORD)
            ]
            if len(positional) != expected_arity:
                raise ValueError(
                    f"Hook {name!r} expected arity {expected_arity} "
                    f"(phase={prefix!r}), got {len(positional)} "
                    f"({[p.name for p in positional]!r})"
                )

        _REGISTRY[name] = fn
        _SIGNATURES[name] = inspect.signature(fn)
        return fn
    return decorator


def call(name: str, *args, **kwargs) -> Any:
    """Invoke a registered hook by name. Raises KeyError if missing."""
    fn = _REGISTRY.get(name)
    if fn is None:
        raise KeyError(
            f"No hook registered under {name!r}. "
            f"Available: {sorted(_REGISTRY.keys())!r}"
        )
    return fn(*args, **kwargs)


def has(name: str) -> bool:
    """True if a hook is registered under this name."""
    return name in _REGISTRY


def all_registered() -> dict[str, inspect.Signature]:
    """Snapshot of all registered hooks (for validation, docs, test assertions)."""
    return dict(_SIGNATURES)


def clear() -> None:
    """Reset the registry. Test-only — production code never calls this."""
    _REGISTRY.clear()
    _SIGNATURES.clear()
