// SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { test } = require("node:test");
const vm = require("node:vm");

function browser(fetchImpl) {
  const posted = [];
  const intervals = [];
  const document = { hasFocus: () => true, visibilityState: "visible" };
  const context = vm.createContext({
    document, window: { confirm: () => true },
    state: { controlActions: ["pause_resume", "toggle_correction", "guide_start", "stop_session",
      "hold_position", "release_exit", "control_lost", "control_heartbeat"] },
    HTMLInputElement: class {}, HTMLTextAreaElement: class {}, HTMLSelectElement: class {},
    AbortSignal, console, setInterval: (fn) => intervals.push(fn),
    fetch: async (_url, options) => {
      const action = JSON.parse(options.body).action;
      posted.push(action);
      return fetchImpl ? fetchImpl(action) : { ok: true };
    },
  });
  // Execute the production control handlers, independently of WebRTC and canvas.
  const source = readFileSync(join(__dirname, "../utils/ovstream/browser_client/app.js"), "utf8");
  vm.runInContext(source.slice(source.indexOf("  const keyActions"), source.indexOf("  function startTelemetry")), context);
  return {
    posted, document, pulse: intervals[0],
    key(code, repeat = false) {
      let prevented = false;
      context.handleControlKeydown({ code, repeat, preventDefault: () => { prevented = true; } });
      return prevented;
    },
    blur: () => context.loseControl(),
    drain: () => vm.runInContext("actionQueue", context),
    owner: (phase) => context.controlOwner(phase)[0],
    owners: () => vm.runInContext("controlOwners", context),
    command: (action, phase) => context.commandState(action, phase),
  };
}

test("Space pause, Tab, one G, Space handback; held G never repeats actions", async () => {
  const b = browser();
  for (const key of ["Space", "Space", "Tab", "KeyG"]) b.key(key);
  for (let i = 0; i < 50; i++) assert.equal(b.key("KeyG", true), true);
  b.key("Space");
  await b.drain();
  assert.deepEqual(b.posted, ["pause_resume", "pause_resume", "toggle_correction", "guide_start", "pause_resume"]);
  await b.pulse();
  assert.equal(b.posted.at(-1), "control_heartbeat");
  assert.equal(b.posted.filter((action) => action === "guide_start").length, 1);
});

test("focus loss cancels keys queued behind an outstanding request", async () => {
  let finish;
  const b = browser((action) => action === "pause_resume"
    ? new Promise((resolve) => { finish = resolve; }) : { ok: true });
  b.key("Space");
  await Promise.resolve();
  b.key("Tab");
  b.key("KeyG");
  b.document.hasFocus = () => false;
  b.blur();
  finish({ ok: true });
  await b.drain();
  assert.deepEqual(b.posted, ["pause_resume", "control_lost"]);
  b.document.hasFocus = () => true;
  await b.pulse();
  assert.equal(b.posted.at(-1), "control_heartbeat");
});

test("Escape bypasses outstanding requests and cancels queued movement", async () => {
  let finish;
  const b = browser((action) => action === "pause_resume"
    ? new Promise((resolve) => { finish = resolve; }) : { ok: true });
  b.key("Space");
  await Promise.resolve();
  b.key("Tab");
  b.key("Escape");
  assert.deepEqual(b.posted, ["pause_resume", "stop_session"]);
  finish({ ok: true });
  await b.drain();
  assert.deepEqual(b.posted, ["pause_resume", "stop_session"]);
});

test("unfocused and hidden pages send no active controls or heartbeat", async () => {
  const b = browser();
  b.document.hasFocus = () => false;
  b.key("KeyG");
  await b.pulse();
  b.document.hasFocus = () => true;
  b.document.visibilityState = "hidden";
  b.key("Space");
  await b.pulse();
  await b.drain();
  assert.deepEqual(b.posted, []);
});

test("every DAgger session phase shows who controls the arm", () => {
  const b = browser();
  const session = readFileSync(join(__dirname, "../utils/sim_dagger.py"), "utf8");
  const phases = new Set([...session.matchAll(/_(?:phase|move)\("(\w+)"/g)].map((match) => match[1]));
  assert.ok(phases.size >= 10);
  assert.deepEqual([...phases].filter((phase) => !(phase in b.owners())), []);
  assert.equal(b.owner("autonomous"), "policy");
  assert.equal(b.owner("guide_starting"), "human");
  assert.equal(b.owner("correcting"), "human");
});

test("the command panel offers each DAgger phase only the keys it accepts", () => {
  const b = browser();
  assert.equal(b.command("guide_start", "paused"), "unavailable");
  assert.equal(b.command("toggle_correction", "paused"), "ready");
  assert.equal(b.command("toggle_correction", "autonomous"), "unavailable");
  assert.equal(b.command("guide_start", "correction_ready"), "next");
  assert.equal(b.command("pause_resume", "correcting"), "next");
  assert.equal(b.command("reset_world", "aligning"), "ready");
  assert.equal(b.command("reset_world", "resetting"), "unavailable");
  for (const phase of Object.keys(b.owners())) {
    for (const action of ["hold_position", "stop_session", "release_exit"]) {
      assert.equal(b.command(action, phase), "ready");
    }
  }
});
