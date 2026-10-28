:::{admonition} Rollout controls
The arm moves to the workshop start pose on startup, then waits for **P**.
Keep the rollout terminal focused. Keys are case-insensitive.

| Key | Action |
|-----|--------|
| **P** | **P for policy:** Start the first or next trial. |
| **S / F** | Score success/failure, return to the start pose, and pause. |
| **N / →** | **N for next:** Discard the trial, return to the start pose, and pause. |
| **Q / Esc** | **Q for Quit:** Exit and discard any unfinished trial. |
| **Ctrl+C** | Stop the rollout and run cleanup. |

Wait for `Paused` before rearranging props. On exit, wait for cleanup and any return motion to finish before touching the arm.

When comparing models, record the first-action delay shown in the terminal and the number of successes out of scored trials.
:::
