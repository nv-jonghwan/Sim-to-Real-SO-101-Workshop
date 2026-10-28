// SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
// Browser client for the ovstream --browser-display path.
//   * Video: the cameras are composited into ONE wide frame server-side and
//     arrive over ovstream's single WebRTC transport (NVENC on the server),
//     decoded into a hidden <video>. Each camera widget crops its own region
//     from that video into its own <canvas>, so the page shows separate
//     side-by-side feeds while still using one stream / one encode.
//   * Telemetry: task name, WebRTC signal port, joint observations / actions,
//     and per-camera FPS arrive over a Server-Sent-Events stream (/telemetry).
//     The page auto-connects using the port from the config event, sets its
//     title, and draws the rolling plots + per-widget FPS natively.

(function () {
  "use strict";

  const { AppStreamer, StreamType } = window.OVWebRTC;

  const els = {
    taskName: document.getElementById("task-name"),
    status: document.getElementById("status"),
    recPill: document.getElementById("rec-pill"),
    episodesPill: document.getElementById("episodes-pill"),
    envSelector: document.getElementById("env-selector"),
    envSelect: document.getElementById("env-select"),
    keyboardHint: document.getElementById("keyboard-hint"),
    video: document.getElementById("video"),
    hint: document.getElementById("hint"),
    streams: document.getElementById("streams"),
    daggerControls: document.getElementById("dagger-controls"),
    controlOwner: document.getElementById("control-owner"),
    commandPanel: document.getElementById("command-panel"),
    plotObs: document.getElementById("plot-obs"),
    plotAct: document.getElementById("plot-act"),
    saving: document.getElementById("saving"),
    savingText: document.getElementById("saving-text"),
    savingBarFill: document.getElementById("saving-bar-fill"),
  };

  let connected = false;
  let connecting = false;
  // True while the recorder is writing an episode; the beforeunload handler
  // uses it to warn against closing the tab mid-save.
  let savingActive = false;

  // ----- telemetry state ---------------------------------------------------
  const CAP = 512; // rolling window sample capacity
  const state = {
    task: "",
    signalPort: 49100,
    jointNames: [],
    feeds: [], // [{name, width, height}]
    numEnvs: 1,
    selectedEnv: 0,
    controlActions: [],
    colors: [], // "#rrggbb" per joint
    samples: [], // [{t, obs:[], act:[]}]
    fps: {}, // {feedName: {render, env}} from server-side submission counters
    displayFps: null, // unique WebRTC frames presented by the browser
    emaMax: 1, // EMA of peak abs (degrees) for shared y-scale
  };

  // name -> {canvas, ctx, fpsEl, sx, sw, sh}
  let camWidgets = {};

  // HSV(i/n, 0.75, 1.0) -> hex, matching the server-side palette.
  function palette(n) {
    const out = [];
    for (let i = 0; i < n; i++) {
      const [r, g, b] = hsvToRgb(i / n, 0.75, 1.0);
      out.push(
        "#" +
          [r, g, b]
            .map((v) => Math.round(v * 255).toString(16).padStart(2, "0"))
            .join("")
      );
    }
    return out;
  }

  function hsvToRgb(h, s, v) {
    const i = Math.floor(h * 6);
    const f = h * 6 - i;
    const p = v * (1 - s);
    const q = v * (1 - f * s);
    const t = v * (1 - (1 - f) * s);
    switch (i % 6) {
      case 0: return [v, t, p];
      case 1: return [q, v, p];
      case 2: return [p, v, t];
      case 3: return [p, q, v];
      case 4: return [t, p, v];
      default: return [v, p, q];
    }
  }

  // ----- camera widgets ----------------------------------------------------
  function buildStreams() {
    els.streams.innerHTML = "";
    camWidgets = {};
    let offset = 0;
    for (const f of state.feeds) {
      const cam = document.createElement("div");
      cam.className = "cam";

      const head = document.createElement("div");
      head.className = "cam-head";
      const name = document.createElement("span");
      name.className = "cam-name";
      name.textContent = f.name;
      const fps = document.createElement("span");
      fps.className = "cam-fps";
      fps.textContent = "render -- fps \u00b7 display -- fps \u00b7 env -- fps";
      head.appendChild(name);
      head.appendChild(fps);

      const frame = document.createElement("div");
      frame.className = "cam-frame";

      const canvas = document.createElement("canvas");
      canvas.className = "cam-canvas";
      canvas.width = f.width;
      canvas.height = f.height;
      canvas.style.aspectRatio = `${f.width} / ${f.height}`;

      const badge = document.createElement("span");
      badge.className = "rec-badge";
      badge.textContent = "REC";

      frame.appendChild(canvas);
      frame.appendChild(badge);
      cam.appendChild(head);
      cam.appendChild(frame);
      els.streams.appendChild(cam);

      camWidgets[f.name] = {
        cam,
        canvas,
        ctx: canvas.getContext("2d"),
        fpsEl: fps,
        sx: offset,
        sw: f.width,
        sh: f.height,
      };
      offset += f.width;
    }
  }

  function drawStreams() {
    const source = els.video;
    const ready = source.readyState >= 2 && source.videoWidth > 0;
    for (const f of state.feeds) {
      const w = camWidgets[f.name];
      if (!w) continue;
      if (ready) {
        w.ctx.drawImage(
          source,
          w.sx,
          0,
          w.sw,
          w.sh,
          0,
          0,
          w.canvas.width,
          w.canvas.height,
        );
      }
      const fps = state.fps[f.name] || {};
      const r = fps.render != null ? fps.render.toFixed(0) : "--";
      const d = state.displayFps != null ? state.displayFps.toFixed(0) : "--";
      const e = fps.env != null ? fps.env.toFixed(0) : "--";
      w.fpsEl.textContent = `render ${r} fps \u00b7 display ${d} fps \u00b7 env ${e} fps`;
    }
  }

  // ----- SSE telemetry -----------------------------------------------------
  let evtSource = null;

  function configureEnvironmentSelector(numEnvs, selectedEnv) {
    state.numEnvs = Math.max(1, Number(numEnvs) || 1);
    els.envSelector.hidden = state.numEnvs <= 1;
    if (els.envSelect.options.length !== state.numEnvs) {
      els.envSelect.innerHTML = "";
      for (let env = 0; env < state.numEnvs; env++) {
        const option = document.createElement("option");
        option.value = String(env);
        option.textContent = String(env);
        els.envSelect.appendChild(option);
      }
    }
    syncSelectedEnvironment(selectedEnv);
  }

  function syncSelectedEnvironment(selectedEnv) {
    const next = Number(selectedEnv);
    if (!Number.isInteger(next) || next < 0 || next >= state.numEnvs) return;
    if (next !== state.selectedEnv) {
      state.selectedEnv = next;
      state.samples.length = 0;
      state.emaMax = 1;
    }
    els.envSelect.value = String(next);
  }

  async function selectEnvironment(env) {
    els.envSelect.disabled = true;
    try {
      const response = await fetch("/control/environment", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ env }),
      });
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json();
      syncSelectedEnvironment(result.selected_env);
    } catch (err) {
      els.envSelect.value = String(state.selectedEnv);
      console.error("Failed to select environment:", err);
    } finally {
      els.envSelect.disabled = false;
    }
  }

  const keyActions = {
    Space: "toggle_recording",
    KeyC: "cancel_episode",
    KeyR: "reset_world",
    Tab: "toggle_correction",
    Escape: "stop_session",
    KeyX: "hold_position",
    KeyL: "release_exit",
    KeyG: "guide_start",
  };

  // How each command is listed: key cap, verb, short hint and, in DAgger
  // sessions, the panel column. Listing order is the order on the page.
  const commands = {
    toggle_recording: { key: "Space", label: "Record", hint: "start / stop episode" },
    pause_resume: { key: "Space", label: "Run / pause policy", group: "workflow" },
    toggle_correction: { key: "Tab", label: "Align leader", hint: "while paused", group: "workflow" },
    guide_start: { key: "G", label: "Take over", hint: "start human correction", group: "workflow" },
    cancel_episode: { key: "C", label: "Discard", hint: "drop unsaved take", group: "workflow" },
    reset_world: { key: "R", label: "Reset scene", group: "workflow" },
    hold_position: { key: "X", label: "Freeze & hold", hint: "physics frozen", group: "safety" },
    stop_session: { key: "Esc", label: "Rest & exit", hint: "torque stays ON", group: "safety" },
    release_exit: { key: "L", label: "Release & exit", hint: "support arm first", group: "safety", warn: true },
  };

  // Workflow commands SimDAgger.handle() acts on in each phase, the command
  // the operator needs next, and what Space does there. Phases not listed
  // accept only Reset; safety commands are accepted in every phase.
  const phaseCommands = {
    paused: { available: ["pause_resume", "toggle_correction", "reset_world"], space: "Run policy" },
    autonomous: { available: ["pause_resume", "reset_world"], space: "Pause policy" },
    correction_ready: {
      available: ["guide_start", "pause_resume", "cancel_episode", "reset_world"],
      next: "guide_start", space: "Hand back to policy",
    },
    guide_starting: { available: ["pause_resume", "cancel_episode", "reset_world"], space: "Save & hand back" },
    correcting: {
      available: ["pause_resume", "cancel_episode", "reset_world"],
      next: "pause_resume", space: "Save & hand back",
    },
    resetting: { available: [] },
  };

  function commandState(action, phase) {
    if (commands[action].group !== "workflow") return "ready";
    const { available = ["reset_world"], next } = phaseCommands[phase] || {};
    if (action === next) return "next";
    return available.includes(action) ? "ready" : "unavailable";
  }

  // Who drives the arm in each DAgger session phase, and the label shown for it.
  const controlOwners = {
    autonomous: ["policy", "Policy in control"],
    guide_starting: ["human", "Human taking over"],
    correcting: ["human", "Human in control"],
    resuming: ["handoff", "Handing back to policy"],
    aligning: ["handoff", "Aligning leader"],
    correction_ready: ["handoff", "Ready for takeover"],
    resetting: ["handoff", "Resetting"],
    holding: ["idle", "Holding"],
    paused: ["idle", "Paused"],
    fault: ["fault", "Fault: holding"],
  };

  function controlOwner(phase) {
    return controlOwners[phase] || ["idle", phase.replaceAll("_", " ")];
  }

  // action -> {el, label} for the listed commands, updated on phase changes.
  let commandItems = {};

  function commandItem(action, detailed) {
    const { key, label, hint, warn } = commands[action];
    const el = document.createElement("div");
    el.className = warn ? "command warn" : "command";
    el.dataset.state = "ready";
    const cap = document.createElement("kbd");
    cap.textContent = key;
    const text = document.createElement("span");
    text.className = "command-text";
    const labelEl = document.createElement("span");
    labelEl.className = "command-label";
    labelEl.textContent = label;
    text.appendChild(labelEl);
    if (detailed && hint) {
      const hintEl = document.createElement("span");
      hintEl.className = "command-hint";
      hintEl.textContent = hint;
      text.appendChild(hintEl);
    }
    el.append(cap, text);
    if (detailed) {
      const next = document.createElement("span");
      next.className = "command-next";
      next.textContent = "Next";
      el.appendChild(next);
    }
    commandItems[action] = { el, label: labelEl };
    return el;
  }

  function configureControlActions(actions) {
    state.controlActions = Array.isArray(actions) ? actions : [];
    const listed = Object.keys(commands).filter((action) => state.controlActions.includes(action));
    commandItems = {};
    els.keyboardHint.replaceChildren();
    els.commandPanel.replaceChildren();
    if (state.controlActions.includes("guide_start")) {
      // DAgger: workflow keys for the current phase beside always-on safety keys.
      for (const [group, title] of [["workflow", "Workflow"], ["safety", "Safety \u00b7 always available"]]) {
        const section = document.createElement("section");
        section.className = `command-group ${group}`;
        const heading = document.createElement("h2");
        heading.textContent = title;
        const list = document.createElement("div");
        list.className = "command-list";
        for (const action of listed) {
          if (commands[action].group === group) list.appendChild(commandItem(action, true));
        }
        section.append(heading, list);
        els.commandPanel.appendChild(section);
      }
      els.daggerControls.hidden = false;
      els.commandPanel.hidden = false;
      els.keyboardHint.hidden = true;
      updateCommands(uiStatus.phase);
    } else {
      for (const action of listed) els.keyboardHint.appendChild(commandItem(action, false));
      els.keyboardHint.hidden = listed.length === 0;
    }
  }

  function updateCommands(phase) {
    if (!phase) return;
    for (const [action, item] of Object.entries(commandItems)) {
      const commandStatus = commandState(action, phase);
      item.el.dataset.state = commandStatus;
      item.el.setAttribute("aria-disabled", String(commandStatus === "unavailable"));
      if (action === "pause_resume") {
        item.label.textContent = phaseCommands[phase]?.space || commands.pause_resume.label;
      }
    }
  }

  const controlSource = `${Date.now()}-${Math.random()}`;
  let controlSequence = 0;
  let actionQueue = Promise.resolve();
  let controlGeneration = 0;
  let pulsePending = false;

  async function sendControlAction(action) {
    try {
      const response = await fetch("/control/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, source: controlSource, sequence: ++controlSequence }),
        keepalive: true,
        signal: AbortSignal.timeout(1000),
      });
      if (!response.ok) throw new Error(await response.text());
      return true;
    } catch (err) {
      console.error("Failed to send control action:", err);
      return false;
    }
  }

  function loseControl() {
    controlGeneration++;
    if (state.controlActions.includes("control_lost")) sendControlAction("control_lost");
  }

  setInterval(async () => {
    if (pulsePending || !state.controlActions.includes("control_heartbeat")) return;
    if (!document.hasFocus() || document.visibilityState !== "visible") return;
    pulsePending = true;
    try {
      await sendControlAction("control_heartbeat");
    } finally {
      pulsePending = false;
    }
  }, 100);

  function handleControlKeydown(event) {
    if (event.repeat && (keyActions[event.code] || event.code === "Space")) event.preventDefault();
    if (
      event.repeat ||
      event.ctrlKey ||
      event.altKey ||
      event.metaKey ||
      document.visibilityState !== "visible" ||
      !document.hasFocus()
    ) {
      return;
    }
    const target = event.target;
    if (
      target instanceof HTMLInputElement ||
      target instanceof HTMLTextAreaElement ||
      target instanceof HTMLSelectElement ||
      target?.isContentEditable
    ) {
      return;
    }
    const action = event.code === "Space" && state.controlActions.includes("pause_resume")
      ? "pause_resume" : keyActions[event.code];
    if (!action || !state.controlActions.includes(action)) return;
    event.preventDefault();
    if (action === "release_exit" && !window.confirm("Support the physical leader arm first. Turn OFF motor torque and exit?")) return;
    if (["stop_session", "hold_position", "release_exit"].includes(action)) {
      // Never make a stop wait behind a stalled request or replay queued keys after it.
      controlGeneration++;
      sendControlAction(action);
      return;
    }
    const generation = controlGeneration;
    actionQueue = actionQueue.then(async () => {
      if (generation === controlGeneration && !await sendControlAction(action)) loseControl();
    });
  }

  function startTelemetry() {
    if (evtSource) return;
    evtSource = new EventSource("/telemetry");
    evtSource.addEventListener("config", (e) => {
      const cfg = JSON.parse(e.data);
      state.task = cfg.task || "";
      state.signalPort = cfg.signal_port || state.signalPort;
      state.jointNames = cfg.joint_names || [];
      state.feeds = cfg.feeds || [];
      configureControlActions(cfg.control_actions);
      state.colors = palette(state.jointNames.length);
      state.samples.length = 0;
      configureEnvironmentSelector(cfg.num_envs, cfg.selected_env);
      els.taskName.textContent = state.task || "Task not specified";
      document.title = state.task
        ? `${state.task} | SO-101 Sim-to-Real`
        : "Train an SO-101 Robot From Sim-to-Real With NVIDIA Isaac";
      buildStreams();
      restartConnection();
    });
    evtSource.onmessage = (e) => {
      const s = JSON.parse(e.data);
      state.fps = s.fps || {};
      configureEnvironmentSelector(s.num_envs, s.selected_env);
      if (Array.isArray(s.obs) && Array.isArray(s.act)) {
        state.samples.push({ t: s.t, obs: s.obs, act: s.act });
        if (state.samples.length > CAP) state.samples.shift();
      }
      applyStatus(s.status);
    };
    evtSource.onerror = () => {
      // EventSource auto-reconnects; nothing to do but wait.
    };
  }

  // ----- recording / saving indicators -------------------------------------
  // Arrives at the telemetry rate (~60 Hz); only touch the DOM when a value
  // actually changes so we never reflow the page every frame.
  const uiStatus = { recording: null, episodes: undefined, saving: null, phase: undefined };

  function applyStatus(status) {
    status = status || {};
    // The control panel and camera frames take the colour of whoever drives
    // the arm; a change of driver flashes the panel.
    const phase = status.phase || null;
    if (phase !== uiStatus.phase) {
      const previous = uiStatus.phase ? controlOwner(uiStatus.phase)[0] : null;
      uiStatus.phase = phase;
      const [owner, label] = phase ? controlOwner(phase) : [null, ""];
      els.controlOwner.textContent = label;
      els.controlOwner.title = phase ? `Session phase: ${phase}` : "";
      els.controlOwner.hidden = !phase;
      updateCommands(phase);
      for (const el of [els.daggerControls, els.streams]) {
        if (owner) el.dataset.owner = owner;
        else delete el.dataset.owner;
      }
      if (previous && owner !== previous) {
        els.daggerControls.classList.remove("control-changed");
        void els.daggerControls.offsetWidth; // restart the animation
        els.daggerControls.classList.add("control-changed");
      }
    }
    const controlMessage = document.getElementById("control-message");
    if (controlMessage) {
      controlMessage.textContent = status.message || "";
      controlMessage.hidden = !status.message;
    }

    // Red border + badge on every feed while recording.
    const recording = !!status.recording;
    if (recording !== uiStatus.recording) {
      uiStatus.recording = recording;
      for (const name in camWidgets) {
        camWidgets[name].cam.classList.toggle("recording", recording);
      }
      if (els.recPill) els.recPill.hidden = !recording;
    }

    // Dataset episode count (only present while recording mode is enabled).
    const episodes = status.episodes == null ? null : status.episodes;
    if (episodes !== uiStatus.episodes) {
      uiStatus.episodes = episodes;
      if (episodes == null) {
        els.episodesPill.hidden = true;
      } else {
        els.episodesPill.textContent =
          episodes === 1 ? "1 episode" : `${episodes} episodes`;
        els.episodesPill.hidden = false;
      }
    }

    // "Saving — do not close" banner while the writer thread drains episodes.
    const saving = status.saving || {};
    const written = saving.written || 0;
    const total = saving.total || 0;
    const queued = saving.queued || 0;
    savingActive = !!saving.active || queued > 0;

    const savingKey = savingActive
      ? `${!!saving.active}|${written}|${total}|${queued}`
      : "off";
    if (savingKey === uiStatus.saving) return;
    uiStatus.saving = savingKey;

    if (savingActive) {
      let txt;
      if (saving.active && total > 0) {
        txt = `Saving episode \u2014 ${written} / ${total} frames`;
      } else if (saving.active) {
        txt = "Saving episode\u2026";
      } else {
        txt = "Saving queued episode\u2026";
      }
      if (queued > 0) txt += ` (+${queued} queued)`;
      txt += " \u00b7 do not close this tab";
      els.savingText.textContent = txt;
      const pct = total > 0 ? Math.round((written / total) * 100) : 0;
      els.savingBarFill.style.width = pct + "%";
      els.saving.hidden = false;
    } else {
      els.saving.hidden = true;
    }
  }

  // ----- theme-aware plot colors -------------------------------------------
  let currentPlotColors = {};

  function updatePlotColors() {
    const styles = getComputedStyle(document.documentElement);
    currentPlotColors = {
      bg: styles.getPropertyValue("--plot-background").trim(),
      gridMinor: styles.getPropertyValue("--plot-grid-minor").trim(),
      gridZero: styles.getPropertyValue("--plot-grid-zero").trim(),
      text: styles.getPropertyValue("--plot-label").trim(),
    };
  }

  function plotColors() {
    return currentPlotColors;
  }

  // ----- plots -------------------------------------------------------------
  function fitCanvas(canvas) {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const w = Math.max(1, Math.round(rect.width * dpr));
    const h = Math.max(1, Math.round(rect.height * dpr));
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    return dpr;
  }

  function drawPlot(canvas, key) {
    const dpr = fitCanvas(canvas);
    const ctx = canvas.getContext("2d");
    const col = plotColors();
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = col.bg;
    ctx.fillRect(0, 0, W, H);

    const pad = 8 * dpr;
    const axisPad = 34 * dpr; // room for y labels
    const botPad = 16 * dpr; // room for x labels
    const innerX = pad + axisPad;
    const innerY = pad;
    const innerW = W - innerX - pad;
    const innerH = H - innerY - pad - botPad;
    if (innerW <= 1 || innerH <= 1) return;

    const samples = state.samples;
    const rad2deg = 180 / Math.PI;

    // Shared y-scale from the EMA of the peak across obs+act (so both plots
    // share a scale).
    let peak = 0;
    for (const s of samples) {
      for (const v of s.obs) peak = Math.max(peak, Math.abs(v * rad2deg));
      for (const v of s.act) peak = Math.max(peak, Math.abs(v * rad2deg));
    }
    if (key === "obs") state.emaMax = Math.max(peak, state.emaMax * 0.97);
    const scale = Math.max(state.emaMax, 1);

    // grid
    ctx.lineWidth = 1;
    ctx.font = `${11 * dpr}px -apple-system, sans-serif`;
    ctx.textBaseline = "middle";
    for (const frac of [0, 0.25, 0.5, 0.75, 1]) {
      const gy = innerY + innerH * frac;
      ctx.strokeStyle = frac === 0.5 ? col.gridZero : col.gridMinor;
      ctx.beginPath();
      ctx.moveTo(innerX, gy);
      ctx.lineTo(innerX + innerW, gy);
      ctx.stroke();
    }
    ctx.fillStyle = col.text;
    ctx.textAlign = "right";
    ctx.fillText(`+${scale.toFixed(0)}\u00b0`, innerX - 4 * dpr, innerY);
    ctx.fillText("0\u00b0", innerX - 4 * dpr, innerY + innerH * 0.5);
    ctx.fillText(`-${scale.toFixed(0)}\u00b0`, innerX - 4 * dpr, innerY + innerH);

    if (samples.length < 2) return;

    const t0 = samples[0].t;
    const tSpan = Math.max(1e-6, samples[samples.length - 1].t - t0);

    // x-axis labels
    ctx.textBaseline = "alphabetic";
    ctx.textAlign = "left";
    ctx.fillText(`${tSpan.toFixed(1)}s window`, innerX, H - 4 * dpr);
    ctx.textAlign = "right";
    ctx.fillText("now", innerX + innerW, H - 4 * dpr);

    const nJoints = state.jointNames.length;
    ctx.lineWidth = 1.75 * dpr;
    for (let ch = 0; ch < nJoints; ch++) {
      ctx.strokeStyle = state.colors[ch];
      ctx.beginPath();
      for (let i = 0; i < samples.length; i++) {
        const s = samples[i];
        const arr = key === "obs" ? s.obs : s.act;
        if (arr[ch] == null) continue;
        const xn = (s.t - t0) / tSpan;
        const deg = arr[ch] * rad2deg;
        const yn = 1 - (deg / (2 * scale) + 0.5);
        const x = innerX + xn * innerW;
        const y = innerY + yn * innerH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    }
  }

  function renderLoop() {
    drawStreams();
    drawPlot(els.plotObs, "obs");
    drawPlot(els.plotAct, "act");
    requestAnimationFrame(renderLoop);
  }

  // ----- connection --------------------------------------------------------
  function setStatus(cls, text) {
    els.status.className = "pill " + cls;
    els.status.textContent = text;
  }

  // Count frames that reach the browser compositor. This measures unique
  // decoded WebRTC frames, unlike the server-side "render" counter which
  // measures frames submitted to the encoder.
  let displayWindowStart = null;
  let displayFrameCount = 0;
  let lastDisplayedFrameAt = null;

  function resetDisplayFps() {
    state.displayFps = null;
    displayWindowStart = null;
    displayFrameCount = 0;
    lastDisplayedFrameAt = null;
  }

  function countDisplayedFrame(now) {
    lastDisplayedFrameAt = now;
    if (displayWindowStart == null) {
      displayWindowStart = now;
    } else {
      displayFrameCount += 1;
      const elapsed = now - displayWindowStart;
      if (elapsed >= 1000) {
        state.displayFps = (displayFrameCount * 1000) / elapsed;
        displayWindowStart = now;
        displayFrameCount = 0;
      }
    }
    els.video.requestVideoFrameCallback(countDisplayedFrame);
  }

  if ("requestVideoFrameCallback" in els.video) {
    els.video.requestVideoFrameCallback(countDisplayedFrame);
    setInterval(() => {
      if (
        connected &&
        lastDisplayedFrameAt != null &&
        performance.now() - lastDisplayedFrameAt > 1500
      ) {
        state.displayFps = 0;
      }
    }, 500);
  }

  async function connect() {
    if (connected || connecting) return;
    connecting = true;
    const server = location.hostname || "127.0.0.1";
    const signalingPort = state.signalPort || 49100;
    setStatus("connecting", "Connecting");
    els.hint.textContent = `Connecting to ${server}:${signalingPort}\u2026`;
    els.hint.style.display = "block";
    try {
      els.video.muted = true; // no audio track; keeps autoplay unblocked
      await AppStreamer.connect({
        streamSource: StreamType.DIRECT,
        logLevel: 2,
        streamConfig: {
          videoElementId: "video",
          server,
          signalingPort,
          fps: 60,
          maxReconnects: 3,
          onStart: (msg) => {
            if (msg.action !== "start") return;
            if (msg.status === "success") {
              connected = true;
              connecting = false;
              resetDisplayFps();
              setStatus("connected", "Connected");
              els.hint.style.display = "none";
              const v = els.video;
              if (v.srcObject) v.play().catch(() => {});
            } else if (msg.status === "error") {
              connected = false;
              connecting = false;
              setStatus("error", "Error");
              els.hint.textContent = "Failed to connect: " + (msg.info || "unknown");
              els.hint.style.display = "block";
            }
          },
          onStop: (msg) => {
            if (msg.action !== "terminate") return;
            connected = false;
            connecting = false;
            resetDisplayFps();
            setStatus(msg.status === "error" ? "error" : "ready",
              msg.status === "error" ? "Disconnected" : "Ready");
            els.hint.textContent = "Disconnected";
            els.hint.style.display = "block";
          },
        },
      });
    } catch (err) {
      connecting = false;
      setStatus("error", "Error");
      els.hint.textContent = "Connect failed: " + err.message;
      els.hint.style.display = "block";
    }
  }

  function restartConnection() {
    // A restarted sim process creates a new HTTP/SSE server and a new ovstream
    // WebRTC server, but the browser page itself may stay open. In that case
    // the previous stream can still report live tracks and leave `connected`
    // true even though its media session is dead. A full reload is intentional:
    // the vendored StreamSDK keeps internal singleton state that cannot be
    // reliably reused after its signaling server disappears.
    // A reconnecting EventSource can deliver another config while the initial
    // WebRTC attempt is still pending. Reloading here leaks that pending SDK
    // worker and leaves an orphan signaling peer on the single-client server.
    if (connecting) return;
    if (connected || els.video.srcObject) {
      window.location.reload();
      return;
    }
    connect();
  }

  // ----- init --------------------------------------------------------------
  els.envSelect.addEventListener("change", () => {
    selectEnvironment(Number(els.envSelect.value));
  });
  document.addEventListener("keydown", handleControlKeydown);
  window.addEventListener("blur", loseControl);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible") loseControl();
  });
  window.addEventListener("beforeunload", (e) => {
    loseControl();
    // Warn before closing mid-save so the episode write isn't abandoned.
    if (savingActive) {
      e.preventDefault();
      e.returnValue = "";
    }
    if (connected || connecting) AppStreamer.terminate();
  });
  const colorScheme = window.matchMedia("(prefers-color-scheme: dark)");
  colorScheme.addEventListener("change", updatePlotColors);
  updatePlotColors();
  startTelemetry();
  requestAnimationFrame(renderLoop);
})();
