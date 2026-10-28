# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import math
import os

import isaaclab.sim as sim_utils
import warp as wp
from isaaclab.assets import (
    ArticulationCfg,
    AssetBaseCfg,
    RigidObjectCfg,
    VisualMaterialCfg,
)
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.managers import TerminationTermCfg as DoneTerm
from isaaclab.sensors import ContactSensorCfg
from isaaclab.sim.spawners.materials import UsdPhysicsRigidBodyMaterialCfg
from isaaclab.utils.configclass import configclass
from isaaclab_newton.sim.schemas import MujocoCollisionCfg, NewtonSDFCollisionCfg
from isaaclab_newton.sim.spawners.materials import NewtonMaterialCfg
from sim_to_real_so101 import mdp
from sim_to_real_so101.assets.so101 import SO101_CONTACT_GRASP_CFG
from sim_to_real_so101.mdp.materials import randomize_task_materials
from sim_to_real_so101.mdp.vision import randomize_camera_blur

from .camera_profiles import BASE_CAMERA_RESPONSES, DR_CAMERA_RESPONSES
from .task_env_cfg import (
    SO101TaskEnvCfg,
    SO101TaskSceneCfg,
    TaskEventCfg,
    TaskObservationsCfg,
)

# Mat top is at z=35 mm, cap radius 17.7 mm; 0.06 leaves a 7.3 mm air gap so the
# SDF colliders spawn clear of the mat (spawn-time penetration is unrecoverable).
VIAL_SPAWN_Z = 0.06
VIAL_MASS_KG = 0.02

# Mat vial spawn distribution. `x`/`y` are the vial root in metres relative to
# the environment origin and cover the robot-side half of the mat; the rack sits
# in the +y corner and the reach/containment/clearance rejection tests in
# `mdp.reset_vials_rack` carve the unusable corners out of the box. `yaw` is the
# world heading of the cap, +/- 40 deg about the authored nominal, and `spin` is
# the free rotation about the vial's own long axis.
VIAL_POSE_RANGE = {
    "x": (0.13, 0.28),
    "y": (-0.20, 0.02),
    "yaw": (-0.6981, 0.6981),
    "spin": (-math.pi, math.pi),
}
# Mat footprint: 0.4572 x 0.3048 authored at yaw 90 deg and centred on
# (0.22, 0). The sampler tests the vial's bounding box against this, so the
# vial radius does not need to be inset here.
MAT_BOUNDS = {"x": (0.068, 0.372), "y": (-0.229, 0.229)}
# Horizontal distance from the robot root to the `sm_grasp` frame, bracketing
# the authored spawn grid's 0.300-0.416 m distances. Scripted collection applies
# its own conservative horizontal reach limit when choosing a target.
VIAL_GRASP_REACH_RANGE = (0.28, 0.42)


_ASSETS_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
)
_USD_DIR = os.path.join(_ASSETS_DIR, "usd")
_HDRI_DIR = os.path.join(_ASSETS_DIR, "hdri")

CONTACT_MATERIAL = [
    UsdPhysicsRigidBodyMaterialCfg(static_friction=0.7, dynamic_friction=0.7),
    NewtonMaterialCfg(
        contact_stiffness=1.57e5,
        contact_damping=1.12e3,
        rolling_friction=0.0005,
        torsional_friction=0.0005,
    ),
]
CONTACT_COLLISION = MujocoCollisionCfg(
    solimp=(0.7, 0.95, 0.0001, 0.5, 2.0)
)
# Vial contacts use a firm normal response instead of mixing with the robot's
# soft default. The 8 ms time constant exceeds two 1/360 s physics substeps.
# Priority also selects the vial material's sliding, torsional, and rolling friction.
VIAL_CONTACT_COLLISION = MujocoCollisionCfg(
    condim=6,
    priority=1,
    solref=(0.008, 1.0),
    solimp=(0.95, 0.99, 0.0001, 0.5, 2.0),
)


