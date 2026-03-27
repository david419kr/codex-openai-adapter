# codex-openai-adapter

FastAPI 기반 어댑터로, Codex/ChatGPT 기반 인증을 사용하면서 OpenAI 호환 및 Ollama 호환 엔드포인트를 제공합니다.

이 저장소는 실제로 동작합니다. 목업이나 placeholder 프로젝트가 아닙니다.  
tool 사용을 지원하며, 실제 [Cline](https://cline.bot/) 에이전트 코딩 워크플로우에 실사용할 수 있는 수준입니다. "OpenAI Compatible" 및 "Ollama" API Provider 설정 모두에서 간단한 동작 확인을 마쳤습니다.  
다른 코딩 에이전트에서는 아직 테스트하지 않았지만, 표준 OpenAI 호환 또는 Ollama 호환 연결을 지원하는 클라이언트라면 대체로 동작할 가능성이 높습니다.  
물론, 일반적인 비에이전트 용도의 chat/completions API로도 문제없이 사용할 수 있습니다.  
Windows와 Apple Silicon Mac에서 테스트되었습니다.

## 실행

처음 설정:

Linux/macOS:

```bash
./install-adapter.sh
```

Windows:

```bat
install-adapter.bat
```

설치 스크립트가 하는 일:

- `uv`가 이미 설치되어 있는지 확인
- 설치되어 있지 않으면 먼저 `uv` 설치
- `.venv`를 만든 뒤 필요한 의존성 전체 설치

설치 후 어댑터 실행:

Linux/macOS:

```bash
./run-adapter.sh
```

Windows:

```bat
run-adapter.bat
```

테스트 페이지:

```text
http://localhost:8888/chat-test
```

`PORT`를 변경했다면 해당 포트의 같은 경로로 접속하면 됩니다.

어댑터는 `.env` 파일이 있으면 해당 파일에서 설정을 읽습니다.
`.env` 파일을 제공하지 않으면:

- 어댑터는 `http://localhost:8888`에서 실행됩니다
- 들어오는 요청에 API key가 필요하지 않습니다

## 설정

`.env`는 선택 사항입니다. 만들지 않으면 위의 기본값을 사용합니다.

커스텀 설정이 포함된 `.env` 예시:

```env
PORT=8888
CODEX_AUTH_PATH=~/.codex/auth.json
API_KEY=ENTER_YOUR_DESIRED_API_KEY_HERE
DEBUG=false
```

Ollama 기본 포트를 그대로 맞추고 싶다면:

```env
PORT=11434
```

이렇게 하면 클라이언트가 원래 Ollama에 연결하던 것과 같은 포트로 어댑터에 연결할 수 있습니다.

`DEBUG=true`로 설정하면, backend와 통신하는 엔드포인트의 요청/응답 trace 로그를 `logs/debug.log`에 기록합니다.

규칙:

1. `API_KEY`가 설정되어 있으면 `/health`와 `/api/tags`는 공개 상태를 유지하고, 나머지는 해당 key가 필요합니다.
2. `API_KEY`가 설정되어 있지 않으면 인증 없이 접근할 수 있습니다. `.env`로 별도 override하지 않았을 때의 기본 동작입니다.

## 엔드포인트 정책

`API_KEY`가 설정되어 있을 때 공개:

- `GET /health`
- `GET /api/tags`

`API_KEY`가 설정되어 있을 때 보호:

- `GET /models`
- `GET /v1/models`
- `GET /api/version`
- `POST /chat/completions`
- `POST /v1/chat/completions`
- `POST /api/chat`
- `POST /api/generate`

## 구현된 엔드포인트

OpenAI 호환:

- `GET /models`
- `GET /v1/models`
- `POST /chat/completions`
- `POST /v1/chat/completions`

Ollama 호환:

- `GET /health`
- `GET /api/version`
- `GET /api/tags`
- `POST /api/chat`
- `POST /api/generate`

## 모델 별칭

클라이언트가 reasoning 제어를 명시적으로 지원한다면:

- OpenAI 호환 라우트에서는 `reasoning_effort` 사용
- Ollama 호환 라우트에서는 `think` 사용

클라이언트가 이 파라미터들을 지원하지 않으면, 모델명 뒤에 suffix를 붙여 reasoning level을 직접 선택할 수 있습니다.

예를 들어 Cline을 Ollama 모드로 사용할 때는 `think`를 사용할 수 없으므로, `gpt-5.4-high` 같은 모델명을 직접 선택해서 reasoning level을 제어할 수 있습니다.

예시:

- `gpt-5.4-low`
- `gpt-5.4-high`
- `gpt-5.3-codex-xhigh`

노출되는 모델명:

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

참고:

- suffix가 없는 `gpt-5.4`와 `gpt-5.3-codex`는 suffix 기반 reasoning level을 강제하지 않는 base 모델입니다
- suffix가 붙은 variant는 `low`, `medium`, `high`, `xhigh`를 강제합니다
- `gpt-5.4-none` 별칭은 없습니다. `none`을 명시적으로 사용해야 한다면 OpenAI 호환 라우트에서는 `reasoning_effort: "none"`을 보내고, Ollama 호환 라우트에서는 `think: false` 또는 `think: "none"`을 보내면 됩니다

## 빠른 예시

헬스 체크:

```bash
curl http://localhost:8888/health
```

OpenAI 호환 요청:

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

OpenAI 호환 스트리밍 요청:

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

Ollama 호환 요청:

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

Ollama 호환 chat 요청:

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

## 검증

현재 테스트 스위트:

```bash
uv run --extra dev pytest
```

## 참고

- Ollama 호환 요청은 선택적 `think` 파라미터를 받습니다: `true`, `false`, `none`, `low`, `medium`, `high`, `xhigh`. `true`는 `medium`으로 매핑되고, `false`와 `none`은 동일하게 처리됩니다.
- `temperature`는 effective reasoning이 `none`일 때의 `gpt-5.4` base-model 요청에 한해서만 backend로 전달됩니다.
