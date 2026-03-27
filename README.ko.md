# codex-openai-adapter

FastAPI 기반 어댑터로, Codex/ChatGPT 기반 인증을 사용하면서 OpenAI 호환 및 Ollama 호환 엔드포인트를 제공합니다.

이 저장소는 실제로 동작합니다. 목업이나 placeholder 프로젝트가 아닙니다.  
tool 사용을 지원하며, 실제 에이전트 코딩 워크플로우에 실사용할 수 있는 수준입니다. [Cline](https://cline.bot/)에서 "OpenAI Compatible" 및 "Ollama" API Provider 설정 모두에서 간단한 동작 확인을 마쳤습니다.  
다른 코딩 에이전트에서는 아직 테스트하지 않았지만, 표준 OpenAI 호환 또는 Ollama 호환 연결을 지원하는 클라이언트라면 대체로 동작할 가능성이 높습니다.  
물론, 일반적인 비에이전트 용도의 chat/completions API로도 문제없이 사용할 수 있습니다.  
Windows와 Apple Silicon Mac에서 테스트되었습니다.

**필수 전제: 이 어댑터를 실행하기 전에, 해당 기기에 Codex가 먼저 설치되어 있고 로그인까지 완료되어 있어야 하며, 유효한 `auth.json` 파일이 이미 존재해야 합니다. 기본 경로는 `~/.codex/auth.json`입니다. 이 파일이 없으면 어댑터가 Codex backend에 인증할 수 없습니다.**

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

**중요: 여기서의 `API_KEY`는 OpenAI API key가 아닙니다. 이 어댑터로의 접속을 보호하기 위해 사용자가 임의로 정하는 비밀번호 역할의 토큰입니다. 로컬에서만 사용할 경우 기본적으로 설정하실 필요가 없습니다.**

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

모델 목록은 Codex backend에서 동적으로 불러옵니다. 따라서 `gpt-5.4`와 `gpt-5.3-codex` 외의 다른 모델도 나타날 수 있으며, `/models`, `/v1/models`, `/api/tags`에 표시되는 정확한 모델명을 입력하면 사용할 수 있는 경우가 많습니다.

추후 Codex 서버에 새 모델이 추가되면, 별도의 어댑터 업데이트 없이 여기서 바로 노출되고 사용할 수 있게 될 수도 있습니다.

호환성을 위해, 어댑터는 동적으로 발견된 모든 base model에 대해 `-low`, `-medium`, `-high`, `-xhigh` suffix alias도 함께 생성합니다. 다만 이 프로젝트는 기본적으로 `gpt-5.4`와 `gpt-5.3-codex`를 중심으로 설계되고 테스트되었기 때문에, 그 외 모델의 동작은 best-effort 수준이며 보장되지 않습니다. 특히 `reasoning_effort`, `think`, `temperature` 및 관련 호환성 동작은 비보장입니다. suffix alias 역시 `gpt-5.4`와 `gpt-5.3-codex`에서만 신뢰 가능한 것으로 보는 편이 좋습니다.

클라이언트가 reasoning 제어를 명시적으로 지원한다면:

- OpenAI 호환 라우트에서는 `reasoning_effort` 사용
- Ollama 호환 라우트에서는 `think` 사용

클라이언트가 이 파라미터들을 지원하지 않으면, 모델명 뒤에 suffix를 붙여 reasoning level을 직접 선택할 수 있습니다.

예시:

- `gpt-5.4-low`
- `gpt-5.4-high`
- `gpt-5.3-codex-xhigh`

상대적으로 검증된 모델명:

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
- `*-none` suffix 별칭은 없습니다. `none`을 명시적으로 사용해야 한다면 OpenAI 호환 라우트에서는 `reasoning_effort: "none"`을 보내고, Ollama 호환 라우트에서는 `think: false` 또는 `think: "none"`을 보내면 됩니다
- 현재 노출되는 전체 모델 목록은 동적으로 바뀔 수 있으므로, README의 정적 목록 대신 `/models`, `/v1/models`, `/api/tags`에서 직접 확인하는 것이 맞습니다
- `/models`, `/v1/models`, `/api/tags`의 raw JSON이 보기 불편하다면, `/chat-test`를 열어서 현재 모델 목록을 간단한 GUI로 더 쉽게 확인할 수 있습니다

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
- `temperature`는 effective reasoning이 `none`일 때의 `gpt-5.4` base-model 요청에서만 동작 보장을 합니다. 다른 동적 모델들도 현재는 같은 일반 규칙으로 처리되지만, 그 동작은 best-effort이며 보장되지 않습니다.
