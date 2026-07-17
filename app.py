import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

API_BASE = "https://api.football-data.org/v4"
DEFAULT_DAYS = 7
MAX_DAILY_PICKS = 10

LABELS_BG = {
    "app_title": "Football Intelligence",
    "subtitle": "Платформа за прогнозиране на футболни срещи",
    "language": "Език",
    "language_bg": "Български",
    "language_en": "Английски",
    "time_mode": "Часова зона",
    "time_bg": "Българско време",
    "time_local": "Локално време",
    "competition_filter": "Лиги",
    "all_leagues": "Всички лиги",
    "top_predictions": "Топ предложения",
    "today": "Днес",
    "week": "Тази седмица",
    "table_view": "Табличен изглед",
    "view": "Изглед",
    "info": "Инфо",
    "summary": "Резюме",
    "recommended": "Препоръчани",
    "best_bets": "Най-сигурни",
    "markets": "Пазари",
    "picks_limit": "Брой прогнози за деня",
    "top_day": "Най-важните мачове за деня",
}

LABELS_EN = {
    "app_title": "Football Intelligence",
    "subtitle": "Football match prediction platform",
    "language": "Language",
    "language_bg": "Bulgarian",
    "language_en": "English",
    "time_mode": "Time zone",
    "time_bg": "Bulgarian time",
    "time_local": "Local time",
    "competition_filter": "Leagues",
    "all_leagues": "All leagues",
    "top_predictions": "Top predictions",
    "today": "Today",
    "week": "This week",
    "table_view": "Table view",
    "view": "View",
    "info": "Info",
    "summary": "Summary",
    "recommended": "Recommended",
    "best_bets": "Safest",
    "markets": "Markets",
    "picks_limit": "Daily prediction limit",
    "top_day": "Most important matches today",
}

COMPETITION_LABELS = {
    "PL": {"bg": "Премиър лийг", "en": "Premier League"},
    "PD": {"bg": "Ла Лига", "en": "La Liga"},
    "BL1": {"bg": "Бундеслига", "en": "Bundesliga"},
    "SA": {"bg": "Серия А", "en": "Serie A"},
    "FL1": {"bg": "Лига 1", "en": "Ligue 1"},
    "DED": {"bg": "Ередивизие", "en": "Eredivisie"},
    "BSA": {"bg": "Кампеонато Бразилейро Сериа А", "en": "Campeonato Brasileiro Série A"},
    "PPL": {"bg": "Примейра Лига", "en": "Primeira Liga"},
    "CL": {"bg": "Шампионска лига", "en": "Champions League"},
    "EL": {"bg": "Лига Европа", "en": "Europa League"},
    "WC": {"bg": "Световно първенство", "en": "World Cup"},
}

FREE_COMPETITIONS = ["PL", "PD", "BL1", "SA", "FL1", "DED", "BSA", "PPL", "CL", "EL", "WC"]
COMPETITION_WEIGHTS = {"PL": 100, "PD": 96, "BL1": 94, "SA": 92, "FL1": 90, "DED": 84, "BSA": 82, "PPL": 80, "CL": 98, "EL": 88, "WC": 99}
STATUS_WEIGHTS = {"LIVE": 50, "IN_PLAY": 50, "PAUSED": 45, "TIMED": 20, "SCHEDULED": 20, "FINISHED": 5, "POSTPONED": 0, "SUSPENDED": 0, "CANCELLED": 0}


def lang():
    return st.session_state.get("lang", "bg")


def t(key):
    return LABELS_BG.get(key, key) if lang() == "bg" else LABELS_EN.get(key, key)


def comp_name(code):
    data = COMPETITION_LABELS.get(code, {"bg": code, "en": code})
    return data["bg"] if lang() == "bg" else data["en"]


def bg_time(dt):
    return dt.astimezone(timezone(timedelta(hours=3))).strftime("%H:%M · %d.%m.%Y") if dt else ""


def local_time(dt):
    return dt.astimezone().strftime("%H:%M · %d.%m.%Y") if dt else ""


def fmt_dt(dt):
    mode = st.session_state.get("time_mode", "bg")
    return bg_time(dt) if mode == "bg" else local_time(dt)


def get_api_key():
    try:
        return st.secrets.get("FOOTBALL_DATA_API_KEY", "") or os.getenv("FOOTBALL_DATA_API_KEY", "")
    except Exception:
        return os.getenv("FOOTBALL_DATA_API_KEY", "")


