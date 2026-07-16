import os
from datetime import date, timedelta
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="wide")

BASE_URL = "https://v3.football.api-sports.io"
WORLDCUP_BASE_URL = os.getenv("WORLDCUP_API_BASE_URL", "https://api.worldcupapi.com")

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
    "wc": "#ef4444",
}

def api_get(url, params=None, headers=None, timeout=20):
    try:
        r = requests.get(url, headers=headers or {}, params=params or {}, timeout=timeout)
        try:
            payload = r.json()
        except Exception:
            payload = None
        return r.status_code, r.text, payload
    except Exception as e:
        return None, str(e), None

def league_rank(league_id):
    return IMPORTANT_LEAGUES.get(int(league_id), 50)

def badge(rank):
    if rank >= 95:
        return "🔥"
    if rank >= 90:
        return "⭐"
    if rank >= 80:
        return "✅"
    return "•"

def parse_af(payload):
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
            "source": "api-football",
            "fixture_id": f"af_{fixture.get('id')}",
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
        df = df.sort_values("match_date").reset_index(drop=True)
    return df

def parse_wc(payload):
    rows = []
    data = payload.get("data", []) if isinstance(payload, dict) else []
    for m in data:
        dt = m.get("date") or m.get("kickoff") or m.get("match_time")
        if not dt:
            continue
        ts = pd.to_datetime(dt, utc=True, errors="coerce")
        if pd.isna(ts):
            continue
        rows.append({
            "source": "worldcupapi",
            "fixture_id": f"wc_{m.get('id') or m.get('match_id') or dt}",
            "match_date": ts.tz_convert(None),
            "date": ts.tz_convert(None).date(),
            "league": m.get("competition", "FIFA World Cup"),
            "league_id": 9999,
            "country": m.get("country", "International"),
            "round": m.get("stage", m.get("group", "")),
            "home": m.get("home_team", m.get("home", "Unknown")),
            "away": m.get("away_team", m.get("away", "Unknown")),
            "status": m.get("status", "NS"),
            "pick": "1",
            "confidence": 64.0,
            "risk": 36.0,
            "score_home": m.get("home_score"),
            "score_away": m.get("away_score"),
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("match_date").reset_index(drop=True)
    return df

@st.cache_data(ttl=300)
def load_af_window(start_date: str, days: int = 10):
    all_rows = []
    debug = []
    start = pd.to_datetime(start_date).date()
    for i in range(days + 1):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        code, text, payload = api_get(f"{BASE_URL}/fixtures", params={"date": d}, headers=HEADERS)
        debug.append(f"AF /fixtures?date={d} => {code}")
        if code != 200 or not payload:
            debug.append(text[:250])
            continue
        df = parse_af(payload)
        if not df.empty:
            all_rows.append(df)
    if all_rows:
        out = pd.concat(all_rows, ignore_index=True).drop_duplicates(subset=["fixture_id"])
        out = out.sort_values(["match_date", "league_id"]).reset_index(drop=True)
        return out, debug
    return pd.DataFrame(), debug

@st.cache_data(ttl=300)
def load_wc_window(start_date: str, days: int = 10):
    all_rows = []
    debug = []
    start = pd.to_datetime(start_date).date()
    for i in range(days + 1):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        code, text, payload = api_get(f"{WORLDCUP_BASE_URL}/fixtures", params={"date": d})
        debug.append(f"WC /fixtures?date={d} => {code}")
        if code != 200 or not payload:
            debug.append(text[:250])
            continue
        df = parse_wc(payload)
        if not df.empty:
            all_rows.append(df)
    if all_rows:
        out = pd.concat(all_rows, ignore_index=True).drop_duplicates(subset=["fixture_id"])
        out = out.sort_values("match_date").reset_index(drop=True)
        return out, debug
    return pd.DataFrame(), debug

def odds_by_fixture(fixture_id):
    code, text, payload = api_get(f"{BASE_URL}/odds", params={"fixture": fixture_id}, headers=HEADERS)
    if code != 200 or not payload:
        return None
    return payload

def extract_best_odds(payload):
    if not payload or "response" not in payload or not payload["response"]:
        return None
    item = payload["response"][0]
    bookmakers = item.get("bookmakers", []) or []
    for bk in bookmakers:
        bets = bk.get("bets", []) or []
        for bet in bets:
            values = bet.get("values", []) or []
            out = {}
            for v in values:
                name = str(v.get("value", "")).upper()
                odd = v.get("odd")
                if name in {"HOME", "1"}:
                    out["1"] = odd
                elif name in {"DRAW", "X"}:
                    out["X"] = odd
                elif name in {"AWAY", "2"}:
                    out["2"] = odd
            if out:
                return {"bookmaker": bk.get("name", ""), "1": out.get("1"), "X": out.get("X"), "2": out.get("2")}
    return None

st.title("Football Predictions")
st.caption(f"Днес: {date.today().strftime('%Y-%m-%d')}")

if not API_KEY:
    st.error("Липсва API_FOOTBALL_KEY secret.")
    st.stop()

window_days = st.slider("Lookahead days", 3, 10, 10)
af_df, af_debug = load_af_window(date.today().strftime("%Y-%m-%d"), days=window_days)
wc_df, wc_debug = load_wc_window(date.today().strftime("%Y-%m-%d"), days=window_days)

with st.expander("API debug"):
    for line in af_debug:
        st.write(line)
    for line in wc_debug:
        st.write(line)

combined = pd.concat([af_df, wc_df], ignore_index=True) if not af_df.empty or not wc_df.empty else pd.DataFrame()
if combined.empty:
    st.warning("Няма fixtures за днес и следващите дни.")
    st.stop()

combined["league_rank"] = combined["league_id"].apply(league_rank)
combined["league_badge"] = combined["league_id"].apply(lambda x: badge(league_rank(x)))

search = st.text_input("Search team or league", placeholder="Напр. World Cup, Arsenal, Madrid")
filtered = combined.copy()
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

st.markdown(f"<div style='color:{COLORS['header']};font-size:1.25rem;font-weight:800'>Top matches for the next {window_days} days</div>", unsafe_allow_html=True)
top_df = filtered.sort_values(["league_rank", "match_date"], ascending=[False, True]).copy()
for league_name, league_df in top_df.groupby("league", sort=False):
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
            c2.markdown(f"<div style='color:{COLORS['confidence']};font-weight:700'>Confidence: {r['confidence']:.1f}%</div>", unsafe_allow_html=True)
            c3.markdown(f"<div style='color:{COLORS['risk']};font-weight:700'>Risk: {r['risk']:.1f}%</div>", unsafe_allow_html=True)
            with st.expander("Odds preview", expanded=False):
                odds = odds_by_fixture(int(str(r["fixture_id"]).replace("af_", ""))) if r["source"] == "api-football" else None
                best = extract_best_odds(odds)
                if best:
                    st.write(f"Bookmaker: {best['bookmaker']}")
                    st.write(f"1: {best['1']} | X: {best['X']} | 2: {best['2']}")
                else:
                    st.info("No odds available yet for this fixture.")

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
                        f"<span style='color:{COLORS['confidence']};font-weight:700'>Conf {r['confidence']:.0f}%</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
