# Publishing in IEEE Internet of Things Journal for **US$ 0**

IEEE IoT-J is a **hybrid** journal. You choose one route at submission:

| Route | Fee | Who can read it |
|---|---|---|
| **Traditional** ✅ (choose this) | **US$ 0** if the final paper is **≤ 8 pages** | IEEE Xplore subscribers (most universities) |
| Open Access ❌ | US$ 2,645 (2025 price; 2026 is higher) + any overlength charges | everyone |

**The only charge on the Traditional route:** US$ 175 for **every page above 8** in the final published version.
This charge is mandatory. 10 pages = US$ 350, 12 pages = US$ 700. **Keep the paper at 8 pages or fewer.**

Legally free ways to make it readable by everyone:
- IEEE allows you to post the **accepted manuscript** (your own final Word/LaTeX version, not the IEEE-formatted PDF) on
  arXiv, your university repository, ResearchGate or Google Scholar.
  Check the rules on the IEEE copyright form when you sign it.
- Post the **preprint** on arXiv (category `eess.SY` or `cs.NI`) **before** submission. IEEE permits this.

---

## Step-by-step checklist

### Before writing the final version
- [ ] Collect the real field data (docs/HARDWARE.md §5). **No simulator data in the results.**
- [ ] Fill every red `[TODO]` in `main.tex`.
- [ ] Add 20–30 references, at least 8 from IEEE IoT-J / IEEE TII from 2020–2025. Reviewers check this.
- [ ] Run `check_pages.bat`. **8 pages or fewer**, including references and biographies.

### Tips for staying within 8 pages
- Cite derivations that already exist in the literature (the journal asks for this) instead of repeating them.
  Cite the dissertation for the rake/drum dynamics instead of re-deriving them.
- Use single-column-width figures (`figure`, not `figure*`) and combine several plots into one figure with subfigures.
- Keep tables compact (`\small`, `booktabs`).
- Use short biographies without photos.
- Leave about 0.5 page free: reviewers usually ask for additions in the revision.

### Accounts (all free)
- [ ] **ORCID** for every author: https://orcid.org/register (mandatory).
- [ ] An IEEE Author Portal account: https://ieee.atyponrex.com/journal/iot
- [ ] IEEE membership is **not** needed for the Traditional route.

### Files to upload
- [ ] `main.pdf`: double-column IEEEtran (already set up)
- [ ] LaTeX sources (`main.tex` + figures) in the final round
- [ ] Cover letter (`cover_letter.tex` → PDF)
- [ ] 3–5 suggested reviewers from other institutions with no joint papers with you
- [ ] Keywords from the journal's list (e.g. *Industrial IoT*, *Cyber-Physical Systems*, *Sensor Networks*)

### In the submission form, pay attention to
- [ ] **Open Access: answer "No" / select "Traditional".** This is the step that saves US$ 2,645.
- [ ] Manuscript type: *Regular Paper*.
- [ ] Declare that no part was published elsewhere. If the dissertation is online, mention it in the cover letter;
      a thesis is normally **not** considered prior publication.

### English language (free options)
- Grammarly (free version) and LanguageTool (free)
- Ask an English-speaking colleague or your university's foreign relations or English department.
- Paid editing services are optional, and IEEE says they do **not** guarantee acceptance.

### Typical timeline
Submission → first decision about 2–4 months → revision (keep it within 8 pages!) → acceptance →
copyright form (free) → proofs → published on IEEE Xplore.

---

## Be realistic: have a backup plan
IoT-J rejects most submissions. Common reasons are weak IoT novelty and too few experiments. If it is rejected,
these journals are also **free** to publish in (subscription/traditional route):
- **IEEE Sensors Journal** (hybrid; choose traditional, check its current page limit)
- **IEEE Transactions on Instrumentation and Measurement** (hybrid)
- **Textile Research Journal** (SAGE, hybrid, free traditional route)
- **Journal of Natural Fibers** (Taylor & Francis, hybrid)

Avoid "fast publication" journals that ask for payment immediately or promise acceptance. Many are predatory.
