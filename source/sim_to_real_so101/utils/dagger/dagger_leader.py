# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Single-owner SO101 serial control with a lease for motion and manual guiding."""

import hashlib
import json
import threading
import time

import numpy as np

# Per-joint limits: arm joints in degrees, gripper in percent. A torque-held
# leader settles a few degrees short of its goal under gravity.
_RATE = np.array([30.0] * 5 + [50.0])  # per second
_SETTLED = np.array([8.0] * 5 + [5.0])
_DRIFT = np.array([5.0] * 5 + [10.0])


class DaggerLeader:
    """Hold by default; only a live control loop may move or release the leader.

    All serial access runs on one worker. A missed 0.5-second lease holds the
    measured pose even when simulation/rendering is blocked. This requires
    working serial communication and powered motors; it is not a hardware stop.
    """

    def __init__(self, teleop, joint_order, rest_pose=None):
        self.teleop = teleop
        self.joint_order = joint_order
        self._lock = threading.Lock()
        self._command = ("hold", None)
        self._deadline = 0.0
        self._closing = threading.Event()
        self._release_on_close = False
        self._thread = None
        self._mode = "pending"
        self._position = None
        self.rest_pose = None if rest_pose is None else self.validate(rest_pose)
        self._error = None
        self._target = None
        self._goal = None
        self._move_deadline = 0.0
        self._last_tick = None
        self._settled = 0
        self._hold_target = None
        self._commanded = None
        self._torque_on = False
        self._drift_samples = 0
        self._shutdown_error = None
        self._published = {"mode": "pending", "position": None, "error": None, "updated_at": time.monotonic()}

    @staticmethod
    def validate(position):
        position = np.asarray(position, dtype=np.float64)
        if position.shape != (6,) or not np.isfinite(position).all():
            raise ValueError("Expected six finite leader joint values.")
        if not 0 <= position[5] <= 100:
            raise ValueError("Leader target gripper must be in the 0–100 range.")
        return position.copy()

    def start(self):
        self._thread = threading.Thread(target=self._run, name="dagger-leader", daemon=True)
        self._thread.start()

    def snapshot(self):
        with self._lock:
            state = self._published.copy()
            if state["position"] is not None:
                state["position"] = state["position"].copy()
            if time.monotonic() - state["updated_at"] > 0.5:
                state["error"] = "Leader feedback is stale; serial worker may be blocked. Support the arm."
            return state

    def renew(self):
        with self._lock:
            self._deadline = time.monotonic() + 0.5

    def _request(self, mode, target=None):
        with self._lock:
            self._command = (mode, target)
            self._published = {**self._published, "mode": "pending"}
            self._deadline = time.monotonic() + 0.5

    def move_to(self, target):
        self._request("move", self.validate(target))

    def follow(self, target):
        """Track ``target`` at the powered move speed; later calls only retarget."""
        self._request("follow", self.validate(target))

    def guide(self):
        self._request("guide")

    def hold(self):
        self._request("hold")

    def _read(self):
        # Tolerate a lost status packet; a dead or browned-out bus still fails.
        for attempt in range(3):
            try:
                values = self.teleop.get_action()
                break
            except ConnectionError:
                if attempt == 2:
                    raise
        position = np.array([values[name] for name in self.joint_order], dtype=np.float64)
        if not np.isfinite(position).all():
            raise ValueError("Non-finite leader feedback.")
        return position

    def _send(self, position):
        self.teleop.send_feedback(dict(zip(self.joint_order, position.tolist(), strict=True)))
        self._commanded = position.copy()

    def _hold(self):
        self._position = self._read()
        # Seed the goal before enabling torque: an old goal must never pull the arm
        # across the workspace. A torqued arm keeps its goal so it does not sag again.
        goal = self._position
        if self._torque_on and np.all(np.abs(self._commanded - self._position) <= _SETTLED):
            goal = self._commanded
        self._send(goal)
        self.teleop.enable_torque()
        self._torque_on = True
        self._hold_target = self._position.copy()
        self._drift_samples = 0
        self._mode = "holding"

    def tick(self, now):
        """Service one serial cycle; callable without a thread in hardware-free tests."""
        with self._lock:
            command, self._command = self._command, None
            deadline = self._deadline
        dt = min(max(now - self._last_tick, 0.0), 0.05) if self._last_tick is not None else 0.0
        self._last_tick = now
        try:
            if command is not None and command[0] == "follow" and self._mode == "following":
                self._target = command[1]
            elif command is not None:
                mode, target = command
                self._error = None
                self._hold()
                if mode == "follow":
                    self._target = target
                    self._goal = self._commanded.copy()
                    self._mode = "following"
                elif mode == "move":
                    self._target = target
                    self._goal = self._position.copy()
                    travel = np.max(np.abs(target - self._position) / _RATE)
                    self._move_deadline = now + max(2.0, float(travel)) + 3.0
                    self._settled = 0
                    self._mode = "moving"
                elif mode == "guide":
                    self.teleop.disable_torque()
                    self._torque_on = False
                    self._mode = "guiding"
            if self._mode in {"moving", "following", "guiding"} and now > deadline:
                raise TimeoutError("Leader control heartbeat expired; holding. Press X to acknowledge or R to reset.")
            if self._mode in {"moving", "following"}:
                self._goal += np.clip(self._target - self._goal, -_RATE * dt, _RATE * dt)
                self._send(self._goal)
                self._position = self._read()
            if self._mode == "moving":
                close = np.all(np.abs(self._position - self._target) <= _SETTLED)
                self._settled = self._settled + 1 if close and np.allclose(self._goal, self._target) else 0
                if self._settled >= 3:
                    self._mode = "holding"
                    self._hold_target = self._position.copy()
                    self._drift_samples = 0
                elif now > self._move_deadline:
                    error = np.round(self._position - self._target, 2).tolist()
                    raise TimeoutError(f"Leader alignment timed out; joint errors (deg, gripper %): {error}. Check obstruction/calibration.")
            elif self._mode == "guiding":
                self._position = self._read()
            elif self._mode == "holding":
                self._position = self._read()
                drift = np.any(np.abs(self._position - self._hold_target) > _DRIFT)
                self._drift_samples = self._drift_samples + 1 if drift else 0
                if self._drift_samples >= 3:
                    raise RuntimeError("Leader drifted while torque-held; check load, motor power and calibration.")
        except Exception as exc:  # noqa: BLE001 - hold and report failures at the control boundary
            self._error = str(exc)
            try:
                self._hold()
            except Exception as hold_error:  # noqa: BLE001 - report lost hardware support
                self._error += f"; unable to hold: {hold_error}. Support the arm; check power/serial."
            self._mode = "fault"
            print(f"[DAGGER][LEADER FAULT]: {self._error}", flush=True)
        with self._lock:
            # A command arriving during serial IO must not look completed.
            mode = self._mode if self._command is None else "pending"
            self._published = {"mode": mode, "position": self._position, "error": self._error,
                               "updated_at": time.monotonic()}

    def park(self):
        """Return to the taught rest pose independently of simulation and browser IO."""
        if self.rest_pose is None:
            print("[DAGGER]: No taught physical rest pose; holding in place.", flush=True)
            return False
        if self.snapshot()["error"]:
            print("[DAGGER]: Leader feedback/fault prevents automatic rest return.", flush=True)
            return False
        self.move_to(self.rest_pose)
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            self.renew()
            state = self.snapshot()
            if state["error"]:
                self.hold()
                return False
            if state["mode"] == "holding":
                return bool(np.all(np.abs(state["position"] - self.rest_pose) <= _SETTLED))
            time.sleep(1 / 30)
        self.hold()
        return False

    def _run(self):
        try:
            while not self._closing.is_set():
                self.tick(time.monotonic())
                self._closing.wait(1 / 30)
        finally:
            self._shutdown()

    def _shutdown(self):
        try:
            if self._release_on_close:
                self.teleop.disable_torque()
            else:
                self._hold()
        except Exception as exc:  # noqa: BLE001 - hold and report failures at the control boundary
            self._shutdown_error = str(exc)
            print(f"[DAGGER]: Leader shutdown could not confirm support: {exc}. Support the arm.", flush=True)
        finally:
            # SOLeader.disconnect() disables torque unconditionally.
            try:
                self.teleop.bus.disconnect(disable_torque=False)
            except Exception as exc:  # noqa: BLE001 - report cleanup failures without releasing torque
                self._shutdown_error = str(exc)
                print(f"[DAGGER]: Unable to close leader serial connection: {exc}", flush=True)

    def close(self, *, release=False):
        """Close serial while holding, unless the operator explicitly requests release."""
        if self._closing.is_set():
            return self._shutdown_error is None
        self._release_on_close = release
        self._closing.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            if self._thread.is_alive():
                self._shutdown_error = "Serial worker unresponsive"
                print("[DAGGER]: Serial worker is unresponsive; motor support cannot be confirmed. Support the arm.")
        else:
            self._shutdown()
        return self._shutdown_error is None


def physical_rest_pose(teleop, joint_order, *, measured=None):
    """Load or deliberately teach a physical rest pose bound to this calibration."""
    calibration = teleop.calibration_fpath
    path = calibration.with_suffix(".dagger-rest.json")
    identity = {
        "robot_id": teleop.id,
        "calibration_sha256": hashlib.sha256(calibration.read_bytes()).hexdigest(),
        "joint_order": list(joint_order),
    }
    if measured is not None:
        position = DaggerLeader.validate(measured)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({**identity, "position": position.tolist()}, indent=2) + "\n")
        temporary.replace(path)
        print(f"[DAGGER]: Physical rest pose saved: {path}", flush=True)
        return position
    if not path.is_file():
        raise ValueError("Teach physical rest first: support/place the leader at rest, then run lerobot_dagger --teach-rest.")
    saved = json.loads(path.read_text())
    if any(saved.get(key) != value for key, value in identity.items()):
        raise ValueError("Saved rest pose does not match leader calibration. Re-teach with lerobot_dagger --teach-rest.")
    return DaggerLeader.validate(saved["position"])
