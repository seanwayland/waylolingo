# Mandarin Translator Prototype

This is a minimal FastAPI prototype for the structured conversation schema.

The app supports two translator backends:

- `ollama`: local Qwen inference through an Ollama server
- `rot13`: deterministic placeholder output for local development fallback

## Workflow

Primary commands:

```bash
make setup
make build
make run
make test
make verify
```

The Make workflow defaults to `TRANSLATOR_BACKEND=ollama`.
Use `TRANSLATOR_BACKEND=rot13` only when you want the placeholder translator explicitly.

Shell wrappers in `scripts/` call those same targets:

```bash
./scripts/setup.sh
./scripts/build.sh
./scripts/run.sh
./scripts/test.sh
./scripts/verify.sh
```

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
uvicorn mandarin_translator.api:app --reload
```

## Ollama setup

To use local Qwen instead of the placeholder translator:

```bash
brew install ollama
ollama serve
TRANSLATOR_BACKEND=ollama make setup
TRANSLATOR_BACKEND=ollama make run
```

You can also pull the configured model explicitly:

```bash
QWEN_MODEL=qwen2.5:7b-instruct ./scripts/pull-model.sh
```

Environment variables:

- `TRANSLATOR_BACKEND`: `rot13` or `ollama`
- `OLLAMA_MODEL`: model tag to load, default `qwen2.5:7b-instruct`
- `OLLAMA_BASE_URL`: Ollama server URL, default `http://127.0.0.1:11434`
- `OLLAMA_TIMEOUT_SECONDS`: request timeout, default `60`

## Local And LAN Access

The run script defaults to binding the API server on `0.0.0.0:8000`.

You can set machine-specific host and port values in a local config file:

```bash
cp .env.local.example .env.local
```

Then edit `.env.local` on your machine, for example:

```bash
HOST="192.168.1.231"
PORT="8000"
```

`.env.local` is ignored by git so local network details are not committed.

Binding to `0.0.0.0` means the server listens on all network interfaces, including localhost.

From the same machine, these URLs work:

- `http://localhost:8000/docs`
- `http://127.0.0.1:8000/docs`

From another device on your LAN, use this machine's IP address:

- `http://YOUR_LOCAL_IP:8000/docs`

You can still override host and port when starting the server:

```bash
HOST=127.0.0.1 PORT=8000 ./scripts/run.sh
```

## Example request

```bash
curl -X POST http://127.0.0.1:8000/translate \
  -H 'Content-Type: application/json' \
  -d '{"text": "What time is it?"}'
```

## Example response

```json
{
  "conversation": [
    {
      "language": "mandarin",
      "language_code": "zh-CN",
      "english": ["what", "time", "is", "it"],
      "phonetic": ["jung", "gvzr", "vf", "vg"],
      "symbols": ["jung", "gvzr", "vf", "vg"]
    }
  ]
}
```