import os
from datetime import date
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="World Cup Daily Pick", page_icon="⚽", layout="centered")

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY} if API_KEY else {}

TODAY = date.today()

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

def parse_matches(payload):
    rows = []
    if not payload or "matches" not in payload:
        return pd.DataFrame()

    for m in payload.get("matches", []):
        comp = m.get("competition", {}) or {}
        home = m.get("homeTeam", {}) or {}
        away = m.get("awayTeam", {}) or {}
        dt = m.get("utcDate")
        if not dt:
            continue

        rows.append({
            "match_id": m.get("id"),
            "match_date": pd.to_datetime(dt, utc=True).tz_convert(None),
            "league": comp.get("name", "World Cup"),
            "competition_code": comp.get("code", "WC"),
            "status": m.get("status", ""),
            "home": home.get("name", "Unknown"),
            "away": away.get("name", "Unknown"),
            "pick": "1",
            "confidence": 64.0,
            "risk": 36.0,
            "odds_1": 2.05,
            "odds_x": 3.20,
            "odds_2": 3.40,
        })

    return pd.DataFrame(rows)

st.title("World Cup Daily Pick")
st.caption(f"Днешна дата: {TODAY.strftime('%d.%m.%Y')}")

status, text, payload = api_get("/competitions/WC/matches", params={"date": TODAY.strftime("%Y-%m-%d")})

st.subheader("API status")
st.write(status)

if status != 200:
    st.error(text[:600])
    st.stop()

df = parse_matches(payload)

if df.empty:
    st.warning("Няма мачове за днес в World Cup.")
    st.stop()

st.success(f"Намерени мачове: {len(df)}")

for _, r in df.iterrows():
    with st.container(border=True):
        st.markdown(f"**{r['home']}** vs **{r['away']}**")
        st.caption(f"{r['league']} • {r['match_date'].strftime('%d.%m.%Y %H:%M')}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Pick", r["pick"])
        c2.metric("Confidence", f"{r['confidence']:.1f}%")
        c3.metric("Risk", f"{r['risk']:.1f}%")
        st.write(f"Odds: 1 {r['odds_1']} | X {r['odds_x']} | 2 {r['odds_2']}")
