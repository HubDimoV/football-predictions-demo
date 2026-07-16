import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="wide")

BASE_URL = "https://v3.football.api-sports.io"

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

IMPORTANT_LEAGUES = {
    39: 100,   # Premier League
    140: 98,   # La Liga
    78: 96,    # Bundesliga
    135: 95,   # Serie A
    61: 94,    # Ligue 1
    2: 93,     # Champions League
    3: 92,     # Europa League
    88: 91,    # Eredivisie
    94: 90,    # Primeira Liga
    203: 89,   # MLS / adjust if not in feed
}

COLOR_PALETTE = {
    "header": "#1f6feb",
    "date": "#8b5cf6",
    "league": "#0ea5e9",
    "team": "#10b981",
    "pick": "#f59e0b",
    "confidence": "#22c55e",
    "risk": "#ef4444",
    "muted": "#64748b",
}

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
    for f in (payload or {}).get("response", []):
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

        hg, ag = goals.get("home"), goals.get("away")
        if hg is not None and ag is not None:
            pick = "1" if hg > ag else "2" if hg < ag else "X"
            confidence, risk = 95.0, 5.0
        else:
            lid = league.get("id") or 0
            pick = "1" if lid % 3 == 0 else ("X" if lid % 3 == 1 else "2")
            confidence, risk = 64.0, 36.0

        rows.append({
            "fixture_id": fixture.get("id"),
            "match_date": pd.to_datetime(dt, utc=True).tz_convert(None),
            "date": pd.to_datetime(dt, utc=True).tz_convert(None).date(),
            "league": league.get("name", "Unknown"),
            "league_id": int(league.get("id") or 0),
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
        df = df.sort_values(["match_date", "league_id"]).reset_index(drop=True)
    return df

@st.cache_data(ttl=300)
def load_fixtures_for_day(target_date: str):
    code, text, payload = api_get("/fixtures", params={"date": target_date})
    debug = [f"/fixtures?date={target_date} => {code}"]
    if code != 200 or not payload:
        debug.append(text[:300])
        return pd.DataFrame(), debug
    return parse_fixtures(payload), debug

@st.cache_data(ttl=300)
def load_window(start_date: str, days: int = 10):
    all_rows = []
    debug = []
    start = pd.to_datetime(start_date).date()

    for i in range(days + 1):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        df, dbg = load_fixtures_for_day(d)
        debug.extend(dbg)
        if not df.empty:
            all_rows.append(df)

    if all_rows:
        out = pd.concat(all_rows, ignore_index=True)
        out = out.drop_duplicates(subset=["fixture_id"]).sort_values(["match_date", "league_id"]).reset_index(drop=True)
        return out, debug
    return pd.DataFrame(), debug

def league_rank(league_id):
    return IMPORTANT_LEAGUES.get(int(league_id), 50)

def importance_badge(rank):
    if rank >= 95:
        return "🔥"
    if rank >= 90:
        return "⭐"
    if rank >= 80:
        return "✅"
    return "•"

st.title("Football Predictions")
st.caption(f"Днес: {date.today().strftime('%Y-%m-%d')}")

if not API_KEY:
    st.error("Липсва API_FOOTBALL_KEY secret.")
    st.stop()

window_days = st.slider("Lookahead days", 3, 10, 10)
fixtures_df, fixtures_debug = load_window(date.today().strftime("%Y-%m-%d"), days=window_days)

with st.expander("API debug"):
    for line in fixtures_debug:
        st.write(line)

if fixtures_df.empty:
    st.warning("Няма fixtures за днес и следващите дни.")
    st.stop()

fixtures_df["league_rank"] = fixtures_df["league_id"].apply(league_rank)
fixtures_df["league_badge"] = fixtures_df["league_id"].apply(lambda x: importance_badge(league_rank(x)))

search = st.text_input("Search team or league", placeholder="Напр. Arsenal, UEFA, Madrid")
filtered = fixtures_df.copy()
if search:
    q = search.lower()
    filtered = filtered[
        filtered["home"].str.lower().str.contains(q, na=False)
        | filtered["away"].str.lower().str.contains(q, na=False)
        | filtered["league"].str.lower().str.contains(q, na=False)
        | filtered["country"].str.lower().str.contains(q, na=False)
    ]

if filtered.empty:
    st.info("Няма съвпадения за търсенето.")
    st.stop()

top_matches = (
    filtered.sort_values(["league_rank", "match_date"], ascending=[False, True])
    .head(12)
    .copy()
)

st.markdown(
    f"<div style='color:{COLOR_PALETTE['header']};font-size:1.2rem;font-weight:800'>Top matches for the next {window_days} days</div>",
    unsafe_allow_html=True,
)
for _, r in top_matches.iterrows():
    with st.container(border=True):
        st.markdown(
            f"<div style='color:{COLOR_PALETTE['date']};font-weight:700'>{r['date'].strftime('%A, %d %B %Y')}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='color:{COLOR_PALETTE['team']};font-size:1.15rem'><b>{r['home']}</b> vs <b>{r['away']}</b></div>",
            unsafe_allow_html=True,
        )
        st.caption(f"{r['league']} • {r['country']} • {r['round']} • {r['match_date'].strftime('%H:%M')} • {r['league_badge']} rank {int(r['league_rank'])}")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div style='color:{COLOR_PALETTE['pick']};font-weight:700'>Pick: {r['pick']}</div>", unsafe_allow_html=True)
        c2.markdown(f"<div style='color:{COLOR_PALETTE['confidence']};font-weight:700'>Confidence: {r['confidence']:.1f}%</div>", unsafe_allow_html=True)
        c3.markdown(f"<div style='color:{COLOR_PALETTE['risk']};font-weight:700'>Risk: {r['risk']:.1f}%</div>", unsafe_allow_html=True)

st.markdown("## Fixtures by date")

for current_date, day_df in filtered.groupby("date", sort=True):
    day_df = day_df.sort_values(["league_rank", "match_date"], ascending=[False, True]).copy()
    date_label = pd.to_datetime(current_date).strftime("%A, %d %B %Y")
    with st.expander(f"{date_label} — {len(day_df)} matches", expanded=False):
        leagues = day_df.sort_values(["league_rank", "match_date"], ascending=[False, True]).groupby("league", sort=False)
        for league_name, league_df in leagues:
            league_df = league_df.sort_values("match_date")
            lid = int(league_df.iloc[0]["league_id"])
            badge = importance_badge(league_rank(lid))
            with st.expander(f"{badge} {league_name} — {len(league_df)} matches", expanded=False):
                for _, r in league_df.iterrows():
                    st.markdown(
                        f"<div style='padding:0.35rem 0.2rem;border-bottom:1px solid #e5e7eb'>"
                        f"<span style='color:{COLOR_PALETTE['team']};font-weight:700'>{r['home']}</span> "
                        f"vs "
                        f"<span style='color:{COLOR_PALETTE['team']};font-weight:700'>{r['away']}</span>"
                        f" <span style='color:{COLOR_PALETTE['muted']}'>({r['match_date'].strftime('%H:%M')})</span>"
                        f" <span style='color:{COLOR_PALETTE['pick']};font-weight:700'>Pick {r['pick']}</span>"
                        f" <span style='color:{COLOR_PALETTE['confidence']};font-weight:700'>Conf {r['confidence']:.0f}%</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if pd.notna(r["score_home"]) and pd.notna(r["score_away"]):
                        st.caption(f"Final score: {r['score_home']} - {r['score_away']}")
