import os
import json
import time
import traceback
from datetime import datetime, timezone, timedelta

import requests

# ========= ENV =========

DART_API_KEY = os.environ.get("DART_API_KEY", "")
CORP_CODE = os.environ.get("DART_CORP_CODE", "")

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


# MODE:
# - "test": 항상 결과(있음/없음) + 상세 로그를 텔레그램으로 보냄, state 저장/커밋은 하지 않음
# - "normal": 새 공시일 때만 알림 전송 + state 저장
MODE = os.environ.get("MODE", "normal").lower().strip()

STATE_FILE = "state.json"


# ========= UTIL =========
def now_kst_str():
    kst = timezone(timedelta(hours=9))
    return datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S KST")


def mask(s: str, keep: int = 4) -> str:
    if not s:
        return "(empty)"
    if len(s) <= keep:
        return "*" * len(s)
    return s[:keep] + "…" + "*" * 6


def log(lines: list, msg: str):
    # 콘솔 + 텔레그램용 버퍼에 같이 적재
    print(msg)
    lines.append(msg)


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"last_rcp_no": None}
    return {"last_rcp_no": None}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ========= DART =========
def get_latest_disclosure(lines: list):
    url = "https://opendart.fss.or.kr/api/list.json"
    # 최근 7일간 공시 중에서 첫 페이지(최신순)를 조회
    today = datetime.now(timezone(timedelta(hours=9)))
    bgn_de = (today - timedelta(days=7)).strftime("%Y%m%d")
    end_de = today.strftime("%Y%m%d")
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": CORP_CODE,
        "page_no": 1,
        "page_count": 10,
        "bgn_de": bgn_de,
        "end_de": end_de,
    }

    log(lines, f"🧭 [{now_kst_str()}] DART 조회 시작")
    log(lines, f"🔑 DART_API_KEY: {mask(DART_API_KEY)} / CORP_CODE: {CORP_CODE or '(empty)'}")
    log(lines, f"🌐 GET {url}")
    log(lines, f"🧾 params: {params}")

    t0 = time.time()
    r = requests.get(url, params=params, timeout=20)
    dt = int((time.time() - t0) * 1000)

    log(lines, f"⏱️ DART 응답 시간: {dt}ms")
    log(lines, f"📡 DART HTTP status: {r.status_code}")

    try:
        data = r.json()
    except Exception:
        log(lines, "💥 DART 응답 JSON 파싱 실패")
        log(lines, f"📄 raw: {r.text[:800]}")
        raise

    status = data.get("status")
    msg = data.get("message")
    log(lines, f"📌 DART status={status} message={msg}")

    print(status)
    if status == "000":
        items = data.get("list", []) or []
        log(lines, f"📦 list count: {len(items)}")
        if not items:
            return None

        first = items[0]
        # 핵심 필드만 로그
        #log(lines, f"🧾 latest rcp_no={first.get('rcp_no')} report_nm={first.get('report_nm')}")
        
        for item in items:
            log(lines, f"🧾 latest rcp_no={item.get('rcp_no')} report_nm={item.get('report_nm')}")
        
        return first

    if status == "013":
        log(lines, "🟦 조회된 데이터 없음(013) => 공시 없음으로 처리")
        return None

    # 그 외는 에러로
    raise RuntimeError(f"DART API error: {data}")