manipulation_object_base = RigidObjectCfg(
    prim_path="{ENV_REGEX_NS}/ManipulationObject",
    spawn=sim_utils.UsdFileCfg(
        usd_path="",
        physics_material=CONTACT_MATERIAL,
        collision_props=[CONTACT_COLLISION],
    ),
    init_state=RigidObjectCfg.InitialStateCfg(pos=(0.0, 0.0, 0.06)),
)

vial = manipulation_object_base.replace()
vial.spawn.usd_path = os.path.join(_USD_DIR, "Vial_three_primitive_collision.usda")
vial.spawn.physics_material = [
    UsdPhysicsRigidBodyMaterialCfg(static_friction=0.2, dynamic_friction=0.2),
    CONTACT_MATERIAL[1].copy(),
]
vial.spawn.collision_props = [VIAL_CONTACT_COLLISION]
vial.spawn.mass_props = [sim_utils.MassCfg(mass=VIAL_MASS_KG)]

rack = manipulation_object_base.replace()
rack.prim_path = "{ENV_REGEX_NS}/VialRack"
rack.spawn.usd_path = os.path.join(_USD_DIR, "Vial_rack_313g.usda")
rack.spawn.mesh_collision_props = [
    NewtonSDFCollisionCfg(
        sdf_max_resolution=128,
        sdf_narrow_band_inner=-0.003,
        sdf_narrow_band_outer=0.003,
        sdf_padding=0.003,
    ),
]


_TASK_SCENE = SO101TaskSceneCfg()


@configclass
class VialsToRackSceneCfg(SO101TaskSceneCfg):
    camera_wrist = _TASK_SCENE.camera_wrist.copy()
    camera_external = _TASK_SCENE.camera_external.copy()
    camera_wrist.renderer_cfg.ovrtx_renderer.camera_responses = BASE_CAMERA_RESPONSES
    camera_external.renderer_cfg.ovrtx_renderer.camera_responses = BASE_CAMERA_RESPONSES

    robot: ArticulationCfg = SO101_CONTACT_GRASP_CFG.replace(
        prim_path="{ENV_REGEX_NS}/Robot"
    )

    vial_1 = vial.replace()
    vial_1.prim_path = "{ENV_REGEX_NS}/Vial_1"
    vial_1.init_state.pos = (0.23, -0.08, VIAL_SPAWN_Z)
    vial_1.init_state.rot = tuple(wp.quat_rpy(0.0, wp.pi / 2.0, 0.0))

    vial_2 = vial.replace()
    vial_2.prim_path = "{ENV_REGEX_NS}/Vial_2"
    vial_2.init_state.pos = (0.23, 0.0, VIAL_SPAWN_Z)
    vial_2.init_state.rot = tuple(wp.quat_rpy(0.0, wp.pi / 2.0, 0.0))

    vial_3 = vial.replace()
    vial_3.prim_path = "{ENV_REGEX_NS}/Vial_3"
    vial_3.init_state.pos = (0.23, -0.16, VIAL_SPAWN_Z)
    vial_3.init_state.rot = tuple(wp.quat_rpy(0.0, wp.pi / 2.0, 0.0))

    rack_left = rack.replace()
    rack_left.prim_path = "{ENV_REGEX_NS}/Rack_Left"
    rack_left.init_state.pos = (0.18, 0.08, 0.06)
    rack_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/Rack_Left/Looks/OmniPBR",
        spawn=None,
        channels=("color", "roughness", "specular"),
    )

    wall_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/LightStudio/LightBox/Looks/PerceptionWall",
        spawn=None, channels=("color", "roughness", "specular"),
    )
    mat_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/Mat/Mat/Looks/PerceptionMat",
        spawn=None, channels=("color", "roughness", "specular"),
    )
    vial_1_body_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/Vial_1/Looks/PerceptionVialBody",
        spawn=None, channels=("color", "roughness", "specular"),
    )
    vial_1_cap_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/Vial_1/Looks/Vial_cap",
        spawn=None, channels=("color", "roughness", "specular"),
    )
    vial_2_body_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/Vial_2/Looks/PerceptionVialBody",
        spawn=None, channels=("color", "roughness", "specular"),
    )
    vial_2_cap_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/Vial_2/Looks/Vial_cap",
        spawn=None, channels=("color", "roughness", "specular"),
    )
    vial_3_body_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/Vial_3/Looks/PerceptionVialBody",
        spawn=None, channels=("color", "roughness", "specular"),
    )
    vial_3_cap_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/Vial_3/Looks/Vial_cap",
        spawn=None, channels=("color", "roughness", "specular"),
    )

    contact_grasp = ContactSensorCfg(
        prim_path="{ENV_REGEX_NS}/Robot/moving_jaw_so101_v1",
        update_period=0.0,
        history_length=1,
        debug_vis=False,
        filter_prim_paths_expr=[
            "{ENV_REGEX_NS}/Vial_1",
            "{ENV_REGEX_NS}/Vial_2",
            "{ENV_REGEX_NS}/Vial_3",
        ],
    )

    def __post_init__(self) -> None:
        for asset in (self.lightstudio, self.mat):
            asset.spawn.physics_material = CONTACT_MATERIAL
            asset.spawn.collision_props = [CONTACT_COLLISION]


