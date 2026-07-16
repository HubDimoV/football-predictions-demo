import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="wide")

BASE_URL = "https://v3.football.api-sports.io"
LOOKAHEAD_DAYS = 10

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
        rows.append({
            "fixture_id": fixture.get("id"),
            "match_date": md,
            "date": md.date(),
            "time": md.strftime("%H:%M"),
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
            "odds_bookmakers": 0,
            "confidence": 20.0,
            "confidence_parts": "",
        })
    return pd.DataFrame(rows)

def seed_fixtures():
    debug = []
    all_rows = []
    start = date.today()
    end = start + timedelta(days=LOOKAHEAD_DAYS)

    for params in [
        {"date": start.strftime("%Y-%m-%d"), "timezone": "Europe/Sofia"},
        {"from": start.strftime("%Y-%m-%d"), "to": end.strftime("%Y-%m-%d"), "timezone": "Europe/Sofia"},
        {"next": LOOKAHEAD_DAYS, "timezone": "Europe/Sofia"},
    ]:
        code, _, payload = api_get("/fixtures", params=params)
        debug.append(f"/fixtures?{params} => {code}")
        if code == 200 and payload and payload.get("response"):
            df = parse_fixtures(payload)
            if not df.empty:
                all_rows.append(df)

    if all_rows:
        out = pd.concat(all_rows, ignore_index=True).drop_duplicates(subset=["fixture_id"])
        out = out.sort_values(["date", "match_date"], ascending=[True, True]).reset_index(drop=True)
        return out, debug

    return pd.DataFrame(), debug

def count_bookmakers(odds_payload):
    total = 0
    for item in (odds_payload or {}).get("response", []):
        total += len(item.get("bookmakers", []) or [])
    return total

def enrich_signals(df):
    if df.empty:
        return df
    df = df.copy()
    for idx in df.index:
        fid = df.at[idx, "fixture_id"]

        code, _, payload = api_get("/odds", params={"fixture": fid})
        has_odds = bool(code == 200 and payload and payload.get("response"))
        df.at[idx, "has_odds"] = has_odds
        df.at[idx, "odds_bookmakers"] = count_bookmakers(payload) if has_odds else 0

        code, _, payload = api_get("/injuries", params={"fixture": fid})
        df.at[idx, "has_injuries"] = bool(code == 200 and payload and payload.get("response"))

        code, _, payload = api_get("/predictions", params={"fixture": fid})
        df.at[idx, "has_predictions"] = bool(code == 200 and payload and payload.get("response"))

        code, _, payload = api_get("/fixtures/statistics", params={"fixture": fid})
        df.at[idx, "has_stats"] = bool(code == 200 and payload and payload.get("response"))

        conf = 20.0
        parts = []
        if df.at[idx, "has_odds"]:
            conf += 20
            parts.append("odds")
        if df.at[idx, "odds_bookmakers"] > 0:
            conf += 10
            parts.append("bookmakers")
        if df.at[idx, "has_predictions"]:
            conf += 25
            parts.append("predictions")
        if df.at[idx, "has_stats"]:
            conf += 15
            parts.append("stats")
        if df.at[idx, "has_injuries"]:
            conf += 10
            parts.append("injuries")
        if df.at[idx, "score_home"] is not None and df.at[idx, "score_away"] is not None:
            conf += 5
            parts.append("score")
        df.at[idx, "confidence"] = min(conf, 100)
        df.at[idx, "confidence_parts"] = ", ".join(parts) if parts else "base"
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
    p = build_pick(row)
    if p == "1":
        base = "домакините изглеждат по-силни"
    elif p == "2":
        base = "гостите изглеждат по-силни"
    else:
        base = "мачът е балансиран"
    return f"Прогнозата е {p}, защото {base}."

def build_flags(row):
    flags = []
    if not row.get("has_odds"):
        flags.append("no odds")
    if row.get("odds_bookmakers", 0) == 0:
        flags.append("no bookmaker coverage")
    if not row.get("has_predictions"):
        flags.append("no prediction api")
    if not row.get("has_stats"):
        flags.append("limited stats")
    if not row.get("has_injuries"):
        flags.append("no injuries data")
    return flags

st.title("Football Predictions")
st.caption(f"Днес: {date.today().strftime('%Y-%m-%d')}")

if not API_KEY:
    st.error("Липсва API_FOOTBALL_KEY secret.")
    st.stop()

df, debug = seed_fixtures()
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

st.markdown(f"<div style='color:{COLORS['header']};font-size:1.25rem;font-weight:800'>Top matches for the next {LOOKAHEAD_DAYS} days</div>", unsafe_allow_html=True)

for current_date, day_df in filtered.groupby("date", sort=True):
    day_df = day_df.sort_values(["confidence", "match_date"], ascending=[False, True])
    date_label = pd.to_datetime(current_date).strftime("%A, %d %B %Y")
    with st.expander(f"{date_label} — {len(day_df)} matches", expanded=True):
        for _, r in day_df.head(10).iterrows():
            st.markdown(f"<div style='color:{COLORS['date']};font-weight:700'>{r['league']}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='color:{COLORS['team']};font-size:1.1rem'><b>{r['home']}</b> vs <b>{r['away']}</b></div>", unsafe_allow_html=True)
            st.caption(f"{r['country']} • {r['round']} • {r['time']}")
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<div style='color:{COLORS['pick']};font-weight:700'>Pick: {build_pick(r)}</div>", unsafe_allow_html=True)
            c2.markdown(f"<div style='color:{COLORS['confidence']};font-weight:700'>Confidence: {r['confidence']:.1f}%</div>", unsafe_allow_html=True)
            c3.markdown(f"<div style='color:{COLORS['risk']};font-weight:700'>Status: {'enough data' if r['confidence'] >= 50 else 'weak data'}</div>", unsafe_allow_html=True)

            with st.expander("Summary and flags", expanded=False):
                st.write(build_summary(r))
                st.caption(f"Signals: {r['confidence_parts']}")
                flags = build_flags(r)
                if flags:
                    st.markdown("**Red flags**")
                    for f in flags:
                        st.markdown(f"- <span style='color:{COLORS['flag']};font-weight:700'>{f}</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span style='color:{COLORS['ok']};font-weight:700'>No major red flags detected from the current data set.</span>", unsafe_allow_html=True)
