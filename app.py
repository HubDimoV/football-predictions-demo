import os
from datetime import datetime, timedelta, timezone
import math

import pandas as pd
import requests
import streamlit as st

API_BASE = "https://api.football-data.org/v4"
FREE_COMPETITIONS = ["PL", "PD", "BL1", "SA", "FL1", "DED", "BSA", "PPL", "CL", "EL", "WC"]
DEFAULT_DAYS = 7
MAX_PICKS = 10

COMPETITION_LABELS = {
    "PL": "Premier League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1",
    "DED": "Eredivisie",
    "BSA": "Campeonato Brasileiro Série A",
    "PPL": "Primeira Liga",
    "CL": "Champions League",
    "EL": "Europa League",
    "WC": "World Cup",
}

COMPETITION_WEIGHTS = {
    "PL": 100,
    "PD": 96,
    "BL1": 94,
    "SA": 92,
    "FL1": 90,
    "DED": 84,
    "BSA": 82,
    "PPL": 80,
    "CL": 98,
    "EL": 88,
    "WC": 99,
}

STATUS_WEIGHTS = {
    "LIVE": 50,
    "IN_PLAY": 50,
    "PAUSED": 45,
    "TIMED": 20,
    "SCHEDULED": 20,
    "FINISHED": 5,
    "POSTPONED": 0,
    "SUSPENDED": 0,
    "CANCELLED": 0,
}


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


def normalize_match(match):
    full_time = match.get("score", {}).get("fullTime", {})
    code = match.get("competition", {}).get("code", "")
    return {
        "id": match.get("id"),
        "provider": "football-data",
        "utcDate": match.get("utcDate"),
        "homeTeam": match.get("homeTeam", {}).get("name", ""),
        "awayTeam": match.get("awayTeam", {}).get("name", ""),
        "competition": match.get("competition", {}).get("name", ""),
        "competitionId": match.get("competition", {}).get("id"),
        "competitionCode": code,
        "competitionLabel": COMPETITION_LABELS.get(code, code),
        "status": match.get("status", ""),
        "scoreHome": full_time.get("home"),
        "scoreAway": full_time.get("away"),
        "importance": 0,
        "matchForm": 0,
        "history": 0,
        "news": 0,
        "comments": 0,
        "bookmakers": 0,
        "pred_home": 0,
        "pred_away": 0,
        "pred_draw": 0,
        "summary": "",
        "raw": match,
    }


def compute_base_importance(m):
    comp = (m.get("competitionCode") or "").upper()
    status = (m.get("status") or "").upper()
    dt = parse_utc(m.get("utcDate"))
    score = 0
    score += COMPETITION_WEIGHTS.get(comp, 60)
    score += STATUS_WEIGHTS.get(status, 10)
    if dt:
        now = datetime.now(timezone.utc)
        delta_hours = abs((dt - now).total_seconds()) / 3600
        score += max(0, 24 - min(delta_hours, 24))
    if m.get("scoreHome") is not None or m.get("scoreAway") is not None:
        score += 5
    return round(score, 2)


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
    codes = {c.get("code") for c in available if c.get("code") in FREE_COMPETITIONS}
    if not codes:
        codes = set(FREE_COMPETITIONS)
    return sorted(codes)


def load_all_matches(selected_codes):
    all_matches = []
    for code in selected_codes:
        all_matches.extend(fetch_competition_matches(code))
    return all_matches


def split_by_date(matches):
    today = datetime.now(timezone.utc).date()
    week_end = today + timedelta(days=7)
    daily, weekly = [], []
    for m in matches:
        dt = parse_utc(m.get("utcDate"))
        if not dt:
            continue
        d = dt.date()
        if d == today:
            daily.append(m)
        if today <= d <= week_end:
            weekly.append(m)
    return daily, weekly