_BASE_SCENE = VialsToRackSceneCfg()


@configclass
class VialsToRackDRSceneCfg(VialsToRackSceneCfg):
    """Domain-randomized scene with camera noise."""

    camera_wrist = _BASE_SCENE.camera_wrist.copy()
    camera_external = _BASE_SCENE.camera_external.copy()
    camera_wrist.renderer_cfg.ovrtx_renderer.camera_responses = DR_CAMERA_RESPONSES
    camera_external.renderer_cfg.ovrtx_renderer.camera_responses = DR_CAMERA_RESPONSES

    sky_light = AssetBaseCfg(
        prim_path="/World/sky_light",
        spawn=sim_utils.DomeLightCfg(
            intensity=1000.0,
            # Initial texture before reset-time HDRI domain randomization.
            texture_file=os.path.join(_HDRI_DIR, "moon_lab_1k.exr"),
            visible_in_primary_ray=False,
            enable_color_temperature=True,
            color_temperature=6500.0,
        ),
    )


@configclass
class VialsToRackExpandedDRSceneCfg(VialsToRackDRSceneCfg):
    """DR assets shared by the coordinated left, center, and right layouts."""


@configclass
class VialsToRackEventCfg(TaskEventCfg):
    reset_vials_setup = EventTerm(
        func=mdp.reset_vials_rack,
        mode="reset",
        params={
            "vials": ["vial_1", "vial_2", "vial_3"],
            "rack": "rack_left",
            "rack_pose_range": {
                "x": (-0.04, 0.04),
                "y": (-0.01, 0.01),
                "yaw": (-0.5, 0.5),
            },
            "vial_pose_range": VIAL_POSE_RANGE,
            "mat_bounds": MAT_BOUNDS,
            "vial_reach_range": VIAL_GRASP_REACH_RANGE,
            # Margin between bounding boxes; each box already carries its own
            # body radius.
            "clearance": 0.004,
            "fixed_vial_z": VIAL_SPAWN_Z,
        },
    )


