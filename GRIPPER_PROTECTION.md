# Estimated STS gripper protection

Implementation: `source/sim_to_real_so101/mdp/gripper_protection.py`, enabled by
the base task's `gripper_protection` startup event. Teleoperation, scripted
collection, and policy evaluation therefore share the same gripper dynamics.

## Model

The USD remains the source of the 3.35 N·m peak, fitted stiffness and damping,
armature, friction, and velocity limits. The six joint drives remain implicit;
`sim.use_newton_actuators` retains its enabled default. The protection model
changes only the gripper's available torque ceiling.

| Quantity | Initial estimate |
| --- | --- |
| Normal ceiling | 50% of USD peak: 1.675 N·m |
| Overload demand threshold | 25% of peak: 0.8375 N·m |
| Protected ceiling | 20% of peak: 0.67 N·m |
| Continuous blockage before protection | 0.1 s (six physics steps at 60 Hz) |
| Blocked-speed threshold | Absolute joint velocity below 0.1 rad/s |
| Position-error tolerance | 0.02 rad |

Demand is the fitted PD expression plus commanded feedforward effort. A blocked
sample requires an unreached target, low speed, and demand above the overload
threshold directed toward the target. The timer counts physics intervals, not
policy commands or solver substeps. Separate blockages do not accumulate.

Protection latches in the blocked direction. Streaming the same target, or
slightly changing it while continuing to squeeze, preserves the latch. Reaching
the target within tolerance, requesting the opposite direction, or resetting
that environment clears protection. Other environments retain their history.
Normal and protected limits apply to either torque direction; a reverse command
restores the normal limit immediately.

