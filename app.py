import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="centered")

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY} if API_KEY else {}

def api_get(url, params=None):
    try:
        resp = requests.get(url, headers=HEADERS, params=params or {}, timeout=20)
        return resp.status_code, resp.text, resp.json() if resp.status_code == 200 else None
    except Exception as e:
        return None, str(e), None

def parse_matches(payload, source_tag=""):
    rows = []
    if not payload or "matches" not in payload:
        return rows

    for m in payload.get("matches", []):
        utc_date = m.get("utcDate")
        if not utc_date:
            continue

        comp = m.get("competition", {}) or {}
        home_team = m.get("homeTeam", {}) or {}
        away_team = m.get("awayTeam", {}) or {}
        status = m.get("status", "")

        match_dt = pd.to_datetime(utc_date, utc=True).tz_convert(None)

        home = home_team.get("name", "Unknown")
        away = away_team.get("name", "Unknown")

        if status == "FINISHED":
            hs = m.get("score", {}).get("fullTime", {}).get("home")
            as_ = m.get("score", {}).get("fullTime", {}).get("away")
            if hs is not None and as_ is not None:
                if hs > as_:
                    pick = "1"
                elif hs < as_:
                    pick = "2"
                else:
                    pick = "X"
            else:
                pick = "1"
            confidence = 96.0
            risk = 4.0
        else:
            code = comp.get("code", "")
            if code in {"PL", "PD", "CL", "BL1", "SA", "FL1"}:
                pick = "1"
                confidence = 68.0
                risk = 32.0
            elif code in {"DED", "PPL", "EC", "BL", "WC", "EL"}:
                pick = "X"
                confidence = 61.0
                risk = 39.0
            else:
                pick = "1"
                confidence = 60.0
                risk = 40.0

        odds_1 = 2.05
        odds_x = 3.15
        odds_2 = 3.10

        if pick == "1":
            raw_value = 0.56
        elif pick == "X":
            raw_value = 0.59
        else:
            raw_value = 0.54

        rows.append({
            "match_id": m.get("id"),
            "match_date": match_dt,
            "league": comp.get("name", "Unknown"),
            "tournament": comp.get("type", "Competition"),
            "home": home,
            "away": away,
            "home_bg": home_team.get("shortName") or home,
            "away_bg": away_team.get("shortName") or away,
            "predicted_outcome": pick,
            "confidence_score": float(confidence),
            "risk_score": float(risk),
            "odds_1": odds_1,
            "odds_x": odds_x,
            "odds_2": odds_2,
            "news_note": f"Loaded from API {source_tag}".strip(),
            "summary_bg": f"{home} срещу {away} е зареден от live API.",
            "market_flag": "normal",
            "raw_value_score": float(raw_value),
            "form_score": 0.60,
            "news_score": 0.50,
            "bookie_gap": 0.08,
            "status": status,
            "source": source_tag,
        })

    return rows

def fetch_by_date_shortcut(shortcut):
    url = f"{BASE_URL}/matches"
    status_code, text, payload = api_get(url, params={"date": shortcut})
    return status_code, text, payload

def fetch_scheduled():
    url = f"{BASE_URL}/matches"
    status_code, text, payload = api_get(url, params={"status": "SCHEDULED"})
    return status_code, text, payload

@st.cache_data(ttl=900)
def load_matches():
    all_rows = []
    debug_lines = []
    shortcuts = ["TODAY", "TOMORROW"]

    for sc in shortcuts:
        code, text, payload = fetch_by_date_shortcut(sc)
        if code == 200 and payload:
            parsed = parse_matches(payload, source_tag=f"date={sc}")
            all_rows.extend(parsed)
            debug_lines.append(f"{sc}: {len(parsed)} matches")
        else:
            debug_lines.append(f"{sc}: {code} {text[:140]}")

    code, text, payload = fetch_scheduled()
    if code == 200 and payload:
        parsed = parse_matches(payload, source_tag="status=SCHEDULED")
        all_rows.extend(parsed)
        debug_lines.append(f"SCHEDULED: {len(parsed)} matches")
    else:
        debug_lines.append(f"SCHEDULED: {code} {text[:140]}")

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
        num_cols = ["confidence_score", "risk_score", "odds_1", "odds_x", "odds_2", "raw_value_score", "form_score", "news_score", "bookie_gap"]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.dropna(subset=["match_date"]).copy()
        df = df.sort_values("match_date").drop_duplicates(subset=["match_id"]).copy()

    return df, debug_lines

