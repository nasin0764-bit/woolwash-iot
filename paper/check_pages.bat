@echo off
rem Compiles the paper and reports the page count. >8 pages = US$175 per extra page.
cd /d "%~dp0"
pdflatex -interaction=nonstopmode main.tex >nul
pdflatex -interaction=nonstopmode main.tex >nul
for /f "tokens=*" %%l in ('findstr /c:"Output written" main.log') do echo %%l
echo.
echo LIMIT: 8 pages for FREE (Traditional) publication.
pause
