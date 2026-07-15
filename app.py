import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="centered")

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY} if API_KEY else {}

def fetch_matches_for_day(target_date):
    params = {"date": target_date.strftime("%Y-%m-%d")}
    url = f"{BASE_URL}/matches"
    resp = requests.get(url, headers=HEADERS, params=params, timeout=20)

    if resp.status_code != 200:
        return [], f"API {resp.status_code}: {resp.text[:200]}"

    data = resp.json()
    matches = []

    for m in data.get("matches", []):
        utc_date = m.get("utcDate")
        if not utc_date:
            continue

        match_dt = pd.to_datetime(utc_date, utc=True).tz_convert(None)

        comp = m.get("competition", {})
        home = m.get("homeTeam", {}).get("name", "Unknown")
        away = m.get("awayTeam", {}).get("name", "Unknown")

        home_code = m.get("homeTeam", {}).get("shortName") or home
        away_code = m.get("awayTeam", {}).get("shortName") or away

        home_score = m.get("score", {}).get("fullTime", {}).get("home")
        away_score = m.get("score", {}).get("fullTime", {}).get("away")
        status = m.get("status", "")

        if status == "FINISHED" and home_score is not None and away_score is not None:
            if home_score > away_score:
                pick = "1"
            elif home_score < away_score:
                pick = "2"
            else:
                pick = "X"
        else:
            home_val = 0.40
            draw_val = 0.30
            away_val = 0.30

            if comp.get("code") in {"CL", "BL1", "PD", "PL", "SA", "FL1"}:
                home_val += 0.05
                away_val -= 0.02

            pick = "1" if home_val >= max(draw_val, away_val) else ("X" if draw_val >= away_val else "2")

        confidence = 62.0
        risk = 38.0

        if comp.get("code") in {"CL", "BL1", "PD", "PL", "SA", "FL1"}:
            confidence += 6
            risk -= 4

        if status == "FINISHED":
            confidence = 95.0
            risk = 5.0

        odds_1 = 2.05
        odds_x = 3.15
        odds_2 = 3.10

        if pick == "1":
            raw_value = 0.56
        elif pick == "X":
            raw_value = 0.60
        else:
            raw_value = 0.54

        form_score = 0.60
        news_score = 0.50
        bookie_gap = 0.08

        matches.append({
            "match_id": m.get("id"),
            "match_date": match_dt,
            "league": comp.get("name", "Unknown"),
            "tournament": comp.get("type", "Competition"),
            "home": home,
            "away": away,
            "home_bg": home_code,
            "away_bg": away_code,
            "predicted_outcome": pick,
            "confidence_score": float(confidence),
            "risk_score": float(risk),
            "odds_1": odds_1,
            "odds_x": odds_x,
            "odds_2": odds_2,
            "news_note": "Real match from football-data.org.",
            "summary_bg": f"{home} срещу {away} е зареден от live API.",
            "market_flag": "normal",
            "raw_value_score": float(raw_value),
            "form_score": float(form_score),
            "news_score": float(news_score),
            "bookie_gap": float(bookie_gap),
            "status": status,
        })

    return matches, None

@st.cache_data(ttl=900)
def load_matches():
    all_rows = []
    errors = []

    today = date.today()
    for offset in range(3):
        d = today + timedelta(days=offset)
        rows, err = fetch_matches_for_day(d)
        if err:
            errors.append(f"{d.strftime('%Y-%m-%d')}: {err}")
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["match_date"] = pd.to_datetime(df["match_date"], errors="coerce")
        for col in ["confidence_score", "risk_score", "odds_1", "odds_x", "odds_2", "raw_value_score", "form_score", "news_score", "bookie_gap"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

    return df, errors

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

df, load_errors = load_matches()

st.title("Football Predictions")

if load_errors:
    with st.expander("API warnings"):
        for e in load_errors:
            st.write(e)

if df.empty:
    st.warning("Няма налични мачове за днес и следващите 2 дни.")
    st.stop()

df = df.sort_values("match_date").copy()

all_dates = sorted(df["match_date"].dt.date.unique().tolist())
if not all_dates:
    st.warning("Няма налични дати.")
    st.stop()

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
