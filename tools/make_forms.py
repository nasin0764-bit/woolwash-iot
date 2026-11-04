"""
Printable bilingual (English / Russian) data-collection forms for the factory campaign.

    python tools/make_forms.py        ->  docs/forms/*.pdf

Forms: shift log, lab moisture sample log, sensor calibration sheet, fault-test log.
Each form maps 1:1 to a sheet of IEEE_IoT_Factory_Validation_Template.xlsx or to the
--faults CSV of tools/analyze_field.py, so the paper copies can be typed in afterwards.
"""
from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "forms"
OUT.mkdir(parents=True, exist_ok=True)

# Cyrillic-capable TrueType font (Windows Arial; DejaVu on Linux)
CANDIDATES = [("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
              ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
for reg, bold in CANDIDATES:
    if os.path.exists(reg) and os.path.exists(bold):
        pdfmetrics.registerFont(TTFont("F", reg))
        pdfmetrics.registerFont(TTFont("FB", bold))
        break
else:
    raise SystemExit("No Cyrillic TrueType font found (Arial or DejaVu).")

TITLE = ParagraphStyle("t", fontName="FB", fontSize=13, leading=16)
SUB = ParagraphStyle("s", fontName="F", fontSize=8.5, leading=11)
CELL = ParagraphStyle("c", fontName="FB", fontSize=7, leading=8.5, alignment=1)


def header_block(fields):
    """Row of 'label: ______' fields."""
    data = [[Paragraph(f"<b>{f}</b>", SUB) for f in fields], ["" for _ in fields]]
    t = Table(data, colWidths=[(277 * mm) / len(fields)] * len(fields), rowHeights=[11, 16])
    t.setStyle(TableStyle([("LINEBELOW", (0, 1), (-1, 1), 0.6, colors.black),
                           ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 6)]))
    return t


def grid(cols, widths_mm, n_rows, row_h=8.2):
    data = [[Paragraph(c, CELL) for c in cols]] + [["" for _ in cols] for _ in range(n_rows)]
    t = Table(data, colWidths=[w * mm for w in widths_mm], rowHeights=[None] + [row_h * mm] * n_rows, repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dde7f0")),
                           ("VALIGN", (0, 0), (-1, 0), "MIDDLE")]))
    return t


def build(name, title_en, title_ru, intro, fields, cols, widths, n_rows, footer):
    doc = SimpleDocTemplate(str(OUT / name), pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=9 * mm, bottomMargin=9 * mm, title=title_en, author="WoolWash-IoT")
    story = [Paragraph(f"{title_en} / {title_ru}", TITLE), Spacer(1, 2 * mm), Paragraph(intro, SUB),
             Spacer(1, 2 * mm), header_block(fields), Spacer(1, 3 * mm), grid(cols, widths, n_rows),
             Spacer(1, 2 * mm), Paragraph(footer, SUB)]
    assert abs(sum(widths) - 277) < 0.6, (name, sum(widths))
    doc.build(story)
    print("->", OUT / name)


COMMON = ["Plant / Предприятие", "Machine ID / ID машины", "Date / Дата", "Shift / Смена", "Operator / Оператор"]

build("01_shift_log.pdf", "Shift log: meters and wool mass", "Журнал смены: счётчики и масса шерсти",
      "One row per batch or shift. Read the <b>physical</b> water and electricity meters at start and end. "
      "Weigh the wool. Mode: A = IoT monitoring, B = closed loop, C = conventional machine. "
      "Одна строка на партию или смену. Снимать показания <b>физических</b> счётчиков в начале и в конце, "
      "шерсть взвешивать. → Excel: лист «Water energy batches».",
      COMMON + ["Wool type / Тип шерсти (spring/autumn)"],
      ["Batch ID<br/>Партия", "Mode<br/>Режим", "Start time<br/>Начало", "End time<br/>Конец",
       "Wool mass, kg<br/>Масса шерсти, кг", "Water meter start, m³<br/>Вода начало, м³",
       "Water meter end, m³<br/>Вода конец, м³", "Energy start, kWh<br/>Энергия начало, кВт·ч",
       "Energy end, kWh<br/>Энергия конец, кВт·ч", "Run hours<br/>Часы работы", "Meter IDs / notes<br/>Счётчики / примечания"],
      [19, 14, 20, 20, 25, 27, 27, 27, 27, 19, 52], 14,
      "Signature / Подпись: ____________________    Checked / Проверил: ____________________")

