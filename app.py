import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="wide")

BASE_URL = "https://v3.football.api-sports.io"
PREDICTION_THRESHOLD = 40
LOOKAHEAD_DAYS = 10
NEXT_PER_LEAGUE = 10

IMPORTANT_LEAGUES = {
    2: 100,
    3: 97,
    39: 96,
    140: 95,
    78: 94,
    135: 93,
    61: 92,
    88: 90,
    94: 89,
}

CANDIDATE_LEAGUES = list(IMPORTANT_LEAGUES.keys())

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
        r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params or {}, timeout=20)
        try:
            payload = r.json()
        except Exception:
            payload = None
        return r.status_code, r.text, payload
    except Exception as e:
        return None, str(e), None

def league_rank(league_id):
    return IMPORTANT_LEAGUES.get(int(league_id or 0), 50)

def badge(rank):
    if rank >= 95:
        return "🔥"
    if rank >= 90:
        return "⭐"
    if rank >= 80:
        return "✅"
    return "•"

def score_fixture(row):
    score = 0
    if row.get("has_fixture"):
        score += 15
    if row.get("has_odds"):
        score += 20
    if row.get("has_prediction_api"):
        score += 20
    if row.get("has_stats"):
        score += 15
    if row.get("has_injuries"):
        score += 10
    if row.get("has_form"):
        score += 10
    if row.get("important_league"):
        score += 10
    return min(score, 100)

def prediction_pick(row):
    if row.get("market_pick"):
        return row["market_pick"]
    if row.get("home_strength", 0) > row.get("away_strength", 0):
        return "1"
    if row.get("away_strength", 0) > row.get("home_strength", 0):
        return "2"
    return "X"

def build_summary(row):
    parts = []
    if row["pick"] == "1":
        parts.append("домакините са по-силният профил")
    elif row["pick"] == "2":
        parts.append("гостите са по-силният профил")
    else:
        parts.append("мачът е балансиран")

    if row["has_odds"]:
        parts.append("има пазарен сигнал")
    if row["has_stats"]:
        parts.append("има статистическа опора")
    if row["has_injuries"]:
        parts.append("има данни за отсъствия")
    if row["has_prediction_api"]:
        parts.append("има външна прогнозна индикация")

    return "Прогнозата е " + row["pick"] + ", защото " + ", ".join(parts) + "."

def build_flags(row):
    flags = []
    if not row.get("has_odds"):
        flags.append("no odds")
    if not row.get("has_stats"):
        flags.append("limited stats")
    if not row.get("has_injuries"):
        flags.append("no injuries data")
    if row.get("prediction_score", 0) < 60:
        flags.append("lower confidence")
    return flags

def parse_fixtures(payload):
    rows = []
    for f in (payload or {}).get("response", []):
        fixture = f.get("fixture", {}) or {}
        league = f.get("league", {}) or {}
        teams = f.get("teams", {}) or {}
        goals = f.get("goals", {}) or {}
        status = fixture.get("status", {}) or {}

        dt = fixture.get("date")
        if not dt:
            continue

        match_date = pd.to_datetime(dt, utc=True).tz_convert(None)
        lid = int(league.get("id") or 0)
        rows.append({
            "fixture_id": fixture.get("id"),
            "match_date": match_date,
            "date": match_date.date(),
            "league": league.get("name", "Unknown"),
            "league_id": lid,
            "country": league.get("country", ""),
            "round": league.get("round", ""),
            "home": (teams.get("home", {}) or {}).get("name", "Unknown"),
            "away": (teams.get("away", {}) or {}).get("name", "Unknown"),
            "status": status.get("short", ""),
            "has_fixture": True,
            "has_odds": bool(f.get("odds")),
            "has_prediction_api": False,
            "has_stats": False,
            "has_injuries": False,
            "has_form": True,
            "important_league": lid in IMPORTANT_LEAGUES,
            "home_strength": 0,
            "away_strength": 0,
            "market_pick": None,
            "score_home": goals.get("home"),
            "score_away": goals.get("away"),
        })
    return pd.DataFrame(rows)

@st.cache_data(ttl=300)
def load_window(start_date: str, days: int = LOOKAHEAD_DAYS):
    all_rows = []
    debug = []
    start = pd.to_datetime(start_date).date()

    for league_id in CANDIDATE_LEAGUES:
        code, text, payload = api_get("/fixtures", params={"league": league_id, "next": NEXT_PER_LEAGUE})
        debug.append(f"/fixtures?league={league_id}&next={NEXT_PER_LEAGUE} => {code}")
        if code == 200 and payload and payload.get("response"):
            df = parse_fixtures(payload)
            if not df.empty:
                all_rows.append(df)

    if all_rows:
        out = pd.concat(all_rows, ignore_index=True).drop_duplicates(subset=["fixture_id"])
        out = out.sort_values(["match_date", "league_id"]).reset_index(drop=True)
        return out, debug

    for i in range(days + 1):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        code, text, payload = api_get("/fixtures", params={"date": d})
        debug.append(f"/fixtures?date={d} => {code}")
        if code != 200 or not payload:
            continue
        df = parse_fixtures(payload)
        if not df.empty:
            all_rows.append(df)

    if all_rows:
        out = pd.concat(all_rows, ignore_index=True).drop_duplicates(subset=["fixture_id"])
        out = out.sort_values(["match_date", "league_id"]).reset_index(drop=True)
        return out, debug

    return pd.DataFrame(), debug

