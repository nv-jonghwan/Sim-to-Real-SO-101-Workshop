# Architecture Tour: Building the Robotics Application

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/lightbox-simulation-orbit.gif
:alt: Camera orbit around the stationary SO-101 simulated workstation, with vials and rack inside the lightbox.
:width: 100%
:class: course-banner simulation-poster
```

We've collected demonstrations in simulation. Now let's look at the code that makes that possible, before we evaluate a policy.

## Learning Objectives

- **Explain** how Omniverse libraries, Newton, Isaac Lab, and LeRobot work together.
- **Describe** how a robot learning simulation environment is structured.
- **Trace** how configuration, sensors, reset events, observations, and recording connect in one control loop.

## How the Pieces Fit Together

We're building a custom robotics application with **Omniverse libraries, Newton, Isaac Lab, and LeRobot**. These libraries give you the building blocks to build the application you need. Here, we combine them for our robot, task, and learning workflow.

````{only} html
```{raw} html
<figure>
<iframe class="interactive-learning-diagram" src="_static/interactive/workshop-code-stack.html" title="How the workshop code stack fits together" loading="lazy" style="display:block; width:100%; height:700px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/workshop-code-stack.svg
:alt: Workshop code connects LeRobot to Isaac Lab, which uses Newton physics and Omniverse rendering with USD assets. Joint state and camera images return as observations.
```

| Component | What it does in this workshop |
|---|---|
| **Omniverse libraries** | ovstage manages the USD scene used for rendering, and ovrtx renders the wrist and external camera images. USD assets describe the robot, rack, vials, and lightbox. |
| **Newton** | Advances the physics: robot motion, gravity, and contacts between the gripper, vials, and rack. This application uses its MJWarp solver. |
| **Isaac Lab** | Organizes the scene, actions, observations, reset events, and conditions that end an episode. It connects the physics and rendering backends to the task. |
| **LeRobot** | Provides robot and teleoperator interfaces, the demonstration dataset format, and policy training and inference tools. The workshop bridge converts between LeRobot joint values and simulation actions. |
| **Workshop code** | Defines the vial-to-rack task, connects teleoperation or a policy to the arm, records demonstrations, and reports evaluation results. |

````

## Isaac Lab Environment Configuration

In Isaac Lab, a registered task identifies the configuration used to create a simulation environment. The `--task` flag selects which environment to load.

These examples are **pseudocode**: they simplify class names, observation groups, and return values to show the architecture, rather than provide runnable scripts.


````{only} html
```{raw} html
<iframe class="interactive-learning-diagram" src="_static/interactive/isaac-lab-manager-based.html" title="Environment configuration connects scene, simulation, and managers to the reset and step loop." loading="lazy" style="display:block;width:100%;height:650px;border:0;"></iframe>
```
````

````{only} not html
```{image} images/architecture/isaac-lab-manager-based.svg
:alt: Environment configuration connects scene, simulation, and managers to the reset and step loop.
:width: 100%
```
````

```python
cfg = EnvironmentConfig(
    scene=Scene(robot=Articulation(...), assets=[...], sensors=[...]),
    simulation=SimulationSettings(physics_dt=1 / 60, decimation=2),
    actions=ActionTerms(...),
    observations=ObservationTerms(...),
    events=EventTerms(startup=..., reset=..., periodic=...),
    terminations=TerminationTerms(success=..., failure=..., time_limit=...),
    rewards=RewardTerms(...),
)
environments = Environment(cfg)
observations = environments.reset()

while running:
    actions = policy.predict(observations)
    observations, rewards, ... = environments.step(actions)
```

Rewards are part of the environment interface; recording demonstrations does not use them to update a policy.

## Camera Sensor

The camera configuration selects image size, channels, update timing, and renderer. ovrtx renders the scene, and the images become observations for the policy or recorder.

````{only} html
```{raw} html
<iframe class="interactive-learning-diagram" src="_static/interactive/isaac-lab-camera-ovrtx.html" title="Camera configuration and ovrtx rendering feed camera images into observations during the environment loop." loading="lazy" style="display:block;width:100%;height:650px;border:0;"></iframe>
```
````

````{only} not html
```{image} images/architecture/isaac-lab-camera-ovrtx.svg
:alt: Camera configuration and ovrtx rendering feed camera images into observations during the environment loop.
:width: 100%
```
````

**Source:** `source/sim_to_real_so101/tasks/task_env_cfg.py`

```python
camera_cfg = CameraCfg(
    ..., width=640, height=480, data_types=["rgb"],
    update_period=1 / 30, renderer_cfg=...,
)

while running:
    actions = policy.predict(observations)
    observations, rewards, ... = environments.step(actions)
    image = observations["visual"]["camera"]