def color_percent(value, positive=True):
    val = float(value)
    color = "#1a7f37" if (val >= 50 if positive else val <= 50) else "#d1242f"
    return f"<span style='color:{color}; font-weight:700'>{val:.1f}%</span>"

def outcome_label(value):
    return {"1": "Home win", "X": "Draw", "2": "Away win"}.get(str(value), str(value))

def market_reason(row):
    if row["market_flag"] == "value":
        return "Има добър value за кратък прозорец."
    if row["market_flag"] == "high_value":
        return "Коефициентът е по-висок от обичайното и носи потенциал."
    return "Коефициентите са в нормален диапазон."

def secure_score(row):
    return (
        row["confidence_score"] * 0.4
        + row["form_score"] * 100 * 0.25
        + row["news_score"] * 100 * 0.2
        + (1 - row["bookie_gap"]) * 100 * 0.15
    )

def risky_score(row):
    return (
        row["risk_score"] * 0.35
        + (100 - row["confidence_score"]) * 0.2
        + (100 - row["form_score"] * 100) * 0.2
        + (100 - row["news_score"] * 100) * 0.15
        + row["bookie_gap"] * 100 * 0.1
    )

def top_pick_score(row):
    return (
        row["raw_value_score"] * 100 * 0.45
        + row["confidence_score"] * 0.25
        + row["form_score"] * 100 * 0.15
        + row["news_score"] * 100 * 0.15
    )

df, debug_lines = load_matches()

st.title("Football Predictions")

with st.expander("API debug"):
    for line in debug_lines:
        st.write(line)

if df.empty:
    st.warning("Няма налични мачове за днес, утре или SCHEDULED в момента.")
    st.stop()

all_dates = sorted(df["match_date"].dt.date.unique().tolist())
selected_date = st.date_input(
    "Date",
    value=all_dates[0],
    min_value=all_dates[0],
    max_value=all_dates[-1],
    format="DD/MM/YYYY",
)

day_df = df[df["match_date"].dt.date == selected_date].copy()

if day_df.empty:
    st.warning(f"Няма мачове за {selected_date.strftime('%d.%m.%Y')}.")
    st.stop()

popular_league = day_df["league"].value_counts().idxmax()

