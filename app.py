import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

API_BASE = "https://api.football-data.org/v4"
FREE_COMPETITIONS = ["PL", "PD", "BL1", "SA", "FL1", "DED", "BSA", "PPL", "CL", "EL", "WC"]
DEFAULT_DAYS = 7
MAX_DAILY_PICKS = 10

LABELS_BG = {
    "app_title": "Football Intelligence",
    "subtitle": "Платформа за прогнозиране на футболни срещи",
    "competition_filter": "Филтър по лиги",
    "competitions": "Лиги",
    "language": "Език",
    "language_bg": "Български",
    "language_en": "Английски",
    "time_mode": "Часова зона",
    "time_bg": "Българско време",
    "time_local": "Локално време на потребителя",
    "top_predictions": "Топ прогнози",
    "today": "Днес",
    "week": "Тази седмица",
    "table_view": "Табличен изглед",
    "view": "Изглед",
    "top_picks": "Препоръчвани",
    "info": "Инфо",
    "summary": "Резюме",
    "combined": "Комбиниран залог",
    "win_prob": "Шанс",
    "picks_limit": "Брой прогнози за деня",
    "best_bets": "Най-сигурни залози",
    "markets": "Пазари",
}

LABELS_EN = {
    "app_title": "Football Intelligence",
    "subtitle": "Football match prediction platform",
    "competition_filter": "League filter",
    "competitions": "Leagues",
    "language": "Language",
    "language_bg": "Bulgarian",
    "language_en": "English",
    "time_mode": "Time zone",
    "time_bg": "Bulgarian time",
    "time_local": "User local time",
    "top_predictions": "Top predictions",
    "today": "Today",
    "week": "This week",
    "table_view": "Table view",
    "view": "View",
    "top_picks": "Recommended",
    "info": "Info",
    "summary": "Summary",
    "combined": "Combined bet",
    "win_prob": "Chance",
    "picks_limit": "Daily prediction limit",
    "best_bets": "Best safe bets",
    "markets": "Markets",
}

COMPETITION_LABELS = {
    "PL": {"bg": "Премиър лийг", "en": "Premier League"},
    "PD": {"bg": "Ла Лига", "en": "La Liga"},
    "BL1": {"bg": "Бундеслига", "en": "Bundesliga"},
    "SA": {"bg": "Серия А", "en": "Serie A"},
    "FL1": {"bg": "Лига 1", "en": "Ligue 1"},
    "DED": {"bg": "Ередивизие", "en": "Eredivisie"},
    "BSA": {"bg": "Кампеонато Бразилейро Серия А", "en": "Campeonato Brasileiro Série A"},
    "PPL": {"bg": "Примейра Лига", "en": "Primeira Liga"},
    "CL": {"bg": "Шампионска лига", "en": "Champions League"},
    "EL": {"bg": "Лига Европа", "en": "Europa League"},
    "WC": {"bg": "Световно първенство", "en": "World Cup"},
}

COMPETITION_WEIGHTS = {
    "PL": 100, "PD": 96, "BL1": 94, "SA": 92, "FL1": 90, "DED": 84, "BSA": 82, "PPL": 80, "CL": 98, "EL": 88, "WC": 99
}

STATUS_WEIGHTS = {
    "LIVE": 50, "IN_PLAY": 50, "PAUSED": 45, "TIMED": 20, "SCHEDULED": 20, "FINISHED": 5, "POSTPONED": 0, "SUSPENDED": 0, "CANCELLED": 0
}


def get_lang():
    return st.session_state.get("lang", "bg")


def t(key):
    lang = get_lang()
    return LABELS_BG.get(key, key) if lang == "bg" else LABELS_EN.get(key, key)


def comp_name(code):
    lang = get_lang()
    data = COMPETITION_LABELS.get(code, {"bg": code, "en": code})
    return data["bg"] if lang == "bg" else data["en"]


def fmt_dt(dt, timezone_mode="bg"):
    if not dt:
        return ""
    if timezone_mode == "local":
        local = dt.astimezone()
        return local.strftime("%H:%M · %d.%m.%Y")
    bg_tz = timezone(timedelta(hours=3))
    bg = dt.astimezone(bg_tz)
    return bg.strftime("%H:%M · %d.%m.%Y")


