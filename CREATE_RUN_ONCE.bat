@echo off
python -m venv venv
call ./venv/scripts/activate.bat
python -m pip install -r requirements.txt
python -m spacy download en
pause