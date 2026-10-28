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
"""LeRobot SO-101 interface for the Newton stack.

Uses numpy for joint math (lerobot is numpy-native); converts to torch only at
the env.step() boundary.

The eval policy client (:class:`LeRobotPolicyServerClient`) speaks LeRobot's
async-inference gRPC protocol (``lerobot.async_inference.policy_server``). The
server is policy-agnostic: the client sends a ``RemotePolicyConfig`` and the
server loads the checkpoint and runs its own pre/post-processor pipeline, so
the GR00T-specific obs packing / normalization / relative-action decoding all
happen server-side. The only sim-side contract that remains is the SO-101
joint mapping (sim radians <-> raw LeRobot units), handled by
:class:`LeRobotSO101Interface`.
"""

import pickle  # nosec B403 - internal trusted localhost gRPC payloads
import time
import uuid
from collections import deque
from typing import ClassVar

import numpy as np
import rerun as rr
import torch
from lerobot.teleoperators.so_leader import SOLeader
from lerobot.teleoperators.so_leader.config_so_leader import SOLeaderTeleopConfig
from sim_to_real_so101.utils.gripper_calibration import (
    WORKSHOP_GRIPPER_CALIBRATION,
    GripperCalibration,
)
from torchvision.io import encode_jpeg


class LeaderReadError(RuntimeError):
    """Raised when the SO-101 leader arm cannot be read after retries.

    Lets callers distinguish a recoverable teleop/serial dropout (so they can
    flush in-flight work and shut down cleanly) from a genuine programming bug.
    """