def get_api_key():
    key = ""
    if hasattr(st, "secrets"):
        try:
            key = st.secrets.get("FOOTBALL_DATA_API_KEY", "")
        except Exception:
            key = ""
    if not key:
        key = os.getenv("FOOTBALL_DATA_API_KEY", "")
    return key.strip()


def api_get(path, params=None):
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("Missing FOOTBALL_DATA_API_KEY")
    headers = {"X-Auth-Token": api_key}
    resp = requests.get(f"{API_BASE}{path}", headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_utc(date_str):
    if not date_str:
        return None
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def fetch_competitions():
    try:
        data = api_get("/competitions")
        return [c for c in data.get("competitions", []) if c.get("code")]
    except Exception:
        return []


def fetch_competition_matches(code, days=DEFAULT_DAYS):
    try:
        today = datetime.now(timezone.utc).date()
        params = {"dateFrom": today.isoformat(), "dateTo": (today + timedelta(days=days)).isoformat()}
        data = api_get(f"/competitions/{code}/matches", params=params)
        return data.get("matches", [])
    except Exception:
        return []


def load_competitions_to_use():
    available = fetch_competitions()
    codes = [c.get("code") for c in available if c.get("code") in FREE_COMPETITIONS]
    if not codes:
        codes = FREE_COMPETITIONS[:]
    seen = set()
    out = []
    for c in codes:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out


def normalize_match(match):
    full_time = match.get("score", {}).get("fullTime", {})
    code = match.get("competition", {}).get("code", "")
    return {
        "id": match.get("id"),
        "utcDate": match.get("utcDate"),
        "homeTeam": match.get("homeTeam", {}).get("name", ""),
        "awayTeam": match.get("awayTeam", {}).get("name", ""),
        "competition": match.get("competition", {}).get("name", ""),
        "competitionCode": code,
        "competitionLabel": comp_name(code),
        "status": match.get("status", ""),
        "scoreHome": full_time.get("home"),
        "scoreAway": full_time.get("away"),
        "raw": match,
    }


def compute_scores(m):
    code = (m.get("competitionCode") or "").upper()
    status = (m.get("status") or "").upper()
    dt = parse_utc(m.get("utcDate"))
    base = COMPETITION_WEIGHTS.get(code, 60)
    status_bonus = STATUS_WEIGHTS.get(status, 10)
    time_bonus = 0
    if dt:
        now = datetime.now(timezone.utc)
        delta_hours = abs((dt - now).total_seconds()) / 3600
        time_bonus = max(0, 24 - min(delta_hours, 24))
    total = base + status_bonus + time_bonus
    return round(total, 2)


def predict_1x2(m):
    code = (m.get("competitionCode") or "").upper()
    strength = COMPETITION_WEIGHTS.get(code, 60) / 100.0
    total = compute_scores(m) / 140.0
    home = max(0.18, min(0.62, 0.30 + 0.20 * strength + 0.12 * total))
    draw = max(0.12, min(0.34, 0.24 - 0.05 * (strength - 0.5) + 0.03 * (1 - total)))
    away = max(0.18, min(0.62, 1 - home - draw))
    s = home + draw + away
    home, draw, away = home / s, draw / s, away / s
    vals = {"1": home, "X": draw, "2": away}
    best = max(vals, key=vals.get)
    sorted_vals = sorted(vals.items(), key=lambda x: x[1], reverse=True)
    second = sorted_vals[1][0]
    third = sorted_vals[2][0]
    return best, vals, second, third


def market_signals(m):
    total = compute_scores(m)
    safe = min(92, max(55, total - 20))
    combo = min(96, max(60, safe + 6))
    cards = min(85, max(50, 62 + (total - 100) / 2))
    goals = min(88, max(48, 60 + (total - 100) / 3))
    shots = min(84, max(45, 58 + (total - 100) / 4))
    return {
        "safe": round(safe, 1),
        "combo": round(combo, 1),
        "cards": round(cards, 1),
        "goals": round(goals, 1),
        "shots": round(shots, 1),
    }


def build_summary(m, pred, vals):
    lang = get_lang()
    home = m.get("homeTeam", "")
    away = m.get("awayTeam", "")
    dt = parse_utc(m.get("utcDate"))
    when = fmt_dt(dt, st.session_state.get("time_mode", "bg"))
    if lang == "bg":
        return f"{m.get('competitionLabel', '')}: {home} срещу {away} на {when}. Прогноза: {pred}."
    return f"{m.get('competitionLabel', '')}: {home} vs {away} at {when}. Prediction: {pred}."


def enrich_matches(matches):
    out = []
    for match in matches:
        m = normalize_match(match)
        m["importance"] = compute_scores(m)
        pred, vals, second, third = predict_1x2(m)
        m["pred1x2"] = pred
        m["probs"] = vals
        m["second_pick"] = second
        m["third_pick"] = third
        m["safe_markets"] = market_signals(m)
        m["confidence"] = round(max(vals.values()) * 100, 1)
        m["summary"] = build_summary(m, pred, vals)
        out.append(m)
    return sorted(out, key=lambda x: (x["confidence"], x["importance"]), reverse=True)


def group_by_competition(matches):
    grouped = {}
    for m in matches:
        grouped.setdefault(m["competitionCode"], []).append(m)
    for code in grouped:
        grouped[code] = sorted(grouped[code], key=lambda x: (x["confidence"], x["importance"]), reverse=True)
    return grouped


def matches_to_df(matches):
    rows = []
    for m in matches:
        dt = parse_utc(m.get("utcDate"))
        rows.append({
            "Време": fmt_dt(dt, st.session_state.get("time_mode", "bg")),
            "Лига": m.get("competitionLabel", ""),
            "Домакин": m.get("homeTeam", ""),
            "Гост": m.get("awayTeam", ""),
            "Прогноза": m.get("pred1x2", ""),
            "Шанс": m.get("confidence", 0),
            "Статус": m.get("status", ""),
        })
    return pd.DataFrame(rows)


def color_for_pick(pick, best):
    if pick == best:
        return "🟢"
    if pick == "X":
        return "⚪"
    return "🔴"


def render_prediction_scale(m):
    vals = m["probs"]
    best = max(vals, key=vals.get)
    cols = st.columns(3)
    for i, k in enumerate(["1", "X", "2"]):
        icon = "🟢" if k == best else ("⚪" if k == "X" else "🔴")
        cols[i].markdown(f"**{icon} {k} — {vals[k]*100:.1f}%**")


def render_match_card(m):
    dt = parse_utc(m.get("utcDate"))
    st.markdown(f"**{m.get('competitionLabel', '')}**")
    st.markdown(f"{m.get('homeTeam', '')} vs {m.get('awayTeam', '')}")
    st.markdown(f"{fmt_dt(dt, st.session_state.get('time_mode', 'bg'))} · {m.get('status', '')}")
    render_prediction_scale(m)
    st.markdown(f"**{t('top_picks')}:** {m.get('pred1x2', '')} | {t('win_prob')}: {m.get('confidence', 0)}%")
    with st.expander(t("info")):
        st.write(m.get("summary", ""))
        st.write(f"1/X/2: {m['probs']['1']*100:.1f}% / {m['probs']['X']*100:.1f}% / {m['probs']['2']*100:.1f}%")
        st.write(f"{t('markets')}:")
        st.write(f"- {t('best_bets')}: {m['safe_markets']['safe']}%")
        st.write(f"- {t('combined')}: {m['safe_markets']['combo']}%")
        st.write(f"- Картони: {m['safe_markets']['cards']}%")
        st.write(f"- Голове: {m['safe_markets']['goals']}%")
        st.write(f"- Удари: {m['safe_markets']['shots']}%")
    st.divider()


def main():
    st.set_page_config(page_title="Football Intelligence", layout="wide")
    st.markdown(
        """
        <style>
        .stApp { background-color: #0d0b16; color: #f4f0ff; }
        h1, h2, h3, h4 { color: #c79cff !important; }
        .stMetric { background: #1a102b; border: 1px solid #7b3fe4; border-radius: 14px; padding: 10px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "lang" not in st.session_state:
        st.session_state.lang = "bg"
    if "time_mode" not in st.session_state:
        st.session_state.time_mode = "bg"

    top_bar = st.columns([2, 1, 1])
    with top_bar[0]:
        st.title(t("app_title"))
        st.caption(t("subtitle"))
    with top_bar[1]:
        lang_choice = st.selectbox(t("language"), ["BG", "EN"], index=0 if st.session_state.lang == "bg" else 1)
        st.session_state.lang = "bg" if lang_choice == "BG" else "en"
    with top_bar[2]:
        time_choice = st.selectbox(t("time_mode"), [t("time_bg"), t("time_local")], index=0 if st.session_state.time_mode == "bg" else 1)
        st.session_state.time_mode = "bg" if time_choice == t("time_bg") else "local"

    try:
        selected_codes = load_competitions_to_use()
        raw_matches = load_all_matches(selected_codes)
        enriched = enrich_matches(raw_matches)

        codes = [m["competitionCode"] for m in enriched]
        unique_codes = []
        for c in codes:
            if c not in unique_codes:
                unique_codes.append(c)

        code_options = {f"{comp_name(c)} ({c})": c for c in unique_codes}
        options = list(code_options.keys())
        default_options = options[:]

        st.subheader(t("competition_filter"))
        chosen_labels = st.multiselect(t("competitions"), options=options, default=default_options)
        chosen_codes = {code_options[label] for label in chosen_labels}

        active_matches = [m for m in enriched if m.get("competitionCode") in chosen_codes]
        today = datetime.now(timezone.utc).date()
        week_end = today + timedelta(days=7)
        daily = [m for m in active_matches if parse_utc(m.get("utcDate")) and parse_utc(m.get("utcDate")).date() == today]
        weekly = [m for m in active_matches if parse_utc(m.get("utcDate")) and today <= parse_utc(m.get("utcDate")).date() <= week_end]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total matches" if get_lang() == "en" else "Общо мачове", len(active_matches))
        c2.metric(t("today"), len(daily))
        c3.metric(t("week"), len(weekly))
        c4.metric(t("top_picks"), min(MAX_DAILY_PICKS, len(active_matches)))

        grouped = group_by_competition(active_matches)

        st.subheader(t("top_predictions"))
        top_predictions = sorted(active_matches, key=lambda x: (x["confidence"], x["importance"]), reverse=True)[:3]
        for m in top_predictions:
            render_match_card(m)

        st.subheader(t("today"))
        daily_limit = st.slider(t("picks_limit"), 1, MAX_DAILY_PICKS, 10)
        daily_sorted = sorted(daily, key=lambda x: (x["confidence"], x["importance"]), reverse=True)[:daily_limit]
        for code in grouped:
            section = [m for m in daily_sorted if m["competitionCode"] == code]
            if section:
                st.markdown(f"### {comp_name(code)}")
                for m in section:
                    render_match_card(m)

        st.subheader(t("week"))
        weekly_sorted = sorted(weekly, key=lambda x: (x["confidence"], x["importance"]), reverse=True)
        week_limit = st.slider("Weekly limit", 1, 20, 10)
        st.dataframe(matches_to_df(weekly_sorted[:week_limit]), use_container_width=True)

        st.subheader(t("table_view"))
        view = st.selectbox(t("view"), [t("top_picks"), t("today"), t("week"), "All"])
        chosen = top_predictions if view == t("top_picks") else daily if view == t("today") else weekly if view == t("week") else active_matches
        st.dataframe(matches_to_df(chosen), use_container_width=True)

        st.subheader("Препоръчваме")
        st.write(" | ".join([f"{m['homeTeam']} vs {m['awayTeam']} ({m['confidence']}%)" for m in top_predictions]))

        st.subheader("Идеи за развитие")
        st.write("1) Добавяне на реални новини и коментари. 2) Добавяне на коефициенти от free odds source. 3) Отделен модул за картони, корнери, голове и удари. 4) Исторически train data + backtesting.")

    except Exception as e:
        st.error(f"Грешка при зареждане на мачовете: {e}")


if __name__ == "__main__":
    main()
