import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

API_BASE = "https://api.football-data.org/v4"
FREE_COMPETITIONS = [
    "PL",
    "PD",
    "BL1",
    "SA",
    "FL1",
    "DED",
    "BSA",
    "PPL",
    "CL",
    "EL",
]

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
}

STATUS_WEIGHTS = {
    "LIVE": 50,
    "TIMED": 20,
    "SCHEDULED": 20,
    "FINISHED": 5,
    "POSTPONED": 0,
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
    return {
        "id": match.get("id"),
        "provider": "football-data",
        "utcDate": match.get("utcDate"),
        "homeTeam": match.get("homeTeam", {}).get("name", ""),
        "awayTeam": match.get("awayTeam", {}).get("name", ""),
        "competition": match.get("competition", {}).get("name", ""),
        "competitionId": match.get("competition", {}).get("id"),
        "competitionCode": match.get("competition", {}).get("code"),
        "status": match.get("status", ""),
        "scoreHome": full_time.get("home"),
        "scoreAway": full_time.get("away"),
        "importance": 0,
        "raw": match,
    }


def compute_importance(m):
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


def enrich_matches(matches):
    enriched = []
    for match in matches:
        item = normalize_match(match)
        item["importance"] = compute_importance(item)
        enriched.append(item)
    return sorted(enriched, key=lambda x: x["importance"], reverse=True)


def fetch_competition_matches(code):
    try:
        data = api_get(f"/competitions/{code}/matches")
        return data.get("matches", [])
    except Exception:
        return []


def fetch_competition_info(code):
    try:
        return api_get(f"/competitions/{code}")
    except Exception:
        return None


def load_all_matches():
    all_matches = []
    for code in FREE_COMPETITIONS:
        matches = fetch_competition_matches(code)
        all_matches.extend(matches)
    return all_matches


def split_by_date(matches):
    today = datetime.now(timezone.utc).date()
    week_end = today + timedelta(days=7)

    daily = []
    weekly = []

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


def matches_to_df(matches):
    rows = []
    for m in matches:
        dt = parse_utc(m.get("utcDate"))
        rows.append(
            {
                "Date": dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else "",
                "Competition": m.get("competition", ""),
                "Home": m.get("homeTeam", ""),
                "Away": m.get("awayTeam", ""),
                "Status": m.get("status", ""),
                "Score": f'{m.get("scoreHome", "-")}-{m.get("scoreAway", "-")}',
                "Importance": m.get("importance", 0),
            }
        )
    return pd.DataFrame(rows)


def render_match_card(m):
    dt = parse_utc(m.get("utcDate"))
    local_dt = dt.astimezone() if dt else None
    score = f'{m.get("scoreHome", "-")}-{m.get("scoreAway", "-")}'
    st.write(f'**{m.get("competition", "")}**')
    st.write(f'{m.get("homeTeam", "")} vs {m.get("awayTeam", "")}')
    st.write(f'[{local_dt.strftime("%Y-%m-%d %H:%M") if local_dt else ""}]  Status: {m.get("status", "")}  Score: {score}  Importance: {m.get("importance", 0)}')
    st.divider()


def main():
    st.set_page_config(page_title="Football Predictions Demo", layout="wide")
    st.title("Football Predictions Demo")
    st.caption("Data provider: football-data.org")

    try:
        raw_matches = load_all_matches()
        enriched = enrich_matches(raw_matches)
        daily, weekly = split_by_date(enriched)

        c1, c2, c3 = st.columns(3)
        c1.metric("Total matches", len(enriched))
        c2.metric("Today", len(daily))
        c3.metric("This week", len(weekly))

        st.subheader("Top matches for today")
        daily_limit = st.slider("Daily limit", 1, 20, 5)
        for m in daily[:daily_limit]:
            render_match_card(m)

        st.subheader("Top matches for this week")
        weekly_limit = st.slider("Weekly limit", 1, 50, 10)
        for m in weekly[:weekly_limit]:
            render_match_card(m)

        st.subheader("Table view")
        view = st.selectbox("View", ["Daily", "Weekly", "All"])
        chosen = daily if view == "Daily" else weekly if view == "Weekly" else enriched
        st.dataframe(matches_to_df(chosen), use_container_width=True)

        st.subheader("Competition details")
        st.write("Free competitions used:")
        st.write(", ".join(FREE_COMPETITIONS))

    except Exception as e:
        st.error(f"Failed to load matches: {e}")


if __name__ == "__main__":
    main()