class LeRobotSO101Interface:
    SO101_JOINT_ORDER: ClassVar[list[str]] = [
        "shoulder_pan.pos",
        "shoulder_lift.pos",
        "elbow_flex.pos",
        "wrist_flex.pos",
        "wrist_roll.pos",
        "gripper.pos",
    ]

    def __init__(
        self,
        port: str,
        robot_id: str,
        sim_device: str = "cuda:0",
        calibration: GripperCalibration = WORKSHOP_GRIPPER_CALIBRATION,
    ):
        self.calibration = calibration
        self.port = port
        self.robot_id = robot_id
        self.sim_device = sim_device

        self.joint_names = [j.split(".")[0] for j in self.SO101_JOINT_ORDER]

    def connect(self, visualize: bool = False, hold_position: bool = False):
        """Connect a leader; held startup requires calibrated position-mode motors."""
        cfg = SOLeaderTeleopConfig(port=self.port, id=self.robot_id, use_degrees=True)
        self.teleop = SOLeader(cfg)
        self._visualize = visualize
        if hold_position:
            # SOLeader.configure() releases every motor. DAgger must reconnect
            # to a held arm without running configuration or calibration motion.
            self.teleop.bus.connect()
            if not self.teleop.is_calibrated:
                raise RuntimeError("Calibrate the leader with the workshop calibration command before DAgger.")
            modes = self.teleop.bus.sync_read("Operating_Mode", normalize=False)
            if any(mode != 0 for mode in modes.values()):
                raise RuntimeError("DAgger requires calibrated SO101 motors already configured in position mode.")
            self.teleop.send_feedback(self.teleop.get_action())
            self.teleop.enable_torque()
        else:
            try:
                self.teleop.connect()
            except ConnectionError as exc:
                raise ConnectionError(
                    f"Could not connect to the SO-101 leader arm on {self.port!r}. "
                    "Make sure the leader arm is plugged in via USB and powered on. "
                    "Run `lerobot-find-port`, then use `setenv` to set TELEOP_PORT "
                    "to the detected leader port."
                ) from exc
        if visualize:
            session_name = f"so101_teleop_{uuid.uuid4().hex[:8]}"
            rr.init(session_name, spawn=True)
            print(f"[INFO]: Rerun visualization started (session={session_name})")
        print(f"[INFO]: Connected to SO-101 leader at {self.port} (id={self.robot_id})")

    def disconnect(self):
        if self._visualize:
            rr.disconnect()
        if hasattr(self, "teleop"):
            self.teleop.disconnect()

    def get_raw_action(self, action_dict: dict) -> np.ndarray:
        """Extract ordered joint values from lerobot action dict → (6,) float32."""
        return np.array(
            [action_dict[j] for j in self.SO101_JOINT_ORDER], dtype=np.float32
        )

    def raw_to_sim_radians(self, raw: np.ndarray) -> np.ndarray:
        """Convert arm degrees and gripper percentage to simulator radians.

        Gripper percentage uses the measured follower scale and jaw-frame zero.
        Arm values are already angles. Conversion is unclipped; the simulator
        enforces physical joint limits through its asset.
        """
        raw = np.asarray(raw)
        degrees = raw.astype(np.result_type(raw.dtype, np.float32), copy=True)
        degrees[..., 5] = self.calibration.percent_to_degrees(raw[..., 5])
        return np.deg2rad(degrees)

    def sim_radians_to_raw(self, radians: np.ndarray) -> np.ndarray:
        """Convert simulator radians to arm degrees and gripper percentage, unclipped."""
        raw = np.rad2deg(radians)
        raw[..., 5] = self.calibration.degrees_to_percent(raw[..., 5])
        return raw

    def _read_action_dict(self, max_retries: int, retry_delay: float) -> dict:
        """Read the leader arm with retries on transient serial dropouts.

        The Feetech bus occasionally drops a status packet (USB/EMI hiccup),
        which surfaces as a ``ConnectionError`` from ``teleop.get_action()``.
        These are almost always momentary, so we retry a few times before
        giving up with a typed :class:`LeaderReadError`.
        """
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                return self.teleop.get_action()
            except Exception as exc:  # noqa: BLE001 - serial layer raises broadly
                last_exc = exc
                if attempt < max_retries:
                    print(
                        f"[WARNING]: Leader read failed "
                        f"(attempt {attempt + 1}/{max_retries + 1}): {exc}. Retrying..."
                    )
                    time.sleep(retry_delay)
        raise LeaderReadError(
            f"Leader read failed after {max_retries + 1} attempts: {last_exc}"
        ) from last_exc

    def read_action(
        self,
        visual_obs: dict | None = None,
        max_retries: int = 3,
        retry_delay: float = 0.02,
    ) -> tuple[np.ndarray, torch.Tensor]:
        """Read leader arm → return (raw_values, sim_action_tensor).

        Args:
            visual_obs: Optional dict of visual observations (e.g. {"rgb_wrist": tensor})
                to log to rerun when visualization is enabled.
            max_retries: Extra attempts on a transient serial read failure
                before raising :class:`LeaderReadError`.
            retry_delay: Seconds to wait between retries.

        Returns:
            raw: (6,) numpy array in lerobot's native space
            sim_action: (6,) torch tensor in sim radians, on sim_device

        Raises:
            LeaderReadError: If the leader cannot be read after all retries.
        """
        action_dict = self._read_action_dict(max_retries, retry_delay)
        raw = self.get_raw_action(action_dict)
        sim_radians = self.raw_to_sim_radians(raw)
        sim_action = torch.from_numpy(sim_radians).to(self.sim_device)

        if self._visualize:
            self._step_count = getattr(self, "_step_count", 0) + 1
            rr.set_time("step", sequence=self._step_count)
            rr.log(
                "joints/observations",
                rr.Scalars(raw.tolist()),
                rr.SeriesLines(names=self.joint_names),
            )
            action_vals = [action_dict[j] for j in self.SO101_JOINT_ORDER]
            rr.log(
                "joints/actions",
                rr.Scalars(action_vals),
                rr.SeriesLines(names=self.joint_names),
            )
            if visual_obs:
                for key, tensor in visual_obs.items():
                    if tensor.numel() > 0:
                        chw = tensor[0].permute(2, 0, 1).contiguous()
                        jpeg = encode_jpeg(chw, quality=85)
                        rr.log(
                            f"cameras/{key}",
                            rr.EncodedImage(
                                contents=jpeg.cpu().numpy().tobytes(),
                                media_type="image/jpeg",
                            ),
                        )

        return raw, sim_action


