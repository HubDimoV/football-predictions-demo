import os
from datetime import date
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="centered")

def get_api_key():
    try:
        key = st.secrets.get("API_FOOTBALL_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.getenv("API_FOOTBALL_KEY", "")

API_KEY = get_api_key()
BASE_URL = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY} if API_KEY else {}

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

def parse_fixtures(payload):
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
            pick = "1" if hg > ag else "2" if hg < ag else "X"
            confidence, risk = 95.0, 5.0
        else:
            league_id = league.get("id") or 0
            pick = "1" if league_id % 3 == 0 else ("X" if league_id % 3 == 1 else "2")
            confidence, risk = 64.0, 36.0

        rows.append({
            "fixture_id": fixture.get("id"),
            "match_date": pd.to_datetime(dt, utc=True).tz_convert(None),
            "league": league.get("name", "Unknown"),
            "league_id": league.get("id"),
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
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("match_date").reset_index(drop=True)
    return df

@st.cache_data(ttl=900)
def load_leagues():
    code, text, payload = api_get("/leagues", params={"current": "true"})
    debug = [f"/leagues?current=true => {code}"]
    rows = []

    if code != 200 or not payload:
        debug.append(text[:300])
        return pd.DataFrame(), debug

    for item in payload.get("response", []):
        league = item.get("league", {}) or {}
        country = item.get("country", {}) or {}
        seasons = item.get("seasons", []) or []

        current_season = None
        for s in seasons:
            if s.get("current"):
                current_season = s.get("year")
                break

        if current_season is None and seasons:
            current_season = seasons[0].get("year")

        rows.append({
            "id": league.get("id"),
            "name": league.get("name", ""),
            "type": league.get("type", ""),
            "country": country.get("name", ""),
            "season": current_season,
            "logo": league.get("logo", ""),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["country", "name"]).reset_index(drop=True)
    return df, debug

def load_fixtures_for_league(league_id, season):
    params = {"league": league_id, "season": season, "next": 10}
    code, text, payload = api_get("/fixtures", params=params)
    debug = [f"/fixtures?league={league_id}&season={season}&next=10 => {code}"]
    if code != 200 or not payload:
        debug.append(text[:300])
        return pd.DataFrame(), debug
    return parse_fixtures(payload), debug

st.title("Football Predictions")
st.caption(f"Днес: {date.today().strftime('%Y-%m-%d')}")

if not API_KEY:
    st.error("Липсва API_FOOTBALL_KEY secret.")
    st.stop()

leagues_df, leagues_debug = load_leagues()

with st.expander("API debug"):
    for line in leagues_debug:
        st.write(line)

if leagues_df.empty:
    st.error("Не можах да заредя лиги. Провери secret-а или лимита.")
    st.stop()

# Автоматичен избор на лига:
preferred_ids = [39, 140, 78, 135, 61, 2]
pref = leagues_df[leagues_df["id"].isin(preferred_ids)].copy()
source_df = pref if not pref.empty else leagues_df.copy()

# Първо автоматично избирай лига със сезон и после превържи fixtures
league_options = {}
for _, r in source_df.iterrows():
    season_val = int(r["season"]) if pd.notna(r["season"]) else date.today().year
    label = f"{r['country']} - {r['name']} (season {season_val})"
    league_options[label] = (int(r["id"]), season_val)

selected_label = st.selectbox("League", list(league_options.keys()))
selected_league_id, selected_season = league_options[selected_label]

df, fixtures_debug = load_fixtures_for_league(selected_league_id, selected_season)

with st.expander("Fixtures debug"):
    for line in fixtures_debug:
        st.write(line)

if df.empty:
    st.warning("Няма fixtures за избраната лига/сезон.")
    st.stop()

search = st.text_input("Search team or league", placeholder="Напр. Arsenal")

filtered = df.copy()
if search:
    q = search.lower()
    filtered = filtered[
        filtered["home"].str.lower().str.contains(q, na=False)
        | filtered["away"].str.lower().str.contains(q, na=False)
        | filtered["league"].str.lower().str.contains(q, na=False)
        | filtered["country"].str.lower().str.contains(q, na=False)
    ]

st.success(f"Loaded {len(filtered)} fixtures")

for _, r in filtered.iterrows():
    with st.container(border=True):
        st.markdown(f"**{r['home']}** vs **{r['away']}**")
        st.caption(f"{r['league']} • {r['country']} • {r['round']} • {r['match_date'].strftime('%d.%m.%Y %H:%M')}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Pick", r["pick"])
        c2.metric("Confidence", f"{r['confidence']:.1f}%")
        c3.metric("Risk", f"{r['risk']:.1f}%")
        if pd.notna(r["score_home"]) and pd.notna(r["score_away"]):
            st.write(f"Final score: {r['score_home']} - {r['score_away']}")