```

## Reset Terms

A reset event calls a function with its configured parameters. Here, the reset function varies rack placement. It runs when an environment resets, rather than on every control step. The example ranges are in meters for position and radians for yaw.

````{only} html
```{raw} html
<iframe class="interactive-learning-diagram" src="_static/interactive/isaac-lab-rack-vial-randomization.html" title="Initial reset or episode ending triggers rack and vial randomization; normal steps continue without resetting." loading="lazy" style="display:block;width:100%;height:650px;border:0;"></iframe>
```
````

````{only} not html
```{image} images/architecture/isaac-lab-rack-vial-randomization.svg
:alt: Initial reset or episode ending triggers rack and vial randomization; normal steps continue without resetting.
:width: 100%
```
````

**Source:** `source/sim_to_real_so101/tasks/vials_to_rack_env_cfg.py`

```python
cfg.events.reset_vials_setup = EventTerm(
    func=mdp.reset_vials_rack,
    mode="reset",
    params={
        "rack_pose_range": {
            "x": (-0.04, 0.04),
            "y": (-0.01, 0.01),
            "yaw": (-0.5, 0.5),
        },
    },
)
```

## Grasp Observation

Observation terms can turn sensor readings into useful task signals. The workshop combines contact force with vial height to estimate whether a vial is grasped, then keeps that flag while contact persists. This is a progress signal, not proof of a stable grasp or successful placement.

````{only} html
```{raw} html
<iframe class="interactive-learning-diagram" src="_static/interactive/isaac-lab-vial-grasp-observation.html" title="The observation manager uses contact sensor data to compute the vial-grasped signal for the running loop." loading="lazy" style="display:block;width:100%;height:650px;border:0;"></iframe>
```
````

````{only} not html
```{image} images/architecture/isaac-lab-vial-grasp-observation.svg
:alt: The observation manager uses contact sensor data to compute the vial-grasped signal for the running loop.
:width: 100%
```
````

**Source:** `source/sim_to_real_so101/tasks/vials_to_rack_env_cfg.py`

```python
cfg.scene.contact_grasp = ContactSensorCfg(...)
cfg.observations.vial_grasped = ObsTerm(
    func=mdp.any_vial_grasped,
    params={"contact_sensor_cfg": SceneEntityCfg("contact_grasp")},
)

while running:
    actions = policy.predict(observations)
    observations, rewards, ... = environments.step(actions)
    vial_grasped = observations["vial_grasped"]
```

## LeRobot Recorder

During teleoperation, the leader supplies the action. Record the current images and joint state with that action **before** advancing simulation, so each observation is paired with the command applied next. The bridge separates simulation actions (radians) from dataset actions (arm degrees and gripper percent). It also converts observed joint state into dataset units before recording.

````{only} html
```{raw} html
<iframe class="interactive-learning-diagram" src="_static/interactive/isaac-lab-lerobot-recording.html" title="Read a leader action, record it with current joint state and camera images, then step the environment and pace the next iteration." loading="lazy" style="display:block;width:100%;height:650px;border:0;"></iframe>
```
````

````{only} not html
```{image} images/architecture/isaac-lab-lerobot-recording.svg
:alt: Read a leader action, record it with current joint state and camera images, then step the environment and pace the next iteration.
:width: 100%
```
````

**Pseudocode — illustrates the recording sequence.**

**Source:** `source/sim_to_real_so101/scripts/lerobot_agent.py`

```python
rate = Rate(30)  # 30 Hz
interface = LeRobotSO101Interface(...)
recorder = LeRobotRecorder(..., fps=30)
observations, _ = environments.reset()

while recording:
    dataset_action, sim_action = interface.read_action()
    dataset_state = interface.sim_radians_to_raw(
        observations["policy"]["joint_pos_obs"][0]
    )
    recorder.record(
        action=dataset_action,
        joint_state=dataset_state,
        images={
            "wrist": observations["visual"]["rgb_wrist"][0],
            "external": observations["visual"]["rgb_external"][0],
        },
    )
    observations, rewards, ... = environments.step(sim_action)
    rate.sleep()

recorder.save_episode()
```

## Follow One Control Step

Now trace how these building blocks work together in one control loop iteration. Start from `lerobot_agent.py`, called with the `--task` flag that selects the environment.

During teleoperation, the leader supplies a command through the LeRobot interface, and the workshop bridge converts it to simulation joint commands. When recording is active, the recorder pairs the current camera images and joint state with the command about to be applied, in LeRobot format. Then `env.step(actions)` advances Newton physics through Isaac Lab, ovrtx renders the cameras, and Isaac Lab returns the observations for the next iteration.

During policy evaluation, the policy supplies actions instead of the leader. The same simulation scene and task checks tell us what happened.
