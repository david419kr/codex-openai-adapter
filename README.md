한국어 README: [README.ko.md](./README.ko.md)

# codex-openai-adapter

FastAPI-based adapter that exposes OpenAI-compatible and Ollama-compatible endpoints while using Codex/ChatGPT-backed authentication.

This repository is actually working. It is not a mockup or placeholder project.  
It supports tool use and is practical for real [Cline](https://cline.bot/) agentic coding workflows, with both "OpenAI Compatible" and "Ollama" API Provider configuration briefly verified to work.  
Other coding agents have not been tested here, but clients that support standard OpenAI-compatible or Ollama-compatible connections will likely work as well.  
Of course, it also works fine as a normal chat/completions API for general non-agent use.  
It has been tested on Windows and Apple Silicon Mac.

## Run

Fresh setup:

Linux/macOS:

```bash
./install-adapter.sh
```

Windows:

```bat
install-adapter.bat
```

The install script:

- checks whether `uv` is already installed
- installs `uv` first if it is missing
- creates `.venv` then installs everything needed

Start the adapter after installation:

Linux/macOS:

```bash
./run-adapter.sh
```

Windows:

```bat
run-adapter.bat
```

Test page:

```text
http://localhost:8888/chat-test
```

If you changed `PORT`, open the same path on that port instead.

The adapter reads configuration from `.env` file if it exists.
If you do not provide a `.env` file:

- the adapter listens on `http://localhost:8888`
- incoming requests do not require an API key

## Configuration

`.env` is optional. If you do not create one, the adapter uses the built-in defaults above.

Example `.env` with custom settings:

```env
PORT=8888
CODEX_AUTH_PATH=~/.codex/auth.json
API_KEY=ENTER_YOUR_DESIRED_API_KEY_HERE
DEBUG=false
```

If you want to mirror Ollama's default port exactly, set:

```env
PORT=11434
```

That is useful when you want clients to talk to the adapter on the same port they normally use for Ollama.

If you set `DEBUG=true`, the adapter writes request/response trace logs for the backend-communicating endpoints to `logs/debug.log`.

Rules:

1. If `API_KEY` is set, `/health` and `/api/tags` stay public and the rest require that key.
2. If `API_KEY` is not set, the adapter allows unauthenticated access. This is the default when you have no `.env` override.

## Endpoint Policy

Public when `API_KEY` is configured:

- `GET /health`
- `GET /api/tags`

Protected when `API_KEY` is configured:

- `GET /models`
- `GET /v1/models`
- `GET /api/version`
- `POST /chat/completions`
- `POST /v1/chat/completions`
- `POST /api/chat`
- `POST /api/generate`

## Implemented Endpoints

OpenAI-compatible:

- `GET /models`
- `GET /v1/models`
- `POST /chat/completions`
- `POST /v1/chat/completions`

Ollama-compatible:

- `GET /health`
- `GET /api/version`
- `GET /api/tags`
- `POST /api/chat`
- `POST /api/generate`

## Model Aliases

Model list is loaded dynamically from the Codex backend. Models other than `gpt-5.4` and `gpt-5.3-codex` may also appear and can often be used as long as you specify the exact model name shown by `/models`, `/v1/models`, or `/api/tags`.

If new Codex models are added later on OpenAI Codex server, they may become available here without a separate adapter update.

For compatibility, the adapter also generates `-low`, `-medium`, `-high`, and `-xhigh` suffix aliases for every dynamically discovered base model. However, this project is primarily designed and tested around `gpt-5.4` and `gpt-5.3-codex`, so behavior for other models is best-effort only and is not guaranteed, especially for `reasoning_effort`, `think`, `temperature`, and related compatibility details. The suffix aliases should likewise be considered reliable only for `gpt-5.4` and `gpt-5.3-codex`.

If your client supports explicit reasoning controls:

- use `reasoning_effort` on OpenAI-compatible routes
- use `think` on Ollama-compatible routes

If your client does not support those parameters, you can select the reasoning level directly by putting a suffix on the model name.

For example, when using Cline in Ollama mode, `think` is not available, so you can control the reasoning level by selecting a model name such as `gpt-5.4-high` directly.

Examples:

- `gpt-5.4-low`
- `gpt-5.4-high`
- `gpt-5.3-codex-xhigh`

Well-tested model names:

- `gpt-5.4`
- `gpt-5.4-low`
- `gpt-5.4-medium`
- `gpt-5.4-high`
- `gpt-5.4-xhigh`
- `gpt-5.3-codex`
- `gpt-5.3-codex-low`
- `gpt-5.3-codex-medium`
- `gpt-5.3-codex-high`
- `gpt-5.3-codex-xhigh`

Notes:

- the suffix-free names `gpt-5.4` and `gpt-5.3-codex` use the base model without forcing a suffix-based reasoning level
- the suffix variants force `low`, `medium`, `high`, or `xhigh`
- there is no `*-none` suffix alias; if you need explicit `none`, send `reasoning_effort: "none"` on OpenAI-compatible routes or `think: false` / `think: "none"` on Ollama-compatible routes
- the full currently exposed model list is dynamic, so check `/models`, `/v1/models`, or `/api/tags` instead of relying on a hardcoded list in this README
- if the raw JSON from `/models`, `/v1/models`, or `/api/tags` is hard to scan, loading `/chat-test` might be an easier way to inspect the current model list in a simple GUI

## Quick Examples

Health check:

```bash
curl http://localhost:8888/health
```

OpenAI-compatible request:

```bash
curl -X POST http://localhost:8888/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ENTER_YOUR_DESIRED_API_KEY_HERE" \
  -d '{
    "model": "gpt-5.4",
    "reasoning_effort": "medium",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

OpenAI-compatible streaming request:

```bash
curl -N -X POST http://localhost:8888/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ENTER_YOUR_DESIRED_API_KEY_HERE" \
  -d '{
    "model": "gpt-5.4",
    "stream": true,
    "messages": [
      {"role": "user", "content": "Stream a short reply"}
    ]
  }'
```

Ollama-compatible request:

```bash
curl -X POST http://localhost:8888/api/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ENTER_YOUR_DESIRED_API_KEY_HERE" \
  -d '{
    "model": "gpt-5.4",
    "think": "high",
    "prompt": "Hello!"
  }'
```

Ollama-compatible chat request:

```bash
curl -X POST http://localhost:8888/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ENTER_YOUR_DESIRED_API_KEY_HERE" \
  -d '{
    "model": "gpt-5.4",
    "think": "high",
    "messages": [
      {"role": "user", "content": "Hello!"}
    ]
  }'
```

## Validation

Current test suite:

```bash
uv run --extra dev pytest
```

## Notes

- Ollama-compatible requests accept an optional `think` parameter: `true`, `false`, `none`, `low`, `medium`, `high`, `xhigh`. `true` maps to `medium`, and `false` and `none` are treated the same.
- `temperature` is guaranteed only for `gpt-5.4` base-model requests when effective reasoning is `none`. Other dynamically discovered models currently follow the same general rule on a best-effort basis, but that behavior is not guaranteed.
