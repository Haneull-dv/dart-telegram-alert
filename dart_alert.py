import os
import json
import requests

DART_API_KEY = os.environ["DART_API_KEY"]
CORP_CODE = os.environ["DART_CORP_CODE"]
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
    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": CORP_CODE,
        "page_no": 1,
        "page_count": 1,
    }

    res = requests.get(url, params=params, timeout=20).json()
    status = res.get("status")

    if status == "000":
        items = res.get("list", [])
        return items[0] if items else None

    if status == "013":
        return None

    raise RuntimeError(f"DART API error: {res}")


def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }

    r = requests.post(url, json=payload, timeout=20)

    # 디버깅용 로그
    print("Telegram status:", r.status_code)
    print("Telegram response:", r.text)

    r.raise_for_status()


def main():
    state = load_state()
    latest = get_latest_disclosure()

    # 🔥 공시 없으면 테스트 메시지 발송
    if not latest:
        send_telegram("🧪 [TEST] 스케줄 정상 작동 중 (공시 없음)")
        print("No new disclosure. Test message sent.")
        return

    rcp_no = latest["rcp_no"]

    # 🔥 새 공시가 아니면 테스트 메시지 발송
    if rcp_no == state.get("last_rcp_no"):
        send_telegram("🧪 [TEST] 스케줄 정상 작동 중 (새 공시 없음)")
        print("No new disclosure. Test message sent.")
        return

    # ✅ 새 공시 발견
    state["last_rcp_no"] = rcp_no
    save_state(state)

    link = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}"
    msg = f"📌 {latest['report_nm']}\n{link}"

    send_telegram(msg)
    print("New disclosure sent.")


if __name__ == "__main__":
    main()
