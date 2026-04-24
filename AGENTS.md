# AI 에이전트 통합 가이드 (AI Agent Integration Guide)

이 문서는 **Codex OpenAI/Ollama Proxy**를 AI 코딩 에이전트(예: Cline, Roo Code, Continue 등)에 연결하고 최적으로 활용하기 위한 가이드를 제공합니다.

## 🚀 개요

이 프록시는 Codex 백엔드 인증을 사용하면서, 에이전트가 기대하는 표준 **OpenAI API** 또는 **Ollama API** 규격으로 요청과 응답을 변환하여 전달합니다. 이를 통해 최신 고성능 모델을 기존의 에이전트 워크플로우에서 그대로 사용할 수 있습니다.

## 🛠️ 에이전트 설정 방법

에이전트 설정에서 다음 두 가지 방식 중 하나를 선택하여 연결하십시오.

### 1. OpenAI 호환 모드 (추천)
가장 표준적인 설정이며, 대부분의 에이전트에서 안정적으로 동작합니다.

- **API Provider**: `OpenAI Compatible`
- **Base URL**: `http://localhost:8888/v1`
- **API Key**: (설정된 경우) `.env`의 `API_KEY` 값 / (설정되지 않은 경우) 아무 문자열이나 입력
- **Model ID**: `gpt-5.4` 또는 `gpt-5.3-codex`

### 2. Ollama 호환 모드
Ollama 스타일의 인터페이스를 선호하거나, Ollama 전용 설정을 사용하는 에이전트에게 적합합니다.

- **API Provider**: `Ollama`
- **Base URL**: `http://localhost:8888`
- **Model ID**: `gpt-5.4` 또는 `gpt-5.3-codex`

---

## 🧠 모델 및 추론(Reasoning) 제어

이 프록시는 모델의 추론 강도를 세밀하게 조절할 수 있는 기능을 제공합니다.

### 추론 레벨 (Reasoning Levels)
- `low`: 빠른 응답, 단순한 작업
- `medium`: 균형 잡힌 성능 (기본값)
- `high`: 복잡한 논리 구조 및 코드 분석
- `xhigh`: 최고 수준의 추론, 매우 난해한 버그 수정 및 아키텍처 설계

### 제어 방법
에이전트가 다음 파라미터를 지원하는 경우 자동으로 적용됩니다:
- **OpenAI**: `reasoning_effort` 파라미터 (`low`, `medium`, `high`)
- **Ollama**: `think` 파라미터 (`low`, `medium`, `high`, `xhigh`)

파라미터를 지원하지 않는 에이전트의 경우, **모델명 뒤에 suffix**를 붙여 강제할 수 있습니다:
- 예: `gpt-5.4-high`, `gpt-5.3-codex-xhigh`

---

## ✨ 주요 기능 및 에이전트 활용 팁

### 🛠️ 도구 사용 (Tool Use/Function Calling)
본 프록시는 표준 도구 호출 규격을 지원합니다. 에이전트가 파일을 읽고, 쓰고, 명령어를 실행하는 모든 워크플로우가 정상적으로 동작합니다.

### ⚡ 스트리밍 지원
`stream: true` 요청을 완벽하게 지원하여, 에이전트가 응답을 실시간으로 생성하는 과정을 확인할 수 있습니다.

### 📈 성능 최적화 제안
- **단순 수정/리팩토링**: `gpt-5.4-low` 또는 `medium`을 사용하여 속도를 높이십시오.
- **심층 분석/어려운 버그 수정**: `gpt-5.4-high` 또는 `xhigh`를 설정하여 정확도를 높이십시오.
- **모델 확인**: 현재 사용 가능한 전체 모델 목록은 `http://localhost:8888/chat-test` GUI 페이지에서 확인할 수 있습니다.

## ⚠️ 주의사항
- **인증 필수**: 프록시 실행 전 반드시 Codex가 설치되어 있고 `~/.codex/auth.json` 파일이 유효해야 합니다.
- **포트 충돌**: 기본 포트 `8888`이 사용 중이라면 `.env` 파일에서 `PORT`를 변경하십시오.