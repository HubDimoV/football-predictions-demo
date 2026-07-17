import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

API_BASE = "https://api.football-data.org/v4"
DEFAULT_DAYS = 10
MAX_DAILY_PICKS = 10

FREE_COMPETITIONS = ["PL", "PD", "BL1", "SA", "FL1", "DED", "BSA", "PPL", "CL", "EL", "WC"]

COMPETITION_LABELS = {
    "PL": {"bg": "Премиър лийг", "en": "Premier League"},
    "PD": {"bg": "Ла Лига", "en": "La Liga"},
    "BL1": {"bg": "Бундеслига", "en": "Bundesliga"},
    "SA": {"bg": "Серия А", "en": "Serie A"},
    "FL1": {"bg": "Лига 1", "en": "Ligue 1"},
    "DED": {"bg": "Ередивизие", "en": "Eredivisie"},
    "BSA": {"bg": "Бразилска Серия A", "en": "Brasileirão Série A"},
    "PPL": {"bg": "Примейра Лига", "en": "Primeira Liga"},
    "CL": {"bg": "Шампионска лига", "en": "Champions League"},
    "EL": {"bg": "Лига Европа", "en": "Europa League"},
    "WC": {"bg": "Световно първенство", "en": "World Cup"},
}

TEAM_TRANSLATIONS = {
    "bg": {
        "Real Madrid": "Реал Мадрид",
        "Barcelona": "Барселона",
        "Atletico Madrid": "Атлетико Мадрид",
        "Bayern Munich": "Байерн Мюнхен",
        "Borussia Dortmund": "Борусия Дортмунд",
        "Inter Milan": "Интер",
        "AC Milan": "Милан",
        "Juventus": "Ювентус",
        "Manchester City": "Манчестър Сити",
        "Manchester United": "Манчестър Юнайтед",
        "Liverpool": "Ливърпул",
        "Arsenal": "Арсенал",
        "Chelsea": "Челси",
        "Tottenham Hotspur": "Тотнъм",
        "Paris Saint-Germain": "Пари Сен Жермен",
        "Marseille": "Марсилия",
        "Lyon": "Лион",
        "Porto": "Порто",
        "Benfica": "Бенфика",
        "Sporting CP": "Спортинг",
        "Brazil": "Бразилия",
        "Argentina": "Аржентина",
        "Spain": "Испания",
        "France": "Франция",
        "Germany": "Германия",
        "England": "Англия",
    }
}

LANGS = {
    "bg": {"flag": "🇧🇬", "label": "Български"},
    "en": {"flag": "🇬🇧", "label": "English"},
}

UI = {
    "bg": {
        "title": "Football Intelligence",
        "subtitle": "Платформа за прогнозиране на футболни срещи",
        "language": "Език",
        "leagues": "Лиги",
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
        "status": "Статус",
        "forecast": "Прогноза",
        "confidence": "Шанс",
        "match": "Мач",
    },
    "en": {
        "title": "Football Intelligence",
        "subtitle": "Football match prediction platform",
        "language": "Language",
        "leagues": "Leagues",
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
        "status": "Status",
        "forecast": "Forecast",
        "confidence": "Confidence",
        "match": "Match",
    },
}

COMPETITION_WEIGHTS = {
    "WC": 105, "CL": 100, "EL": 92, "PL": 95, "PD": 94, "BL1": 92,
    "SA": 91, "FL1": 88, "DED": 84, "BSA": 83, "PPL": 82
}

STATUS_WEIGHTS = {
    "LIVE": 55, "IN_PLAY": 55, "PAUSED": 45, "TIMED": 25, "SCHEDULED": 25,
    "FINISHED": 5, "POSTPONED": 0, "SUSPENDED": 0, "CANCELLED": 0
}


def ui():
    return UI[st.session_state.get("lang", "bg")]


def tr_team(name):
    return TEAM_TRANSLATIONS.get(st.session_state.get("lang", "bg"), {}).get(name, name)


def comp_name(code):
    return COMPETITION_LABELS.get(code, {}).get(st.session_state.get("lang", "bg"), code)


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


def fmt_dt(dt):
    if not dt:
        return ""
    try:
        return dt.astimezone().strftime("%H:%M · %d.%m.%Y")
    except Exception:
        return dt.strftime("%H:%M · %d.%m.%Y")