# ========= TELEGRAM =========
def send_telegram(lines: list, text: str, tag: str = "SEND"):
    """
    텔레그램 전송은 가능한 한 실패해도 로그를 남기고,
    main에서 예외를 잡아 전체 흐름이 무엇 때문에 죽는지 알 수 있게 함.
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }

    log(lines, f"📨 [{tag}] Telegram 전송 시도")
    log(lines, f"🔐 BOT_TOKEN: {mask(BOT_TOKEN)} / CHAT_ID: {CHAT_ID or '(empty)'}")
    log(lines, f"🌐 POST {url}")

    t0 = time.time()
    try:
        r = requests.post(url, json=payload, timeout=20)
    except Exception as e:
        log(lines, f"💥 Telegram 요청 자체 실패: {repr(e)}")
        raise

    dt = int((time.time() - t0) * 1000)
    log(lines, f"⏱️ Telegram 응답 시간: {dt}ms")
    log(lines, f"📡 Telegram HTTP status: {r.status_code}")
    log(lines, f"📄 Telegram response(앞부분): {r.text[:800]}")

    # raise_for_status()로 죽이지 않고,
    # main에서 상태코드 기반으로 판단하게 한다.
    return r


def chunk_text(s: str, max_len: int = 3500):
    # 텔레그램 메시지 길이 제한 고려 (보수적으로 3500)
    chunks = []
    cur = []
    cur_len = 0
    for line in s.split("\n"):
        add_len = len(line) + 1
        if cur_len + add_len > max_len:
            chunks.append("\n".join(cur))
            cur = [line]
            cur_len = len(line)
        else:
            cur.append(line)
            cur_len += add_len
    if cur:
        chunks.append("\n".join(cur))
    return chunks


def main():
    lines = []
    log(lines, "🚀 DART Telegram Alert 시작")
    log(lines, f"🧩 MODE = {MODE}")
    log(lines, f"🕒 now = {now_kst_str()}")

    # 기본 ENV 유효성 체크
    missing = []
    if not DART_API_KEY:
        missing.append("DART_API_KEY")
    if not CORP_CODE:
        missing.append("DART_CORP_CODE")
    if not BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")

    if missing:
        log(lines, f"❗ ENV 누락: {', '.join(missing)}")
        # 누락이어도 텔레그램 전송은 가능할 수도 있으니(예: DART만 누락)
        # 여기서는 실패 처리
        raise RuntimeError(f"Missing env: {missing}")

    state = load_state()
    log(lines, f"🗂️ last_rcp_no(state) = {state.get('last_rcp_no')}")

    latest = None
    try:
        latest = get_latest_disclosure(lines)
    except Exception as e:
        log(lines, "💥 DART 조회 중 예외 발생")
        log(lines, f"🧨 error: {repr(e)}")
        log(lines, "🧾 traceback:")
        log(lines, traceback.format_exc())
        # 테스트/운영 모두: 에러 로그를 텔레그램으로 보내고 종료
        summary = "❌ DART 조회 실패"
        report_and_exit(lines, summary, exit_code=1)
        return

    # 공시 유무 판단
    if not latest:
        summary = "🟦 결과: 새 공시 없음"
        log(lines, summary)

        # test 모드: 항상 텔레그램으로 전체 로그 발송
        # normal 모드: 기존처럼 "테스트 메시지"를 보내지 않으려면 여기서 return하면 됨
        if MODE == "test":
            report_and_exit(lines, "🧪 [TEST] 새 공시 없음", exit_code=0)
        else:
            # 운영 모드는 조용히 종료 (원하면 여기서도 알림 보낼 수 있음)
            log(lines, "🔕 (normal) 공시 없음 → 알림 전송 생략")
        return

    rcp_no = latest.get("rcp_no")
    report_nm = latest.get("report_nm", "(no report_nm)")
    link = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}"

    log(lines, f"🧾 최신 공시 발견 rcp_no={rcp_no}")
    log(lines, f"📌 report_nm={report_nm}")
    log(lines, f"🔗 {link}")

    # test 모드: 새 공시 있으면 있다고 텔레그램 전송(항상)
    if MODE == "test":
        report_and_exit(
            lines,
            f"🧪 [TEST] 새 공시 있음!\n📌 {report_nm}\n🔗 {link}",
            exit_code=0
        )
        return

    # normal 모드: state 비교 후 새 공시만 전송
    if rcp_no == state.get("last_rcp_no"):
        log(lines, "🟨 새 공시 아님(이미 전송한 rcp_no)")
        log(lines, "🔕 (normal) 알림 전송 생략")
        return

    # 새 공시: state 업데이트 + 저장
    state["last_rcp_no"] = rcp_no
    save_state(state)
    log(lines, "✅ state.json 업데이트 완료")

    msg = f"📌 {report_nm}\n{link}"
    try:
        resp = send_telegram(lines, msg, tag="NEW_DISCLOSURE")
        if resp.status_code != 200:
            # 텔레그램 실패해도 로그 남기고 실패로 종료
            report_and_exit(lines, "❌ Telegram 전송 실패(새 공시)", exit_code=1)
            return
    except Exception as e:
        log(lines, f"💥 Telegram 전송 예외: {repr(e)}")
        log(lines, traceback.format_exc())
        report_and_exit(lines, "❌ Telegram 전송 예외(새 공시)", exit_code=1)
        return

    log(lines, "🎉 새 공시 알림 전송 성공")
    # normal 모드는 여기서 종료 (state 커밋/푸시는 workflow가 수행)
    return


def report_and_exit(lines: list, headline: str, exit_code: int = 0):
    """
    텔레그램으로 '요약 + 상세로그'를 최대한 보내고 끝내기.
    """
    log_text = "\n".join(lines)
    # 텔레그램으로 보내기(가능하면)
    try:
        # 1) 헤드라인
        send_telegram(lines, f"{headline}\n\n🧾 로그 요약 전송 시작", tag="HEADLINE")
        # 2) 상세 로그(분할)
        chunks = chunk_text("🧾 상세 로그\n\n" + log_text)
        for i, c in enumerate(chunks, 1):
            send_telegram(lines, f"{c}\n\n📦 chunk {i}/{len(chunks)}", tag=f"LOG_{i}")
    except Exception as e:
        # 텔레그램 자체가 안 되면 콘솔 로그라도 남김
        print("💥 report_and_exit Telegram send failed:", repr(e))

    # exit_code는 main에서 실제로 sys.exit 안 쓰고,
    # GitHub Actions는 예외 없으면 0으로 끝나므로,
    # 실패를 표시하고 싶으면 여기서 예외를 던지는 방식으로 처리
    if exit_code != 0:
        raise RuntimeError(f"Exit with code {exit_code}")


if __name__ == "__main__":
    main()
