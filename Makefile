.PHONY: all lints pylint check-pylint check-flake8 check-isort check-black format venv venv-test

VENV ?= ./venv
VENV_PYTHON ?= $(VENV)/bin/python3

all:

lints: pylint check-flake8 check-isort check-black

format: isort black

check-pylint pylint:
	$(VENV_PYTHON) -m pylint intg-mythtv
check-flake8:
	$(VENV_PYTHON) -m flake8 intg-mythtv --count --show-source --statistics

check-isort:
	$(VENV_PYTHON) -m isort intg-mythtv/. --check --verbose
isort:
	$(VENV_PYTHON) -m isort intg-mythtv/. --verbose

check-black:
	$(VENV_PYTHON) -m black intg-mythtv --check --verbose --line-length 120
black:
	$(VENV_PYTHON) -m black intg-mythtv --verbose --line-length 120

venv:
	python3 -m venv --system-site-packages --prompt intg-mythtv $(VENV)
	$(VENV)/bin/pip3 install -r requirements.txt

venv-test: venv
	$(VENV)/bin/pip3 install -r test-requirements.txt