These are **starting estimates, not a measured model of this robot's firmware**.
[LeRobot's SO follower setup](https://github.com/huggingface/lerobot/blob/main/src/lerobot/robots/so_follower/so_follower.py)
sets the gripper maximum-torque register to 500 and overload threshold to 25.
[Feetech's STS3215 documentation](https://www.feetechrc.com/20210430-56680.html)
mentions "2S" and a reduced protected output for an older 7.4 V variant. The
100 ms trigger delay is a user-requested estimate for a near-immediate response,
not that documented timing or a setting read from this robot. The model is an
approximation of rapid derating under blocked load; it does not calculate motor
current or reproduce a specific firmware protection mechanism.
Mapping output percentages linearly to torque, the speed/error gates, and the
directional release rule are modeling assumptions. The protected 20% is a
fraction of the USD peak, not 20% of the already limited normal output.
Voltage, temperature, current transients, and shutdown behavior are not modeled.

## Newton integration

The event binds after solver initialization and registers a Newton
post-actuator callback. Each physics interval launches Warp kernels that update
history and publish the ceiling before the six MJWarp solver substeps.
Newton still integrates the original implicit PD drive at its solver cadence.
The gripper does not submit an explicit torque held over the physics interval.

Both Newton's joint effort-limit array and MJWarp's `jnt_actfrcrange` receive the
ceiling. This updates actual torque enforcement as well as the reported limit.
The immutable peak is copied before applying the normal ceiling, so repeated
resets cannot compound the percentage reduction.

The solver binding uses `NewtonManager._solver` and the pinned backend's
`mjc_jnt_to_newton_dof` mapping. It resolves the selected robot's gripper once
per environment; step callbacks have no scene queries or host readbacks. This
is specific to Newton/MJWarp. Revalidate the binding and physical torque test
when updating Isaac Lab or Newton. Arm drives, joint calibration, and
observation/action timing are unchanged.

## Scripted insertion checks

The state machine measures jaw-to-vial contact force in newtons independently
of the actuator torque ceiling in newton-metres. Grasp acceptance requires
4–14 N of stable contact; transfer aborts after 100 ms above 14 N.

During rack insertion, contact above 14 N is allowed under the same actuator
torque protection. The controller tracks the measured vial tip's distance to
the final insertion target, including both lateral alignment and depth. Each
improvement of more than 0.5 mm below the best recorded distance restarts a
three-second stall timer. A stalled insertion resets only its environment;
commanded trajectory progress and oscillation around an unchanged position
do not restart the timer. Grasp loss, orientation, clearance, release depth,
placement confirmation, and return-home checks also apply.

Validation on 2026-10-04 used eight default-task environments with seed 42.
Replaying the progress check against the force-guard bypass traces preserved
all 140 successful episodes; the longest pause between 0.5 mm improvements
was 2.27 seconds. All 11 recorded insertion timeouts reached the stall limit.
A fresh 200-episode run completed 138 placements (69%) and reset 12 stalled
insertions after 5.9–6.5 seconds in that phase, with no full-episode timeouts.
Reset timing changes the sampled layouts, so these batches are not paired trials.
The full suite passed all 84 tests, including GPU checks; a two-camera run
confirmed release and retreat visually. Changed Python files and Vulture pass;
full-package Ruff reports 11 findings in untouched files.
Evidence: [`outputs/state-machine-insertion-progress-20261004`](outputs/state-machine-insertion-progress-20261004).

## Initial validation on 2026-10-04 (two-second delay)

These initial results apply to commit `4796000`, with the two-second assumption
and the force-regulating state machine. The close-and-hold integration and
100 ms delay are validated separately below.

Local branch: `feature/sts-gripper-protection`, based on `newton` at `006389e`.
Runtime: the existing workshop image, RTX 6000 Ada, in `so101-sts-protection`.

- Unit suite: **63 passed**. Includes 60 Hz and 120 Hz timer checks, free
  motion, target tolerance, interrupted stalls, repeated commands, reversal,
  and selective resets.
- Full suite: **65 passed**, including the two GPU simulation tests.
- The GPU test closes both grippers against their joint stops and checks
  MJWarp's actual generalized actuator torque at **−0.67 N·m**. A partial
  reset restores only the selected gripper to 1.675 N·m. Both grippers then
  reach the 0.8 rad opening command. Fitted stiffness and damping stay intact.
- Ruff passes for every changed Python file. The full-repository Ruff check
  reports 11 existing findings in unchanged files. Vulture passes.
- Ten single-environment DR state-machine attempts, seed 42: **5/10 completed
  placements**, compared with **4/10** with this event disabled and the
  original 3.35 N·m ceiling. This small sample does not establish a success-rate
  improvement. The force-controlled state machine generally kept demand below
  the overload gate, so these attempts did not activate the protected state.
- Loaded-grasp stress check: after picking up a vial, hold the Cartesian
  command and request a fully closed gripper for five seconds. Protection
  activates at about 2.8 s after the close command, including initial motion
  before continuous blockage. Actual torque settles at **−0.67 N·m**;
  selected-vial contact persists throughout the protected interval and ends
  at **12.1 N**. This isolates actuator behavior and is not a placement test.

![Simulated torque and vial contact during a sustained close command](outputs/sts-gripper-protection-20261004/loaded-grasp-protection.png)

Logs and traces are under
[`outputs/sts-gripper-protection-20261004`](outputs/sts-gripper-protection-20261004).
The standard scripted trials are in `grasps/`; the unmodified-drive comparison
is in `baseline/`; `blockage-trace.json` records the two-environment stop test.
`loaded-contact/loaded-hold.json` records the loaded-grasp stress check plotted
above. The earlier `loaded-hold/` probe also resumed the force-controlled state
machine after the manual override; that interrupted trajectory failed, so it
is not counted among the ten unmodified scripted attempts.

The actuator response is validated in simulation. Matching the real motor's
torque and recovery behavior remains an empirical question. This dynamics
change warrants fresh demonstrations and policy evaluation; these checks do
not establish real-robot transfer or existing-policy performance.

## Close-and-hold integration and 100 ms validation

The controller imports the close-and-hold command and 0.65 rad approach wrist
posture from `codex/teleop-gripper-close-hold` (`8a15bcb`, `52a1ef1`). It does
not import that branch's task-specific 0.6 N·m USD cap. Collection, teleop, and
evaluation use the same robot asset and shared STS protection event.

The grasp phase waits for stable 4–14 N contact after the rate-limited close
command reaches -0.17 rad. It does not require the obstructed jaw to physically
reach that angle. Excess force can settle within the six-second grasp timeout;
100 ms of excess force during transfer or insertion aborts the attempt.

- Full suite: **74 passed**, including GPU torque, reset, and rendering checks.
  The unit timer checks cover a 100 ms blockage at both 60 Hz and 120 Hz.
- Changed Python files pass Ruff; Vulture passes. Full-repository Ruff retains
  11 findings in unchanged files.
- Single-environment DR smoke run, seed 42, cameras disabled: **5/10 successful
  placements**. Traces show protection active during loaded grasp and carry.
- A second ten-attempt run with jaw-position tracing also completed **5/10**.
  Three failures lost contact during transfer; one failed the insertion
  overload check; one failed during grasp. Reset timing and simulation
  variation mean these are not paired independent trials or a reliable
  estimate of production success rate.

### Grasp-depth observation

The user visually observed high grips followed by slips. In the geometry run,
the five successful grasps entered transfer with the jaw midpoint **8.6–10.6 mm
below the grasp target**, while the three transfer-slip cases were **0.1–2.2 mm
above it**. Both groups had a protected ceiling of **0.67 N·m** at transfer
start. This is consistent with grip depth affecting retention, but does not
isolate height from orientation or establish that every slip has the same cause.

That controller accepted a 15 mm three-dimensional position error after the
0.5 s descent period, without independently requiring a small vertical error.
The floor-contact sequence below replaces that closure gate.

Evidence: [`outputs/sts-close-hold-integration-20261004`](outputs/sts-close-hold-integration-20261004).
`grasp-100ms-tracking/` contains the first smoke run; `grasp-geometry/` contains
the second run and `geometry-summary.json`. `full-suite.log` and `ruff.log`
record the checks. The `initial-grasps/` and `grasp-100ms/` directories contain
intermediate experiments, not results for this final controller. In particular,
freezing arm translation as soon as closing latched produced 0/10 placements;
the controller at that stage continued following the grasp target during
closure. The surface-contact sequence below holds position only after a
measured touch of the mat.

## Descent to mat contact

The grasp phase holds the jaws at **0.4 rad** (about 27% in the workshop
calibration) and advances its descent target at **25 mm/s**. It follows the
selected vial horizontally while descending from the approach height. A
dedicated contact sensor measures the mat against the fixed-jaw body and moving
jaw, excluding vial-to-mat and jaw-to-vial forces.

At the first control sample with at least **1 N** of jaw-to-mat contact, the
controller holds the measured arm and wrist pose, clears command velocity,
and closes to -0.17 rad. Closure requires lateral error at most 15 mm and
measured gripper opening within 0.03 rad of the open target. Mat contact while
misaligned or insufficiently open rejects the attempt. Loss of mat contact
after closure does not restart descent or reopen the gripper. The descent
target is bounded to **65 mm**, and the existing **six-second** grasp timeout
rejects attempts that never reach the surface or establish a grasp.

The shared 100 ms STS protection and torque limits are unchanged. Mat sensing
is present only in the state-machine task configurations; it does not alter
the robot dynamics or the policy observation/action contract.

Validation on 2026-10-04, one DR environment, seed 42:

- Full suite: **77 passed**, including GPU simulation checks. Changed Python
  files pass Ruff; Vulture passes. The 11 previously reported full-repository
  Ruff findings are in unchanged files.
- Ten camera-free attempts: **5 completed placements**, **no transfer-slip
  failures**. Three attempts failed the excess-force check during insertion;
  one timed out before surface contact; one was rejected around the
  grasp-to-transfer transition. This small run does not establish a general
  success-rate improvement.
- All nine closures had measured mat contact, with the gripper still at
  0.400–0.401 rad. The tenth attempt never closed. Commanded descent before
  contact was 24–31 mm; that distance is a trajectory target, not a measurement
  of the jaw's displacement.
- Three additional two-camera recordings: one completed placement and two
  insertion failures. The recorded grasp sequence was visually inspected;
  the user also reported that the motion looks good. The videos include
  failures rather than selecting successful attempts only.

Evidence: [`outputs/sts-floor-grasp-20261004`](outputs/sts-floor-grasp-20261004).
`initial/contact-summary.json` records contact at each closure. The
[`videos/`](outputs/sts-floor-grasp-20261004/videos/) directory contains three
MP4s with external and wrist views and a `grasp-sequence.jpg` contact sheet.
The unit checks cover surface-triggered closure, rejection of vial-only
contact, stopping the arm target at contact, preserving the hold after contact
loss, descent bounds, timeout, and reset.

## Firm grasp and insertion geometry

The shared Newton/MJWarp configuration uses elliptic friction cones,
`impratio=10`, and solver tolerance `1e-10`. Vial colliders use
`solref=(0.006, 1.0)` and `solimp=(0.95, 0.99, 0.0001, 0.5, 2.0)` with contact
priority 1. The 6 ms time constant exceeds twice the 1/360 s solver substep;
revalidate these settings if the physics cadence changes. Priority selects the
vial's sliding friction 0.7 and torsional/rolling friction 0.0005. At equal
priority the robot-vial pair instead selected sliding friction 1.0 and
torsional friction 0.005, and mixed the robot's 20 ms contact response with
the vial's response. The firmer normal contact limits penetration without
requiring the high frictional impedance of the initial trial.

USD actuator gains, STS effort protection, and joint mapping are unchanged.
Collection and evaluation use the same contact model. These contact parameters
are simulation tuning, not measured material properties.

Scene sampling reads the vial's `sm_grasp` frame, 60 mm above its root. The
physical bottom is 17 mm below the root, so its offset from the sampled frame
is -77 mm along the vial axis. All four rack `top_01`–`top_04` USD frames lie
at the mesh's opening rim, asset z=73 mm. Insertion targets the physical tip
8 mm below this plane and permits release after at least 6 mm of measured
entry. The same geometry determines the estimated jaw clearance from other
vials. There is no separate Python correction for the rack frame height.

Initial geometry validation on 2026-10-04 used `impratio=100` and mixed
normal-contact parameters, default task, eight environments, seed 42. It
predates the penetration/release correction above:

- 101 completed attempts: **85 successful placements**, **zero insertion
  stalls**, nine resets with no eligible vial, four blocked-slot rejections,
  two grasp timeouts, and one timeout during retreat after placement.
- Median maximum vial displacement relative to the gripper during transfer:
  **0.65 mm**, with a 90th percentile of **1.12 mm**. Median maximum relative
  rotation: **2.12 degrees**. The original 24-attempt baseline measured
  12.51 mm and 19.20 degrees. Reset timing changes layouts, so these are not
  paired trials or a controlled success-rate comparison.
- **98 tests passed**, including GPU checks of the sampled tip against the
  physical root in upright and tilted poses and independent environments.
  The USD geometry check verifies every slot frame against the mesh rim.
  Changed Python files and Vulture pass; full-package Ruff retains 11 findings
  in untouched files.

Evidence: [`outputs/grasp-creep-20261004`](outputs/grasp-creep-20261004).
`final-validation.json` contains measurements for `final-default/`.
Earlier trial directories include the uncorrected geometry and a temporary
Python rack offset; they are not the final asset configuration. The user
subsequently observed jaw penetration and persistent contact after opening.
A 24-attempt probe measured median carrying penetration of 3.19 mm (maximum
5.26 mm), and up to 2.13 seconds of overlap exceeding 0.1 mm after the gripper
opened past 0.60 rad. Low creep and successful placement alone did not validate
the contact behavior.

Validation of the firmer vial contacts and `impratio=10`, also on 2026-10-04:

- 100 attempts: **76 completed placements**, nine no-eligible-vial resets,
  six blocked-slot rejections, six grasp timeouts, one insertion stall, and
  two timeouts in release after the placement flag had been confirmed.
- Median carrying penetration **0.156 mm**, 90th percentile **0.178 mm**, and
  maximum **0.287 mm**, measured from solver contacts at control intervals.
  Median maximum transfer creep **0.89 mm**, 90th percentile **2.59 mm**.
- After measured opening exceeded 0.60 rad, overlap above 0.1 mm lasted at
  most one 30 Hz control frame. This threshold does not establish separation:
  one release timeout retained roughly 0.21 N of jaw-to-vial force with only
  0.017 mm penetration. Both release timeouts also had arm-position residuals
  above the 8 mm retreat gate. Persistent release contact is reduced, not
  proven eliminated.
- **96 unit tests**, changed-file Ruff, and Vulture passed. The 98-test GPU
  suite result above precedes the final contact refinement; it was not rerun
  before the user's request to stop testing and commit. Full-package Ruff
  retains the 11 findings in untouched files.

Evidence: [`outputs/grasp-contact-20261004/comparison.json`](outputs/grasp-contact-20261004/comparison.json),
with final traces in `firm-final/`. The user reported visibly improved
behavior and requested stopping further tests. Contact
dynamics and demonstration trajectories change, so collect fresh datasets
and reassess existing policies. These checks do not establish real-robot
transfer or eliminate every source of grasp and placement failure.

### Follow-up: cap catching during release (2026-10-04)

The real robot grips the vial body below the cap and releases without a large
opening. Wider simulated opening is not an accepted solution to sticky release.
That investigation retained the 0.65 rad release target and 10 mm lateral
clearance. The withdrawal sequence below supersedes that lateral motion.

Additional probes measured contact against both claws. In the reproduced stuck
states, the active contact was between the cap's lower outer rim and a claw,
with a nearly vertical supporting normal. The contact points lay at cap radius
17.65–17.69 mm and local height 86.76–86.77 mm. Several moving-claw contacts
were on the box proxies' corners, approximately 0.5–0.9 mm from the visible
surface. This establishes a mechanical catch in those samples; it does not
establish that every reported pull-out has the same cause or that the collider
discrepancy alone explains it.

Experiments with a stricter release gate required combined claw contact below
0.05 N for 0.15 s before retreat. They also anchored release to the measured
pose, so their completion rates are not direct comparisons with the committed
controller. All experimental controller, asset, and contact changes were
reverted after these trials:

| Trial | Attempts | Completed | Release rejections | Insertion stalls |
| --- | ---: | ---: | ---: | ---: |
| Original opening/clearance with experimental guards | 100 | 65 | 11 | 0 |
| Cap contacts without torsional/rolling resistance | 40 | 18 | 9 | 0 |
| Six distal claw proxies fitted to visual geometry | 40 | 23 | 5 | 0 |
| Release after 40 mm insertion | 40 | 15 | 0 | 11 |
| Smaller 0.4 rad opening and 4 mm lateral clearance | 40 | 16 | 7 | 1 |

Other attempts include no-eligible-vial resets, blocked slots, and grasp
failures. Reset timing changes subsequent layouts; these are diagnostic runs,
not paired success-rate measurements. Deeper insertion traded release catches
for insertion stalls. Neither fitting the claw bevels nor removing cap contact
moments eliminated the snag. The physical release issue remains unresolved;
no new fix is claimed or committed from this investigation.

Evidence: `outputs/sticky-release-20261004/`, especially
`simultaneous/stuck_contacts.jsonl` and the per-trial traces.


### Backward withdrawal with downward finger pitch

Scripted release removes closing preload by anchoring the gripper command at
the measured held angle, then opens toward 0.65 rad with command limits of
1.2 rad/s and 4 rad/s². This changes the servo target without changing the
physical jaw position. Opening, downward finger pitch, and backward withdrawal
start together on the first release control step. Arm motion starts from the
measured insertion pose to clear downward command lag.

Pitch and withdrawal share a one-second distance schedule. There is no fixed
settling delay or opening-fraction lead. Finger pitch interpolates from the
measured starting pitch toward
10 degrees below horizontal. The controller derives pitch from the fixed
claw's local -Z direction and uses the measured wrist-flex axis to correct it.
The target stays floor-relative as the arm withdraws.

Withdrawal advances by distance without easing to a stop at the clearance
waypoint; the command limiter supplies acceleration. The measured opening and
claw contact gate lifting rather than the start of horizontal withdrawal.

The gripper withdraws 35 mm horizontally toward the wrist at up to 40 mm/s,
keeping the release height and wrist-roll target. Actual tracking can differ
under contact or near joint limits. Upward retreat requires placement
confirmation, an almost completed blend, the measured opening and withdrawal
position, a pitch within 5 degrees of the downward target, and combined contact
against both claws below 0.05 N for 0.15 seconds. A release that cannot clear
within six seconds resets only that environment. A vial pulled above the rack
opening during release or retreat cannot be accepted as a demonstration.
The return curve starts at the withdrawal endpoint with a matching horizontal
tangent, then curves upward. Return speed blends from withdrawal speed to
cruise over the first 60 mm. Wrist posture follows the same distance progress
with an entry tangent from the incoming wrist velocity. Its cubic interpolation
limits the tangent to prevent target-angle overshoot. Return handles use a
short backward entry and an end handle two-thirds of the way toward home to
limit outward bowing. Position and wrist posture advance on a shared distance
clock that slows continuously with measured Cartesian tracking error, using
a 20 mm error scale. This lets the arm compensate wrist rotation without
letting posture race ahead of position. Contact or tracking checks can still
require a pause before lifting.

Approach, transfer, and return use approximate arc-length traversal at a common
160 mm/s cruise speed, with acceleration limits and braking for the slower
contact motions or the final home stop. Transfer blends down to insertion speed
over its final 80 mm. Their speed no longer depends on the
spacing of Bézier handles. Approach/descent and transfer/insertion handoffs
continue from the preceding geometric goal instead of rewinding to the lagging
measured position. Surface contact and release entry still anchor the measured
pose to stop pushing against an obstacle.

Insertion rounds its lateral-alignment/descent corner within the space above
the rim, then follows a vertical line into the slot at 35 mm/s. The rounded
target curve stays at least 1 mm above the rim when the starting tip has that clearance;
otherwise alignment stays at its starting height. The two parts have a matching
vertical tangent whenever there is room to round the corner; the alignment
curve also enters vertically to continue the incoming transfer direction.

Grasp targets, insertion depth, contact materials, collider geometry, and joint
calibration are unchanged. These trajectories change recorded actions; collect
fresh demonstrations for the updated controller.

The phase-velocity baseline at commit `142982d` captured 12 attempts with five
successful placements. Successful releases spent a median 0.9 seconds below
5 mm/s before withdrawal developed. Three release attempts timed out, including
two with remaining claw contact. These observations motivated immediate
unloading and coordinated phase handoffs; they are not validation of those
changes. Evidence: `outputs/motion-phase-analysis-20261005/`.

Validation of simultaneous release and coordinated return (2026-10-05 local):

- Fifteen focused release/insertion/retreat contract checks pass; changed-file
  Ruff passes.
- Four environments, seed 42, 12 completed attempts: seven accepted placements,
  three no-eligible-vial resets, one transfer rejection, and one insertion
  failure. No release timeout occurred in this small run.
- Successful releases spend a median 0.10 seconds below 5 mm/s, compared with
  0.90 seconds in the baseline. Median release duration and per-episode traces
  are retained with the plots; residual contact or tracking gates can still
  extend a release.
- Peak Cartesian command-to-hand error during successful returns is about
  30–31 mm, compared with 64–77 mm in the baseline. The representative path
  shows reduced sideways bowing. Return is deliberately slower where the arm
  needs time to compensate wrist rotation.
- These are separate diagnostic samples with different reset timing, not a
  paired reliability benchmark. They do not establish that every catch or
  physical overshoot is eliminated. No camera validation was run.

Evidence: `outputs/motion-continuous-tracking-20261005/`. The intermediate
`motion-continuous-placement-20261005/` run lacks return tracking feedback;
its tighter curve increased physical bowing despite bounded command geometry.


Validation of the sequential downward-pitch, slower-opening sequence before
blending (2026-10-05 local):

- Eight environments, seed 42, 60 completed attempts: 41 accepted placements,
  nine no-eligible-vial resets, three blocked slots, three grasp timeouts,
  one vertical-recovery failure, one insertion stall, and two release resets.
- All 43 attempts reaching release cleared claw contact. The two release
  resets had zero remaining vial contact but 18 mm and 23 mm arm-position
  residuals, exceeding the 8 mm withdrawal gate.
- Across 3,843 sampled retreat frames, combined claw contact with the selected
  vial was zero and its tip stayed at least 25.7 mm below the opening.
  No persistent cap catch or retreat pull-out was observed in this run; this
  finite sample does not establish that either failure is eliminated.
- All 107 tests passed, including the GPU simulation tests. Changed-file Ruff
  and Vulture pass; full-package Ruff retains 11 findings in untouched files.
- Five additional single-environment episodes with both cameras all completed.
  Camera frames show the downward pitch and backward clearance before the lift;
  their traces and images are in `outputs/sticky-release-20261004/final-visual/`.

Evidence: `outputs/sticky-release-20261004/final-downward-slow/validation.json`
and its traces. Earlier directories contain intermediate configurations and
are not validation of the final release sequence.

## Demonstration-controller contact review (2026-10-09)

The demonstration-derived controller retains its release samples, opening logic,
and withdrawal path. Two controller corrections address independent failure
causes: insertion and placement checks follow the live selected rack hole, and
the pointing IK redistributes error when a joint reaches its position bound.
The release path stops following rack displacement once it is anchored. Locally
infeasible grasp/placement combinations still time out; respecting joint limits
does not make every retargeted pose reachable.

This review used sliding friction **0.7**, torsional and rolling friction
**0.0005**, `impratio=10`, and **six physics substeps**. These measurements
predate the SDF collision and softened-contact configuration. Lower-friction
candidates in this review were rejected after full-cycle validation exposed
acquisition regressions.

Isolated paired probes reconstructed a fixed-claw cap catch, a tilted rack jam,
and a loaded grasp from saved states. Reducing sliding friction to 0.35 allowed
the cap to clear and the tilted vial to descend and settle, with unchanged held
robot commands and normal contact parameters. These probes establish a friction
contribution in those states, not suitable material coefficients for an entire
pick-and-place cycle.

An initial fixed bank contained 32 scenes covering all ten demonstration styles,
including known failures. The original controller accepted 12; the corrected
controller with original contacts accepted 13. Sliding-only friction reduction
also accepted 13, but exchanged cleared cap catches for other failures. Reducing
rotational friction worsened carrying drift. A milder sliding coefficient of 0.5
and harder friction constraints (`impratio=40`) did not improve overall results.
This bank deliberately includes failures and is not a population success estimate.

A separate seed-2026 run supplied 64 unselected completed attempts, including
preparation aborts. Their initial scenes and demonstration-style draws were
replayed with the corrected controller and candidate physics:

| Sliding friction | Substeps | Accepted / attempted | Material finding |
|---|---:|---:|---|
| 0.7 | 6 | 33 / 64 | Reference contact configuration |
| 0.35 | 6 | 36 / 64 | Accepted case 60 has 6.14 mm jaw overlap and about 123 rad/s acquisition spin; rejected cases have larger transients |
| 0.35 | 12 | 26 / 64 | Rejected case 53 reaches 16.45 mm overlap; case 63 retains 7.44 mm jaw overlap and about 65 rad/s spin |

Torsional/rolling coefficients were 0.0005 and `impratio` was 10 in all three
rows. Finer substeps retained the 30 Hz control/render cadence and the 6 ms
normal time constant. Joint state, orientation, and style draws match exactly;
moving initial scenes between clones introduces at most 0.30 micrometres of
float32 position roundoff. Quiet final placement alone concealed transient
failures, so a higher accepted count did not justify promoting either candidate.

Contact distances were sampled from the final physics substep at 30 Hz; the
reported overlaps are sampled maxima, not bounds on every substep. Camera
observations and motion traces supplement these measurements. The remaining
cap catches and rack jams are not claimed fixed by the controller corrections.
The reference's maximum sampled overlap is 1.494 mm over the 64 attempts.

The final camera capture uses the corrected controller and original physics:
eight of 16 attempts complete, with all ten styles attempted. All 32 camera
videos (13,678 frames) decode at 30 Hz with matching control-frame counts. Event
comparisons against the real demonstrations show similar pacing in several
successful cycles, but some carrying caps are oversized or clipped in the wrist
view, and failures can substantially move the rack. These observations do not
establish general visual equivalence or resolve every contact failure.

Evidence: [contact review and camera comparisons](outputs/physics_contact_tuning/report.html),
[paired 32-case results](outputs/physics_contact_tuning/bank32_comparison.json),
and [acquisition regressions](outputs/physics_contact_tuning/fresh_contact_regressions.json).
These are diagnostic captures, not training episodes. Changed-file Ruff and
Vulture pass; repository-wide Ruff retains 11 findings in untouched files.
Repository tests were skipped at the user's request.
