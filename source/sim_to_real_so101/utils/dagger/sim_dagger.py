# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""DAgger collection with explicit pause, alignment, guidance and policy handback."""

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch
from sim_to_real_so101.utils.sim_observations import refresh_reset_visuals


class AsyncDaggerPolicy:
    """Serialize policy RPCs off the simulation thread and reject stale results."""

    def __init__(self, policy):
        self.policy = policy
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dagger-policy")
        self.future = None
        self.epoch = 0
        self.request_epoch = 0
        self.needs_reset = True

    def invalidate(self):
        self.epoch += 1
        self.needs_reset = True

    def request(self, obs):
        if self.future is not None and self.future.done() and self.request_epoch != self.epoch:
            self.future = None
        if self.future is not None:
            return
        state = obs["policy"]["joint_pos_obs"][0].clone()
        images = {key: value.clone() for key, value in obs["visual"].items()}
        reset = self.needs_reset
        self.needs_reset = False
        self.request_epoch = self.epoch
        self.future = self.executor.submit(self._query, state, images, reset)

    def _query(self, state, images, reset):
        if reset:
            self.policy.reset()
        return self.policy.get_action(state, images)

    def take(self):
        if self.future is None or not self.future.done():
            return None
        future, self.future = self.future, None
        if self.request_epoch != self.epoch:
            return None
        return future.result()

    def close(self):
        self.policy.close()
        self.executor.shutdown(wait=False, cancel_futures=True)


