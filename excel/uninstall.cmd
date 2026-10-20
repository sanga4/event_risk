@echo off
rem Template: the API serves this at /excel/uninstall.cmd with the add-in id and file name filled in.
rem Removes the EventRisk Analyst add-in installed by install.cmd.
title EventRisk Analyst for Excel - uninstaller
echo.
reg delete "HKCU\Software\Microsoft\Office\16.0\WEF\Developer" /v "{ID}" /f >nul 2>&1
if exist "C:\addins\{FILE}" del "C:\addins\{FILE}"
echo The Event Risk add-in has been removed. Close and reopen Excel to finish.
echo.
pause
