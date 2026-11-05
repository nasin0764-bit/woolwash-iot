"""
Authorship and approval form (Word) for the co-authors.

    python tools/make_authorship_form.py   ->  paper/approval/AUTHORSHIP_FORM.docx

CRediT roles: https://credit.niso.org. Pre-marked roles are only PROPOSALS that follow from known facts
(dissertation author, scientific supervisor, statistical reanalysis); every author confirms or corrects them.
"""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "paper" / "approval" / "AUTHORSHIP_FORM.docx"

AUTHORS = ["R. Tuguzbayeva", "S. Khakimov", "F. Dustova", "R. Rosulov", "M. Anorkulov"]
ROLES = ["Conceptualization", "Methodology", "Software", "Validation", "Formal analysis", "Investigation",
         "Resources", "Data curation", "Writing – original draft", "Writing – review & editing", "Visualization",
         "Supervision", "Project administration", "Funding acquisition"]
# proposals from known facts only (author: roles)
PROPOSED = {
    "R. Tuguzbayeva": {"Conceptualization", "Investigation", "Data curation", "Writing – original draft"},
    "S. Khakimov": {"Supervision"},
    "M. Anorkulov": {"Formal analysis", "Validation"},
}


def shade(cell, color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color)
    tcPr.append(shd)


def main():
    doc = Document()
    doc.styles["Normal"].font.name = "Calibri"
    doc.styles["Normal"].font.size = Pt(10)
    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(1.8)
        s.top_margin = s.bottom_margin = Cm(1.5)

    doc.add_heading("Authorship and approval form", level=1)
    p = doc.add_paragraph()
    p.add_run("Manuscript: ").bold = True
    p.add_run("“An IoT-Enabled Hybrid Soft Sensor for Real-Time Residual-Moisture Monitoring and Resource Accounting "
              "in Compact Wool Scouring Machines”, IEEE Internet of Things Journal (draft, Section VII pending).")
    doc.add_paragraph("Форма авторства и согласия / Mualliflik va rozilik shakli. Please return the completed form to "
                      "the corresponding author (trobiya89@mail.ru).")

    doc.add_heading("1. Contributions (CRediT roles)", level=2)
    note = doc.add_paragraph()
    r = note.add_run("“proposed” marks are suggestions from known facts only. Every author must confirm or correct "
                     "their own column (write ✓ or ✗). An author needs at least one substantial role.")
    r.italic = True
    r.font.size = Pt(9)
    t = doc.add_table(rows=len(ROLES) + 1, cols=len(AUTHORS) + 1)
    t.style = "Table Grid"
    t.cell(0, 0).text = "Role"
    for j, a in enumerate(AUTHORS, 1):
        t.cell(0, j).text = a
    for c in t.rows[0].cells:
        shade(c, "DDE7F0")
        for run in c.paragraphs[0].runs:
            run.bold = True
            run.font.size = Pt(9)
    for i, role in enumerate(ROLES, 1):
        t.cell(i, 0).text = role
        for j, a in enumerate(AUTHORS, 1):
            cell = t.cell(i, j)
            cell.text = "proposed" if role in PROPOSED.get(a, set()) else ""
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in cell.paragraphs[0].runs:
                run.font.size = Pt(8)
                run.font.color.rgb = RGBColor(0x1F, 0x5F, 0x8B)
        t.cell(i, 0).paragraphs[0].runs[0].font.size = Pt(9)

    doc.add_heading("2. Personal details and declarations (one block per author)", level=2)
    for a in AUTHORS:
        doc.add_paragraph().add_run(a).bold = True
        tb = doc.add_table(rows=8, cols=2)
        tb.style = "Table Grid"
        rows = ["Name exactly as printed (as in ORCID)", "Affiliation, city, country", "E-mail", "ORCID iD",
                "Biography and photo checked; photo may be published (yes / no)",
                "Conflict of interest (none / describe)",
                "AI-use disclosure in the Acknowledgment accepted (yes / edit)",
                "I approve the current content (yes / changes requested) · date · signature"]
        for k, label in enumerate(rows):
            tb.cell(k, 0).text = label
            tb.cell(k, 0).paragraphs[0].runs[0].font.size = Pt(9)
            shade(tb.cell(k, 0), "F2F4F6")
        doc.add_paragraph()

    doc.add_paragraph("Final approval of the complete manuscript, including Section VII with the factory results, "
                      "will be requested separately before submission.").runs[0].italic = True
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print("->", OUT)


if __name__ == "__main__":
    main()
