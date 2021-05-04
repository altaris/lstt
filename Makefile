SCRIPT_PATH = ./lstt.py

.ONESHELL:

all: format typecheck

.PHONY: format
format:
	black --line-length 79 --target-version py38 $(SCRIPT_PATH)

.PHONY: typecheck
typecheck:
	mypy $(SCRIPT_PATH)
