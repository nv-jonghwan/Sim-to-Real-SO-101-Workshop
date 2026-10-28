# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import tempfile

import isaaclab.sim as sim_utils
import warp as wp
from isaaclab.assets import AssetBaseCfg, RigidObjectCfg
from isaaclab.envs.mdp import reset_root_state_uniform
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import CameraCfg
from isaaclab.utils.configclass import configclass
from isaaclab_tasks.utils.presets import MultiBackendRendererCfg
from sim_to_real_so101.mdp import (
    image,
    randomize_light_exposure,
)
from sim_to_real_so101.utils.ovrtx.renderer_cfg import SO101OVRTXRendererCfg

from .so101_env_cfg import (
    EventCfg,
    ObservationsCfg,
    SO101BaseSceneCfg,
    SO101TeleopEnvCfg,
)


# Both cameras share one OVRtx backend.
@configclass
class _CameraRendererCfg(MultiBackendRendererCfg):
    ovrtx_renderer: SO101OVRTXRendererCfg = SO101OVRTXRendererCfg(
        log_file_path=os.path.join(tempfile.gettempdir(), "ovrtx_cameras.log")
    )


_USD_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "assets",
        "usd",
    )
)
@configclass
class SO101TaskSceneCfg(SO101BaseSceneCfg):
    ground = None

    lightstudio = AssetBaseCfg(
        prim_path="{ENV_REGEX_NS}/LightStudio",
        spawn=sim_utils.UsdFileCfg(
            usd_path=os.path.join(_USD_DIR, "lightbox-backing-colliders.usda"),
        ),
        init_state=AssetBaseCfg.InitialStateCfg(pos=(-0.1, 0, 0.0257)),
    )

    mat = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Mat",
        spawn=sim_utils.UsdFileCfg(
            usd_path=os.path.join(_USD_DIR, "mat-thick-collision.usda"),
            rigid_props=[sim_utils.UsdPhysicsRigidBodyCfg(kinematic_enabled=True)],
        ),
        init_state=RigidObjectCfg.InitialStateCfg(
            pos=(0.22, 0, 0.032),
            rot=tuple(wp.quat_rpy(0.0, 0.0, wp.pi / 2.0)),
        ),
    )

    lightbox_light = AssetBaseCfg(
        prim_path="{ENV_REGEX_NS}/LightStudio/LightBox/RectLight"
    )

    # Wrist camera authored by the robot asset's Sensor=sensors variant.
    # The workshop USD layer supplies its mount and native OpenCV-fisheye lens.
    # This cfg binds the composed camera to Isaac Lab without respawning.
    camera_wrist: CameraCfg = CameraCfg(
        prim_path="{ENV_REGEX_NS}/Robot/gripper/wowrobo_2MP_camera",
        # 30 Hz to match the real SO-101 camera and control loop.
        update_period=1.0 / 30.0,
        height=480,
        width=640,
        data_types=["rgb"],
        update_latest_camera_pose=True,
        spawn=None,
        renderer_cfg=_CameraRendererCfg(),
    )

    camera_external: CameraCfg = CameraCfg(
        prim_path="{ENV_REGEX_NS}/ExternalStandaloneCamera",
        offset=CameraCfg.OffsetCfg(
            pos=(0.138, 0.330, 0.489),
            rot=(-0.0278, 0.3056, 0.9499, -0.0599),
            convention="opengl",
        ),
        # 30 Hz to match the real SO-101 camera and control loop.
        update_period=1.0 / 30.0,
        height=480,
        width=640,
        data_types=["rgb"],
        update_latest_camera_pose=True,
        spawn=sim_utils.PinholeCameraCfg(
            focal_length=2.5,
            horizontal_aperture=2.4,
            clipping_range=(0.01, 1.0e6),
        ),
        renderer_cfg=_CameraRendererCfg(),
    )


@configclass
class TaskEventCfg(EventCfg):
    reset_lightbox_light_exposure = EventTerm(
        func=randomize_light_exposure,
        mode="reset",
        params={
            "exposure_range": (1.0, 1.0),
            "asset_cfg": SceneEntityCfg("lightbox_light"),
        },
    )

    reset_mat_rotation = EventTerm(
        func=reset_root_state_uniform,
        mode="reset",
        params={
            "pose_range": {"yaw": (-0.1, 0.1)},
            "velocity_range": {},
            "asset_cfg": SceneEntityCfg("mat"),
        },
    )


@configclass
class TaskObservationsCfg(ObservationsCfg):
    @configclass
    class VisualCfg(ObsGroup):
        rgb_wrist = ObsTerm(
            func=image,
            params={
                "sensor_cfg": SceneEntityCfg("camera_wrist"),
                "data_type": "rgb",
                "normalize": False,
            },
        )

        rgb_external = ObsTerm(
            func=image,
            params={
                "sensor_cfg": SceneEntityCfg("camera_external"),
                "data_type": "rgb",
                "normalize": False,
            },
        )

        def __post_init__(self) -> None:
            self.enable_corruption = False
            self.concatenate_terms = False

    visual: VisualCfg = VisualCfg()


@configclass
class SO101TaskEnvCfg(SO101TeleopEnvCfg):
    scene: SO101TaskSceneCfg = SO101TaskSceneCfg()
    events: TaskEventCfg = TaskEventCfg()
    observations: TaskObservationsCfg = TaskObservationsCfg()

    def __post_init__(self) -> None:
        super().__post_init__()
        # Match control, rendering, and camera capture at 30 Hz while retaining
        # the 60 Hz physics rate.
        self.decimation = 2
        self.sim.render_interval = self.decimation