def enrich_predictions(df):
    if df.empty:
        return df
    df = df.copy()
    df["prediction_score"] = df.apply(score_fixture, axis=1)
    df["pick"] = df.apply(prediction_pick, axis=1)
    df["prediction_status"] = df["prediction_score"].apply(
        lambda x: "enough data" if x >= PREDICTION_THRESHOLD else "weak data"
    )
    return df

st.title("Football Predictions")
st.caption(f"Днес: {date.today().strftime('%Y-%m-%d')}")

if not API_KEY:
    st.error("Липсва API_FOOTBALL_KEY secret.")
    st.stop()

window_days = st.slider("Lookahead days", 3, 10, 10)
df, debug = load_window(date.today().strftime("%Y-%m-%d"), days=window_days)
df = enrich_predictions(df)

with st.expander("API debug"):
    for line in debug:
        st.write(line)

if df.empty:
    st.warning("Няма fixtures за днес и следващите дни.")
    st.stop()

search = st.text_input("Search team or league", placeholder="Напр. Arsenal, Champions League")
filtered = df.copy()
if search:
    q = search.lower()
    filtered = filtered[
        filtered["home"].str.lower().str.contains(q, na=False)
        | filtered["away"].str.lower().str.contains(q, na=False)
        | filtered["league"].str.lower().str.contains(q, na=False)
        | filtered["country"].str.lower().str.contains(q, na=False)
    ]

filtered = filtered[filtered["prediction_score"] >= PREDICTION_THRESHOLD].copy()

if filtered.empty:
    st.info("Няма мачове с достатъчно данни за показване.")
    st.stop()

filtered["league_rank"] = filtered["league_id"].apply(league_rank)
filtered["league_badge"] = filtered["league_id"].apply(lambda x: badge(league_rank(x)))

st.markdown(
    f"<div style='color:{COLORS['header']};font-size:1.25rem;font-weight:800'>Top matches for the next {window_days} days</div>",
    unsafe_allow_html=True,
)

top_groups = filtered.sort_values(["league_rank", "match_date"], ascending=[False, True]).groupby("league", sort=False)
for league_name, league_df in top_groups:
    league_df = league_df.sort_values("match_date")
    lid = int(league_df.iloc[0]["league_id"])
    lg_rank = league_rank(lid)
    lg_badge = badge(lg_rank)
    with st.expander(f"{lg_badge} {league_name} — {len(league_df)} matches", expanded=False):
        for _, r in league_df.iterrows():
            st.markdown(f"<div style='color:{COLORS['date']};font-weight:700'>{pd.to_datetime(r['date']).strftime('%A, %d %B %Y')}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='color:{COLORS['team']};font-size:1.1rem'><b>{r['home']}</b> vs <b>{r['away']}</b></div>", unsafe_allow_html=True)
            st.caption(f"{r['country']} • {r['round']} • {r['match_date'].strftime('%H:%M')} • {r['league_badge']} rank {int(r['league_rank'])}")
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<div style='color:{COLORS['pick']};font-weight:700'>Pick: {r['pick']}</div>", unsafe_allow_html=True)
            c2.markdown(f"<div style='color:{COLORS['confidence']};font-weight:700'>Confidence: {r['prediction_score']:.1f}%</div>", unsafe_allow_html=True)
            c3.markdown(f"<div style='color:{COLORS['risk']};font-weight:700'>Status: {r['prediction_status']}</div>", unsafe_allow_html=True)

            with st.expander("Summary and flags", expanded=False):
                st.write(build_summary(r))
                flags = build_flags(r)
                if flags:
                    st.markdown("**Red flags**")
                    for f in flags:
                        st.markdown(f"- <span style='color:{COLORS['flag']};font-weight:700'>{f}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span style='color:{COLORS['ok']};font-weight:700'>No major red flags detected from the current data set.</span>", unsafe_allow_html=True)

st.markdown("## Fixtures by date")
for current_date, day_df in filtered.groupby("date", sort=True):
    day_df = day_df.sort_values(["league_rank", "match_date"], ascending=[False, True]).copy()
    date_label = pd.to_datetime(current_date).strftime("%A, %d %B %Y")
    with st.expander(f"{date_label} — {len(day_df)} matches", expanded=False):
        leagues = day_df.sort_values(["league_rank", "match_date"], ascending=[False, True]).groupby("league", sort=False)
        for league_name, league_df in leagues:
            league_df = league_df.sort_values("match_date")
            lid = int(league_df.iloc[0]["league_id"])
            lg_rank = league_rank(lid)
            lg_badge = badge(lg_rank)
            with st.expander(f"{lg_badge} {league_name} — {len(league_df)} matches", expanded=False):
                for _, r in league_df.iterrows():
                    st.markdown(
                        f"<div style='padding:0.35rem 0.2rem;border-bottom:1px solid #e5e7eb'>"
                        f"<span style='color:{COLORS['team']};font-weight:700'>{r['home']}</span> vs "
                        f"<span style='color:{COLORS['team']};font-weight:700'>{r['away']}</span> "
                        f"<span style='color:{COLORS['muted']}'>({r['match_date'].strftime('%H:%M')})</span> "
                        f"<span style='color:{COLORS['pick']};font-weight:700'>Pick {r['pick']}</span> "
                        f"<span style='color:{COLORS['confidence']};font-weight:700'>Conf {r['prediction_score']:.0f}%</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
