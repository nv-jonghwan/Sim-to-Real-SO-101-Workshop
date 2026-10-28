# Overview

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/task-wireframe.gif
:alt: Wireframe view of the SO-101, cameras, vials, and rack in the simulated workspace.
:width: 100%
:class: course-banner
```

::::::::{audience} learner
```{raw} html
<iframe width="560" height="315" src="https://www.youtube-nocookie.com/embed/3TL3ALQxQX8?si=tsrYaeoEqoBUNXVk" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
```
::::::::

## What Is Physical AI?

Physical AI refers to AI systems that interact with and manipulate the physical world. Unlike generative or agentic AI (think image generators, chatbots), Physical AI has the ability to:

- **Perceive** the real world through sensors
- **Reason** about physics, objects, and spatial relationships
- **Act** through motors, actuators, and end-effectors
- **Adapt** to the unpredictability of real environments

:::{figure} images/workshop-concepts/slide-08.png
:alt: Sensor images and text enter a Physical AI model, which produces actions for factory robots, humanoids, and autonomous vehicles.
:width: 100%

Physical AI connects sensor observations and instructions to actions in the world.
:::

This learning path teaches a complete Physical AI workflow with physical robots, from simulation to a robot acting autonomously, right in front of you.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/physical-ai-loop.html" title="Camera observations and robot actions form a feedback loop" loading="lazy" style="display:block; width:100%; height:600px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/physical-ai-loop.svg
:alt: Camera observations and robot actions form a feedback loop
```
````

## Specialist and Generalist Robots

A specialist learns a narrow task. A generalist aims to handle a wider range of tasks; post-training adapts that broad foundation to a particular robot and job. In this workshop, we adapt GR00T to the SO-101 vial-to-rack task.

:::{figure} images/workshop-concepts/slide-09.png
:alt: Specialist robots have narrow scope; generalists cover more tasks; adapting a generalist adds task proficiency. Broad capability across robots remains a research goal.
:width: 100%


:::

::::{dropdown} See examples of specialist and generalist robots

:::{figure} images/workshop-concepts/slide-10.png
:alt: Examples illustrate a factory production line, robot manipulation, and a humanoid performing a household task.
:width: 100%


:::

::::

## The Task: Centrifuge Vial Pick-and-Place

:::{figure} images/so101_vial_to_rack_task.gif
:alt: Vial to rack task performed by SO-101 robot
:width: 100%

Vial to rack pick-and-place task performed autonomously by an SO-101 robot.
:::

The task we'll use today is unstructured pick-and-place of centrifuge vials. The vials are scattered on a table and need to be placed into a designated rack.

We've simplified some of the constraints with a lightbox, and with some of the parameters of the task, to make it more approachable. 

But the tools and techniques you'll learn are applicable to more complex tasks and production robots. The focus of this learning path is the sim-to-real workflow.

::::::::{audience} learner
```{raw} html
<iframe width="560" height="315" src="https://www.youtube-nocookie.com/embed/iWp8Wj2LBF4?si=23pVqaidClhkyUeR" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
```
::::::::

### Why This Task?

::::::{dropdown} Read more about why we chose vial pick-and-place

So why did we pick this task? Let's imagine we are engineers solving a laboratory problem.

In our fictional problem, these vials are dropped down a chute or otherwise scattered in an unstructured way, but need to be organized into a rack for processing by automated machinery - a line that already exists.

- **Real-world relevance**: this is an analogy for workflows where items must be prepared for autonomous analysis machines.
- **Safety implications**: think of use cases where potentially hazardous samples are handled, so minimizing human exposure is critical, hence the use of robotics. The ability to teach the task in simulation also saves time and reduces exposure.
- **Technical challenge**: adaptation to change, ability for the robot to adapt and retry.
- **Approachable**: for learning, this task is simple enough to gather objects for and perform teleoperation.

::::::

## Why Is This Problem Interesting?

Our policy will work from 2D camera information, and the placement of the vials in the rack requires re-orienting the vials and placing them fairly precisely. Depth information isn't there to help in this configuration.

As you'll likely find from teleoperating the task yourself, it's not easy at first. 

One major issue is that the robot's wrist camera will become occluded after the robot grasps a vial, so the policy will need to be able to operate without this information.