def api_get(path, params=None):
    key = get_api_key().strip()
    if not key:
        raise RuntimeError("Missing FOOTBALL_DATA_API_KEY")
    r = requests.get(f"{API_BASE}{path}", headers={"X-Auth-Token": key}, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def parse_utc(v):
    return datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None


def fetch_competitions():
    try:
        data = api_get("/competitions")
        return [c for c in data.get("competitions", []) if c.get("code")]
    except Exception:
        return []


def fetch_matches_for_competition(code):
    try:
        today = datetime.now(timezone.utc).date()
        params = {"dateFrom": today.isoformat(), "dateTo": (today + timedelta(days=DEFAULT_DAYS)).isoformat()}
        data = api_get(f"/competitions/{code}/matches", params=params)
        return data.get("matches", [])
    except Exception:
        return []


def load_competitions():
    available = fetch_competitions()
    codes = [c["code"] for c in available if c.get("code") in FREE_COMPETITIONS]
    if not codes:
        codes = FREE_COMPETITIONS[:]
    seen, out = set(), []
    for c in codes:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out


def load_all_matches(codes):
    matches = []
    for code in codes:
        matches.extend(fetch_matches_for_competition(code))
    return matches


def normalize_match(m):
    ft = m.get("score", {}).get("fullTime", {})
    code = m.get("competition", {}).get("code", "")
    return {
        "id": m.get("id"),
        "utcDate": m.get("utcDate"),
        "homeTeam": m.get("homeTeam", {}).get("name", ""),
        "awayTeam": m.get("awayTeam", {}).get("name", ""),
        "competitionCode": code,
        "competitionLabel": comp_name(code),
        "status": m.get("status", ""),
        "scoreHome": ft.get("home"),
        "scoreAway": ft.get("away"),
    }


def score_match(m):
    code = m["competitionCode"]
    status = m["status"]
    dt = parse_utc(m["utcDate"])
    base = COMPETITION_WEIGHTS.get(code, 60) + STATUS_WEIGHTS.get(status, 10)
    time_bonus = 0
    if dt:
        hours = abs((dt - datetime.now(timezone.utc)).total_seconds()) / 3600
        time_bonus = max(0, 24 - min(hours, 24))
    return round(base + time_bonus, 2)


def predict_1x2(m):
    strength = COMPETITION_WEIGHTS.get(m["competitionCode"], 60) / 100
    total = score_match(m) / 140
    home = max(0.18, min(0.62, 0.30 + 0.20 * strength + 0.12 * total))
    draw = max(0.12, min(0.34, 0.24 - 0.05 * (strength - 0.5) + 0.03 * (1 - total)))
    away = max(0.18, min(0.62, 1 - home - draw))
    s = home + draw + away
    probs = {"1": home / s, "X": draw / s, "2": away / s}
    best = max(probs, key=probs.get)
    return best, probs


def safe_markets(m):
    total = score_match(m)
    return {
        "safe": round(min(92, max(55, total - 20)), 1),
        "combo": round(min(96, max(60, total - 14)), 1),
        "cards": round(min(85, max(50, 62 + (total - 100) / 2)), 1),
        "goals": round(min(88, max(48, 60 + (total - 100) / 3)), 1),
        "shots": round(min(84, max(45, 58 + (total - 100) / 4)), 1),
    }


def enrich(matches):
    out = []
    for raw in matches:
        m = normalize_match(raw)
        m["importance"] = score_match(m)
        pred, probs = predict_1x2(m)
        m["pred1x2"] = pred
        m["probs"] = probs
        m["confidence"] = round(max(probs.values()) * 100, 1)
        m["markets"] = safe_markets(m)
        m["summary"] = f"{m['competitionLabel']}: {m['homeTeam']} срещу {m['awayTeam']}. Прогноза: {pred}."
        out.append(m)
    return sorted(out, key=lambda x: (x["confidence"], x["importance"]), reverse=True)


def color_bar(p1, px, p2):
    return f"""
    <div style="display:flex; height:16px; border-radius:999px; overflow:hidden; background:#3a3a3a; width:100%;">
      <div style="width:{p1}%; background:linear-gradient(90deg,#19c37d,#7bffb8);"></div>
      <div style="width:{px}%; background:linear-gradient(90deg,#9c9c9c,#cfcfcf);"></div>
      <div style="width:{p2}%; background:linear-gradient(90deg,#ff5b5b,#ff8a8a);"></div>
    </div>
    """


def render_scale(m):
    p1 = m["probs"]["1"] * 100
    px = m["probs"]["X"] * 100
    p2 = m["probs"]["2"] * 100
    c1 = "#19c37d"
    cx = "#a8a8a8"
    c2 = "#ff5b5b"
    st.markdown(
        f"""
        <div style="display:flex; justify-content:space-between; font-size:0.95rem; margin-bottom:0.25rem;">
          <span style="color:{c1}; font-weight:700;">1 {p1:.1f}%</span>
          <span style="color:{cx}; font-weight:700;">X {px:.1f}%</span>
          <span style="color:{c2}; font-weight:700;">2 {p2:.1f}%</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(color_bar(p1, px, p2), unsafe_allow_html=True)


def render_match(m):
    dt = parse_utc(m["utcDate"])
    st.markdown(f"### {m['homeTeam']} vs {m['awayTeam']}")
    st.markdown(f"**{fmt_dt(dt)}** · {m['status']}")
    render_scale(m)
    st.markdown(f"**Прогноза:** {m['pred1x2']} · **Шанс:** {m['confidence']}%")
    with st.expander(t("info")):
        st.write(m["summary"])
        st.write(f"1/X/2: {m['probs']['1']*100:.1f}% / {m['probs']['X']*100:.1f}% / {m['probs']['2']*100:.1f}%")
        st.write(f"{t('markets')}:")
        st.write(f"- {t('best_bets')}: {m['markets']['safe']}%")
        st.write(f"- {t('recommended')}: {m['markets']['combo']}%")
        st.write(f"- Картони: {m['markets']['cards']}%")
        st.write(f"- Голове: {m['markets']['goals']}%")
        st.write(f"- Удари: {m['markets']['shots']}%")
    st.divider()


def df_view(matches):
    rows = []
    for m in matches:
        rows.append({
            "Време": fmt_dt(parse_utc(m["utcDate"])),
            "Лига": m["competitionLabel"],
            "Домакин": m["homeTeam"],
            "Гост": m["awayTeam"],
            "Прогноза": m["pred1x2"],
            "Шанс": m["confidence"],
            "Статус": m["status"],
        })
    return pd.DataFrame(rows)


def main():
    st.set_page_config(page_title="Football Intelligence", layout="wide")
    st.markdown("<style>.stApp{background:#0d0b16;color:#f5f0ff;} h1,h2,h3,h4{color:#c79cff !important;}</style>", unsafe_allow_html=True)

    if "lang" not in st.session_state:
        st.session_state.lang = "bg"
    if "time_mode" not in st.session_state:
        st.session_state.time_mode = "bg"

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        st.title(t("app_title"))
        st.caption(t("subtitle"))
    with c2:
        st.session_state.lang = "bg" if st.selectbox(t("language"), ["BG", "EN"], index=0 if st.session_state.lang == "bg" else 1) == "BG" else "en"
    with c3:
        tm = st.selectbox(t("time_mode"), [t("time_bg"), t("time_local")], index=0 if st.session_state.time_mode == "bg" else 1)
        st.session_state.time_mode = "bg" if tm == t("time_bg") else "local"

    try:
        codes = load_competitions()
        raw = load_all_matches(codes)
        matches = enrich(raw)

        code_to_label = {c: comp_name(c) for c in codes}
        selection = st.selectbox(t("competition_filter"), [t("all_leagues")] + [code_to_label[c] for c in codes], index=0)
        if selection == t("all_leagues"):
            filtered = matches
        else:
            chosen_code = next(c for c in codes if code_to_label[c] == selection)
            filtered = [m for m in matches if m["competitionCode"] == chosen_code]

        top = filtered[:3]
        daily = [m for m in filtered if parse_utc(m["utcDate"]) and parse_utc(m["utcDate"]).date() == datetime.now(timezone.utc).date()]
        weekly = [m for m in filtered if parse_utc(m["utcDate"]) and datetime.now(timezone.utc).date() <= parse_utc(m["utcDate"]).date() <= datetime.now(timezone.utc).date() + timedelta(days=7)]

        if not selection or selection == t("all_leagues"):
            st.subheader(t("top_predictions"))
            for m in top:
                render_match(m)
        else:
            st.subheader(f"{selection}")
            for m in filtered:
                render_match(m)

        st.subheader(t("top_day"))
        for m in top:
            render_match(m)

        st.subheader(t("today"))
        for m in daily[:st.slider(t("picks_limit"), 1, MAX_DAILY_PICKS, 10)]:
            render_match(m)

        st.subheader(t("week"))
        st.dataframe(df_view(weekly[:10]), use_container_width=True)

        st.subheader(t("table_view"))
        view = st.selectbox(t("view"), [t("top_predictions"), t("today"), t("week"), "All"])
        chosen = top if view == t("top_predictions") else daily if view == t("today") else weekly if view == t("week") else filtered
        st.dataframe(df_view(chosen), use_container_width=True)

    except Exception as e:
        st.error(f"Грешка при зареждането: {e}")


if __name__ == "__main__":
    main()
