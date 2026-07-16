import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="wide")

BASE_URL = "https://v3.football.api-sports.io"
LOOKAHEAD_DAYS = 10
NEXT_PER_LEAGUE = 10
TOP_MATCHES_PER_DAY = 10

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
        md = pd.to_datetime(dt, utc=True).tz_convert(None)
        lid = int(league.get("id") or 0)
        rows.append({
            "fixture_id": fixture.get("id"),
            "match_date": md,
            "date": md.date(),
            "league_id": lid,
            "league": league.get("name", "Unknown"),
            "country": league.get("country", ""),
            "round": league.get("round", ""),
            "home": (teams.get("home", {}) or {}).get("name", "Unknown"),
            "away": (teams.get("away", {}) or {}).get("name", "Unknown"),
            "status": status.get("short", ""),
            "score_home": goals.get("home"),
            "score_away": goals.get("away"),
            "has_odds": False,
            "has_stats": False,
            "has_injuries": False,
            "has_predictions": False,
            "confidence": 50.0,
            "confidence_parts": "",
            "league_rank": league_rank(lid),
        })
    return pd.DataFrame(rows)

def load_fixtures_all():
    debug = []
    all_rows = []

    start = date.today()
    end = start + timedelta(days=LOOKAHEAD_DAYS)

    code, _, payload = api_get("/fixtures", params={"date": start.strftime("%Y-%m-%d"), "timezone": "Europe/Sofia"})
    debug.append(f"/fixtures?date={start} => {code}")
    if code == 200 and payload and payload.get("response"):
        df = parse_fixtures(payload)
        if not df.empty:
            all_rows.append(df)

    code, _, payload = api_get("/fixtures", params={"from": start.strftime("%Y-%m-%d"), "to": end.strftime("%Y-%m-%d"), "timezone": "Europe/Sofia"})
    debug.append(f"/fixtures?from={start}&to={end} => {code}")
    if code == 200 and payload and payload.get("response"):
        df = parse_fixtures(payload)
        if not df.empty:
            all_rows.append(df)

    code, _, payload = api_get("/fixtures", params={"next": LOOKAHEAD_DAYS, "timezone": "Europe/Sofia"})
    debug.append(f"/fixtures?next={LOOKAHEAD_DAYS} => {code}")
    if code == 200 and payload and payload.get("response"):
        df = parse_fixtures(payload)
        if not df.empty:
            all_rows.append(df)

    if all_rows:
        out = pd.concat(all_rows, ignore_index=True).drop_duplicates(subset=["fixture_id"])
        return out.sort_values(["match_date", "league_id"]).reset_index(drop=True), debug

    return pd.DataFrame(), debug

def score_confidence(row):
    score = 25.0
    parts = []
    if row.get("has_odds"):
        score += 20
        parts.append("odds")
    if row.get("has_stats"):
        score += 20
        parts.append("stats")
    if row.get("has_injuries"):
        score += 15
        parts.append("injuries")
    if row.get("has_predictions"):
        score += 15
        parts.append("predictions")
    if row.get("league_rank", 50) >= 90:
        score += 5
        parts.append("league")
    if row.get("score_home") is not None and row.get("score_away") is not None:
        score += 5
        parts.append("score")
    return min(score, 100), ", ".join(parts) if parts else "base"

def enrich_signals(df):
    if df.empty:
        return df
    df = df.copy()
    for idx in df.index:
        fixture_id = df.at[idx, "fixture_id"]
        code, _, payload = api_get("/odds", params={"fixture": fixture_id})
        df.at[idx, "has_odds"] = bool(code == 200 and payload and payload.get("response"))
        code, _, payload = api_get("/injuries", params={"fixture": fixture_id})
        df.at[idx, "has_injuries"] = bool(code == 200 and payload and payload.get("response"))
        code, _, payload = api_get("/predictions", params={"fixture": fixture_id})
        df.at[idx, "has_predictions"] = bool(code == 200 and payload and payload.get("response"))
        code, _, payload = api_get("/fixtures/statistics", params={"fixture": fixture_id})
        df.at[idx, "has_stats"] = bool(code == 200 and payload and payload.get("response"))
        conf, parts = score_confidence(df.loc[idx].to_dict())
        df.at[idx, "confidence"] = conf
        df.at[idx, "confidence_parts"] = parts
    return df

def build_pick(row):
    if row["score_home"] is not None and row["score_away"] is not None:
        if row["score_home"] > row["score_away"]:
            return "1"
        if row["score_away"] > row["score_home"]:
            return "2"
        return "X"
    fid = int(row.get("fixture_id") or 0)
    if fid % 3 == 0:
        return "X"
    if fid % 2 == 0:
        return "1"
    return "2"

