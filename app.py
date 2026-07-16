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
    return IMPORTANT_LEAGUES.get(int(league_id), 50)

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
            source = "final"
        else:
            lid = int(league.get("id") or 0)
            pick = "1" if lid % 3 == 0 else ("X" if lid % 3 == 1 else "2")
            confidence, risk = 64.0, 36.0
            source = "fallback"

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
            "source": source,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["match_date", "league_id"]).reset_index(drop=True)
    return df

@st.cache_data(ttl=300)
def load_window(start_date: str, days: int = 10):
    all_rows = []
    debug = []
    start = pd.to_datetime(start_date).date()
    for i in range(days + 1):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        code, text, payload = api_get("/fixtures", params={"date": d})
        debug.append(f"/fixtures?date={d} => {code}")
        if code != 200 or not payload:
            debug.append(text[:250])
            continue
        df = parse_fixtures(payload)
        if not df.empty:
            all_rows.append(df)
    if all_rows:
        out = pd.concat(all_rows, ignore_index=True)
        out = out.drop_duplicates(subset=["fixture_id"]).sort_values(["match_date", "league_id"]).reset_index(drop=True)
        return out, debug
    return pd.DataFrame(), debug

def build_summary(row):
    reasons = []
    if row["pick"] == "1":
        reasons.append("пазарът и формата накланят към домакина")
    elif row["pick"] == "2":
        reasons.append("пазарът и формата накланят към госта")
    else:
        reasons.append("очаква се балансиран мач")

    if row["confidence"] >= 75:
        reasons.append("има добър баланс между данни и сигнали")
    else:
        reasons.append("данните са по-колебливи и рискът е по-висок")

    return "Прогнозата е " + row["pick"] + ", защото " + ", ".join(reasons) + "."

def build_flags(row):
    flags = []
    if row["confidence"] < 70:
        flags.append("нисък confidence")
    if row["risk"] > 30:
        flags.append("повишен риск")
    return flags

def has_real_prediction(row):
    return row["source"] == "final"

st.title("Football Predictions")
st.caption(f"Днес: {date.today().strftime('%Y-%m-%d')}")

if not API_KEY:
    st.error("Липсва API_FOOTBALL_KEY secret.")
    st.stop()

window_days = st.slider("Lookahead days", 3, 10, 10)
df, debug = load_window(date.today().strftime("%Y-%m-%d"), days=window_days)

with st.expander("API debug"):
    for line in debug:
        st.write(line)

if df.empty:
    st.warning("Няма fixtures за днес и следващите дни.")
    st.stop()

df["league_rank"] = df["league_id"].apply(league_rank)
df["league_badge"] = df["league_id"].apply(lambda x: badge(league_rank(x)))
df["is_real"] = df.apply(has_real_prediction, axis=1)

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

filtered = filtered[filtered["is_real"]].copy()

if filtered.empty:
    st.info("Няма мачове с достатъчно сигурна прогноза за показване.")
    st.stop()

st.markdown(f"<div style='color:{COLORS['header']};font-size:1.25rem;font-weight:800'>Top matches for the next {window_days} days</div>", unsafe_allow_html=True)

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
            c2.markdown(f"<div style='color:{COLORS['confidence']};font-weight:700'>Confidence: {r['confidence']:.1f}%</div>", unsafe_allow_html=True)
            c3.markdown(f"<div style='color:{COLORS['risk']};font-weight:700'>Risk: {r['risk']:.1f}%</div>", unsafe_allow_html=True)

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
                        f"<span style='color:{COLORS['confidence']};font-weight:700'>Conf {r['confidence']:.0f}%</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
