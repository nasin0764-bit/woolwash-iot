@echo off
rem Builds the CURRENT WORKING VERSION only:
rem   main.tex         -> main_5authors.pdf
rem   cover_letter.tex -> cover_letter_5authors.pdf
rem Earlier PDFs (main.pdf, main_build.pdf, cover_letter.pdf) are NOT overwritten.
rem More than 8 pages = US$175 per extra page.
cd /d "%~dp0"
pdflatex -interaction=nonstopmode -jobname=main_5authors main.tex >nul
pdflatex -interaction=nonstopmode -jobname=main_5authors main.tex >nul
pdflatex -interaction=nonstopmode -jobname=cover_letter_5authors cover_letter.tex >nul
pdflatex -interaction=nonstopmode -jobname=cover_letter_5authors cover_letter.tex >nul
for /f "tokens=*" %%l in ('findstr /c:"Output written" main_5authors.log') do echo %%l
for /f "tokens=*" %%l in ('findstr /c:"Output written" cover_letter_5authors.log') do echo %%l
del /q main_5authors.aux main_5authors.log main_5authors.out cover_letter_5authors.aux cover_letter_5authors.log 2>nul
echo.
echo LIMIT: 8 pages for FREE (Traditional) publication.
pause
