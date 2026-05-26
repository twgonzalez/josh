// Copyright (C) 2026 Thomas Gonzalez
// SPDX-License-Identifier: AGPL-3.0-or-later
// This file is part of JOSH (Jurisdictional Objective Standards for Housing).
// See LICENSE for full terms. See CONTRIBUTING.md for contributor license terms.

/**
 * Tests for static/hooks.js — the JS-side hook registry.
 *
 * Mirrors the Python registry tests in tests/test_hazard_config.py
 * (TestHookRegistration class). Same semantic contract; both languages
 * must enforce the same idempotency + arity rules so YAML hook references
 * behave identically across pipeline (Python) and runtime (JS) phases.
 *
 * Run:
 *   node --test tests/test_hooks.js
 */
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const Hooks = require(path.join(__dirname, '..', 'static', 'hooks.js'));

test.beforeEach(() => {
  // Each test starts with a clean registry — required because @register
  // is idempotent across calls but persistent across tests.
  Hooks.clear();
});

test('register + call + has work end-to-end', () => {
  Hooks.register('post_fetch.identity', function (features, params) {
    return features;
  });

  assert.equal(Hooks.has('post_fetch.identity'), true);
  assert.equal(Hooks.call('post_fetch.identity', 'X', {}), 'X');
});

test('register is idempotent for the same function under the same name', () => {
  const fn = function (features, params) { return features; };

  Hooks.register('post_fetch.test', fn);
  // Re-register same function — must not raise
  Hooks.register('post_fetch.test', fn);

  assert.equal(Hooks.has('post_fetch.test'), true);
});

test('register rejects a different function under an existing name', () => {
  Hooks.register('post_fetch.test', function (a, b) { return a; });

  assert.throws(
    () => Hooks.register('post_fetch.test', function (a, b) { return b; }),
    /already registered by a different function/
  );
});

test('register validates arity by phase prefix — post_fetch needs 2 args', () => {
  assert.throws(
    () => Hooks.register('post_fetch.bad', function (onlyOneArg) { return onlyOneArg; }),
    /arity 2.*got 1/
  );
});

test('register validates arity by phase prefix — augment_graph needs 3 args', () => {
  assert.throws(
    () => Hooks.register('augment_graph.bad', function (g, f) { return g; }),
    /arity 3.*got 2/
  );
});

test('register validates arity by phase prefix — classify needs 3 args', () => {
  assert.throws(
    () => Hooks.register('classify.bad', function (p, f) { return 'outside'; }),
    /arity 3.*got 2/
  );
});

test('register validates arity by phase prefix — degradation needs 4 args', () => {
  assert.throws(
    () => Hooks.register('degradation.bad', function (e, z, f) { return 1.0; }),
    /arity 4.*got 3/
  );
});

test('register validates arity by phase prefix — egress_window needs 4 args', () => {
  assert.throws(
    () => Hooks.register('egress_window.bad', function (p, z, f) { return 120; }),
    /arity 4.*got 3/
  );
});

test('build_result is NOT a hookable phase — engine-internal only', () => {
  // build_result was a hook phase in v2 of the plan; v3 promoted it to
  // engine-internal driven by HazardConfig.result_extras (declarative DSL).
  // Registering build_result.* hooks now skips arity validation because
  // the phase prefix isn't in EXPECTED_ARITY — they'd silently succeed.
  // This test documents the deliberate absence; future engineers should
  // not be tempted to add build_result back without explicit design review.
  assert.equal(Hooks.EXPECTED_ARITY.build_result, undefined);
});

test('register skips arity check for default.* names', () => {
  // default.* hooks register internal stub signatures by phase; arity varies.
  // The registry shouldn't enforce against the generic phase prefix.
  Hooks.register('default.identity', function (anything) { return anything; });
  assert.equal(Hooks.has('default.identity'), true);
});

test('register rejects non-string names', () => {
  assert.throws(
    () => Hooks.register(null, function () {}),
    /name must be a non-empty string/
  );
  assert.throws(
    () => Hooks.register('', function () {}),
    /name must be a non-empty string/
  );
});

test('register rejects non-function values', () => {
  assert.throws(
    () => Hooks.register('post_fetch.bad', 'not a function'),
    /fn must be a function/
  );
});

test('call raises for unregistered names', () => {
  assert.throws(
    () => Hooks.call('post_fetch.never_registered', {}, {}),
    /no hook registered under post_fetch.never_registered/
  );
});

test('call forwards multiple arguments correctly', () => {
  Hooks.register('post_fetch.echo', function (a, b) {
    return [a, b];
  });
  const result = Hooks.call('post_fetch.echo', 'first', 'second');
  assert.deepEqual(result, ['first', 'second']);
});

test('has returns false for unregistered names', () => {
  assert.equal(Hooks.has('classify.nope'), false);
});

test('allRegistered returns sorted list of registered names', () => {
  Hooks.register('post_fetch.b', function (a, b) { return a; });
  Hooks.register('post_fetch.a', function (a, b) { return a; });
  Hooks.register('classify.c', function (a, b, c) { return 'x'; });

  const names = Hooks.allRegistered();
  assert.deepEqual(names, ['classify.c', 'post_fetch.a', 'post_fetch.b']);
});

test('clear empties the registry', () => {
  Hooks.register('post_fetch.test', function (a, b) { return a; });
  assert.equal(Hooks.has('post_fetch.test'), true);

  Hooks.clear();

  assert.equal(Hooks.has('post_fetch.test'), false);
  assert.deepEqual(Hooks.allRegistered(), []);
});

test('call error message lists available hooks', () => {
  Hooks.register('post_fetch.a', function (a, b) { return a; });
  Hooks.register('classify.b', function (a, b, c) { return 'x'; });

  try {
    Hooks.call('does.not.exist');
    assert.fail('expected throw');
  } catch (err) {
    assert.match(err.message, /Available:.*classify\.b.*post_fetch\.a/);
  }
});

test('EXPECTED_ARITY constants are frozen / immutable', () => {
  assert.equal(Hooks.EXPECTED_ARITY.post_fetch, 2);
  assert.equal(Hooks.EXPECTED_ARITY.augment_graph, 3);
  assert.equal(Hooks.EXPECTED_ARITY.classify, 3);
  assert.equal(Hooks.EXPECTED_ARITY.degradation, 4);
  assert.equal(Hooks.EXPECTED_ARITY.egress_window, 4);
  // build_result intentionally absent — engine-internal, not a hook phase
  assert.equal(Hooks.EXPECTED_ARITY.build_result, undefined);
  // Object.freeze is enforced — assignment is a silent no-op in non-strict
  // mode, error in strict. Either way the value doesn't change.
  try { Hooks.EXPECTED_ARITY.post_fetch = 999; } catch (e) { /* expected in strict */ }
  assert.equal(Hooks.EXPECTED_ARITY.post_fetch, 2);
});