@configclass
class VialsToRackEventDRCfg(VialsToRackEventCfg):
    reset_robot_base_tilt = EventTerm(
        func=mdp.randomize_robot_base_tilt,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg("robot"),
            "tilt_degrees": (-3.0, 6.0),
        },
    )

    reset_external_camera = EventTerm(
        func=mdp.randomize_external_camera,
        mode="reset",
        params={
            "camera_cfg": SceneEntityCfg("camera_external"),
            "tilt_degrees": (-5.0, 5.0),
            "focal_length_scale": (0.97, 1.0),
        },
    )

    reset_task_materials = EventTerm(
        func=randomize_task_materials,
        mode="reset",
        params={},
    )

    reset_lightbox_light_exposure = EventTerm(
        func=mdp.randomize_light_exposure,
        mode="reset",
        params={
            "exposure_range": (1.5, 2.25),
            "asset_cfg": SceneEntityCfg("lightbox_light"),
        },
    )

    reset_sky_light = EventTerm(
        func=mdp.randomize_sky_light,
        mode="reset",
        params={
            "exposure_range": (-5.5, -4.5),
            "temperature_range": (4500.0, 7000.0),
            "textures_root": _HDRI_DIR,
            "asset_cfg": SceneEntityCfg("sky_light"),
        },
    )

    # Wider DR range than the base task (±0.3 rad vs ±0.1).
    reset_mat_rotation = EventTerm(
        func=mdp.reset_root_state_uniform,
        mode="reset",
        params={
            "pose_range": {"yaw": (-0.3, 0.3)},
            "velocity_range": {},
            "asset_cfg": SceneEntityCfg("mat"),
        },
    )

    reset_wrist_blur = EventTerm(
        func=randomize_camera_blur, mode="reset",
        params={"sensor_cfg": SceneEntityCfg("camera_wrist"), "sigma_range": (0.7, 1.1)},
    )


# Scaling each horizontal span by sqrt(1.2) enlarges its sampling area by 20%.
_EXPANDED_POSITION_SCALE = math.sqrt(1.2)
_EXPANDED_VIAL_POSE_RANGE = dict(VIAL_POSE_RANGE)
for _axis in ("x", "y"):
    _lo, _hi = VIAL_POSE_RANGE[_axis]
    _center = (_lo + _hi) / 2
    _half_span = (_hi - _lo) / 2 * _EXPANDED_POSITION_SCALE
    _EXPANDED_VIAL_POSE_RANGE[_axis] = (_center - _half_span, _center + _half_span)


@configclass
class VialsToRackEventExpandedDRCfg(VialsToRackEventDRCfg):
    """Sample wider rack/vial regions with a reachable grasp and insertion slot."""

    reset_vials_setup = VialsToRackEventDRCfg().reset_vials_setup.copy()
    reset_vials_setup.params.update(
        rack_centers=((0.27, 0.14), (0.29, 0.0), (0.27, -0.14)),
        rack_min_center_distance=0.33,
        rack_pose_range={
            "x": (-0.04 * _EXPANDED_POSITION_SCALE, 0.04 * _EXPANDED_POSITION_SCALE),
            "y": (-0.01 * _EXPANDED_POSITION_SCALE, 0.01 * _EXPANDED_POSITION_SCALE),
            "yaw": (-0.5, 0.5),
        },
        vial_pose_range=_EXPANDED_VIAL_POSE_RANGE,
    )


@configclass
class VialsToRackObservationsCfg(TaskObservationsCfg):
    """Per-subtask eval observations (grasp + placement tracking)."""

    @configclass
    class SubtaskCfg(ObsGroup):
        vial_grasped = ObsTerm(
            func=mdp.any_vial_grasped,
            params={
                "contact_sensor_cfg": SceneEntityCfg("contact_grasp"),
                "vials": ["vial_1", "vial_2", "vial_3"],
                "min_height": 0.055,
                "warmup_steps": 30,
                "force_threshold": 2,  # N
            },
        )

        vial_placed = ObsTerm(
            func=mdp.vial_placed_on_rack,
            params={
                "contact_sensor_cfg": SceneEntityCfg("contact_grasp"),
                "vials": ["vial_1", "vial_2", "vial_3"],
                "rack_name": "rack_left",
                "warmup_steps": 30,
                "grasp_history_window": 20,
                "force_threshold": 2,  # N
                "rack_local_x_min": 0.0,
                "rack_local_x_max": 0.12,
                "rack_local_y_min": 0.0,
                "rack_local_y_max": 0.12,
                "rack_local_z_max": 0.1,
                "vertical_threshold": 0.7,
            },
        )

        def __post_init__(self) -> None:
            self.enable_corruption = False
            self.concatenate_terms = False

    subtask_terms: SubtaskCfg = SubtaskCfg()


