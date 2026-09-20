@echo off
rem Double-click to rebuild everything: data (if missing), the SQL Server database, the A/B test, and the charts.
cd /d "%~dp0"
echo.
echo === Kaarobar: building everything in SQL Server ===
echo It uses your Windows login to reach SQL Server, so there is no password to type.
echo.
if not exist dataaw\orders.csv (
    echo Creating the dataset first, about 40 seconds...
    python src\generate_data.py || goto :fail
)
python srcun_pipeline.py || goto :fail
python srcb_test.py || goto :fail
python src\eda_charts.py || goto :fail
echo.
echo === Done. Charts are in the images folder, results in the outputs folder. ===
pause
exit /b 0
:fail
echo.
echo === Something failed. Copy the error above and send it to Claude. ===
pause
exit /b 1