class SimDAgger:
    """One environment with explicit, feedback-verified transfers of control."""

    def __init__(self, env, iface, policy, recorder, active_cameras, leader, leader_follows=False):
        self.env, self.iface, self.recorder = env, iface, recorder
        self.policy = AsyncDaggerPolicy(policy)
        self.leader = leader
        self.leader_follows = leader_follows
        self.active_cameras = active_cameras
        self.phase = "paused"
        self.message = "Leader held. Space: policy; Tab: prepare correction."
        self.running = True
        self.assisted = False
        self.obs = None
        self.action = None
        self.last_outcome = None
        self._after_move = "paused"
        self._guide_anchor = None
        self._sim_anchor = None
        self._release_on_close = False
        self._closed = False
        # Called on every phase change, so the browser learns the phase before
        # a blocking real-follower reset runs.
        self.on_phase = None

    def _state_raw(self):
        return self.iface.sim_radians_to_raw(self.obs["policy"]["joint_pos_obs"][0].detach().cpu().numpy().copy())

    def _phase(self, phase, message):
        if self.last_outcome:
            message += f" Last episode: {self.last_outcome}."
        self.phase, self.message = phase, message
        print(f"[DAGGER]: {phase}: {message}", flush=True)
        if self.on_phase is not None:
            self.on_phase()

    def _leader_target(self, raw=None):
        target = self._state_raw() if raw is None else np.array(raw, dtype=np.float64)
        if -2 <= target[5] <= 102:
            # Contact can produce small gripper-limit overshoots; the leader
            # stays within its calibrated percentage range.
            target[5] = np.clip(target[5], 0, 100)
        return target

    def _track(self, raw):
        self.leader.renew()
        self.leader.follow(self._leader_target(raw))

    def _move(self, phase, after):
        self.leader.move_to(self._leader_target())
        self._after_move = after
        self._phase(phase, "Powered leader movement; X holds immediately. Physics frozen.")

    def reset(self):
        """Reset the environment, move the leader to the new start pose, then pause."""
        if self.obs is not None:
            self.last_outcome = "manual reset"
        self.leader.hold()
        self.policy.invalidate()
        self.recorder.cancel_recording()
        self._phase("resetting", "Moving to the start pose; keys take effect when it finishes.")
        # A real follower resets along blocking waypoints; the leader tracks them.
        self.obs, _ = self.env.reset(options={"on_move": self._track})
        self._finish_reset()

    def _finish_reset(self):
        self.assisted = False
        refresh_reset_visuals(self.env, self.obs, self.active_cameras)
        self.action = self.obs["policy"]["joint_pos_obs"][0].clone()
        self.policy.invalidate()
        self._move("resetting", "paused")

    def _hold_correction(self):
        self.leader.hold()
        self._after_move = "correction_ready"
        self._phase("holding", "Holding leader; correction retained. Physics frozen.")

    def report_fault(self, error):
        self.policy.invalidate()
        self.leader.hold()
        self.recorder.cancel_recording()
        self._phase("fault", f"{error} Physics frozen. X acknowledges/holds; R resets; Escape exits.")

    def handle(self, command):
        """Accept one operator action; movement completion is serviced by advance()."""
        if not self.running:
            return
        if command == "stop_session":
            self.running = False
            self.policy.invalidate()
            self.leader.hold()
            return
        if command == "release_exit":
            self._release_on_close = True
            self.running = False
            self.leader.hold()
            return
        if command == "control_lost":
            if self.phase not in {"paused", "fault", "holding", "correction_ready"}:
                self.handle("hold_position")
                self.message = "Browser disconnected/unfocused. Held once; resume deliberately."
            return
        if command == "hold_position":
            self.policy.invalidate()
            if self.phase in {"correcting", "guide_starting", "correction_ready", "resuming"}:
                self._hold_correction()
            else:
                self.leader.hold()
                self._after_move = "paused"
                self._phase("holding", "Holding leader. Physics frozen.")
            return
        if command == "reset_world":
            if self.phase != "resetting":
                self.reset()
            return
        if self.phase in {"aligning", "resetting", "holding", "resuming", "fault"}:
            return
        if command == "pause_resume":
            if self.phase == "autonomous":
                self.policy.invalidate()
                if self.leader_follows:
                    self.leader.hold()
                self._phase("paused", "Policy paused; leader stays put. Space resumes; Tab aligns for correction.")
            elif self.phase in {"correcting", "guide_starting", "correction_ready"}:
                self.policy.invalidate()
                self.leader.hold()
                self._phase("resuming", "Holding leader, saving correction, then resuming fresh policy inference.")
            elif self.phase == "paused" and self.leader.snapshot()["mode"] == "holding":
                self.policy.invalidate()
                self._phase("autonomous", "Policy running; leader held. Space pauses.")
        elif command == "toggle_correction":
            if self.phase == "paused":
                self.policy.invalidate()
                self._move("aligning", "correction_ready")
            elif self.phase == "autonomous":
                self.message = "Press Space to pause before Tab alignment."
        elif command == "guide_start" and self.phase == "correction_ready":
            self.leader.guide()
            self._phase("guide_starting", "Guidance requested. Support the leader; Space hands back to policy.")
        elif command == "cancel_episode" and self.phase in {"correction_ready", "guide_starting", "correcting"}:
            self.leader.hold()
            self.recorder.cancel_recording()
            self._after_move = "paused"
            self._phase("holding", "Correction discarded; holding leader.")

    def advance(self, poll_controls):
        """Service completion without blocking on serial motion or inference."""
        if not self.running:
            return
        self.leader.renew()
        try:
            self._advance(poll_controls)
        except Exception as exc:  # noqa: BLE001 - hold and report failures at the control boundary
            self.report_fault(exc)

    def _advance(self, poll_controls):
        leader = self.leader.snapshot()
        if leader["error"] and self.phase != "fault":
            raise RuntimeError(leader["error"])
        saving = self.recorder.saving_status()
        if saving.get("error") and self.phase != "fault":
            raise RuntimeError(f"Dataset save failed: {saving['error']}")
        if self.phase in {"aligning", "resetting", "holding"}:
            if leader["mode"] == "holding":
                if self._after_move == "correction_ready":
                    self._phase("correction_ready", "Leader aligned and held. Support it, press G once. Space resumes policy.")
                else:
                    self._phase("paused", "Leader held. Space: policy; Tab: align for correction.")
            return
        if self.phase == "resuming":
            if leader["mode"] == "holding":
                self.recorder.save_episode()
                self.policy.invalidate()
                self._phase("autonomous", "Correction accepted. Policy running from corrected state; Space pauses.")
            return
        if self.phase == "guide_starting":
            if leader["mode"] == "guiding":
                self._guide_anchor = leader["position"].copy()
                # Preserve the existing actuator target, including tracking lag.
                # Replacing it with measured joints at takeover can cause sag.
                self._sim_anchor = self.iface.sim_radians_to_raw(self.action.detach().cpu().numpy().copy())
                self.assisted = True
                self._phase("correcting", "Human correction recording. Space saves and resumes policy; X pauses and holds.")
            return
        if self.phase not in {"autonomous", "correcting"}:
            return
        if self.phase == "autonomous":
            self.policy.request(self.obs)
            action = self.policy.take()
            if action is None:
                return
            for command in poll_controls():
                self.handle(command)
            if self.phase != "autonomous" or not self.running:
                return
            capture = None
        else:
            if leader["mode"] != "guiding":
                raise RuntimeError("Manual-control lease ended")
            desired = self._sim_anchor + leader["position"] - self._guide_anchor
            previous = self.iface.sim_radians_to_raw(self.action.detach().cpu().numpy().copy())
            # Limit discontinuities at guidance boundaries and rapid manual motion.
            maximum = np.array([60] * 5 + [100]) * self.env.unwrapped.step_dt
            raw = previous + np.clip(desired - previous, -maximum, maximum)
            raw[5] = np.clip(raw[5], 0, 100)
            action = torch.as_tensor(self.iface.raw_to_sim_radians(raw), device=self.env.unwrapped.device, dtype=torch.float32)
            capture = raw.copy(), self._state_raw(), {
                name: self.obs["visual"][f"rgb_{name}"][0] for name in self.recorder.cameras
            }
        if action.shape != (6,) or not torch.isfinite(action).all():
            raise ValueError("Expected six finite SO101 action values")
        if capture is not None:
            self.recorder.push_frame_to_buffer(*capture)
        self.action = action.clone()
        self.obs, _, terminated, truncated, _ = self.env.step(action.unsqueeze(0))
        if bool((terminated[0] | truncated[0]).item()):
            self.leader.hold()
            manager = self.env.unwrapped.termination_manager
            terms = {name: bool(manager.get_term(name)[0].item()) for name in manager.active_terms}
            unsafe = terms.get("unsafe_rack_state", False) or terms.get("escaped_vial", False)
            success = terms.get("success", False) and not unsafe and not bool(truncated[0].item())
            self.last_outcome = "success" if success else ", ".join(name for name, active in terms.items() if active)
            if bool(truncated[0].item()):
                self.last_outcome = "timeout"
            if self.phase == "correcting":
                if success:
                    self.recorder.save_episode()
                else:
                    self.recorder.cancel_recording()
            print(f"[DAGGER]: Episode ended: assisted={self.assisted}, success={success}, terms={terms}", flush=True)
            self._finish_reset()
        elif self.phase == "autonomous":
            if self.leader_follows:
                self.leader.follow(self._leader_target())
            self.policy.request(self.obs)

    def stop(self):
        """Return to physical rest and close held; explicit supported release skips return."""
        if self._closed:
            return
        self._closed = True
        self.running = False
        parked = False
        if not self._release_on_close:
            print("[DAGGER]: Exiting: returning leader to saved physical rest pose.", flush=True)
            try:
                parked = self.leader.park()
            except KeyboardInterrupt:
                print("[DAGGER]: Return interrupted; holding in place. Rest NOT reached.", flush=True)
                self.leader.hold()
            except Exception as exc:  # noqa: BLE001 - hardware cleanup must still run
                print(f"[DAGGER]: Rest return failed: {exc}. Support the arm.", flush=True)
        confirmed = self.leader.close(release=self._release_on_close)
        if parked:
            print("[DAGGER]: Physical rest pose reached and verified.", flush=True)
        elif not self._release_on_close:
            print("[DAGGER]: Rest NOT confirmed. Support the arm before switching power off.", flush=True)
        self.policy.close()
        self.recorder.cancel_recording()
        if not confirmed:
            print("[DAGGER]: Motor state could not be confirmed. Support the arm and inspect power/serial.", flush=True)
        else:
            print("[DAGGER]: Motors released by request." if self._release_on_close else
                  "[DAGGER]: Exited with motor torque ON. Support the arm before switching power off.", flush=True)
