import os
from datetime import date
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="centered")

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {
    "x-apisports-key": API_KEY
} if API_KEY else {}

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

@st.cache_data(ttl=900)
def load_fixtures(target_date):
    code, text, payload = api_get("/fixtures", params={"date": target_date})
    rows = []
    debug = [f"/fixtures?date={target_date} => {code}"]

    if code != 200 or not payload:
        debug.append(text[:400])
        return pd.DataFrame(), debug

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

        home_goals = goals.get("home")
        away_goals = goals.get("away")

        if home_goals is not None and away_goals is not None:
            if home_goals > away_goals:
                pick = "1"
            elif home_goals < away_goals:
                pick = "2"
            else:
                pick = "X"
        else:
            league_id = league.get("id")
            if league_id and league_id % 3 == 0:
                pick = "1"
            elif league_id and league_id % 3 == 1:
                pick = "X"
            else:
                pick = "2"

        confidence = 64.0 if status.get("short") in {"NS", "TBD"} else 95.0
        risk = 100 - confidence

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
            "score_home": home_goals,
            "score_away": away_goals,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("match_date").reset_index(drop=True)
    return df, debug

def pct(x):
    return f"{float(x):.1f}%"

today = date.today().strftime("%Y-%m-%d")
df, debug_lines = load_fixtures(today)

st.title("Football Predictions")
st.caption(f"Днес: {today}")

with st.expander("API debug"):
    for line in debug_lines:
        st.write(line)

if df.empty:
    st.warning("Няма fixtures за днес или API-то не връща данни.")
    st.stop()

st.success(f"Loaded {len(df)} fixtures")

search = st.text_input("Search team or league", placeholder="Напр. Arsenal, World Cup, Premier League")

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
        c2.metric("Confidence", pct(r["confidence"]))
        c3.metric("Risk", pct(r["risk"]))
        if pd.notna(r["score_home"]) and pd.notna(r["score_away"]):
            st.write(f"Final score: {r['score_home']} - {r['score_away']}")