class LeRobotPolicyServerClient:
    """Drive the sim from a LeRobot async-inference policy server over gRPC.

    Synchronous adapter around ``lerobot.async_inference.policy_server``: the
    Newton env steps on the main thread (GPU / OVRtx), so rather than running
    the reference :class:`RobotClient`'s two real-time threads we drive the
    server in a request/response cadence (one observation -> one action chunk)
    for deterministic eval.

    The server is policy-agnostic. On :meth:`connect` we hand it a
    ``RemotePolicyConfig`` (policy type, checkpoint id, the LeRobot feature
    spec, ``actions_per_chunk``, device); the server runs
    ``from_pretrained`` and builds the checkpoint's pre/post-processor pipeline.
    We therefore send a *raw* observation (per-joint scalars in raw LeRobot
    units + bare-camera-name RGB arrays + ``task``) and receive *absolute*
    action vectors already in the dataset action space -- all modality packing,
    normalization, image resizing and relative-action decoding is server-side.
    """

    def __init__(
        self,
        robot_iface: LeRobotSO101Interface,
        camera_names: list[str],
        pretrained_name_or_path: str,
        policy_type: str = "groot",
        server_address: str = "localhost:8080",
        policy_device: str = "cuda",
        actions_per_chunk: int = 16,
        lang_instruction: str = "Pick up the vial and place it in the rack",
        rename_map: dict | None = None,
        camera_shape: tuple[int, int, int] = (480, 640, 3),
        action_timeout_s: float = 30.0,
    ):
        self._iface = robot_iface
        self._camera_names = camera_names
        self._pretrained = pretrained_name_or_path
        self._policy_type = policy_type
        self._server_address = server_address
        self._policy_device = policy_device
        self._actions_per_chunk = actions_per_chunk
        self._lang_instruction = lang_instruction
        # The server looks up image shapes before its rename processor runs.
        camera_map = {}
        for source, target in (rename_map or {}).items():
            source = source.removeprefix("observation.images.")
            target = target.removeprefix("observation.images.")
            if source in camera_map and camera_map[source] != target:
                raise ValueError(f"rename_map has conflicting targets for camera {source!r}")
            camera_map[source] = target
        if set(camera_map) - set(camera_names):
            raise ValueError("rename_map sources must name active cameras")
        self._policy_camera_names = {
            camera: camera_map.get(camera, camera) for camera in camera_names
        }
        targets = list(self._policy_camera_names.values())
        if len(set(targets)) != len(targets):
            raise ValueError("rename_map must give each camera a distinct name")
        if any(not name or "." in name or name == "task" for name in targets):
            raise ValueError("rename_map targets must be bare camera names or observation.images.<name>")
        self._camera_shape = camera_shape
        self._action_timeout_s = action_timeout_s

        self._action_queue: deque = deque()
        self._timestep = 0
        self._channel = None
        self._stub = None
        self._pb2 = None

    def _build_lerobot_features(self) -> dict:
        """Describe the robot's obs features the way the server expects them.

        Produces ``observation.state`` (names = SO101 joint order) plus one
        ``observation.images.<cam>`` per camera, matching the checkpoint's
        ``input_features``.
        """
        from lerobot.utils.constants import OBS_STR
        from lerobot.utils.feature_utils import hw_to_dataset_features

        hw_features: dict = {name: float for name in self._iface.SO101_JOINT_ORDER}
        for camera in self._camera_names:
            hw_features[self._policy_camera_names[camera]] = self._camera_shape
        return hw_to_dataset_features(hw_features, OBS_STR, use_video=False)

    def connect(self):
        """Open the gRPC channel and hand the server its policy instructions."""
        import grpc
        from lerobot.async_inference.helpers import RemotePolicyConfig
        from lerobot.transport import services_pb2, services_pb2_grpc
        from lerobot.transport.utils import grpc_channel_options

        self._pb2 = services_pb2

        print(f"[INFO]: Connecting to LeRobot policy server at {self._server_address}...")
        self._channel = grpc.insecure_channel(self._server_address, grpc_channel_options())
        self._stub = services_pb2_grpc.AsyncInferenceStub(self._channel)

        # Handshake: Ready() flushes any prior server state, then we ship the
        # policy spec so the server loads the checkpoint and its processors.
        self._stub.Ready(services_pb2.Empty(), timeout=self._action_timeout_s)

        lerobot_features = self._build_lerobot_features()
        policy_config = RemotePolicyConfig(
            policy_type=self._policy_type,
            pretrained_name_or_path=self._pretrained,
            lerobot_features=lerobot_features,
            actions_per_chunk=self._actions_per_chunk,
            device=self._policy_device,
            rename_map={},
        )
        self._stub.SendPolicyInstructions(
            services_pb2.PolicySetup(data=pickle.dumps(policy_config))
        )
        print(
            f"[INFO]: Policy server loading '{self._pretrained}' "
            f"(type={self._policy_type}, device={self._policy_device})"
        )

    def reset(self):
        """Flush server-side state and the local action buffer for a new episode."""
        self._stub.Ready(self._pb2.Empty(), timeout=self._action_timeout_s)
        self._action_queue.clear()
        self._timestep = 0

    def _build_raw_observation(
        self, joint_positions: torch.Tensor, visual_obs: dict
    ) -> dict:
        """Assemble the raw observation dict the server's processor consumes.

        Per-joint scalar keys (``shoulder_pan.pos`` ...) in raw LeRobot units,
        RGB arrays keyed by checkpoint camera names, and ``task``.
        """
        radians = joint_positions.detach().cpu().numpy().astype(np.float32)
        state_raw = self._iface.sim_radians_to_raw(radians).astype(np.float32)

        raw_obs: dict = {
            name: float(state_raw[i])
            for i, name in enumerate(self._iface.SO101_JOINT_ORDER)
        }
        for camera in self._camera_names:
            raw_obs[self._policy_camera_names[camera]] = visual_obs[f"rgb_{camera}"][0].cpu().numpy()
        raw_obs["task"] = self._lang_instruction
        return raw_obs

    def _query_action_chunk(self, joint_positions: torch.Tensor, visual_obs: dict):
        """Send one observation and block for the resulting action chunk."""
        from lerobot.async_inference.helpers import TimedObservation
        from lerobot.transport.utils import send_bytes_in_chunks

        raw_obs = self._build_raw_observation(joint_positions, visual_obs)
        # must_go=True bypasses the server's similarity / already-predicted
        # filtering so every query is guaranteed to run inference.
        timed_obs = TimedObservation(
            timestamp=time.time(),
            timestep=self._timestep,
            observation=raw_obs,
            must_go=True,
        )
        self._timestep += 1

        obs_iter = send_bytes_in_chunks(
            pickle.dumps(timed_obs),
            self._pb2.Observation,
            log_prefix="[EVAL] obs",
            silent=True,
        )
        self._stub.SendObservations(obs_iter, timeout=self._action_timeout_s)

        deadline = time.monotonic() + self._action_timeout_s
        while time.monotonic() < deadline:
            actions = self._stub.GetActions(self._pb2.Empty(), timeout=max(0.01, deadline - time.monotonic()))
            if len(actions.data) > 0:
                return pickle.loads(actions.data)  # nosec B301 - trusted server
        raise RuntimeError(
            f"Policy server returned no actions within {self._action_timeout_s}s"
        )

    def get_action(
        self, joint_positions: torch.Tensor, visual_obs: dict
    ) -> torch.Tensor:
        """Return the next sim action as a radians tensor.

        Queries the server only when the local buffer is empty (open-loop over
        the returned chunk), then pops one action per call.
        """
        if len(self._action_queue) == 0:
            timed_actions = self._query_action_chunk(joint_positions, visual_obs)
            for timed_action in timed_actions:
                raw = (
                    timed_action.get_action()
                    .detach()
                    .cpu()
                    .numpy()
                    .astype(np.float32)
                )
                sim_radians = self._iface.raw_to_sim_radians(raw)
                self._action_queue.append(
                    torch.from_numpy(sim_radians).to(self._iface.sim_device)
                )

        return self._action_queue.popleft()

    def close(self):
        """Close the gRPC channel."""
        if self._channel is not None:
            self._channel.close()
            self._channel = None