def simulate_prediction(m):
    comp = (m.get("competitionCode") or "").upper()
    base = COMPETITION_WEIGHTS.get(comp, 60) / 100.0
    time_factor = 0.08 if m.get("status") in {"TIMED", "SCHEDULED"} else 0.05
    history = m.get("history", 0) / 100.0
    news = m.get("news", 0) / 100.0
    comments = m.get("comments", 0) / 100.0
    bookmakers = m.get("bookmakers", 0) / 100.0
    form = m.get("matchForm", 0) / 100.0
    model = (
        0.22 * base
        + 0.18 * form
        + 0.16 * history
        + 0.12 * news
        + 0.10 * comments
        + 0.12 * bookmakers
        + 0.10 * time_factor
    )
    model = max(0.05, min(0.95, model))
    draw = max(0.10, min(0.30, 0.28 - 0.10 * (model - 0.5)))
    home = max(0.05, min(0.90, model - draw / 2))
    away = max(0.05, min(0.90, 1 - home - draw))
    total = home + draw + away
    home /= total
    draw /= total
    away /= total
    if home >= away and home >= draw:
        pick = f"{m.get('homeTeam', '')} to win"
        chance = home
        color = "green"
    elif away >= home and away >= draw:
        pick = f"{m.get('awayTeam', '')} to win"
        chance = away
        color = "green"
    else:
        pick = "Draw"
        chance = draw
        color = "red"
    return pick, chance, color, home, draw, away


def build_summary(m, pick, chance):
    comp = m.get("competitionLabel", m.get("competition", ""))
    home = m.get("homeTeam", "")
    away = m.get("awayTeam", "")
    dt = parse_utc(m.get("utcDate"))
    when = dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else ""
    return f"{comp}: {home} vs {away} at {when}. Predicted: {pick} ({int(chance * 100)}%)."


def enrich_matches(matches):
    out = []
    for match in matches:
        item = normalize_match(match)
        item["importance"] = compute_base_importance(item)
        item["matchForm"] = min(100, item["importance"] * 0.5)
        item["history"] = min(100, item["importance"] * 0.35)
        item["news"] = min(100, item["importance"] * 0.25)
        item["comments"] = min(100, item["importance"] * 0.2)
        item["bookmakers"] = min(100, item["importance"] * 0.3)
        pick, chance, color, home, draw, away = simulate_prediction(item)
        item["prediction"] = pick
        item["confidence"] = round(chance * 100, 1)
        item["confidenceColor"] = color
        item["pred_home"] = round(home * 100, 1)
        item["pred_draw"] = round(draw * 100, 1)
        item["pred_away"] = round(away * 100, 1)
        item["summary"] = build_summary(item, pick, chance)
        out.append(item)
    return sorted(out, key=lambda x: (x["confidence"], x["importance"]), reverse=True)


def matches_to_df(matches):
    rows = []
    for m in matches:
        dt = parse_utc(m.get("utcDate"))
        rows.append(
            {
                "Date": dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else "",
                "Competition": m.get("competitionLabel", m.get("competition", "")),
                "Home": m.get("homeTeam", ""),
                "Away": m.get("awayTeam", ""),
                "Status": m.get("status", ""),
                "Prediction": m.get("prediction", ""),
                "Confidence %": m.get("confidence", 0),
                "Score": f'{m.get("scoreHome", "-")}-{m.get("scoreAway", "-")}',
            }
        )
    return pd.DataFrame(rows)