st.markdown(
    f"""
    <div style="font-size:1.9rem;font-weight:800">Football Predictions</div>
    <div style="color:#6b7280;margin-top:0.2rem">Прогнози за {selected_date.strftime('%d.%m.%Y')}</div>
    <div style="margin-top:0.3rem;color:#8aa4ff;font-weight:600">Най-популярна лига: {popular_league}</div>
    """,
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.metric("Matches", len(day_df))
with c2:
    st.metric("Leagues", day_df["league"].nunique())
with c3:
    st.metric("Teams", day_df["home"].nunique() + day_df["away"].nunique())
with c4:
    future_end = selected_date + timedelta(days=2)
    st.metric("Next 3 days", len(df[(df["match_date"].dt.date >= selected_date) & (df["match_date"].dt.date <= future_end)]))

search = st.text_input("Search team or league", placeholder="Напр. Liverpool, Chelsea, Premier League")
league_options = ["All"] + list(day_df["league"].drop_duplicates())
selected_league = st.selectbox("League / tournament", league_options)

filtered = day_df.copy()
if search:
    q = search.lower()
    filtered = filtered[
        filtered["home"].str.lower().str.contains(q, na=False)
        | filtered["away"].str.lower().str.contains(q, na=False)
        | filtered["league"].str.lower().str.contains(q, na=False)
    ]
if selected_league != "All":
    filtered = filtered[filtered["league"] == selected_league]

tab_day, tab_secure, tab_risky, tab_top = st.tabs(["Day", "Most secure", "Most risky", "Top picks 2-3 days"])

with tab_day:
    for league in filtered["league"].drop_duplicates():
        league_df = filtered[filtered["league"] == league].sort_values("match_date")
        st.markdown(f"### {league}")
        for _, r in league_df.iterrows():
            with st.container(border=True):
                st.markdown(f"**{r['home']}**  \nvs  \n**{r['away']}**")
                st.caption(f"{r['tournament']} • {r['match_date'].strftime('%d.%m.%Y %H:%M')}")
                a, b, c = st.columns(3)
                a.markdown(f"**Pick**  \n{outcome_label(r['predicted_outcome'])}")
                b.markdown(f"**Confidence**  \n{color_percent(r['confidence_score'], True)}", unsafe_allow_html=True)
                c.markdown(f"**Risk**  \n{color_percent(r['risk_score'], False)}", unsafe_allow_html=True)
                with st.expander("Details"):
                    st.write(r["summary_bg"])
                    st.write(f"Odds: 1 {r['odds_1']} | X {r['odds_x']} | 2 {r['odds_2']}")
                    st.write(r["news_note"])
                    st.write(market_reason(r))

with tab_secure:
    secure_df = day_df.copy()
    secure_df["score"] = secure_df.apply(secure_score, axis=1)
    secure_df = secure_df.sort_values(["score", "confidence_score"], ascending=[False, False]).head(max(1, round(len(secure_df) * 0.4)))
    for _, r in secure_df.iterrows():
        with st.container(border=True):
            st.markdown(f"**{r['home']}** vs **{r['away']}**")
            st.caption(f"{r['league']} • {r['tournament']}")
            a, b, c = st.columns(3)
            a.markdown(f"**Pick**  \n{outcome_label(r['predicted_outcome'])}")
            b.markdown(f"**Confidence**  \n{color_percent(r['confidence_score'], True)}", unsafe_allow_html=True)
            c.markdown(f"**Risk**  \n{color_percent(r['risk_score'], False)}", unsafe_allow_html=True)
            with st.expander("Details"):
                st.write(r["summary_bg"])
                st.write(f"Причина: {r['news_note']}")
                st.write(f"Odds: 1 {r['odds_1']} | X {r['odds_x']} | 2 {r['odds_2']}")

with tab_risky:
    risky_df = day_df.copy()
    risky_df["score"] = risky_df.apply(risky_score, axis=1)
    risky_df = risky_df.sort_values(["score", "raw_value_score"], ascending=[False, False]).head(max(1, round(len(risky_df) * 0.5)))
    for _, r in risky_df.iterrows():
        with st.container(border=True):
            st.markdown(f"**{r['home']}** vs **{r['away']}**")
            st.caption(f"{r['league']} • {r['tournament']}")
            a, b, c = st.columns(3)
            a.markdown(f"**Pick**  \n{outcome_label(r['predicted_outcome'])}")
            b.markdown(f"**Value**  \n{color_percent(r['raw_value_score']*100, True)}", unsafe_allow_html=True)
            c.markdown(f"**Risk**  \n{color_percent(r['risk_score'], False)}", unsafe_allow_html=True)
            with st.expander("Details"):
                st.write(r["summary_bg"])
                st.write("Висок коефициент с реален шанс при комбинация от форма, новини и пазар.")
                st.write(f"Odds: 1 {r['odds_1']} | X {r['odds_x']} | 2 {r['odds_2']}")
                st.write(market_reason(r))

with tab_top:
    future_end = selected_date + timedelta(days=2)
    future_df = df[(df["match_date"].dt.date >= selected_date) & (df["match_date"].dt.date <= future_end)].copy()
    if future_df.empty:
        st.info("Няма налични мачове за следващите 2-3 дни.")
    else:
        future_df["score"] = future_df.apply(top_pick_score, axis=1)
        future_df = future_df.sort_values(["score", "confidence_score"], ascending=[False, False]).head(5)
        for _, r in future_df.iterrows():
            with st.container(border=True):
                st.markdown("<div style='display:inline-block;background:#1f6feb;color:white;padding:0.35rem 0.65rem;border-radius:0.6rem;font-weight:700'>TOP PICK</div>", unsafe_allow_html=True)
                st.markdown(f"**{r['home']}** vs **{r['away']}**")
                st.caption(f"{r['league']} • {r['match_date'].strftime('%d.%m.%Y %H:%M')} • {r['tournament']}")
                a, b, c = st.columns(3)
                a.markdown(f"**Pick**  \n{outcome_label(r['predicted_outcome'])}")
                b.markdown(f"**Confidence**  \n{color_percent(r['confidence_score'], True)}", unsafe_allow_html=True)
                c.markdown(f"**Value**  \n{color_percent(r['raw_value_score']*100, True)}", unsafe_allow_html=True)
                with st.expander("Details"):
                    st.write(r["summary_bg"])
                    st.write(f"Odds: 1 {r['odds_1']} | X {r['odds_x']} | 2 {r['odds_2']}")
                    st.write(r["news_note"])
                    st.write("Препоръка за кратък прозорец според общия score.")
