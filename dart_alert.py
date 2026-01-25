import os, json, requests

DART_API_KEY = os.environ["DART_API_KEY"]
CORP_CODE = os.environ["DART_CORP_CODE"]  # 01803635
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
    if res.get("status") != "000":
        raise RuntimeError(f"DART API error: {res}")
    return res["list"][0]

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()

def main():
    state = load_state()
    latest = get_latest_disclosure()

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
