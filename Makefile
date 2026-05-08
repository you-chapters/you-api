PYTHON = .venv/Scripts/python
TABLE_NAME = entries

ifeq ($(OS),Windows_NT)
	SHELL := C:/Program Files/Git/bin/bash.exe
endif

requirements:
	uv export --no-dev --output-file app/requirements.txt

run:
	REPOSITORY_TYPE=dynamodb DYNAMODB_TABLE_NAME=test_$(TABLE_NAME) $(PYTHON) -m uvicorn app.main:app --reload

run-mem:
	$(PYTHON) -m uvicorn app.main:app --reload

run-prod:
	REPOSITORY_TYPE=dynamodb DYNAMODB_TABLE_NAME=$(TABLE_NAME) $(PYTHON) -m uvicorn app.main:app --reload