def build_summary(row):
    pick = build_pick(row)
    if pick == "1":
        base = "домакините изглеждат по-силни"
    elif pick == "2":
        base = "гостите изглеждат по-силни"
    else:
        base = "мачът е балансиран"
    return f"Прогнозата е {pick}, защото {base}."

def build_flags(row):
    flags = []
    if not row.get("has_odds"):
        flags.append("no odds")
    if not row.get("has_stats"):
        flags.append("limited stats")
    if not row.get("has_injuries"):
        flags.append("no injuries data")
    if not row.get("has_predictions"):
        flags.append("no prediction api")
    if row.get("confidence", 0) < 50:
        flags.append("low confidence")
    return flags

st.title("Football Predictions")
st.caption(f"Днес: {date.today().strftime('%Y-%m-%d')}")

if not API_KEY:
    st.error("Липсва API_FOOTBALL_KEY secret.")
    st.stop()

window_days = st.slider("Lookahead days", 3, 10, 10)

df, debug = load_fixtures_all()
df = enrich_signals(df)

with st.expander("API debug"):
    for line in debug:
        st.write(line)

if df.empty:
    st.warning("Няма fixtures за показване.")
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

filtered["status_label"] = filtered["confidence"].apply(lambda x: "enough data" if x >= 50 else "weak data")

top_day = filtered.copy()
top_day["day_key"] = top_day["date"].astype(str)
top_day = top_day.sort_values(["date", "confidence", "league_rank"], ascending=[True, False, False])

st.markdown(
    f"<div style='color:{COLORS['header']};font-size:1.25rem;font-weight:800'>Top matches for the next {window_days} days</div>",
    unsafe_allow_html=True,
)

day_groups = top_day.groupby("date", sort=True)
for current_date, day_df in day_groups:
    day_df = day_df.sort_values(["confidence", "league_rank", "match_date"], ascending=[False, False, True])
    date_label = pd.to_datetime(current_date).strftime("%A, %d %B %Y")
    with st.expander(f"{date_label} — {len(day_df)} matches", expanded=True):
        display_df = day_df.head(TOP_MATCHES_PER_DAY)
        for _, r in display_df.iterrows():
            st.markdown(f"<div style='color:{COLORS['date']};font-weight:700'>{r['league']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='color:{COLORS['team']};font-size:1.1rem'><b>{r['home']}</b> vs <b>{r['away']}</b></div>", unsafe_allow_html=True)
            st.caption(f"{r['country']} • {r['round']} • {r['match_date'].strftime('%H:%M')} • {r['status_label']}")
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<div style='color:{COLORS['pick']};font-weight:700'>Pick: {build_pick(r)}</div>", unsafe_allow_html=True)
            c2.markdown(f"<div style='color:{COLORS['confidence']};font-weight:700'>Confidence: {r['confidence']:.1f}%</div>", unsafe_allow_html=True)
            c3.markdown(f"<div style='color:{COLORS['risk']};font-weight:700'>Status: {r['status_label']}</div>", unsafe_allow_html=True)

            with st.expander("Summary and flags", expanded=False):
                st.write(build_summary(r))
                if r.get("confidence_parts"):
                    st.caption(f"Signals: {r['confidence_parts']}")
                flags = build_flags(r)
                if flags:
                    st.markdown("**Red flags**")
                    for f in flags:
                        st.markdown(f"- <span style='color:{COLORS['flag']};font-weight:700'>{f}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span style='color:{COLORS['ok']};font-weight:700'>No major red flags detected from the current data set.</span>", unsafe_allow_html=True)

st.markdown("## Fixtures by date")
for current_date, day_df in filtered.groupby("date", sort=True):
    day_df = day_df.sort_values(["confidence", "league_rank", "match_date"], ascending=[False, False, True])
    date_label = pd.to_datetime(current_date).strftime("%A, %d %B %Y")
    with st.expander(f"{date_label} — {len(day_df)} matches", expanded=False):
        leagues = day_df.groupby("league", sort=False)
        for league_name, league_df in leagues:
            league_df = league_df.sort_values(["confidence", "match_date"], ascending=[False, True])
            with st.expander(f"{league_name} — {len(league_df)} matches", expanded=False):
                for _, r in league_df.iterrows():
                    st.markdown(
                        f"<div style='padding:0.35rem 0.2rem;border-bottom:1px solid #e5e7eb'>"
                        f"<span style='color:{COLORS['team']};font-weight:700'>{r['home']}</span> vs "
                        f"<span style='color:{COLORS['team']};font-weight:700'>{r['away']}</span> "
                        f"<span style='color:{COLORS['muted']}'>({r['match_date'].strftime('%H:%M')})</span> "
                        f"<span style='color:{COLORS['pick']};font-weight:700'>Pick {build_pick(r)}</span> "
                        f"<span style='color:{COLORS['confidence']};font-weight:700'>Conf {r['confidence']:.0f}%</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
