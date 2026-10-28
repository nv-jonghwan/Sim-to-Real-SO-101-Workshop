# Debugging Sim-to-Real Issues

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/wrist-sim-real-debugging.png
:alt: Overlaid wrist-camera views showing differences in rack holes, vial cap, and gripper alignment between simulation and reality.
:width: 100%
:class: course-banner debugging-header
```

These checks come from this workshop's SO-101 vial-to-rack case study. They are useful hypotheses to test, but the causes and fixes may differ for another robot, task, policy, or environment.

1. :::{dropdown} Verify the robot configuration and mechanical condition.

   Check the follower's calibration, homing offsets, joint order and units, measured position, and gripper mapping. Confirm that the achieved pose matches the commanded pose before blaming the policy. On the SO-101, fasteners can loosen over time as the printed plastic compresses, and servos can wear after heavy use. Inspect the joints and mounts, then use basic teleoperation or a known-good replay to confirm that the robot moves accurately and consistently. See [Calibration](07-calibrating-so101.md) for the workshop procedure.

   :::

2. :::{dropdown} Inspect the complete camera pipeline

   Check focus and alignment, tighten loose camera mounts and nuts, and confirm that each physical camera maps to the feature name expected by the checkpoint. When more than one camera is present, make sure they have not been swapped. Confirm that captured frames remain fresh and sustain the requested frame rate; a responsive preview alone does not prove that the policy receives every frame on time.

   :::

3. :::{dropdown} Look for learned position bias.

   If the arm reaches toward a place where no object exists, the policy may be relying on a narrow set of familiar object positions instead of the current image. Compare predictions while changing only the object's position, then inspect whether the training data covers those layouts. Treat overfitting as a hypothesis until a controlled test supports it.

   :::

4. :::{dropdown} Match the training-data starting pose.

   If the robot hesitates or does not begin the task, check whether its achieved start lies inside the checkpoint's actual training-start distribution. In this SO-101 vial-to-rack case study, moving the robot to a represented start was essential for the best observed policy performance. Account for the current calibration and any continuation or teleoperation data.

   :::

5. :::{dropdown} Compare visual conditions.

   For a vision-language-action policy, check whether lighting, shadows, reflections, backgrounds, materials, exposure, or camera response fall outside the training distribution. Hold the pose and layout fixed while changing one visual factor at a time.

   :::

6. :::{dropdown} Replay a known-good physical episode.

   Replay an episode collected on the same robot to check whether its recorded commands still reproduce the task. This bypasses policy prediction and can reveal coarse calibration, joint-mapping, gripper, timing, or actuator problems. Follow the [recorded-episode replay procedure](troubleshooting.md#replay-a-recorded-episode-on-the-physical-arm) and match its calibration, start pose, joint order, units, and frame rate.

   :::

7. :::{dropdown} Test with known-good recorded observations.

   Feed saved camera images, robot state, and the task instruction through the checkpoint offline, using its original preprocessing and action decoding. Compare the predictions with those from live observations to help isolate camera, observation-timing, preprocessing, or policy-runtime differences. See the [fixed-observation procedure](troubleshooting.md#test-policy-inputs-with-fixed-or-dummy-observations).

   As an optional advanced test, a custom harness can apply those decoded actions to the robot. Start from the recorded pose and supervise the motion: the saved observations no longer track what the robot is doing. This can help check action execution, but it is a diagnostic, not a policy-success trial. Record the observations, achieved starting pose, runtime revision, and executed actions; a changed result alone does not establish the cause.

   :::

There is no single sim-to-real solution. It remains an active robotics research area with both strong results and unresolved challenges. Learning to isolate hardware, observation, policy, action, and environment failures helps you choose the next experiment instead of changing several factors at once.

## What's Next?

Continue to [Isaac GR00T: Vision-Language-Action Models](10-groot.md).
