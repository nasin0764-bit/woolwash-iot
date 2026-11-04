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

- [x] 1. **Field-analysis tool** `tools/analyze_field.py`: read the filled
      `IEEE_IoT_Factory_Validation_Template.xlsx` plus the server exports. Compute held-out soft-sensor RMSE, MAE and
      R² for the four models (day-separated split), packet delivery %, median and p95 latency, kWh/kg and L/kg
      (mean ± SD, 95% CI), and fault-detection delays. Write LaTeX table snippets to `results/field/` for Section VII.
      Test only on simulated data written to a temporary folder; never commit simulated field results.
- [x] 2. **Automated tests and CI:** add a pytest suite (softsensor stages, ingest/alerts, validation CSV exports,
      fill_template, analyze_field). Add a GitHub Actions workflow running the tests and compiling the firmware with
      arduino-cli (esp32:esp32@3.3.12, pinned libraries). Make sure it passes.
- [x] 3. **Dirty-liquor advisory:** add hysteresis and a minimum-duration debounce, with the threshold editable per
      machine through the API. Rerun `tools/sim_study.py` S3 only, if possible, and update the Section VI text and
      numbers.
- [x] 4. **Page budget:** tighten the paper text, especially Section VI, so that `main_5authors.pdf` is at most 6
      pages, leaving at least 2 pages for Section VII. Keep every number and claim intact.
- [x] 5. **Russian and Uzbek guides:** `docs/PLAN_RU.md` and `docs/PLAN_UZ.md` (Latin script), covering the
      step-by-step plan to submission, the factory commissioning checklist and the flashing/setup steps for the ESP32.
- [x] 6. **Printable data-collection forms** (PDF in `docs/forms/`): shift log (meter readings, wool mass, wool type),
      lab moisture sample log (wet/dry mass, 3 replicates), sensor calibration sheet, fault-test log. In English and
      Russian.
- [x] 8. **App commissioning tab:** EN/RU tab in the web/mobile app to view and set per-machine alarm limits
      (`/api/limits`) and squeeze geometry (`/api/geometry`) with the device token; verify against a running server.
- [ ] 9. **Cover letter consistency:** contributions match the current paper (Sections V/VI/VII), 1 page if possible.
- [ ] 10. **Supervisor copy of the corrections:** Word version of `Dissertation_Corrections.md` (tables kept).
- [ ] 11. **Firmware boot test in an emulator** (Espressif QEMU): check that the image boots and reaches setup;
      record honestly what can and cannot be tested without hardware (no Wi-Fi in QEMU).
- [ ] [HUMAN] 7. **Repository release** (blocked for the agent: creating a public release is the user's decision). Command: `gh release create v1.1.0 firmware/bin/woolwash_esp32_1.1.0.merged.bin firmware/bin/woolwash_esp32_1.1.0.bin firmware/bin/SHA256SUMS.txt --title "WoolWash-IoT 1.1.0 (firmware pre-release)" --notes-file firmware/RELEASE_NOTES_1.1.0.md --prerelease`
- [ ] [HUMAN] Factory measurements (docs/HARDWARE.md §5): needed for Section VII.
- [ ] [HUMAN] Written approval of the full manuscript by all five authors; M. Anorkulov confirms his contribution.
- [ ] [HUMAN] Bowl volume from the engineering drawing; patent certificate inventors.
- [ ] [HUMAN] Journal submission (IEEE Author Portal, Traditional route).
- [ ] [HUMAN] Install the autopilot scheduled task (blocked for the agent as persistence): `powershell -ExecutionPolicy Bypass -File autopilot\install_task.ps1`
- [ ] [HUMAN] Enable CI: `gh auth refresh -h github.com -s workflow`, then copy ci/ci.yml to .github/workflows/ci.yml, commit and push

## Results log
(one line per finished task: number | date | result | commit)

1 | 2026-11-04 | tools/analyze_field.py done: calibration MAE/RMSE/bias per sensor, day-separated 4-model comparison, PDR + median/p95 latency, kWh/kg and L/kg (mean ± SD, 95% CI, Welch test), fault delays; 5 LaTeX snippets + summary.json. Tested end to end on simulated data in a temp folder only. Fixed a bug where lost packets of simulated trials were counted in strict mode. Template limit: 300 packet rows, so use 8-h windows. | see git log
2 | 2026-11-04 | pytest suite: 17 tests (soft-sensor stages, ingest/token/alerts, out-of-sample lab prediction, packet gap export, CSV export, fill_template safety, analyze_field metrics) all pass locally. CI workflow written to ci/ci.yml (tests + pinned firmware compile) but NOT active: the gh token lacks the workflow scope; activation steps are at the top of ci/ci.yml. | see git log
3 | 2026-11-04 | Advisory now has a 30-s debounce, on/off hysteresis (800/700 NTU) and per-machine limits via GET/PUT /api/limits/{id} (token-protected; geometry PUT now token-protected too). S3 rerun: advisory active 64 % -> 37.8 % (default) -> 18.8 % (commissioned 820/700); all 56 simulated liquor changes preceded by an advisory; fault detection unchanged (60/60). 4 new tests (21 total) pass; Section VI text updated. | see git log
4 | 2026-11-04 | Paper 7 -> 6 pages (Sec. III instrumentation, Sec. IV protocol, Sec. VII placeholders and Discussion condensed; all numbers and claims kept), ~2 pages free for Sec. VII within the 8-page free limit. main_5authors.pdf was locked by a PDF viewer; the 6-page build is paper/main_check.pdf (rebuild with check_pages.bat). | see git log
5 | 2026-11-04 | docs/PLAN_RU.md and docs/PLAN_UZ.md (Latin script): goal, status, 8 steps, ESP32 flashing and portal setup, commissioning checklist. | see git log
6 | 2026-11-04 | docs/forms/01-04 PDFs (A4 landscape, English + Russian): shift log, lab moisture log (wet basis, 3 replicates), sensor calibration sheet, supervised fault-test log; each maps to a template sheet or the analyze_field --faults CSV. Generator: tools/make_forms.py (reportlab 4.2.5, Arial/DejaVu). | see git log
7 | 2026-11-04 | Release creation denied by the safety classifier (public surface). Release notes saved to firmware/RELEASE_NOTES_1.1.0.md; task moved to [HUMAN] with the exact command. | see git log
8 | 2026-11-05 | App tab Commissioning / Пусконаладка: view and save per-machine geometry and alarm limits with the device token (sessionStorage only). Server PUT /api/limits now coerces types and validates the merged ON/OFF and debounce values. Verified in headless Edge against a temp server: prefill, wrong token -> error, right token -> saved on server, RU labels, no JS errors; phone-width layout checked. 22 tests pass. | see git log