@configclass
class VialsToRackSafetyTerminationsCfg:
    """Reject invalid layouts and reset before escaped objects destabilize simulation."""

    invalid_vial_layout = DoneTerm(func=mdp.vial_layout_sampling_failed)

    unsafe_rack_state = DoneTerm(
        func=mdp.rack_state_is_unsafe,
        time_out=False,
        params={
            "asset_cfg": SceneEntityCfg("rack_left"),
            "max_linear_speed": 2.0,
            "max_angular_speed": 15.0,
            # Environment-local containment bounds cover the complete lightbox
            # and reset before a rack can fall indefinitely outside the scene.
            "position_lower": (-0.15, -0.42, 0.0),
            "position_upper": (0.43, 0.42, 0.65),
        },
    )

    escaped_vial = DoneTerm(
        func=mdp.any_vial_outside_radius,
        time_out=False,
        params={
            "vials": ["vial_1", "vial_2", "vial_3"],
            "max_distance": 1.0,
        },
    )


@configclass
class VialsToRackTerminationsCfg(VialsToRackSafetyTerminationsCfg):
    """Safety, horizon, and success terms for the eval task."""

    time_out = DoneTerm(
        func=mdp.time_out,
        time_out=True,
    )

    success = DoneTerm(
        func=mdp.vial_placed_on_rack_termination,
        time_out=False,
        params={
            "contact_sensor_cfg": SceneEntityCfg("contact_grasp"),
            "vials": ["vial_1", "vial_2", "vial_3"],
            "rack_name": "rack_left",
            "warmup_steps": 30,
            "grasp_history_window": 20,
            "force_threshold": 2,  # N
            "rack_local_x_min": 0.0,
            "rack_local_x_max": 0.12,
            "rack_local_y_min": 0.0,
            "rack_local_y_max": 0.12,
            "rack_local_z_max": 0.1,
            "vertical_threshold": 0.7,
        },
    )


@configclass
class VialsToRackEnvCfg(SO101TaskEnvCfg):
    scene: VialsToRackSceneCfg = VialsToRackSceneCfg()
    events: VialsToRackEventCfg = VialsToRackEventCfg()
    observations: VialsToRackObservationsCfg = VialsToRackObservationsCfg()
    terminations: VialsToRackSafetyTerminationsCfg = (
        VialsToRackSafetyTerminationsCfg()
    )


@configclass
class VialsToRackDREnvCfg(VialsToRackEnvCfg):
    scene: VialsToRackDRSceneCfg = VialsToRackDRSceneCfg()
    events: VialsToRackEventDRCfg = VialsToRackEventDRCfg()


@configclass
class VialsToRackEvalEnvCfg(VialsToRackEnvCfg):
    terminations: VialsToRackTerminationsCfg = VialsToRackTerminationsCfg()

    def __post_init__(self) -> None:
        super().__post_init__()
        self.episode_length_s = 550 / 30.0


@configclass
class VialsToRackEvalDREnvCfg(VialsToRackDREnvCfg):
    terminations: VialsToRackTerminationsCfg = VialsToRackTerminationsCfg()

    def __post_init__(self) -> None:
        super().__post_init__()
        self.episode_length_s = 550 / 30.0


@configclass
class VialsToRackExpandedDREnvCfg(VialsToRackDREnvCfg):
    scene: VialsToRackExpandedDRSceneCfg = VialsToRackExpandedDRSceneCfg()
    events: VialsToRackEventExpandedDRCfg = VialsToRackEventExpandedDRCfg()


@configclass
class VialsToRackEvalExpandedDREnvCfg(VialsToRackEvalDREnvCfg):
    scene: VialsToRackExpandedDRSceneCfg = VialsToRackExpandedDRSceneCfg()
    events: VialsToRackEventExpandedDRCfg = VialsToRackEventExpandedDRCfg()
