# WoolWash-IoT: maqolani topshirishgacha bo'lgan ish rejasi (o'zbek tilida)

## Maqsad
Maqolani **IEEE Internet of Things Journal**da **bepul** chop etish: topshirishda **Traditional** yo'nalishini
tanlash va maqola hajmini **8 sahifadan oshirmaslik** kerak. 8 sahifadan ortiq har bir sahifa 175 AQSh dollari turadi.
Maqola R. B. Tuguzbayeva dissertatsiyasidagi takomillashgan jun yuvish mashinasida IoT tizimining ishlashini
ko'rsatishi kerak.

**Asosiy qoida:** jurnalga **korxonada IoT tizimi bilan olingan haqiqiy o'lchovlar** kerak. Dissertatsiya
ma'lumotlari IoT tizimini emas, mashinani tavsiflaydi, shuning uchun maqolada ular alohida bo'limda (V bo'lim) beriladi.
VI bo'limda (modellashtirish va stend sinovlari) korxona ma'lumotlari yo'q. VII bo'lim **faqat** haqiqiy
o'lchovlar bilan to'ldiriladi.

## Nimalar tayyor
| Qism | Holati |
|---|---|
| Dissertatsiyaga izohlar (`Dissertation_Corrections.md`) | ✅ |
| ESP32 dasturi 1.1.0, tayyor fayl `firmware/bin/*.merged.bin` | ✅ kompilyatsiya qilingan, platada hali sinalmagan |
| Server, veb/mobil ilova (EN/RU), simulyator | ✅ sinovdan o'tgan, 21 ta avtotest |
| Excel shablon va `fill_template.py`, `analyze_field.py` skriptlari | ✅ |
| Maqola: 5 muallif, ORCID, rasmlar, 30 ta tekshirilgan manba, V va VI bo'limlar | ✅ 6 sahifa |
| VII bo'lim (korxonadagi IoT natijalari) | ❌ o'lchovlar kerak |

## Bosqichlar
1. **Tekshiruvlar (1 hafta):** chizma bo'yicha qozon hajmi (2500×600×515 mm = 0,77 m³, dissertatsiyada esa 2,5 m³);
   FAP 02351 patentidagi mualliflar; R. Tuguzbayevaning lavozimi; 5 muallifning qo'lyozmaga yozma roziligi;
   M. Anorkulov o'z hissasini (statistik qayta hisoblash) tasdiqlaydi.
2. **Uskunalarni xarid qilish (1–3 hafta, ~150–200 AQSh dollari):** ro'yxat `docs/HARDWARE.md` faylida. Shuningdek,
   quritish shkafi (105 °C) va analitik tarozi kerak.
3. **Korxonada o'rnatish (1–2 kun):** elektr qismini (PZEM-004T, ta'minot) **faqat elektrik** ulaydi. Datchiklar
   `docs/HARDWARE.md` §3 dagi sxema bo'yicha o'rnatiladi.
4. **ESP32 dasturini yozish (10 daqiqa):**
   - platani USB kabel bilan ulang;
   - Chrome brauzerida https://espressif.github.io/esptool-js/ ni oching → Connect, manzil **0x0**, fayl
     `woolwash_esp32_1.1.0.merged.bin` → Program (yoki `firmware\flash.bat COM5`);
   - telefonda **WoolWash-Setup-xxxx** Wi-Fi tarmog'iga ulaning (parol `woolwash123`), http://192.168.4.1 ni oching va
     sex Wi-Fi'si, server manzili `http://<kompyuter-IP>:8000/api/telemetry`, token va mashina ID sini kiriting;
   - sozlamalarni tozalash: yoqishda BOOT tugmasini 3 soniya bosib turing.
5. **Kalibrlash (1–2 kun):** har bir datchikni uch darajada etalon bilan solishtiring (termometr, ruletka, 20 litrli
   chelak, formazin standartlari, taxometr). Natijalarni shablonning «Sensor calibration» varag'iga yozing.
6. **O'lchovlar (3–4 hafta):** kamida 10 smena; har 30 daqiqada namlik namunalari (105 °C, 3 takror) ilovaning «Lab»
   bo'limiga kiritiladi; o'qitish uchun kamida 60 ta va boshqa kunlarda tekshirish uchun 20 ta namuna; har smenada suv
   va elektr hisoblagichlari ko'rsatkichlari va jun massasi; har smenadan keyin CSV eksport va zaxira nusxa.
7. **Tahlil (1 hafta):** `python tools/fill_template.py ...`, keyin
   `python tools/analyze_field.py toldirilgan.xlsx --machine WW-01`. VII bo'lim uchun jadvallar `results/field/`
   papkasida paydo bo'ladi.
8. **Topshirish:** IEEE Author Portal, «Regular Paper», **Open Access = No (Traditional)**. Nazorat ro'yxati
   `paper/SUBMISSION_FREE_ROUTE.md` faylida.

## Ishga tushirish nazorat ro'yxati
- [ ] Mashina tokdan uzilgan va qulflangan, elektrik joyida
- [ ] 5 ta harorat datchigi: chuqurlikning o'rtasida, devordan 10 sm, bug' kirishidan uzoqda
- [ ] 5 ta sath datchigi: eritma ustida, maksimal sathdan ≥ 25 sm yuqorida
- [ ] 2 ta loyqalik datchigi: 1–2 qozonlarning namuna olish idishlarida
- [ ] Siquvchi baraban valida Xoll datchigi va magnit
- [ ] Toza suv kirishida sarf o'lchagich; dvigatellar ta'minotida PZEM tok transformatori
- [ ] ECHO liniyalari va analog kirishlarda 5 V → 3,3 V bo'lgichlar
- [ ] IP65 korpus, alohida 5 V ta'minot bloki
- [ ] Server ishga tushirilgan (`start_server.bat`), token plata sozlamalaridagi token bilan bir xil
- [ ] Ilovada ma'lumotlar «SIMULATED DATA» belgisisiz ko'rinadi
- [ ] Loyqalik signali chegaralari eritmani almashtirish amaliyotiga ko'ra o'rnatilgan (`PUT /api/limits/WW-01`)
- [ ] Kompyuter va ESP32 soatlari sinxronlangan (NTP); shablonda «Negative latencies» = 0
