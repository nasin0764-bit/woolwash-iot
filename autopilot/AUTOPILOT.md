# WoolWash-IoT autopilot: rules and task queue

This file is the single source of truth for unattended work. Each autopilot run takes the **first unchecked task
that is not marked [HUMAN]**, finishes it, ticks it, and commits and pushes. Then it continues with the next task.

## Rules (binding for every run)

1. **Scope:** work only inside `C:\Users\Nasiba\Desktop\Tuguzbayeva` (the repository `WoolWash-IoT` and
   `Dissertation_Corrections.md`). Do not touch other folders, settings, credentials or other repositories.
2. **Research integrity:** never invent factory measurements. Never put simulator or synthetic numbers into
   Section VII (factory) of the paper, and never present them as measured. Keep Sections V (historical),
   VI (simulation and bench) and VII (factory) strictly separate.
3. **Never:** submit to a journal, send emails or messages, spend money, change repository visibility, delete the
   repository, force-push, rewrite git history, or remove author information.
4. **Paper:** `paper/main.tex`, built as `paper/main_5authors.pdf` with `paper/check_pages.bat` or
   `pdflatex -jobname=main_5authors`. Keep it at **8 pages or fewer**. Do not overwrite `main.pdf`, `main_build.pdf`
   or `cover_letter.pdf`.
5. **Decisions:** do not ask the user. When a choice is unclear, ask a subagent (Agent tool, `model: "fable"`) for a
   recommendation with the relevant context, decide, and append one line to `autopilot/DECISIONS.md`:
   `date | task | question | decision | reason`.
6. **Quality:** verify every change (run the tests, compile the firmware, rebuild the PDF and check it visually).
   Report failures honestly in the task's result line.
7. **Git:** after each finished task: `git add -A`, commit with a clear message ending with the Co-Authored-By line,
   and `git push`. Small, separate commits.
8. **Finish:** when no open non-[HUMAN] task is left, write `ALL AUTONOMOUS TASKS DONE` at the end of this file,
   then stop.

## Task queue

- [ ] 1. **Field-analysis tool** `tools/analyze_field.py`: read the filled
      `IEEE_IoT_Factory_Validation_Template.xlsx` plus the server exports. Compute held-out soft-sensor RMSE, MAE and
      R² for the four models (day-separated split), packet delivery %, median and p95 latency, kWh/kg and L/kg
      (mean ± SD, 95% CI), and fault-detection delays. Write LaTeX table snippets to `results/field/` for Section VII.
      Test only on simulated data written to a temporary folder; never commit simulated field results.
- [ ] 2. **Automated tests and CI:** add a pytest suite (softsensor stages, ingest/alerts, validation CSV exports,
      fill_template, analyze_field). Add a GitHub Actions workflow running the tests and compiling the firmware with
      arduino-cli (esp32:esp32@3.3.12, pinned libraries). Make sure it passes.
- [ ] 3. **Dirty-liquor advisory:** add hysteresis and a minimum-duration debounce, with the threshold editable per
      machine through the API. Rerun `tools/sim_study.py` S3 only, if possible, and update the Section VI text and
      numbers.
- [ ] 4. **Page budget:** tighten the paper text, especially Section VI, so that `main_5authors.pdf` is at most 6
      pages, leaving at least 2 pages for Section VII. Keep every number and claim intact.
- [ ] 5. **Russian and Uzbek guides:** `docs/PLAN_RU.md` and `docs/PLAN_UZ.md` (Latin script), covering the
      step-by-step plan to submission, the factory commissioning checklist and the flashing/setup steps for the ESP32.
- [ ] 6. **Printable data-collection forms** (PDF in `docs/forms/`): shift log (meter readings, wool mass, wool type),
      lab moisture sample log (wet/dry mass, 3 replicates), sensor calibration sheet, fault-test log. In English and
      Russian.
- [ ] 7. **Repository release:** create GitHub release `v1.1.0` with the firmware binaries, SHA256SUMS and a short
      changelog (`gh release create`).
- [ ] [HUMAN] Factory measurements (docs/HARDWARE.md §5): needed for Section VII.
- [ ] [HUMAN] Written approval of the full manuscript by all five authors; M. Anorkulov confirms his contribution.
- [ ] [HUMAN] Bowl volume from the engineering drawing; patent certificate inventors.
- [ ] [HUMAN] Journal submission (IEEE Author Portal, Traditional route).

## Results log
(one line per finished task: number | date | result | commit)
