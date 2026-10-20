@echo off
rem Lanceur Windows de la CLI de la Factory : « factory <commande> » depuis la racine de la Factory.
python -P "%~dp0factory.py" %*
