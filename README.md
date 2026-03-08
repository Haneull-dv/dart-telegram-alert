📢 DART 공시 텔레그램 알림 봇

금융감독원 DART 공시를 주기적으로 조회하여, 새 공시가 올라올 때 텔레그램으로 알림을 보내는 자동화 봇입니다.
GitHub Actions를 이용해 장중 시간(KST)에만 5분 간격으로 자동 실행되도록 구성되어 있습니다.

---

## 구조

```text
.
├─ dart-telegram-alert/
│  └─ dart_alert.py        # 실제 알림 스크립트
├─ .github/
│  └─ workflows/
│     └─ dart_telegram_alert.yml   # GitHub Actions 워크플로
├─ state.json              # 마지막으로 알림 보낸 공시 rcp_no 저장
└─ README.md
```

---

## 동작 개요

1. `dart_alert.py`가 DART Open API를 호출해 **특정 회사의 최신 공시**를 조회합니다.
2. `state.json`에 저장된 마지막 공시의 `rcp_no`와 비교해 **새 공시인지 판단**합니다.
3. 새 공시일 경우, 텔레그램 봇으로 **공시 제목 + 링크**를 전송합니다.
4. 정상 전송 후 `state.json`의 `last_rcp_no`를 최신 값으로 업데이트합니다.

스크립트는 **KST 기준**으로 동작하며, `MODE`에 따라 로그 전송 방식이 달라집니다.

---

## 환경 변수 / GitHub 시크릿

GitHub Actions에서 아래 네 개 값을 **시크릿**으로 설정해 사용합니다.

- `DART_API_KEY` : DART Open API 인증키
- `DART_CORP_CODE` : 조회 대상 회사 고유번호
- `TELEGRAM_BOT_TOKEN` : 텔레그램 봇 토큰
- `TELEGRAM_CHAT_ID` : 알림을 받을 채팅 ID

워크플로(`.github/workflows/dart_telegram_alert.yml`)에서 이 값들을 `env`로 주입하여 `dart_alert.py`가 `os.environ`으로 읽어 사용합니다.

---

## MODE 설정 (`test` / `normal`)

`MODE` 환경 변수에 따라 행동이 달라집니다.

- `test`
  - DART 조회 결과가 **있어도/없어도 매번** 텔레그램으로 **상세 로그**까지 전송합니다.
  - `state.json`을 업데이트하지 않습니다. (테스트용)
- `normal`
  - **새 공시가 있을 때만** 공시 제목과 링크를 텔레그램으로 보냅니다.
  - 새 공시가 아니면 조용히 종료합니다.
  - 새 공시를 보낸 경우에만 `state.json`의 `last_rcp_no`를 갱신합니다.

GitHub Actions에서는:

- 스케줄 실행: 기본적으로 `MODE=normal`
- 수동 실행(`workflow_dispatch`): 입력값으로 `mode`를 받으며, `test`로 지정하면 테스트 모드로 동작합니다.

---

## GitHub Actions 워크플로

워크플로 파일: `.github/workflows/dart_telegram_alert.yml`

- **트리거**
  - `workflow_dispatch` : 수동 실행 + `delay_minutes`, `mode` 입력 지원
  - `schedule` : 장중 시간대에 5분 간격으로 자동 실행
- **주요 단계**
  - Checkout 레포지토리
  - Python 3.11 설정 후 `requests` 설치
  - (필요 시) 지정된 분 만큼 대기
  - `python dart-telegram-alert/dart_alert.py` 실행
  - 스케줄 실행(normal 모드) 시 `state.json` 변경 내용을 커밋 후 `main` 브랜치에 푸시

GitHub에서 Actions 탭으로 들어가면 실행 이력과 로그를 확인할 수 있습니다.

---

## 로컬에서 테스트 실행하기

1. 파이썬 환경 준비

```bash
pip install requests
```

2. 필요한 환경 변수 설정 (예시 – PowerShell)

```bash
$env:DART_API_KEY="..."
$env:DART_CORP_CODE="..."
$env:TELEGRAM_BOT_TOKEN="..."
$env:TELEGRAM_CHAT_ID="..."
$env:MODE="test"  # 또는 normal
```

3. 스크립트 실행

```bash
python dart-telegram-alert/dart_alert.py
```

`MODE=test`로 실행하면, 실제 GitHub Actions와 동일한 로직으로 동작하면서도, 매번 결과와 상세 로그를 텔레그램으로 보내기 때문에 동작 확인에 유용합니다.

---

## 참고

- `state.json`은 단순히 마지막으로 알림 보낸 공시의 `rcp_no`만 저장합니다.
- 복수 공시를 한 번에 처리하거나, 여러 회사에 대해 확장하고 싶다면 `state.json` 구조와 조회 로직을 변경하면 됩니다.