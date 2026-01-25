import os
import json
import requests

DART_API_KEY = os.environ["DART_API_KEY"]
CORP_CODE = os.environ["DART_CORP_CODE"]  # 예: 01803635
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state.json"


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_rcp_no": None}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def get_latest_disclosure():
    """
    DART list API 호출 결과:
    - status == "000": 정상 (list가 비어있을 수도 있음)
    - status == "013": 조회된 데이터 없음 (새 공시 없음) => 정상으로 처리
    - 그 외: 실제 에러로 간주
    """
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": CORP_CODE,
        "page_no": 1,
        "page_count": 1,
    }

    res = requests.get(url, params=params, timeout=20).json()
    status = res.get("status")

    # ✅ 정상 + 데이터 있을 수도/없을 수도
    if status == "000":
        items = res.get("list", [])
        return items[0] if items else None

    # ✅ 새 공시 없음(0건) = 정상 종료
    if status == "013":
        return None

    # ❌ 그 외는 진짜 에러
    raise RuntimeError(f"DART API error: {res}")


def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()


def main():
    state = load_state()
    latest = get_latest_disclosure()

    # ✅ 새 공시 없음이면 성공 종료 (exit code 0)
    if not latest:
        print("No new disclosure.")
        return

    rcp_no = latest["rcp_no"]
    if rcp_no == state.get("last_rcp_no"):
        print("No new disclosure.")
        return

    state["last_rcp_no"] = rcp_no
    save_state(state)

    link = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}"
    msg = f"📌 {latest['report_nm']}\n{link}"
    send_telegram(msg)
    print("Sent.")


if __name__ == "__main__":
    main()
