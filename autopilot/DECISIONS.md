# Autopilot decision log

date | task | question | decision | reason
---|---|---|---|---
2026-11-04 | setup | Resume the long session or start fresh each run? | Resume the session by ID, fall back to a fresh session if the resume fails | Keeps the full project context; the repository files (AUTOPILOT.md) make a fresh start safe
2026-11-04 | setup | Trigger for a restart | Session transcript unchanged for 20 min and open tasks remain | Covers credits running out and normal ends without a second agent running in parallel
2026-11-04 | 1 | How to split field data for held-out accuracy | Last 25 % of calendar days form the test set | Avoids leakage between replicates and neighbouring samples of the same day (protocol in Sec. IV)
2026-11-04 | 1 | Trial containing some simulated rows | Exclude the whole trial in strict mode | Lost-packet rows carry no SIM mark; partial exclusion gave a false 0 % delivery
2026-11-04 | setup | Scheduled-task install was blocked by the safety classifier | Leave the install to the user; do not work around it | Persistence must be the user's own action
2026-11-04 | 2 | CI push needs the workflow scope, which the token lacks | Keep the workflow in ci/ci.yml with activation steps | A rejected push would block all other commits; scope changes are the user's decision