def render_match_card(m, show_summary=True):
    dt = parse_utc(m.get("utcDate"))
    local_dt = dt.astimezone() if dt else None
    score = f'{m.get("scoreHome", "-")}-{m.get("scoreAway", "-")}'
    color = "🟢" if m.get("confidenceColor") == "green" else "🔴"
    st.markdown(f"**{m.get('competitionLabel', m.get('competition', ''))}**")
    st.markdown(f"{m.get('homeTeam', '')} vs {m.get('awayTeam', '')}")
    st.markdown(f"[{local_dt.strftime('%Y-%m-%d %H:%M') if local_dt else ''}] Status: {m.get('status', '')} Score: {score}")
    st.markdown(f"Prediction: {m.get('prediction', '')}  |  {color} {m.get('confidence', 0)}%")
    if show_summary:
        with st.expander("Info / summary"):
            st.write(m.get("summary", ""))
            st.write(f"Form: {m.get('matchForm', 0):.1f} | History: {m.get('history', 0):.1f} | News: {m.get('news', 0):.1f}")
            st.write(f"Comments: {m.get('comments', 0):.1f} | Bookmakers: {m.get('bookmakers', 0):.1f}")
            st.write(f"Home / Draw / Away: {m.get('pred_home', 0)}% / {m.get('pred_draw', 0)}% / {m.get('pred_away', 0)}%")
    st.divider()


def get_top_predictions(matches):
    return sorted(matches, key=lambda x: (x["confidence"], x["importance"]), reverse=True)[:3]


def main():
    st.set_page_config(page_title="Football Intelligence", layout="wide")
    st.markdown(
        """
        <style>
        .stApp { background-color: #0f0f18; color: #f3f0ff; }
        .stMarkdown, .stText, .stDataFrame, .stSelectbox, .stSlider { color: #f3f0ff; }
        div[data-testid="stMetric"] { background: #1b1230; padding: 12px; border-radius: 12px; border: 1px solid #6f42c1; }
        h1, h2, h3, h4 { color: #c9a7ff !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Football Intelligence")
    st.caption("Purple predictive football dashboard")

    try:
        selected_codes = load_competitions_to_use()
        raw_matches = load_all_matches(selected_codes)
        enriched = enrich_matches(raw_matches)

        code_to_label = {code: COMPETITION_LABELS.get(code, code) for code in selected_codes}
        selected_labels = [f"{code_to_label[c]} ({c})" for c in selected_codes]

        st.subheader("Competition filter")
        chosen_labels = st.multiselect("Competitions", options=selected_labels, default=selected_labels)
        chosen_codes = {item.split("(")[-1].replace(")", "").strip() for item in chosen_labels}

        active_matches = [m for m in enriched if m.get("competitionCode") in chosen_codes]
        daily, weekly = split_by_date(active_matches)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total matches", len(active_matches))
        c2.metric("Today", len(daily))
        c3.metric("This week", len(weekly))
        c4.metric("Top picks", min(MAX_PICKS, len(active_matches)))

        st.subheader("Top predictions")
        top_predictions = get_top_predictions(active_matches)
        for m in top_predictions:
            render_match_card(m, show_summary=True)

        st.subheader("Top matches for today")
        daily_limit = st.slider("Daily limit", 1, MAX_PICKS, 5)
        for m in daily[:daily_limit]:
            render_match_card(m, show_summary=True)

        st.subheader("Top matches for this week")
        weekly_limit = st.slider("Weekly limit", 1, 20, 10)
        for m in weekly[:weekly_limit]:
            render_match_card(m, show_summary=True)

        st.subheader("Table view")
        view = st.selectbox("View", ["Top picks", "Daily", "Weekly", "All"])
        chosen = top_predictions if view == "Top picks" else daily if view == "Daily" else weekly if view == "Weekly" else active_matches
        st.dataframe(matches_to_df(chosen), use_container_width=True)

        st.subheader("Recommended now")
        st.write(" | ".join([f"{m['homeTeam']} vs {m['awayTeam']} ({m['confidence']}%)" for m in top_predictions[:3]]))

        st.subheader("Free competitions used")
        st.write(", ".join(selected_labels))

        st.subheader("Next improvements")
        st.write("Add form, history, news, comments, and bookmaker feeds per match. Then replace simulated signals with real sources and keep the same scoring pipeline.")

    except Exception as e:
        st.error(f"Failed to load matches: {e}")


if __name__ == "__main__":
    main()
