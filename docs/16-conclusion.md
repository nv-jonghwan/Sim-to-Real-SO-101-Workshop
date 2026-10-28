# Conclusion

Your responses help us improve our content. Please help us by taking a few minutes to provide your feedback.

:::{button-link} https://forms.gle/WC82m74fnxTrB8et9
:color: primary
:expand:
:class: sd-fs-4 sd-py-3

Share Your Feedback
:::

```{raw} html
:file: _includes/module-types/lecture.html
```

```{image} images/vial_rack.jpg
:alt: Blue-capped centrifuge vials in the yellow rack used throughout the workshop.
:width: 100%
:class: course-banner
```

This session provides time for remaining questions, continued experimentation, and a conclusion for this learning path.

## Learning Path Summary

### What You Accomplished

- Learned why simulation matters and what the sim-to-real gap is

:::{audience} learner

- Built and standardized the physical lightbox workspace to match the sim task

:::

:::{audience} event

- Used a prepared physical lightbox workspace matched to the simulation task

:::

- Got hands-on time with the SO-101 robot and LeRobot tools
- Applied Strategy 1: Domain randomization with teleoperation
- Explored NVIDIA GR00T, vision-language-action models
- Evaluated policies in simulation and on the real robot (sim-to-real gap)
- Applied Strategy 2: Co-training with real data, deployed to robot
- Explored Strategy 3: HG-DAgger, collecting human corrections around policy failures
- Applied Strategy 4: Cosmos synthetic data augmentation
- Explored Strategy 5: System identification with Anchor-Lab measurements and an AnchorBench actuator-profile comparison

### The Five Strategies We Covered

| Strategy | Approach | Key Benefit |
|----------|----------|-------------|
| **1. Domain Randomization** | Vary simulation parameters | Robust to configured visual and scene variation |
| **2. Co-training** | Mix sim and real data | Better real-world distribution |
| **3. HG-DAgger** | Mix human corrections with original demonstrations | Target the states where the policy needs help |
| **4. Cosmos Augmentation** | Synthetic visual diversity | Robust to visual variations |
| **5. System Identification** | Fit simulation parameters to measured robot behavior | More representative actuator dynamics |

### Key Lessons

1. **The gap is real** — simulation success doesn't guarantee real-world success

2. **Multiple strategies combine** — no single approach solves everything

3. **Measurement enables improvement** — system identification connects actuator parameters to observed motion

4. **Iteration is essential** — systematic improvement beats one-shot attempts

5. **Documentation matters** — recorded observations guide decisions

## How Can I Get This Code Later?

Bookmark the [public SO-101 workshop page](https://docs.nvidia.com/learning/physical-ai/sim-to-real-so-101/latest/index.html) for the learning content and links to the code. This updated workshop will replace the version currently published there and will be publicly available soon.

The [bill of materials](05-building-workspace.md#bill-of-materials) will be largely the same as in the current public workshop. The [YouTube playlist](https://www.youtube.com/playlist?list=PL2bKqBZg-pzVQspO8-wieuIFctBdz_Tr_) can help you get started building your robot and workspace before the update is published.

For further courses, documentation, community links, and papers, see [Explore and Experiment](15-explore.md#further-resources).

## Conclusion

Congratulations on finishing this course **"Train an SO-101 Robot From Sim-to-Real With NVIDIA Isaac."**

We hope this will enable and inspire you to keep learning and practicing your skills in Physical AI!
