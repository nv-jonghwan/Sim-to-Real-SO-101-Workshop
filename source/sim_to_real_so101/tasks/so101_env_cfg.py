# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import isaaclab.sim as sim_utils
from isaaclab.assets import ArticulationCfg, AssetBaseCfg, VisualMaterialCfg
from isaaclab.envs import ManagerBasedRLEnvCfg
from isaaclab.managers import EventTermCfg as EventTerm
from isaaclab.managers import ObservationGroupCfg as ObsGroup
from isaaclab.managers import ObservationTermCfg as ObsTerm
from isaaclab.managers import SceneEntityCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sensors import FrameTransformerCfg
from isaaclab.utils.configclass import configclass
from isaaclab.visualizers import VisualizerCfg
from isaaclab_newton.physics import (
    MJWarpSolverCfg,
    NewtonCfg,
    NewtonCollisionPipelineCfg,
)
from isaaclab_tasks.utils import PresetCfg
from sim_to_real_so101.assets.so101 import SO101_CFG, SO101_JOINT_NAMES
from sim_to_real_so101.mdp import (
    GripperProtectionTerm,
    JointPositionActionCfg,
    ee_frame_state,
    joint_pos,
    joint_pos_rel,
    randomize_visual_material,
    reset_joints_by_offset,
)


# Tutorial solver settings tested with the workshop rack SDF and primitive vial.
@configclass
class SO101PhysicsCfg(PresetCfg):
    newton: NewtonCfg = NewtonCfg(
        solver_cfg=MJWarpSolverCfg(
            solver="newton",
            njmax=1024,
            nconmax=1024,
            # Harder tangential constraints suppress creep during a loaded grasp.
            cone="elliptic",
            impratio=10.0,
            tolerance=1e-10,
            update_data_interval=2,
            iterations=100,
            ls_iterations=50,
            integrator="implicitfast",
            use_mujoco_contacts=False,
        ),
        collision_cfg=NewtonCollisionPipelineCfg(),
        # SAH avoids the reproduced cuBQL mesh-overlap CUDA fault in the pinned runtime.
        bvh_constructor_geometry="sah",
        num_substeps=6,
        debug_mode=False,
    )
    # Newton is both the implicit default and the explicit `presets=newton`
    # selection.
    default = newton


@configclass
class SO101BaseSceneCfg(InteractiveSceneCfg):

    env_spacing = 1.0
    num_envs = 1

    ground = AssetBaseCfg(
        prim_path="/World/ground",
        spawn=sim_utils.GroundPlaneCfg(
            size=(2.0, 2.0),
            physics_material=sim_utils.RigidBodyMaterialCfg(
                static_friction=0.5,
                dynamic_friction=0.5,
            ),
        ),
    )

    robot: ArticulationCfg = SO101_CFG.replace(prim_path="{ENV_REGEX_NS}/Robot")

    # Randomize printed materials; preserve the authored motor material.
    robot_printed_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/Robot/Looks/material_a_d_printed",
        spawn=None,
        channels=("color",),
    )
    robot_sensor_printed_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/Robot/Looks/material_a_3d_printed",
        spawn=None,
        channels=("color",),
    )
    robot_motor_material = VisualMaterialCfg(
        prim_path="{ENV_REGEX_NS}/Robot/Looks/material_sts3215",
        spawn=None,
        channels=("color",),
    )

    ee_frame: FrameTransformerCfg = FrameTransformerCfg(
        prim_path="{ENV_REGEX_NS}/Robot/base",
        debug_vis=False,
        target_frames=[
            FrameTransformerCfg.FrameCfg(
                prim_path="{ENV_REGEX_NS}/Robot/gripper",
                name="gripper",
            ),
        ],
    )


@configclass
class ActionsCfg:
    joint_positions = JointPositionActionCfg(
        asset_name="robot",
        joint_names=SO101_JOINT_NAMES,
        scale=1,
        use_default_offset=False,
    )


@configclass
class ObservationsCfg:

    @configclass
    class PolicyCfg(ObsGroup):
        joint_pos_obs = ObsTerm(
            func=joint_pos,
            params={
                "asset_cfg": SceneEntityCfg(
                    "robot",
                    joint_names=SO101_JOINT_NAMES,
                )
            },
        )

        joint_pos_rel = ObsTerm(
            func=joint_pos_rel,
            params={
                "asset_cfg": SceneEntityCfg(
                    "robot",
                    joint_names=SO101_JOINT_NAMES,
                )
            },
        )
        ee_frame_state = ObsTerm(
            func=ee_frame_state,
            params={
                "ee_frame_cfg": SceneEntityCfg("ee_frame"),
                "robot_cfg": SceneEntityCfg("robot"),
            },
        )

        def __post_init__(self) -> None:
            self.enable_corruption = True
            self.concatenate_terms = False

    policy: PolicyCfg = PolicyCfg()


@configclass
class EventCfg:
    gripper_protection = EventTerm(func=GripperProtectionTerm, mode="startup")

    reset_robot_position = EventTerm(
        func=reset_joints_by_offset,
        mode="reset",
        params={
            "asset_cfg": SceneEntityCfg(
                "robot",
                joint_names=SO101_JOINT_NAMES,
            ),
            "position_range": (0, 0),
            "velocity_range": (0, 0),
        },
    )

    # Base task uses a single colour (no robot-colour DR); the DR variant
    # overrides this with the full palette.
    reset_set_robot_visual_material = EventTerm(
        func=randomize_visual_material,
        mode="reset",
        params={
            "materials": [
                SceneEntityCfg("robot_printed_material"),
                SceneEntityCfg("robot_sensor_printed_material"),
            ],
            "channels": {
                "color": {
                    "choices": [(0.876, 0.317, 0.132)],
                }
            },
        },
    )


@configclass
class SO101TeleopEnvCfg(ManagerBasedRLEnvCfg):
    seed: int = 42
    scene: SO101BaseSceneCfg = SO101BaseSceneCfg()

    observations: ObservationsCfg = ObservationsCfg()
    actions: ActionsCfg = ActionsCfg()
    events: EventCfg = EventCfg()

    rewards = None
    terminations = None

    def __post_init__(self) -> None:
        self.decimation = 2
        self.episode_length_s = 5

        self.scene.num_envs = 1
        self.sim.dt = 1 / 60
        self.sim.render_interval = self.decimation
        self.sim.physics = SO101PhysicsCfg()
        # Local visualization is opt-in through ``--visualizer``. Keeping the
        # base task empty also avoids importing an optional visualizer backend.
        self.sim.visualizer_cfgs = []
        self.sim.default_visualizer_cfg = VisualizerCfg(
            eye=(-0.76, -0.57, 0.38),
            lookat=(-0.15, -0.09, 0.19),
            enable_live_plots=False,
        )