def fetch_competitions():
    try:
        return api_get("/competitions").get("competitions", [])
    except Exception:
        return []


def load_competitions():
    available = fetch_competitions()
    codes = [c["code"] for c in available if c.get("code") in FREE_COMPETITIONS]
    return list(dict.fromkeys(codes or FREE_COMPETITIONS))


def fetch_matches_for_competition(code):
    today = datetime.now(timezone.utc).date()
    params = {"dateFrom": today.isoformat(), "dateTo": (today + timedelta(days=DEFAULT_DAYS)).isoformat()}
    try:
        return api_get(f"/competitions/{code}/matches", params=params).get("matches", [])
    except Exception:
        return []


def load_all_matches(codes):
    out = []
    for c in codes:
        out.extend(fetch_matches_for_competition(c))
    return out


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
    base = COMPETITION_WEIGHTS.get(m["competitionCode"], 70) + STATUS_WEIGHTS.get(m["status"], 10)
    dt = parse_utc(m["utcDate"])
    if dt:
        hours = abs((dt - datetime.now(timezone.utc)).total_seconds()) / 3600
        base += max(0, 24 - min(hours, 24))
    return round(base, 2)


def predict_1x2(m):
    s = COMPETITION_WEIGHTS.get(m["competitionCode"], 70) / 105
    t = score_match(m) / 140
    home = max(0.18, min(0.62, 0.30 + 0.18 * s + 0.12 * t))
    draw = max(0.12, min(0.34, 0.26 - 0.04 * (s - 0.5) + 0.03 * (1 - t)))
    away = max(0.18, min(0.62, 1 - home - draw))
    z = home + draw + away
    probs = {"1": home / z, "X": draw / z, "2": away / z}
    return max(probs, key=probs.get), probs


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
        out.append(m)
    return sorted(out, key=lambda x: (x["confidence"], x["importance"]), reverse=True)


def league_header(code):
    return f"<div style='font-size:0.9rem;color:#8dd3ff;font-weight:700;letter-spacing:0.4px;text-transform:uppercase;margin:8px 0 2px 0;'>{comp_name(code)}</div>"


def scale_html(m):
    p1, px, p2 = m["probs"]["1"] * 100, m["probs"]["X"] * 100, m["probs"]["2"] * 100
    return f"""
    <div style='width:360px; max-width:100%; margin:0 0 8px 0;'>
      <div style='display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; margin-bottom:4px;'>
        <div style='text-align:center; font-size:0.85rem; font-weight:700; color:#8dd3ff;'>1</div>
        <div style='text-align:center; font-size:0.85rem; font-weight:700; color:#8dd3ff;'>X</div>
        <div style='text-align:center; font-size:0.85rem; font-weight:700; color:#8dd3ff;'>2</div>
      </div>
      <div style='display:grid; grid-template-columns:repeat(3, 1fr); height:26px; border-radius:999px; overflow:hidden; box-shadow:0 0 0 1px rgba(255,255,255,0.08) inset;'>
        <div style='background:linear-gradient(90deg,#0dbf6b 0%,#79f2b4 100%); display:flex; align-items:center; justify-content:center;'><span style='color:#000;font-weight:800;font-size:0.9rem;text-shadow:0 0 2px rgba(255,255,255,0.55);'>{p1:.1f}%</span></div>
        <div style='background:linear-gradient(90deg,#9a9a9a 0%,#d9d9d9 100%); display:flex; align-items:center; justify-content:center;'><span style='color:#000;font-weight:800;font-size:0.9rem;text-shadow:0 0 2px rgba(255,255,255,0.55);'>{px:.1f}%</span></div>
        <div style='background:linear-gradient(90deg,#ff5b5b 0%,#ff9b9b 100%); display:flex; align-items:center; justify-content:center;'><span style='color:#000;font-weight:800;font-size:0.9rem;text-shadow:0 0 2px rgba(255,255,255,0.55);'>{p2:.1f}%</span></div>
      </div>
    </div>
    """


