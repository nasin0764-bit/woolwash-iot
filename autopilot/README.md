# Autopilot: unattended continuation with Claude Code

When the interactive Claude session stops (credits or usage limit used up, or it simply finished), the watchdog
continues the open tasks in `AUTOPILOT.md` on its own.

| File | Purpose |
|---|---|
| `AUTOPILOT.md` | rules + task queue (single source of truth), results log |
| `DECISIONS.md` | decisions made without the user (advised by a Claude Fable subagent) |
| `PROMPT.txt` | the instruction given to every unattended run |
| `autopilot.ps1` | watchdog: idle check → `claude -p --dangerously-skip-permissions --resume <id>` → limit/reset handling |
| `install_task.ps1` / `uninstall_task.ps1` | register / remove the Windows scheduled task `WoolWashAutopilot` |
| `start_autopilot.bat` | start the watchdog once by hand |
| `logs/` | one log per watchdog start + the JSON output of each run (not in git) |

**How it works**
1. Waits until this session's transcript has not changed for 20 min, so it never runs next to an active session.
2. Resumes the session (`--resume`). If that fails, it starts fresh sessions that read `AUTOPILOT.md`.
3. On a usage limit, it reads the reset time from Claude's message (epoch, "resets 3pm", "at 15:00",
   "in 2 hours"), sleeps until reset + 3 min, and retries. If no time is given, it backs off 15 → 30 → 60 min.
4. Stops when all autonomous tasks are done, a `STOP` file exists, after 25 runs, or after 6 unexpected errors.

**Commands**
```
powershell -ExecutionPolicy Bypass -File install_task.ps1     # install (already done)
powershell -ExecutionPolicy Bypass -File autopilot.ps1 -SelfTest
echo stop > STOP                                               # pause/stop at the next check
powershell -ExecutionPolicy Bypass -File uninstall_task.ps1   # remove completely
```

> ⚠️ Runs use `--dangerously-skip-permissions`, so Claude acts without asking. The rules in `AUTOPILOT.md` limit what
> it may do: project folder only, no submission, no emails, no fabricated data, no force-push. Do not type into the
> interactive session while an autopilot run is active. Create `STOP` first.
