# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Browser-based multi-feed sensor display over ovstream (WebRTC).

Streams the live camera feed to a browser instead of opening a local window —
so it needs no ``$DISPLAY`` and runs headless inside the sim container.

Two channels, on purpose:

* **Video** — the N camera feeds are composited side-by-side on the GPU into
  one BGRA buffer and streamed through ovstream's WebRTC transport (NVENC-
  encoded on the GPU, no host copy).
* **Telemetry** — joint observations / actions / per-camera FPS are pushed to
  the browser over a Server-Sent-Events stream (stdlib ``http.server``, no
  extra deps). The browser draws the rolling plots and the FPS overlay
  natively, so they stay crisp instead of being rasterized into the video.

The same static server also serves the browser client (``browser_client/``).
With the sim container on ``--network=host`` the whole thing is reachable from
the host browser at ``http://localhost:<http_port>``.

Public API used by the agent loop: ``update(name, frame)``,
``push_telemetry(obs, act)``, ``drain_control_actions()``, ``flush()``,
``close()``.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import ovstream
import torch

logger = logging.getLogger(__name__)

_CLIENT_DIR = Path(__file__).parent / "browser_client"
_CONTROL_ACTIONS = frozenset(
    {"toggle_recording", "cancel_episode", "reset_world", "pause_resume", "toggle_correction", "stop_session",
     "guide_start", "control_heartbeat", "control_lost", "hold_position", "release_exit"}
)

# Static files the server is allowed to hand out, mapped to content types.
# An explicit allowlist avoids any path-traversal surface.
_STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/omniverse-webrtc-streaming-library.js": (
        "omniverse-webrtc-streaming-library.js",
        "text/javascript; charset=utf-8",
    ),
}


class _FPSCounter:
    """Wall-clock event-rate counter with a one-second window."""

    def __init__(self):
        self._window_start: float | None = None
        self._count = 0
        self._fps: float = 0.0

    def tick(self) -> None:
        now = time.perf_counter()
        if self._window_start is None:
            self._window_start = now
            return
        self._count += 1
        elapsed = now - self._window_start
        if elapsed >= 1.0:
            self._fps = self._count / elapsed
            self._window_start = now
            self._count = 0

    @property
    def fps(self) -> float:
        return self._fps


class _TelemetryHandler(BaseHTTPRequestHandler):
    """Serves the browser client and the ``/telemetry`` SSE stream.

    The owning :class:`BrowserSensorDisplay` is attached to the server as
    ``server.display`` so every request can read the shared telemetry state.
    """

    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:
        pass

    def handle(self) -> None:
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self) -> None:
        if self.path == "/telemetry":
            self._serve_sse()
            return
        entry = _STATIC_FILES.get(self.path)
        if entry is None:
            self.send_error(404, "Not Found")
            return
        filename, content_type = entry
        try:
            data = (_CLIENT_DIR / filename).read_bytes()
        except OSError:
            self.send_error(404, "Not Found")
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        if self.path not in {"/control/environment", "/control/action"}:
            self.send_error(404, "Not Found")
            return
        if self.headers.get("Content-Type", "").partition(";")[0] != "application/json":
            self.send_error(415, "Content-Type must be application/json")
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_error(400, "Invalid Content-Length")
            return
        if content_length <= 0 or content_length > 1024:
            self.send_error(400, "Invalid request body")
            return

        try:
            request = json.loads(self.rfile.read(content_length))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error(400, "Invalid JSON")
            return

        display: BrowserSensorDisplay = self.server.display  # type: ignore[attr-defined]
        if self.path == "/control/environment":
            env_index = request.get("env") if isinstance(request, dict) else None
            if not isinstance(env_index, int) or isinstance(env_index, bool):
                self.send_error(400, "env must be an integer")
                return
            try:
                display.select_environment(env_index)
            except ValueError as exc:
                self.send_error(400, str(exc))
                return
            response = {"selected_env": display.selected_environment}
        else:
            action = request.get("action") if isinstance(request, dict) else None
            if not isinstance(action, str):
                self.send_error(400, "action must be a string")
                return
            try:
                display.enqueue_control_action(action, source=request.get("source"), sequence=request.get("sequence"))
            except ValueError as exc:
                self.send_error(400, str(exc))
                return
            response = {"accepted": action}

        payload = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _serve_sse(self) -> None:
        display: BrowserSensorDisplay = self.server.display  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        try:
            self._write_sse("config", display.config_json())
            last_seq = -1
            last_send = 0.0
            while display.running:
                seq, payload = display.telemetry_snapshot()
                now = time.perf_counter()
                # Push on a new sample, plus a ~2 Hz heartbeat so FPS keeps
                # refreshing even while teleop is paused.
                if seq != last_seq or (now - last_send) > 0.5:
                    self._write_sse(None, payload)
                    last_seq = seq
                    last_send = now
                time.sleep(0.015)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass  # client navigated away / reloaded

    def _write_sse(self, event: str | None, data: str) -> None:
        chunk = ""
        if event is not None:
            chunk += f"event: {event}\n"
        chunk += f"data: {data}\n\n"
        self.wfile.write(chunk.encode("utf-8"))
        self.wfile.flush()