You'll experience this challenge first-hand when you do teleoperation yourself.

:::{note}
The SO-101 isn't a production robot, but it's a fun, approachable platform for learning these tools before you apply them to production robots. Again, the focus here is a **workflow** that you can apply to other tasks, or to production robots.
:::

## Learning From Demonstrations

A demonstration pairs what the robot observed with the action that followed. **Imitation learning** uses many such examples to teach a policy how to act in new situations.

````{only} html
```{raw} html
<figure>
  <iframe class="interactive-learning-diagram" src="_static/interactive/learning-from-demonstrations.html" title="Collect demonstrations, review episodes, post-train, and evaluate" loading="lazy" style="display:block; width:100%; height:600px; border:0;"></iframe>
</figure>
```
````

````{only} not html
```{figure} images/interactive/learning-from-demonstrations.svg
:alt: Collect demonstrations, review episodes, post-train, and evaluate
```
````

## Scaling Physical AI

Broad pre-training, task-specific post-training, and additional computation at inference are different ways to develop capability. This illustration shows the idea; its curves are conceptual rather than measured workshop results.

:::{figure} images/workshop-concepts/slide-64.png
:alt: Conceptual scaling curves show pre-training, post-training, and test-time computation, with internet video, human demonstrations, and synthetic data as sources.
:width: 100%


:::

### Why Robot Data Takes Work

Videos show what happened, but robot demonstrations also need the observations and actions that produced it. Human teleoperation takes time, and different robots have different controls and camera views. We use simulation and real demonstrations together to help address that collection burden.

:::{figure} images/workshop-concepts/slide-65.png
:alt: Robot learning needs observations paired with actions and outcomes. Teleoperation takes human effort, while hardware differences complicate dataset reuse.
:width: 100%


:::

## Why Simulation Matters

:::{figure} images/task-wireframe.gif
:alt: Task wireframe: vials on table, target rack outlined.
:width: 80%

Task wireframe: vials are scattered on a table, to be placed into a rack by the robot.
:::

Testing robots in the real world is expensive, risky, and sometimes dangerous.

Simulation addresses these fundamental limitations:

1. **Time**: Real-world data collection is slow—one trajectory takes the same time whether you have one robot or one thousand
2. **Cost**: Robot hardware is expensive, and failures during exploration can cause damage
3. **Safety**: Exploring failure modes on real hardware can be dangerous
4. **Diversity**: Creating varied training scenarios (different lighting, objects, positions) is labor-intensive

::::::{dropdown} Compare real-world and simulated training

Simulation addresses all of these:

| Challenge | Real World | Simulation |
|-----------|------------|------------|
| Training speed | 1x real-time | 1000x+ parallel environments |
| Hardware cost | $10K-$100K+ per robot | Marginal compute cost |
| Failure consequence | Damage, downtime | Reset and continue |
| Scenario diversity | Manual setup | Procedural generation |

::::::

### Privileged Information

::::::{dropdown} Read more about privileged information in simulation

Simulation also provides access to information that might be impossible to obtain in the real world:

- **Exact object poses**: No perception noise or occlusion
- **Contact forces**: Precise measurements at every contact point
- **Ground truth labels**: Perfect segmentation and object identity
- **State derivatives**: Exact velocities and accelerations

This privileged information can accelerate learning, even when the final policy only uses realistic sensor inputs.

::::::

## Key Takeaways

- Simulation enables fast, safe, diverse training that can be impossible in the real world
- The sim-to-real gap is a fundamental challenge that requires systematic approaches
- This learning path provides hands-on experience with NVIDIA Isaac and multiple gap-closing strategies
- Success comes from iteration and combining approaches

Using a VLA (Vision Language Action) model from Isaac GR00T 1.7, our system will receive a language command like "pick up the vial and place it on the rack", and use robot joint feedback and camera observations as policy inputs. 

The policy then outputs motor positions to execute the task.

## What's Next?

::::::::{audience} learner

This learning path has some flexibility built-in to match your goals and time constraints. Let's cover those options next!

Continue to [How to Take This Course](02-how-to-take-this-course.md).

::::::::

::::::::{audience} event

Continue to [LeRobot and the SO-101](04-lerobot.md).

::::::::
