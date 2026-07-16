import os
from datetime import date

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="wide")

BASE_URL = "https://v3.football.api-sports.io"
TOP_COUNTRIES_TO_TEST = 12
NEXT_PER_LEAGUE = 3

COUNTRY_IDS = [
    41,   # England
    62,   # Spain
    76,   # Italy
    82,   # Germany
    98,   # France
    122,  # Netherlands
    139,  # Portugal
    119,  # Turkey
    6,    # Brazil
    11,   # Argentina
    50,   # Belgium
    20,   # Austria
]

COLORS = {
    "header": "#1f6feb",
    "date": "#8b5cf6",
    "team": "#10b981",
    "pick": "#f59e0b",
    "confidence": "#22c55e",
    "risk": "#ef4444",
    "muted": "#64748b",
    "flag": "#dc2626",
    "ok": "#16a34a",
}

def get_api_key():
    try:
        key = st.secrets.get("API_FOOTBALL_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("API_FOOTBALL_KEY", "")

API_KEY = get_api_key()
HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}

def api_get(path, params=None):
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params or {}, timeout=25)
        try:
            payload = r.json()
        except Exception:
            payload = None
        return r.status_code, r.text, payload
    except Exception as e:
        return None, str(e), None

def parse_leagues(payload):
    rows = []
    for item in (payload or {}).get("response", []):
        league = item.get("league", {}) or {}
        country = item.get("country", {}) or {}
        seasons = item.get("seasons", []) or []
        for s in seasons:
            if s.get("current"):
                rows.append({
                    "league_id": league.get("id"),
                    "league": league.get("name", "Unknown"),
                    "country": country.get("name", ""),
                    "season": s.get("year"),
                })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["league_id"] = pd.to_numeric(df["league_id"], errors="coerce")
        df["season"] = pd.to_numeric(df["season"], errors="coerce")
        df = df.dropna(subset=["league_id", "season"])
    return df

def parse_fixtures(payload):
    rows = []
    for f in (payload or {}).get("response", []):
        fixture = f.get("fixture", {}) or {}
        league = f.get("league", {}) or {}
        teams = f.get("teams", {}) or {}
        dt = fixture.get("date")
        if not dt:
            continue
        md = pd.to_datetime(dt, utc=True).tz_convert(None)
        rows.append({
            "fixture_id": fixture.get("id"),
            "date": md.date(),
            "time": md.strftime("%H:%M"),
            "league_id": league.get("id"),
            "league": league.get("name", "Unknown"),
            "country": league.get("country", ""),
            "home": (teams.get("home", {}) or {}).get("name", "Unknown"),
            "away": (teams.get("away", {}) or {}).get("name", "Unknown"),
            "status": (fixture.get("status", {}) or {}).get("short", ""),
        })
    return pd.DataFrame(rows)

st.title("Football Predictions")
st.caption(f"Днес: {date.today().strftime('%Y-%m-%d')}")

if not API_KEY:
    st.error("Липсва API_FOOTBALL_KEY secret.")
    st.stop()

debug = []
all_leagues = []

for cid in COUNTRY_IDS:
    code, _, payload = api_get("/leagues", params={"country": cid})
    debug.append(f"/leagues?country={cid} => {code}")
    if code == 200 and payload and payload.get("response"):
        df = parse_leagues(payload)
        if not df.empty:
            df["country_id"] = cid
            all_leagues.append(df)

leagues_df = pd.concat(all_leagues, ignore_index=True).drop_duplicates(subset=["league_id", "season"]) if all_leagues else pd.DataFrame()

with st.expander("API debug"):
    st.write("Leagues rows:", len(leagues_df))
    if not leagues_df.empty:
        st.dataframe(leagues_df.head(30), use_container_width=True)
    for line in debug:
        st.write(line)

if leagues_df.empty:
    st.warning("Няма active leagues за тестване по избраните country IDs.")
    st.stop()

test_rows = []
fixtures_debug = []

for _, lg in leagues_df.head(25).iterrows():
    league_id = int(lg["league_id"])
    season = int(lg["season"])
    code, _, payload = api_get("/fixtures", params={
        "league": league_id,
        "season": season,
        "next": NEXT_PER_LEAGUE,
        "timezone": "Europe/Sofia",
    })
    fixtures_debug.append(f"/fixtures?league={league_id}&season={season}&next={NEXT_PER_LEAGUE} => {code}")
    if code == 200 and payload and payload.get("response"):
        df = parse_fixtures(payload)
        if not df.empty:
            df["source_country_id"] = lg["country_id"]
            df["source_league_id"] = league_id
            df["source_season"] = season
            test_rows.append(df)

with st.expander("Fixtures debug"):
    for line in fixtures_debug:
        st.write(line)

if not test_rows:
    st.warning("Нито една от тестваните лиги не върна fixtures.")
    st.stop()

out = pd.concat(test_rows, ignore_index=True).drop_duplicates(subset=["fixture_id"])
out = out.sort_values(["date", "time", "league"], ascending=[True, True, True]).reset_index(drop=True)

st.success(f"Намерени fixtures: {len(out)}")
st.dataframe(out, use_container_width=True)

st.markdown("## Matches")
for d, day_df in out.groupby("date", sort=True):
    with st.expander(f"{d} — {len(day_df)} matches", expanded=True):
        for _, r in day_df.iterrows():
            st.markdown(f"**{r['league']}** • {r['home']} vs {r['away']} • {r['time']} • {r['status']}")
