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
"""Camera selection utilities for benchmarking OVRtx rendering overhead.

Provides :func:`apply_camera_selection` to disable cameras in the env cfg
at runtime, so the same task env can be run with different camera subsets
without separate gym registrations.

Benchmarking matrix (combine ``--cameras`` with ``--browser-display`` / ``--rerun``)::

    --cameras none                 → baseline: physics + Newton vis, no OVRtx
    --cameras wrist                → single OVRtx renderer (gripper cam)
    --cameras external             → single OVRtx renderer (webcam)
    --cameras all                  → both OVRtx renderers (default)
    --cameras all --browser-display → full pipeline with the browser display
    --cameras all --rerun          → full pipeline with Rerun streaming
"""

from __future__ import annotations

import argparse
import logging

logger = logging.getLogger(__name__)

# Short name → scene cfg attribute
_CAMERA_ALIASES: dict[str, str] = {
    "wrist": "camera_wrist",
    "gripper": "camera_wrist",
    "external": "camera_external",
}

# Scene cfg attribute → observation term attribute inside the visual group
_CAMERA_OBS_TERMS: dict[str, str] = {
    "camera_wrist": "rgb_wrist",
    "camera_external": "rgb_external",
}

ALL_CAMERAS: frozenset[str] = frozenset({"camera_wrist", "camera_external"})


def add_camera_args(parser: argparse.ArgumentParser) -> None:
    """Add ``--cameras`` and ``--headless-render`` to *parser*."""
    parser.add_argument(
        "--cameras",
        type=str,
        default="all",
        metavar="CAMS",
        help=(
            "Comma-separated camera selection. "
            "Choices: none, wrist/gripper, external, all (default: all). "
            "Controls which OVRtx renderers are created."
        ),
    )
    parser.add_argument(
        "--headless-render",
        action="store_true",
        default=False,
        help=(
            "Cameras render to GPU buffers but no display window is opened. "
            "Overrides --browser-display and --rerun. "
            "A local visualizer runs only when requested with --visualizer."
        ),
    )


def add_browser_display_args(parser: argparse.ArgumentParser) -> None:
    """Add ``--browser-display`` and its port flags to *parser*.

    The browser display streams the composited camera feed over ovstream's
    WebRTC transport and pushes joint/FPS telemetry over an SSE stream, both
    served from the sim container. It needs no ``$DISPLAY`` and is intended to
    run only via the Docker path.
    """
    parser.add_argument(
        "--browser-display",
        action="store_true",
        default=False,
        help=(
            "Stream cameras + telemetry to a browser via ovstream WebRTC "
            "(no $DISPLAY needed; open http://localhost:<http-port>). "
            "Mutually exclusive with --rerun."
        ),
    )
    parser.add_argument(
        "--signal-port",
        type=int,
        default=49100,
        help="ovstream WebRTC signalling port for --browser-display (default: 49100).",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=8090,
        help="HTTP port serving the browser client + telemetry SSE (default: 8090).",
    )


# Camera feed dimensions (height, width) and joint labels for the display.
_DISPLAY_FEEDS: dict[str, tuple[int, int]] = {
    "camera_external": (480, 640),
    "camera_wrist": (480, 640),
}
_DISPLAY_FEED_NAMES: dict[str, str] = {
    "camera_external": "external",
    "camera_wrist": "wrist",
}
DISPLAY_JOINT_NAMES: list[str] = [
    "shoulder_pan",
    "shoulder_lift",
    "elbow_flex",
    "wrist_flex",
    "wrist_roll",
    "gripper",
]


def build_sensor_display(
    active_cameras: set[str],
    args_cli,
    device: str,
    num_envs: int = 1,
    control_actions: set[str] | None = None,
):
    """Construct the browser sensor display, or ``None`` if not enabled.

    Returns a :class:`BrowserSensorDisplay` when ``--browser-display`` is set
    and at least one camera is active, else ``None``. ``device`` is the
    indexed CUDA device that owns the camera tensors. ``num_envs`` controls
    whether the browser exposes its environment selector.
    ``control_actions`` selects which browser keyboard actions the display
    accepts.
    """
    if not args_cli.browser_display or not active_cameras:
        return None

    # Preserve insertion order (external first, then wrist) for tiling parity.
    feeds: dict[str, tuple[int, int]] = {
        _DISPLAY_FEED_NAMES[cam]: _DISPLAY_FEEDS[cam]
        for cam in ("camera_external", "camera_wrist")
        if cam in active_cameras
    }
    if not feeds:
        return None

    from sim_to_real_so101.utils.ovstream import BrowserSensorDisplay

    return BrowserSensorDisplay(
        feeds,
        device=device,
        task_name=args_cli.task or "",
        joint_names=DISPLAY_JOINT_NAMES,
        signal_port=args_cli.signal_port,
        http_port=args_cli.http_port,
        num_envs=num_envs,
        control_actions=control_actions,
    )


