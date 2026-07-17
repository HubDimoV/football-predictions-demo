import os
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st
import pandas as pd

API_BASE = "https://api.football-data.org/v4"
DEFAULT_COMPETITIONS = ["PL", "CL", "BSA", "PD", "SA", "BL1", "DED", "FL1", "ELC", "PPL"]


def get_api_key():
    key = st.secrets.get("FOOTBALL_DATA_API_KEY", None) if hasattr(st, "secrets") else None
    if not key:
        key = os.getenv("FOOTBALL_DATA_API_KEY", "")
    return key.strip()


def api_get(path, params=None):
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("Missing FOOTBALL_DATA_API_KEY")

    headers = {"X-Auth-Token": api_key}
    url = f"{API_BASE}{path}"
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_today_matches():
    return api_get("/matches")


def fetch_competition_matches(competition_code):
    return api_get(f"/competitions/{competition_code}/matches")


def normalize_match(match):
    full_time = match.get("score", {}).get("fullTime", {})
    home_score = full_time.get("home")
    away_score = full_time.get("away")

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
        "scoreHome": home_score,
        "scoreAway": away_score,
        "importance": 0,
        "raw": match,
    }


def parse_utc(date_str):
    if not date_str:
        return None
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def compute_importance(m):
    score = 0

    comp = (m.get("competitionCode") or "").upper()
    status = (m.get("status") or "").upper()
    dt = parse_utc(m.get("utcDate"))

    top_competitions = {"PL": 100, "CL": 95, "PD": 90, "BL1": 88, "SA": 86, "FL1": 84, "BSA": 75}
    score += top_competitions.get(comp, 50)

    if status == "LIVE":
        score += 40
    elif status in {"TIMED", "SCHEDULED"}:
        score += 20
    elif status == "FINISHED":
        score += 5

    if dt:
        now = datetime.now(timezone.utc)
        delta_hours = abs((dt - now).total_seconds()) / 3600
        score += max(0, 24 - min(delta_hours, 24))

    if m.get("scoreHome") is not None or m.get("scoreAway") is not None:
        score += 5

    return round(score, 2)


def enrich_matches(matches):
    normalized = [normalize_match(m) for m in matches]
    for m in normalized:
        m["importance"] = compute_importance(m)
    return sorted(normalized, key=lambda x: x["importance"], reverse=True)


def split_by_date(matches):
    today = datetime.now(timezone.utc).date()
    week_end = today + timedelta(days=7)

    daily = []
    weekly = []

    for m in matches:
        dt = parse_utc(m.get("utcDate"))
        if not dt:
            continue
        match_date = dt.date()
        if match_date == today:
            daily.append(m)
        if today <= match_date <= week_end:
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


def get_all_matches():
    base = fetch_today_matches()
    matches = base.get("matches", [])
    if matches:
        return matches

    collected = []
    for code in DEFAULT_COMPETITIONS:
        try:
            data = fetch_competition_matches(code)
            collected.extend(data.get("matches", []))
        except Exception:
            continue
    return collected


def main():
    st.set_page_config(page_title="Football Predictions Demo", layout="wide")
    st.title("Football Predictions Demo")

    st.caption("Data provider: football-data.org")

    try:
        raw_matches = get_all_matches()
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
        df = matches_to_df(chosen)
        st.dataframe(df, use_container_width=True)

    except Exception as e:
        st.error(f"Failed to load matches: {e}")


if __name__ == "__main__":
    main()