build("02_lab_moisture_log.pdf", "Lab moisture sample log (oven-dry, 105 °C)",
      "Журнал лабораторных проб влажности (сушка при 105 °C)",
      "Take the sample right after the squeeze device; three replicates per sampling point. "
      "Residual moisture (wet basis) W = (Tin+wet − Tin+dry) / (Tin+wet − Tin) × 100 %. Dry to constant mass. "
      "Enter the mean W in the app tab <b>Lab</b> immediately and mark the column In app (x). "
      "Пробу брать сразу после отжимного устройства, 3 повтора. Влажность (на влажную массу) "
      "W = (Бюкс+влажн. − Бюкс+сух.) / (Бюкс+влажн. − Бюкс) × 100 %. Среднее W сразу ввести во вкладку <b>Лаборатория</b>.",
      COMMON + ["Oven / balance ID / Шкаф / весы"],
      ["Sample #<br/>Проба №", "Time<br/>Время", "Stage / bowl<br/>Ступень / ванна", "Rep.<br/>Повт.",
       "Tin ID<br/>Бюкс №", "Tin, g<br/>Бюкс, г", "Tin + wet, g<br/>Бюкс + влажн., г", "Tin + dry, g<br/>Бюкс + сух., г",
       "W, %", "Mean W, %<br/>Среднее W, %", "In app (x)<br/>В прил. (x)", "Initials<br/>Подпись"],
      [17, 18, 26, 13, 18, 22, 30, 30, 20, 28, 20, 35], 15,
      "Repeat W if replicates differ by more than 1.5 pp. / Повторить, если повторы отличаются более чем на 1,5 п.п.")

build("03_sensor_calibration.pdf", "Sensor calibration sheet", "Лист калибровки датчиков",
      "Compare each IoT sensor with a reference instrument at low, middle and high values (live readings: "
      "http://&lt;board-IP&gt;/). Сравнить каждый датчик с эталоном на низком, среднем и высоком уровне. "
      "→ Excel: лист «Sensor calibration».",
      COMMON + ["Firmware / Прошивка"],
      ["Sensor type<br/>Тип датчика", "Sensor ID / bowl<br/>Датчик / ванна", "Reference instrument<br/>Эталон",
       "Level<br/>Уровень (L/M/H)", "Time (UTC)<br/>Время", "Reference reading<br/>Показание эталона",
       "IoT reading<br/>Показание IoT", "Unit<br/>Ед.", "Certificate / date<br/>Сертификат / дата",
       "Initials<br/>Подпись"],
      [32, 27, 38, 20, 24, 30, 28, 14, 38, 26], 15,
      "Temperature: reference thermometer · Level: tape · Flow: 20-L bucket · Turbidity: formazin 0/400/800 NTU · "
      "Drum ω: hand tachometer · Power: revenue-grade meter.")

build("04_fault_test_log.pdf", "Supervised fault-test log", "Журнал контролируемых испытаний неисправностей",
      "<b>Safety:</b> supervisor present, safety interlocks stay active, no live mains work. Record the onset time "
      "from an <b>independent</b> clock (phone, UTC). <b>Безопасность:</b> присутствует руководитель, блокировки не "
      "отключаются. Время начала фиксировать по <b>независимым</b> часам (UTC). → CSV for analyze_field.py "
      "(fault_id, type, onset_utc, first_alert_utc).",
      COMMON + ["Supervisor / Руководитель"],
      ["Fault ID<br/>№", "Type<br/>Тип (heater_off / low_level / drum_speed)", "How induced<br/>Как вызвано",
       "Onset (UTC)<br/>Начало (UTC)", "First alert (UTC)<br/>Первый сигнал (UTC)", "Alert code<br/>Код сигнала",
       "Restored (UTC)<br/>Восстановлено", "Safety OK (x)<br/>Безоп. (x)", "Notes<br/>Примечания"],
      [16, 44, 40, 30, 32, 26, 27, 20, 42], 12,
      "False alarms during normal operation are counted from the server log. / Ложные срабатывания считаются по журналу сервера.")