def _parse_camera_selection(cameras: str) -> set[str]:
    """Parse a ``--cameras`` value into scene cfg attribute names."""
    cameras = cameras.strip().lower()
    if cameras == "none":
        return set()
    if cameras == "all":
        return set(ALL_CAMERAS)
    result: set[str] = set()
    for token in cameras.split(","):
        token = token.strip()
        if token in _CAMERA_ALIASES:
            result.add(_CAMERA_ALIASES[token])
        elif token in ALL_CAMERAS:
            result.add(token)
        else:
            raise ValueError(
                f"Unknown camera '{token}'. "
                f"Valid tokens: none, all, {', '.join(sorted(_CAMERA_ALIASES))}"
            )
    return result


def _prune_event_terms_for_cameras(env_cfg, disabled: set[str]) -> None:
    """Set to ``None`` any event term referencing a disabled camera entity.

    Scans the events cfg for ``EventTerm`` params holding a ``SceneEntityCfg``
    whose ``name`` is a disabled camera. Such a term would otherwise crash
    ``ManagerBase`` term resolution at play time with "scene entity does not
    exist" because the term still references a disabled scene entity.
    """
    events_cfg = getattr(env_cfg, "events", None)
    if events_cfg is None:
        return
    for term_name in list(vars(events_cfg)):
        term_cfg = getattr(events_cfg, term_name)
        params = getattr(term_cfg, "params", None)
        if not isinstance(params, dict):
            continue
        for value in params.values():
            name = getattr(value, "name", None)
            if name in disabled:
                setattr(events_cfg, term_name, None)
                logger.info("Disabled event term: %s (references %s)", term_name, name)
                break


def apply_camera_selection(env_cfg, cameras: str) -> set[str]:
    """Disable cameras not in *cameras* and strip matching obs/event terms.

    Sets disabled camera attributes to ``None`` on the scene cfg (skipped
    by ``InteractiveScene``) and their observation terms to ``None`` on the
    visual obs group (skipped by ``ObservationManager``).  If no cameras
    remain, the entire visual group is set to ``None``.  Event terms that
    reference a disabled camera via a ``SceneEntityCfg`` are also pruned, so
    ``--cameras none`` or a single-camera selection keeps scene init valid
    (a term referencing a disabled camera would fail term resolution).
    Multi-camera selections use eager sensor updates so Isaac Lab batches all
    due camera products through their shared renderer.

    Args:
        env_cfg: Resolved environment config (mutated in-place).
        cameras: Raw ``--cameras`` CLI value.

    Returns:
        Set of active camera attribute names present in the scene cfg.
    """
    wanted = _parse_camera_selection(cameras)
    scene_cfg = env_cfg.scene

    existing = {name for name in ALL_CAMERAS if hasattr(scene_cfg, name) and getattr(scene_cfg, name) is not None}
    if not existing:
        return set()

    to_disable = existing - wanted

    for cam_name in to_disable:
        setattr(scene_cfg, cam_name, None)
        logger.info("Disabled camera: %s", cam_name)

    _prune_event_terms_for_cameras(env_cfg, to_disable)

    obs_cfg = getattr(env_cfg, "observations", None)
    if obs_cfg is not None:
        visual_group = getattr(obs_cfg, "visual", None)
        if visual_group is not None:
            active = existing - to_disable
            if not active:
                obs_cfg.visual = None
                logger.info("Disabled visual observation group (no active cameras)")
            else:
                for cam_name in to_disable:
                    term_name = _CAMERA_OBS_TERMS.get(cam_name)
                    if term_name and hasattr(visual_group, term_name):
                        setattr(visual_group, term_name, None)
                        logger.info("Disabled obs term: %s", term_name)

    active = existing - to_disable
    if len(active) > 1:
        scene_cfg.lazy_sensor_update = False
    if active:
        logger.info("Active cameras: %s", ", ".join(sorted(active)))
    else:
        logger.info("All cameras disabled — OVRtx rendering will be skipped")

    return active
