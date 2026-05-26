// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * JOSH Hook Registry — JavaScript side (runtime hazard transforms).
 *
 * Per docs/plan-multihazard-stage-1-hooks.md §3. Mirror of
 * agents/scenarios/hooks_py.py — same API shape (register/call/has/clear),
 * different side of the pipeline:
 *
 *   Python (build time):  post_fetch, augment_graph
 *   JS (runtime):         classify, degradation, egress_window, build_result
 *
 * UMD: works in browser (`window.Hooks`) and node (`require('./hooks')`).
 *
 * Usage (per-hazard transform module):
 *
 *   var Hooks = (typeof window !== 'undefined' ? window.Hooks : require('./hooks'));
 *   Hooks.register('flood.degradation', function (edge, zone, features, params) {
 *     ...
 *     return factor;
 *   });
 *
 * Usage (engine dispatcher):
 *
 *   var hookName = cfg.hooks.classify || 'default.classify';
 *   var zone = Hooks.call(hookName, point, features, cfg);
 *
 * Defaults are registered under `default.*` names by static/transforms/_defaults.js,
 * which must be loaded before any hazard_engine.js code runs (concatenation order
 * in app.js bundle handles this; tests must require() defaults explicitly).
 */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.Hooks = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  // Phase prefix → expected arity (positional parameters). Mirrors the Python
  // _EXPECTED_ARITY in agents/scenarios/hooks_py.py. Used at register() time
  // to catch the most common bug class (wrong signature).
  //
  // FIVE hookable phases: post_fetch + augment_graph (Python pipeline-time);
  // classify + degradation + egress_window (JS runtime). `build_result` is
  // NOT a hook — it's engine-internal, driven by HazardConfig.result_extras
  // (declarative DSL).
  var EXPECTED_ARITY = Object.freeze({
    'post_fetch':    2,   // (features, params)
    'augment_graph': 3,   // (graph, features, params)
    'classify':      3,   // (point, features, cfg)
    'degradation':   4,   // (edge, zone, features, params)
    'egress_window': 4,   // (point, zone, features, params)
    'default':       null // default.* hooks bypass arity check (vary by phase)
  });

  // Module-level registry. Keyed by `{phase}.{name}` (e.g. "flood.degradation",
  // "default.classify").
  var _registry = Object.create(null);

  function register(name, fn) {
    if (typeof name !== 'string' || name.length === 0) {
      throw new Error('Hooks.register: name must be a non-empty string');
    }
    if (typeof fn !== 'function') {
      throw new Error('Hooks.register: fn must be a function (got ' + typeof fn + ')');
    }

    // Idempotent: re-registering the SAME function under the SAME name is a no-op.
    // Required so test modules can re-import transform files without raising.
    var existing = _registry[name];
    if (existing === fn) return fn;
    if (existing !== undefined) {
      throw new Error(
        'Hooks.register: ' + name + ' already registered by a different function'
      );
    }

    // Phase-prefix arity check (skipped for default.* — those vary by phase
    // and live in _defaults.js where they're checked individually).
    var prefix = name.split('.', 1)[0];
    if (prefix !== 'default') {
      var expected = EXPECTED_ARITY[prefix];
      if (expected !== undefined && expected !== null && fn.length !== expected) {
        throw new Error(
          'Hooks.register: ' + name + ' expected arity ' + expected +
          ' (phase=' + prefix + '), got ' + fn.length
        );
      }
    }

    _registry[name] = fn;
    return fn;
  }

  function call(name /*, ...args */) {
    var fn = _registry[name];
    if (fn === undefined) {
      throw new Error(
        'Hooks.call: no hook registered under ' + name +
        '. Available: ' + Object.keys(_registry).sort().join(', ')
      );
    }
    var args = Array.prototype.slice.call(arguments, 1);
    return fn.apply(null, args);
  }

  function has(name) {
    return Object.prototype.hasOwnProperty.call(_registry, name);
  }

  function allRegistered() {
    return Object.keys(_registry).slice().sort();
  }

  /**
   * Reset the registry. TEST-ONLY — production code never calls this.
   * Required for test isolation when transform modules register hooks at
   * import time (re-importing across tests would otherwise leak state).
   */
  function clear() {
    _registry = Object.create(null);
  }

  return {
    register: register,
    call: call,
    has: has,
    allRegistered: allRegistered,
    clear: clear,
    EXPECTED_ARITY: EXPECTED_ARITY
  };
}));
