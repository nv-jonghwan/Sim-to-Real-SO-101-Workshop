# Learning From Real Demonstrations With a State Machine

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/state-machine/real-to-sim.gif
:alt: Real and simulated vial manipulation shown side by side, with joint traces underneath.
:width: 100%
:class: course-banner simulation-poster
```

A state machine can generate large-scale demonstration data as well as help us fine-tune the physics configuration to narrow the sim-to-real gap. It breaks the task into phases and rules for moving between them.

Building one by hand takes motion analysis and careful programming - but capturing the motion’s “DNA” is hard.
Coding agents can help by studying a few human demonstrations, finding the nuances and patterns, writing the state machine, and refining its behavior against those examples. Here, we call this process **real-to-sim**: real data used to create and tune a simulation.

## Learning Objectives

- **Explain** how real demonstrations can guide a state machine.
- **Compare** trajectory nuances and timing across human and generated demonstrations.
- **Guide** an agent to make corrections before collecting a larger dataset.

## From a Few Demonstrations to New Layouts

As an example use case, we use the state machine approach to collect simulated demonstrations with new vial and rack layouts, without manually teleoperating each episode.

We then fine-tune an existing policy with generated data of new layouts. 
In our experiments, we have seen successful real-world rollouts in layouts that existed only in simulation.

```{raw} html
<figure>
  <video controls playsinline preload="metadata" style="width:100%" aria-label="Selected real-robot rollouts showing external and wrist camera views">
    <source src="_static/videos/state-machine/real-rollouts.mp4" type="video/mp4">
  </video>
  <figcaption>Selected real-robot rollouts. Watch the approach, grasp, and placement in an unseen layout.</figcaption>
</figure>
```

## Start With a Focused Prompt

We seed the process with 10 real demonstrations from [sreetz-nv/so101_real_manual](https://huggingface.co/datasets/sreetz-nv/so101_real_manual). The prompt keeps the agent focused on motion so it does not change the scene to make the comparison look better.

:::{dropdown} Example Prompt: Build and Refine the State Machine

```text
Review these 10 real demonstrations of our task:
https://huggingface.co/datasets/sreetz-nv/so101_real_manual

Analyze them closely and build a state machine that matches their motion
characteristics.

Keep the existing geometry, shapes, colors, camera parameters, lighting,
materials, and render settings unchanged. These are already established
in our code.

Focus on robot commands: trajectories, linear and angular velocities,
smoothness, natural variation, grasp positions, and the approach, grasp,
lift, insertion, and retraction strategies. Build a state machine that
can generate reliable demonstrations at a larger scale than these
10 examples.

Compare the resulting motions in the camera observations against the
real demonstrations. Check framing, how much of the image each object
occupies, and the timing of each movement. Review, compare, and refine.
```

:::

## Analyze the Motion, Then Refine It

Look beyond whether the task is completed. Compare the sequence of stages, the path of the gripper, and how its speed changes through the task.

```{figure} images/state-machine/motion-analysis.png
:alt: Ten demonstration timelines alongside jaw-center paths and speed traces.
:width: 100%

Selected plots from the agent’s initial analysis of the human example. Note the patterns it was able to extract.
```

```{raw} html
<figure>
  <video controls playsinline preload="metadata" style="width:100%" aria-label="Real demonstration compared with baseline and refined state-machine motions">
    <source src="_static/videos/state-machine/first-refinement.mp4" type="video/mp4">
  </video>
  <figcaption>The agent’s first self-refinement pass: a comparison of the real demonstration, baseline simulation, and revised simulation in both camera views.</figcaption>
</figure>
```

## Lessons Learned

### Think Procedurally

The agent may choose to simply mimic the provided examples by creating a “motion bank.” We guide it to decompose the motion into atomic pieces so that it can procedurally generate motions for different layouts.

```{raw} html
<figure>
  <video controls playsinline preload="metadata" style="width:100%" aria-label="State-machine demonstration with a mirrored vial and rack layout">
    <source src="_static/videos/state-machine/mirrored-layout.mp4" type="video/mp4">
  </video>
  <figcaption>A mirrored layout tests whether the state machine can adapt its approach and placement.</figcaption>