def render_match(m):
    dt = parse_utc(m["utcDate"])
    st.markdown(league_header(m["competitionCode"]), unsafe_allow_html=True)
    st.markdown(f"### {tr_team(m['homeTeam'])} vs {tr_team(m['awayTeam'])}")
    st.markdown(f"**{fmt_dt(dt)}** · {m['status']}")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown(scale_html(m), unsafe_allow_html=True)
    with c2:
        st.markdown(f"**{ui()['forecast']}:** {m['pred1x2']}\n\n**{ui()['confidence']}:** {m['confidence']}%")
    with st.expander(ui()["info"]):
        st.write(f"{m['competitionLabel']}: {tr_team(m['homeTeam'])} срещу {tr_team(m['awayTeam'])}")
        st.write(f"1/X/2: {m['probs']['1']*100:.1f}% / {m['probs']['X']*100:.1f}% / {m['probs']['2']*100:.1f}%")
        st.write(f"{ui()['markets']}:")
        st.write(f"- {ui()['best_bets']}: {m['markets']['safe']}%")
        st.write(f"- {ui()['recommended']}: {m['markets']['combo']}%")
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
            "Домакин": tr_team(m["homeTeam"]),
            "Гост": tr_team(m["awayTeam"]),
            "Прогноза": m["pred1x2"],
            "Шанс": m["confidence"],
            "Статус": m["status"],
        })
    return pd.DataFrame(rows)


def language_button():
    current = st.session_state.get("lang", "bg")
    choice = st.selectbox(
        " ",
        ["bg", "en"],
        index=0 if current == "bg" else 1,
        format_func=lambda x: f"{LANGS[x]['flag']}  {LANGS[x]['label']}",
        label_visibility="collapsed",
        key="lang_selector",
    )
    st.session_state.lang = choice


def main():
    st.set_page_config(page_title="Football Intelligence", layout="wide")
    st.markdown(
        """
        <style>
        .stApp{background:#0d0b16;color:#f5f0ff;}
        h1,h2,h3,h4{color:#c79cff !important;}
        div[data-baseweb='select'] > div{
            border-radius:14px !important;
            min-height:34px !important;
            height:34px !important;
            width:84px !important;
        }
        div[data-baseweb='select'] span{
            font-size:0.88rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "lang" not in st.session_state:
        st.session_state.lang = "bg"

    components.html(
        "<script>window.parent.postMessage(JSON.stringify({timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC'}),'*');</script>",
        height=0,
    )

    c1, c2 = st.columns([4, 1])
    with c1:
        st.title(ui()["title"])
        st.caption(ui()["subtitle"])
    with c2:
        language_button()

    try:
        codes = load_competitions()
        raw = load_all_matches(codes)
        matches = enrich(raw)

        code_to_label = {c: comp_name(c) for c in codes}
        league_choice = st.selectbox(
            ui()["leagues"],
            [ui()["all_leagues"]] + [code_to_label[c] for c in codes],
            index=0,
        )

        if league_choice == ui()["all_leagues"]:
            filtered = matches
        else:
            chosen_code = next(c for c in codes if code_to_label[c] == league_choice)
            filtered = [m for m in matches if m["competitionCode"] == chosen_code]

        top = filtered[:3]
        today_utc = datetime.now(timezone.utc).date()
        daily = [
            m for m in filtered
            if parse_utc(m["utcDate"]) and parse_utc(m["utcDate"]).date() == today_utc
        ]
        weekly = [
            m for m in filtered
            if parse_utc(m["utcDate"]) and today_utc <= parse_utc(m["utcDate"]).date() <= today_utc + timedelta(days=7)
        ]

        st.subheader(ui()["top_predictions"])
        for m in top:
            render_match(m)

        st.subheader(ui()["top_day"])
        for m in top:
            render_match(m)

        st.subheader(ui()["today"])
        for m in daily[:st.slider(ui()["picks_limit"], 1, MAX_DAILY_PICKS, 10)]:
            render_match(m)

        st.subheader(ui()["week"])
        st.dataframe(df_view(weekly[:10]), use_container_width=True)

        st.subheader(ui()["table_view"])
        view = st.selectbox(ui()["view"], [ui()["top_predictions"], ui()["today"], ui()["week"], "All"])
        chosen = top if view == ui()["top_predictions"] else daily if view == ui()["today"] else weekly if view == ui()["week"] else filtered
        st.dataframe(df_view(chosen), use_container_width=True)

    except Exception as e:
        st.error(f"Грешка при зареждането: {e}")


if __name__ == "__main__":
    main()
