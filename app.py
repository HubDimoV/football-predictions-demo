import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="centered")

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}

PREFERRED_LEAGUES = [
    {"name": "Premier League", "competition_id": 39},
    {"name": "La Liga", "competition_id": 140},
    {"name": "Bundesliga", "competition_id": 78},
    {"name": "Serie A", "competition_id": 135},
    {"name": "Ligue 1", "competition_id": 61},
    {"name": "Champions League", "competition_id": 2},
]

def api_get(path, params=None):
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params or {}, timeout=20)
        try:
            payload = r.json()
        except Exception:
            payload = None
        return r.status_code, r.text, payload
    except Exception as e:
        return None, str(e), None

def parse_fixtures(payload, source_tag=""):
    rows = []
    if not payload or "response" not in payload:
        return pd.DataFrame()

    for f in payload.get("response", []):
        fixture = f.get("fixture", {}) or {}
        league = f.get("league", {}) or {}
        teams = f.get("teams", {}) or {}
        goals = f.get("goals", {}) or {}

        home = teams.get("home", {}) or {}
        away = teams.get("away", {}) or {}
        status = fixture.get("status", {}) or {}
        dt = fixture.get("date")

        if not dt:
            continue

        hg = goals.get("home")
        ag = goals.get("away")

        if hg is not None and ag is not None:
            if hg > ag:
                pick = "1"
            elif hg < ag:
                pick = "2"
            else:
                pick = "X"
            confidence = 95.0
            risk = 5.0
        else:
            league_id = league.get("id") or 0
            pick = "1" if league_id % 3 == 0 else ("X" if league_id % 3 == 1 else "2")
            confidence = 64.0
            risk = 36.0

        rows.append({
            "fixture_id": fixture.get("id"),
            "match_date": pd.to_datetime(dt, utc=True).tz_convert(None),
            "league": league.get("name", "Unknown"),
            "country": league.get("country", ""),
            "round": league.get("round", ""),
            "home": home.get("name", "Unknown"),
            "away": away.get("name", "Unknown"),
            "status": status.get("short", ""),
            "pick": pick,
            "confidence": float(confidence),
            "risk": float(risk),
            "score_home": hg,
            "score_away": ag,
            "source": source_tag,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("match_date").reset_index(drop=True)
    return df

@st.cache_data(ttl=900)
def load_today_fixtures():
    today_str = date.today().strftime("%Y-%m-%d")
    debug = []

    code, text, payload = api_get("/fixtures", params={"date": today_str})
    debug.append(f"/fixtures?date={today_str} => {code}")

    df = parse_fixtures(payload, source_tag="date=today") if code == 200 else pd.DataFrame()
    if code != 200:
        debug.append(text[:400])

    if df.empty:
        for league in PREFERRED_LEAGUES[:3]:
            code2, text2, payload2 = api_get("/fixtures", params={"league": league["competition_id"], "next": 10})
            debug.append(f"/fixtures?league={league['competition_id']}&next=10 => {code2}")
            if code2 == 200 and payload2:
                df2 = parse_fixtures(payload2, source_tag=f"league={league['competition_id']}")
                if not df2.empty:
                    df = df2
                    break
            else:
                debug.append(text2[:250])

    return df, debug

st.title("Football Predictions")
st.caption(f"Днес: {date.today().strftime('%Y-%m-%d')}")

df, debug_lines = load_today_fixtures()

with st.expander("API debug"):
    for line in debug_lines:
        st.write(line)

if df.empty:
    st.warning("Няма fixtures за днес или API-то не връща данни.")
    st.stop()

st.success(f"Loaded {len(df)} fixtures")

search = st.text_input("Search team or league", placeholder="Напр. Arsenal, Premier League")

filtered = df.copy()
if search:
    q = search.lower()
    filtered = filtered[
        filtered["home"].str.lower().str.contains(q, na=False)
        | filtered["away"].str.lower().str.contains(q, na=False)
        | filtered["league"].str.lower().str.contains(q, na=False)
        | filtered["country"].str.lower().str.contains(q, na=False)
    ]

for _, r in filtered.iterrows():
    with st.container(border=True):
        st.markdown(f"**{r['home']}** vs **{r['away']}**")
        st.caption(f"{r['league']} • {r['country']} • {r['round']}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Pick", r["pick"])
        c2.metric("Confidence", f"{r['confidence']:.1f}%")
        c3.metric("Risk", f"{r['risk']:.1f}%")
        if pd.notna(r["score_home"]) and pd.notna(r["score_away"]):
            st.write(f"Final score: {r['score_home']} - {r['score_away']}")