class BrowserSensorDisplay:
    """Composite N camera feeds and stream them to a browser via ovstream.

    Args:
        feeds: Ordered mapping of ``{name: (height, width)}``. All feeds must
            share the same height (they are tiled left-to-right).
        device: Indexed CUDA device that owns the camera and stream buffers.
        task_name: Task name shown in the browser title ("OVRTX Stream - ...").
        joint_names: Labels for the telemetry plots.
        n_joints: Number of joint channels in the telemetry plots.
        signal_port: ovstream WebRTC signalling port (browser connects here).
        http_port: Port for the static client + ``/telemetry`` SSE stream.
        target_fps: Encoder target FPS hint.
        num_envs: Number of environments available for browser selection.
        control_actions: Browser control actions accepted by this display.
    """

    def __init__(
        self,
        feeds: dict[str, tuple[int, int]],
        *,
        device: str | torch.device,
        task_name: str = "",
        n_joints: int = 6,
        joint_names: list[str] | None = None,
        signal_port: int = 49100,
        http_port: int = 8090,
        target_fps: int = 60,
        num_envs: int = 1,
        control_actions: set[str] | None = None,
    ):
        heights = {h for h, _w in feeds.values()}
        if len(heights) != 1:
            raise ValueError(f"All feeds must have the same height, got {heights}")

        self._device = torch.device(device)
        if self._device.type != "cuda" or self._device.index is None:
            raise ValueError(f"Browser streaming requires an indexed CUDA device, got {device}")

        self._feed_names = list(feeds.keys())
        self._feed_widths = {name: w for name, (_, w) in feeds.items()}
        self._cam_height = next(iter(heights))
        self._total_width = sum(w for _, w in feeds.values())

        self._n_joints = n_joints
        if joint_names is not None and len(joint_names) != n_joints:
            raise ValueError(f"joint_names length {len(joint_names)} != n_joints {n_joints}")
        self._joint_names = joint_names or [f"j{i}" for i in range(n_joints)]

        self._task_name = task_name
        self._signal_port = signal_port
        self._http_port = http_port
        if num_envs < 1:
            raise ValueError(f"num_envs must be positive, got {num_envs}")
        self._num_envs = num_envs
        self._selected_env = 0
        self._enabled_control_actions = frozenset(control_actions or ())
        unknown_actions = self._enabled_control_actions - _CONTROL_ACTIONS
        if unknown_actions:
            raise ValueError(f"Unknown browser control actions: {sorted(unknown_actions)}")
        self._control_actions: deque[str] = deque(maxlen=64)
        self._client_deadline = 0.0
        self._client_floor = 0
        self._client_source = None
        self._control_lost_reported = True
        self._control_sequences = {}

        # GPU compositing buffers (allocated on first frame, on its device).
        self._canvas: torch.Tensor | None = None
        self._bgra_buffer: torch.Tensor | None = None
        self._video_frame: ovstream.VideoFrame | None = None
        self._producer_event: torch.cuda.Event | None = None
        # FPS accounting: env_fps ticks every update() (control-loop rate);
        # render_fps ticks only when a genuinely new frame arrives (camera
        # update_period, detected via a cheap strided checksum).
        self._fps_counters = {n: _FPSCounter() for n in self._feed_names}
        self._render_fps_counters = {n: _FPSCounter() for n in self._feed_names}
        self._last_frame_sig: dict[str, int | None] = {n: None for n in self._feed_names}

        # Shared telemetry state (read by SSE handler threads).
        self._lock = threading.Lock()
        self._t0 = time.perf_counter()
        self._sample = {"t": 0.0, "obs": [], "act": []}
        self._sample_seq = 0
        # Recording / episode-saving state mirrored to the browser client
        # (red border while recording; "saving — do not close" banner while
        # the recorder's writer thread drains an episode to disk).
        self._status = {
            "recording": False,
            "saving": {"active": False, "written": 0, "total": 0, "queued": 0},
            "episodes": None,
        }
        self.running = True
        self._closed = False
        self._ovstream_initialized = False
        self._server: ovstream.Server | None = None
        self._httpd: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._http_thread_started = False

        try:
            # ovstream and NVENC use the calling thread's current CUDA context.
            with torch.cuda.device(self._device):
                torch.cuda.init()
                ovstream.initialize()
                self._ovstream_initialized = True
                self._server = ovstream.Server(ovstream.ServerType.WEBRTC)
                self._server.on_connection = lambda c: logger.info(
                    "Browser %s", "connected" if c else "disconnected"
                )
                cfg = ovstream.ServerConfig(
                    width=self._total_width,
                    height=self._cam_height,
                    target_fps=target_fps,
                    video_input=ovstream.VideoInput.CUDA,
                    webrtc_signal_port=signal_port,
                )
                self._server.start(cfg)
                self._producer_event = torch.cuda.Event()

            # Static client + telemetry SSE server.
            self._httpd = ThreadingHTTPServer(("0.0.0.0", http_port), _TelemetryHandler)
            self._httpd.daemon_threads = True
            self._httpd.display = self  # type: ignore[attr-defined]
            self._http_thread = threading.Thread(
                target=self._httpd.serve_forever,
                daemon=True,
                name="BrowserSensorDisplay-HTTP",
            )
            self._http_thread.start()
            self._http_thread_started = True
        except Exception:
            self.close()
            raise

        print(
            f"[INFO]: Browser sensor display ready.\n"
            f"        Open http://localhost:{http_port}  (WebRTC signal port {signal_port})\n"
            f"        Feeds: {self._feed_names}"
        )

    # ------------------------------------------------------------------
    # Telemetry state accessed by the SSE handler threads
    # ------------------------------------------------------------------

    def config_json(self) -> str:
        return json.dumps(
            {
                "task": self._task_name,
                "signal_port": self._signal_port,
                "num_envs": self._num_envs,
                "selected_env": self.selected_environment,
                "control_actions": [
                    action
                    for action in (
                        "toggle_recording",
                        "cancel_episode",
                        "reset_world",
                        "pause_resume",
                        "toggle_correction",
                        "stop_session",
                        "guide_start", "control_heartbeat", "control_lost",
                        "hold_position", "release_exit",
                    )
                    if action in self._enabled_control_actions
                ],
                "joint_names": self._joint_names,
                "feeds": [
                    {"name": n, "width": self._feed_widths[n], "height": self._cam_height}
                    for n in self._feed_names
                ],
            }
        )

    def telemetry_snapshot(self) -> tuple[int, str]:
        with self._lock:
            seq = self._sample_seq
            payload = json.dumps(
                {
                    **self._sample,
                    "fps": {
                        n: {
                            "render": round(self._render_fps_counters[n].fps, 1),
                            "env": round(self._fps_counters[n].fps, 1),
                        }
                        for n in self._feed_names
                    },
                    "status": self._status,
                    "num_envs": self._num_envs,
                    "selected_env": self._selected_env,
                }
            )
        return seq, payload

    @property
    def selected_environment(self) -> int:
        """Return the environment currently selected by browser clients."""
        with self._lock:
            return self._selected_env

    def select_environment(self, env_index: int) -> None:
        """Select an environment and clear telemetry from the previous one."""
        if not 0 <= env_index < self._num_envs:
            raise ValueError(
                f"env must be between 0 and {self._num_envs - 1}, got {env_index}"
            )
        with self._lock:
            if env_index == self._selected_env:
                return
            self._selected_env = env_index
            self._t0 = time.perf_counter()
            self._sample = {"t": 0.0, "obs": [], "act": []}
            self._sample_seq += 1

    def enqueue_control_action(self, action: str, source=None, sequence=None) -> None:
        """Queue ordered operator actions; a browser lease gates active DAgger control."""
        if action not in self._enabled_control_actions:
            raise ValueError(f"Browser control action is not enabled: {action}")
        with self._lock:
            if "guide_start" in self._enabled_control_actions:
                if not isinstance(source, str) or not isinstance(sequence, int) or isinstance(sequence, bool):
                    raise ValueError("DAgger controls require source and sequence")
                channel = (source, "heartbeat" if action == "control_heartbeat" else "action")
                previous_sequence = self._control_sequences.get(channel, -1)
                if sequence <= previous_sequence and action != "stop_session":
                    return
                self._control_sequences[channel] = max(sequence, previous_sequence)
                now = time.monotonic()
                if action == "control_heartbeat":
                    if self._client_source not in {None, source} and self._client_deadline > now:
                        return
                    if self._client_source != source or self._client_deadline <= now:
                        self._client_floor = sequence
                        retained = [action for action in self._control_actions if action in {
                            "stop_session", "hold_position", "release_exit",
                        }]
                        self._control_actions.clear()
                        self._control_actions.extend(retained)
                        if self._client_source is not None:
                            # A first connection has lost nothing; later (re)acquisitions hold.
                            self._control_actions.append("control_lost")
                    self._client_source = source
                    self._client_deadline = now + 1.0
                    self._control_lost_reported = False
                    return
                if action not in {"stop_session", "hold_position", "release_exit", "control_lost"} and (
                    source != self._client_source or self._client_deadline <= now or sequence <= self._client_floor
                ):
                    return
                if action == "control_lost":
                    self._client_deadline = 0.0
            self._control_actions.append(action)

    def drain_control_actions(self) -> tuple[str, ...]:
        """Expire control once; never resume guidance from a heartbeat or key repeat."""
        with self._lock:
            actions = tuple(self._control_actions)
            self._control_actions.clear()
            if "stop_session" in actions:
                return ("stop_session",)
            if "guide_start" in self._enabled_control_actions and self._client_deadline <= time.monotonic():
                actions = tuple(action for action in actions if action in {
                    "stop_session", "release_exit", "hold_position", "control_lost",
                })
                if not self._control_lost_reported and "control_lost" not in actions:
                    actions += ("control_lost",)
                self._control_lost_reported = True
            return actions

    # ------------------------------------------------------------------
    # Main-thread API
    # ------------------------------------------------------------------

    def push_telemetry(
        self,
        joint_pos_obs: torch.Tensor,
        joint_action: torch.Tensor,
        env_index: int | None = None,
    ) -> None:
        """Append one telemetry sample to the rolling plots.

        Both tensors must be 1-D of length ``n_joints``. Copied to host here
        (6 floats — negligible) so the SSE thread never touches the GPU. When
        ``env_index`` is given, a sample racing with a browser selection change
        is discarded instead of contaminating the newly cleared plot.
        """
        if self._n_joints == 0:
            return
        obs = joint_pos_obs[: self._n_joints].detach().cpu().tolist()
        act = joint_action[: self._n_joints].detach().cpu().tolist()
        with self._lock:
            if env_index is not None and env_index != self._selected_env:
                return
            self._sample = {"t": time.perf_counter() - self._t0, "obs": obs, "act": act}
            self._sample_seq += 1

    def push_status(
        self, recording: bool, saving: dict | None = None, episodes: int | None = None,
        phase: str | None = None,
        message: str | None = None,
    ) -> None:
        """Mirror recording / saving state to the browser client.

        Cheap enough to call every control step. ``recording`` toggles the red
        border on the camera feeds; ``saving`` (from
        :meth:`LeRobotRecorder.saving_status`) drives the "saving — do not
        close" banner and its progress bar; ``episodes`` is the dataset episode
        count shown while recording mode is enabled (``None`` hides it). Bumps
        the sample sequence so the SSE stream pushes the change without waiting
        for the heartbeat.
        """
        with self._lock:
            self._status = {
                "recording": bool(recording),
                "saving": saving
                or {"active": False, "written": 0, "total": 0, "queued": 0},
                "episodes": episodes,
                "phase": phase,
                "message": message,
            }
            self._sample_seq += 1

    def tick_control(self) -> None:
        """Count one control-loop iteration for the FPS overlay."""
        for counter in self._fps_counters.values():
            counter.tick()

    def update(
        self,
        name: str,
        frame: torch.Tensor,
        *,
        frame_is_new: bool | None = None,
    ) -> None:
        """Stage a feed into the composite canvas (GPU copy only).

        Args:
            name: Feed name (must match a key passed to the constructor).
            frame: ``(H, W, 3)`` (or ``(H, W, 4)``) uint8 CUDA tensor.
            frame_is_new: When true, count this call as a camera render without
                synchronizing the GPU for content-based change detection. When
                omitted, infer new frames from a strided checksum.
        """
        if frame.device != self._device:
            raise ValueError(
                f"Feed {name!r} is on {frame.device}, expected {self._device}"
            )
        if frame_is_new is None:
            self._fps_counters[name].tick()
            try:
                sig = int(frame[::32, ::32, 0].sum().item())
            except Exception:  # noqa: BLE001
                sig = None
            if sig is None or sig != self._last_frame_sig.get(name):
                self._render_fps_counters[name].tick()
                self._last_frame_sig[name] = sig
        elif frame_is_new:
            self._render_fps_counters[name].tick()

        if self._canvas is None:
            self._canvas = torch.zeros(
                (self._cam_height, self._total_width, 3),
                dtype=torch.uint8,
                device=self._device,
            )

        with torch.cuda.device(self._device):
            x = 0
            for n in self._feed_names:
                if n == name:
                    w = self._feed_widths[n]
                    self._canvas[:, x : x + w, :] = frame[:, :, :3]
                    return
                x += self._feed_widths[n]

    def flush(self) -> None:
        """Swizzle the composite canvas to BGRA and stream one frame."""
        if self._canvas is None or not self.running or self._server is None:
            return

        with torch.cuda.device(self._device):
            if self._bgra_buffer is None:
                # ovstream's frame lifetime contract supports refilling one
                # long-lived CUDA allocation after each submission.
                self._bgra_buffer = torch.empty(
                    (self._cam_height, self._total_width, 4),
                    dtype=torch.uint8,
                    device=self._device,
                )
            bgra = self._bgra_buffer

            # RGB -> BGRA (ovstream's raw-CUDA pixel format).
            bgra[..., 0] = self._canvas[..., 2]
            bgra[..., 1] = self._canvas[..., 1]
            bgra[..., 2] = self._canvas[..., 0]
            bgra[..., 3] = 255

            producer_stream = torch.cuda.current_stream(self._device)
            assert self._producer_event is not None
            self._producer_event.record(producer_stream)
            self._video_frame = ovstream.VideoFrame.from_cuda_array(
                bgra,
                sync=ovstream.CudaSync(
                    stream=producer_stream.cuda_stream,
                    wait_event=self._producer_event.cuda_event,
                ),
            )
            try:
                self._server.stream_video(self._video_frame)
            except ovstream.OvstreamError:
                pass  # no client connected yet, encoder warm-up, etc.

    def close(self) -> None:
        """Stop the servers and release ovstream."""
        if self._closed:
            return
        self._closed = True
        self.running = False
        if self._server is not None:
            with torch.cuda.device(self._device):
                try:
                    self._server.stop()
                except ovstream.OvstreamError:
                    logger.debug("ovstream server was already stopped", exc_info=True)
                self._server.close()
            self._server = None
        if self._httpd is not None:
            if self._http_thread_started:
                self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._http_thread is not None:
            if self._http_thread_started:
                self._http_thread.join()
            self._http_thread = None
            self._http_thread_started = False
        self._video_frame = None
        self._bgra_buffer = None
        self._canvas = None
        self._producer_event = None
        if self._ovstream_initialized:
            ovstream.shutdown()
            self._ovstream_initialized = False