</figure>
```

### Match the Starting-Pose Distribution

A state machine that always starts in one pose can produce a narrow training distribution, even when the vial and rack positions vary. This is easy to miss visually: domain randomization changes the camera view between runs, making the same starting pose look different.

```{figure} images/state-machine/posture-distributions.png
:alt: Manual and procedural simulation joint postures at the start and at gripper closure. Procedural starts cluster at one pose while manual starts are spread out.
:width: 100%

The left plot exposes a fixed procedural starting pose. The other plots compare joint configurations at gripper closure. Similar grasp poses do not mean the starting poses match.
```

### Check the Grasp Height

Where the jaws grip the vial affects its position in the wrist image. A successful simulated grasp can still look different from the real demonstrations. Compare the cap, vial body, and jaws in both views, and consider how contact with real materials affects the grasp.

```{figure} images/state-machine/grasp-height.png
:alt: Before-and-after grasp-height adjustment, showing the external view above and the wrist view below.
:width: 100%

Changing the grasp height changes how much of the vial and cap the wrist camera sees.
```

### Match the Pickup Timing

A pause after closing the gripper becomes part of the training data. If generated demonstrations repeatedly hesitate before lifting, a policy trained on them may learn that hesitation too. When observations barely change during the pause, the policy may struggle to determine when to begin lifting and continue predicting stationary actions. Compare when the lift begins, not just where it ends.

```{figure} images/state-machine/lift-timing.png
:alt: Vertical rise after gripper closure for 20 manual and 20 procedural examples. Procedural lifting starts later, though both reach similar heights.
:width: 100%

The procedural examples begin lifting later than the manual examples. Aligning the traces at gripper closure makes the delay easier to see.
```

## Another Way to Scale Demonstrations: Isaac AutoData

[Isaac AutoData](https://github.com/isaac-sim/AutoData) expands a small set of annotated seed demonstrations into many more demonstrations in simulation. It splits the examples into motion segments relative to objects, adapts those segments to new object placements and scene configurations, then joins and executes them in simulation, saving successful demonstrations. Our approach uses a coding agent to write and refine a state machine; AutoData transforms and recombines the demonstrated motions themselves. Both reduce manual collection, with AutoData providing a structured way to generate variation from seed examples. See the [AutoData documentation](https://isaac-sim.github.io/AutoData/) to learn more.

## Another Way to Scale Demonstrations: an Agent as the Policy

Another agentic alternative for generating robot demonstrations is to let a coding agent act as the policy, having it drive the simulated robot directly. Here it receives camera images and joint readings and replies with joint targets.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/agent-policy-loop.html"
    title="An agent as a policy: select a step for details" loading="lazy"
    style="display:block; width:100%; height:960px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/agent-policy-loop.svg
:alt: The simulation pauses and is observed, a prompt is built, the agent returns joint targets, an adapter validates and converts them, and the robot executes a short chunk before observing again.

Each control cycle ends with a new observation, so the agent decides again from the updated scene.
```
````

```{raw} html
<figure>
  <video controls playsinline preload="metadata" style="width:100%" aria-label="Simulated rollout with the agent as the policy, shown in the external and wrist camera views">
    <source src="_static/videos/state-machine/agent-rollout.mp4" type="video/mp4">
  </video>
  <figcaption><strong>This video is not running in real time.</strong> A simulated rollout with the agent as the policy, shown in the external and wrist camera views. In this video, the agent controlling the policy is GPT-6 Astra.</figcaption>
</figure>
```

There is no state machine to write or debug. However, the bottleneck with this technique is inference time. Every decision is a blocking call to a remote model, and in our runs the agent can take several seconds to reason before each chunk. The simulation pauses for that wait, so the motion plays out in simulated time and collection is far slower than a state machine.

Review these rollouts the way you reviewed the state machine's. Check the starting pose, the grasp height, and when the lift begins before you collect a large set.

## Key Takeaways

- **Watch the timing.** Remove unintended delays and hesitations while preserving the pauses needed to grasp and place objects.
- **Inspect the motion and contact.** Check joint configurations, grasp positions, and interactions with real materials.
- **Compare trends, not just outcomes.** Small differences in poses and timing can accumulate across a trajectory.
- **Use agents to review, compare, and refine.** Inspect the generated demonstrations before scaling up collection, then evaluate the trained policy in both sim and real.

## What's Next?

Continue to [Sim Evaluation](11-sim-evaluation.md) to run a supplied policy in this environment. The [scripted collection reference](08-simulation-teleoperation.md) provides the collection commands.
