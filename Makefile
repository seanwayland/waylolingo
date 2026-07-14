SHELL := /bin/bash

.DEFAULT_GOAL := all

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn

TRANSLATOR_BACKEND ?= ollama
QWEN_MODEL ?= qwen2.5:7b-instruct
OLLAMA_BASE_URL ?= http://127.0.0.1:11434
OLLAMA_TIMEOUT_SECONDS ?= 60
OLLAMA_NUM_PARALLEL ?= 4
OLLAMA_MAX_QUEUE ?= 8
OLLAMA_KEEP_ALIVE ?= 30m
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: all help setup install-ollama ensure-ollama-running start-ollama stop-ollama pull-model build test verify run clean

all: setup verify

help:
	@printf "Targets:\n"
	@printf "  make             Run the default local workflow: setup + verify\n"
	@printf "  make setup       Create venv, install deps, optionally pull Qwen via Ollama\n"
	@printf "  make install-ollama  Install Ollama for the current host OS\n"
	@printf "  make start-ollama  Start Ollama service/process\n"
	@printf "  make stop-ollama   Stop Ollama service/process\n"
	@printf "  make ensure-ollama-running  Start/check local Ollama server\n"
	@printf "  make pull-model  Pull the configured Qwen model with Ollama\n"
	@printf "  make build       Refresh package, compile sources, and sync pinyin audio\n"
	@printf "  make test        Run focused test suite\n"
	@printf "  make verify      Build and test the backend\n"
	@printf "  make run         Start FastAPI locally\n"
	@printf "\n"
	@printf "Defaults:\n"
	@printf "  default goal=all\n"
	@printf "  TRANSLATOR_BACKEND=$(TRANSLATOR_BACKEND)\n"
	@printf "  QWEN_MODEL=$(QWEN_MODEL)\n"
	@printf "  OLLAMA_NUM_PARALLEL=$(OLLAMA_NUM_PARALLEL)\n"
	@printf "  OLLAMA_MAX_QUEUE=$(OLLAMA_MAX_QUEUE)\n"
	@printf "  OLLAMA_KEEP_ALIVE=$(OLLAMA_KEEP_ALIVE)\n"
	@printf "\n"
	@printf "Fallback example:\n"
	@printf "  TRANSLATOR_BACKEND=rot13 make all\n"
	@printf "  TRANSLATOR_BACKEND=rot13 make run\n"

$(PYTHON):
	python3 -m venv $(VENV)

setup: $(PYTHON)
	$(PIP) install -e '.[dev]'
	@if [[ "$(TRANSLATOR_BACKEND)" == "ollama" ]]; then \
		if ! command -v ollama >/dev/null 2>&1; then \
			$(MAKE) install-ollama; \
		fi; \
		command -v ollama >/dev/null 2>&1 || { \
			echo "Ollama is still unavailable after install attempt."; \
			echo "On macOS 13, Homebrew ollama may be unsupported."; \
			echo "Options:"; \
			echo "  1) Upgrade to macOS Sonoma or newer and rerun make all"; \
			echo "  2) Use fallback backend: TRANSLATOR_BACKEND=rot13 make all"; \
			echo "  3) Run ollama on another machine (for example Ubuntu EC2) and set OLLAMA_BASE_URL"; \
			exit 1; \
		}; \
		$(MAKE) ensure-ollama-running; \
		ollama pull "$(QWEN_MODEL)"; \
	fi

install-ollama:
	@if command -v ollama >/dev/null 2>&1; then \
		echo "Ollama is already installed"; \
	elif [[ "$$(uname -s)" == "Darwin" ]]; then \
		major="$$(sw_vers -productVersion | cut -d. -f1)"; \
		if [[ "$$major" -lt 14 ]]; then \
			echo "Automatic Ollama install is not supported on this macOS version ($$(sw_vers -productVersion))."; \
			echo "Homebrew ollama currently requires macOS Sonoma or newer."; \
			echo "Upgrade macOS or run: TRANSLATOR_BACKEND=rot13 make all"; \
			exit 1; \
		fi; \
		command -v brew >/dev/null 2>&1 || { echo "Homebrew is required to install Ollama on macOS: https://brew.sh"; exit 1; }; \
		brew install ollama; \
	elif [[ "$$(uname -s)" == "Linux" ]]; then \
		curl -fsSL https://ollama.com/install.sh | sh; \
	else \
		echo "Unsupported OS for automatic Ollama installation: $$(uname -s)"; \
		exit 1; \
	fi

ensure-ollama-running:
	@command -v ollama >/dev/null 2>&1 || { echo "Ollama CLI not found. Run: make install-ollama"; exit 1; }
	@if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then \
		echo "Ollama server is already running"; \
	elif [[ "$$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then \
		echo "Starting Ollama with Homebrew service..."; \
		echo "Note: brew service ignores Makefile concurrency env vars. To apply OLLAMA_NUM_PARALLEL/OLLAMA_MAX_QUEUE, run ollama serve manually."; \
		brew services start ollama >/dev/null; \
		sleep 2; \
		curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || { echo "Ollama service did not start. Try: brew services restart ollama"; exit 1; }; \
	else \
		echo "Starting Ollama in background..."; \
		OLLAMA_NUM_PARALLEL=$(OLLAMA_NUM_PARALLEL) OLLAMA_MAX_QUEUE=$(OLLAMA_MAX_QUEUE) nohup ollama serve >/tmp/ollama-serve.log 2>&1 & \
		sleep 2; \
		curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1 || { echo "Could not start Ollama server. Check /tmp/ollama-serve.log"; exit 1; }; \
	fi

start-ollama:
	@$(MAKE) ensure-ollama-running

stop-ollama:
	@if [[ "$$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1 && brew services list | grep -q '^ollama\s'; then \
		echo "Stopping Ollama Homebrew service..."; \
		brew services stop ollama >/dev/null || true; \
	else \
		echo "Stopping Ollama process..."; \
		pkill -f 'ollama serve' >/dev/null 2>&1 || true; \
	fi
	@if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then \
		echo "Ollama still appears to be running on 127.0.0.1:11434"; \
		exit 1; \
	else \
		echo "Ollama stopped"; \
	fi

pull-model:
	@if ! command -v ollama >/dev/null 2>&1; then \
		$(MAKE) install-ollama; \
	fi
	@$(MAKE) ensure-ollama-running
	ollama pull "$(QWEN_MODEL)"

build: $(PYTHON)
	$(PIP) install -e '.[dev]'
	$(PYTHON) -m compileall src
	$(PYTHON) scripts/download_pinyin_audio.py

test: $(PYTHON)
	$(PYTHON) -m pytest tests/test_api.py tests/test_translator.py

verify: build test

run: $(PYTHON)
	TRANSLATOR_BACKEND=$(TRANSLATOR_BACKEND) \
	OLLAMA_MODEL=$(QWEN_MODEL) \
	OLLAMA_BASE_URL=$(OLLAMA_BASE_URL) \
	OLLAMA_TIMEOUT_SECONDS=$(OLLAMA_TIMEOUT_SECONDS) \
	OLLAMA_NUM_PARALLEL=$(OLLAMA_NUM_PARALLEL) \
	OLLAMA_MAX_QUEUE=$(OLLAMA_MAX_QUEUE) \
	OLLAMA_KEEP_ALIVE=$(OLLAMA_KEEP_ALIVE) \
	$(UVICORN) mandarin_translator.api:app --reload --host $(HOST) --port $(PORT)

clean:
	rm -rf .pytest_cache
	rm -rf src/mandarin_translator/__pycache__ tests/__pycache__