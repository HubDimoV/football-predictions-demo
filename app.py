import streamlit as st
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Football Predictions", page_icon="⚽", layout="centered")

DATA_CSV = """match_id,match_date,league,tournament,home,away,home_bg,away_bg,predicted_outcome,confidence_score,risk_score,odds_1,odds_x,odds_2,news_note,summary_bg,market_flag,raw_value_score,form_score,news_score,bookie_gap
1,2026-07-08,Champions League,Club,Real Madrid,Manchester City,Реал Мадрид,Манчестър Сити,1,81.2,18.8,1.72,3.65,4.60,City have key defensive doubts.,Реал Мадрид изглежда по-стабилен а Сити имат колебания в защитата.,normal,0.74,0.82,0.65,0.12
2,2026-07-08,Champions League,Club,Bayern Munich,Inter,Байерн Мюнхен,Интер,1,77.9,22.1,1.61,3.75,5.10,Inter rotation expected after a busy run.,Байерн има леко по-добър момент и по-ясен път към успех.,normal,0.69,0.79,0.61,0.10
3,2026-07-08,European Championship,National,France,Portugal,Франция,Португалия,X,63.5,36.5,2.18,3.10,3.85,Very even matchup with strong midfield control.,Мачът е изравнен и X изглежда напълно реален вариант.,normal,0.58,0.63,0.67,0.06
4,2026-07-08,World Cup,National,Argentina,Brazil,Аржентина,Бразилия,1,66.2,33.8,2.05,3.20,3.55,Argentina have slightly better recent stability.,Аржентина е по-стабилна в последните мачове но рискът остава.,normal,0.61,0.69,0.62,0.08
5,2026-07-08,Bulgarian League,Club,Ludogorets,CSKA Sofia,Лудогорец,ЦСКА София,1,84.1,15.9,1.48,3.30,6.20,Home form is strong and odds are compressed.,Лудогорец има ясен домакински плюс и нисък риск.,value,0.81,0.84,0.74,0.14
6,2026-07-08,Bulgarian League,Club,Levski Sofia,Botev Plovdiv,Левски София,Ботев Пловдив,1,71.4,28.6,1.85,3.15,4.05,Levski squad looks more balanced today.,Левски е по-стабилен но не е без риск.,normal,0.66,0.72,0.66,0.07
7,2026-07-08,Primeira Liga,Club,Benfica,Porto,X,58.7,41.3,2.42,3.25,2.95,Derby context usually raises variance.,Дербито е непредвидимо и X е логичен сценарий.,normal,0.52,0.59,0.55,0.05
8,2026-07-08,Eredivisie,Club,Feyenoord,Ajax,Фейенорд,Аякс,1,60.8,39.2,2.22,3.45,3.10,Form is mixed for both sides.,Формата е колеблива и това увеличава риска.,normal,0.55,0.61,0.53,0.06
9,2026-07-09,Champions League,Club,Arsenal,PSG,Арсенал,ПСЖ,1,67.1,32.9,2.60,3.20,2.68,Strong tactical battle expected.,Арсенал има шанс но мачът е труден за прогнозиране.,high_value,0.63,0.66,0.60,0.16
10,2026-07-09,World Cup,National,England,Spain,X,57.9,42.1,2.80,3.05,2.62,Even odds and strong balance from bookmakers.,Мачът е балансиран и високият коефициент носи шанс.,high_value,0.59,0.57,0.58,0.18
11,2026-07-09,European Championship,National,Germany,Italy,Германия,Италия,1,62.4,37.6,2.32,3.05,3.15,Recent form slightly favors Germany.,Германия е малко по-стабилна в момента.,normal,0.57,0.62,0.56,0.09
12,2026-07-09,Bulgarian League,Club,Arda,Slavia Sofia,Арда,Славия София,1,74.2,25.8,1.92,3.10,3.75,Arda looks fitter with fewer absences.,Арда има добър баланс и по-нисък риск.,value,0.72,0.75,0.68,0.11
13,2026-07-10,Champions League,Club,Barcelona,Dortmund,Барселона,Дортмунд,1,79.2,20.8,1.66,3.60,4.90,Barcelona create more pressure at home.,Барселона е по-опасен домакин и има добър импулс.,value,0.77,0.81,0.70,0.13
14,2026-07-10,World Cup,National,Portugal,England,X,61.8,38.2,2.35,3.15,3.00,Both teams have balanced profiles and low gap.,Мачът е близък и равенството изглежда доста реално.,normal,0.60,0.64,0.59,0.08
15,2026-07-10,European Championship,National,Spain,Germany,Испания,Германия,1,65.6,34.4,2.15,3.25,3.40,Spain control tempo well in current form.,Испания е леко по-силна в контрол на мача.,normal,0.62,0.67,0.61,0.07"""

def load_data():
    lines = DATA_CSV.strip().split("\n")
    header = lines[0].split(",")
    data = []
    for line in lines[1:]:
        parts = line.split(",", 20)
        if len(parts) == 21:
            data.append(parts)
    df = pd.DataFrame(data, columns=header)
    df["match_date"] = pd.to_datetime(df["match_date"], format="%Y-%m-%d")
    df["confidence_score"] = pd.to_numeric(df["confidence_score"], errors="coerce")
    df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")
    df["raw_value_score"] = pd.to_numeric(df["raw_value_score"], errors="coerce")
    df["form_score"] = pd.to_numeric(df["form_score"], errors="coerce")
    df["news_score"] = pd.to_numeric(df["news_score"], errors="coerce")
    df["bookie_gap"] = pd.to_numeric(df["bookie_gap"], errors="coerce")
    return df

df = load_data()

if df.empty:
    st.error("Няма заредени данни.")
    st.stop()

all_dates = sorted(df["match_date"].dropna().unique().tolist())
if not all_dates:
    st.error("Няма налични дати.")
    st.stop()

selected_date = st.date_input(
    "Date",
    value=all_dates[-1].date(),
    min_value=all_dates[0].date(),
    max_value=all_dates[-1].date(),
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
    st.metric("Tags", day_df["tournament"].nunique())
with c4:
    st.metric("Top 3 days", len(df[(df["match_date"].dt.date >= selected_date) & (df["match_date"].dt.date <= (selected_date + timedelta(days=2)))]))

search = st.text_input("Search team or league", placeholder="Напр. Ливърпул, Champions League, Левски")
league_options = ["All"] + list(day_df["league"].drop_duplicates())
selected_league = st.selectbox("League / tournament", league_options)

filtered = day_df.copy()
if search:
    q = search.lower()
    filtered = filtered[
        filtered["home"].str.lower().str.contains(q)
        | filtered["away"].str.lower().str.contains(q)
        | filtered["home_bg"].str.lower().str.contains(q)
        | filtered["away_bg"].str.lower().str.contains(q)
        | filtered["league"].str.lower().str.contains(q)
        | filtered["tournament"].str.lower().str.contains(q)
    ]
if selected_league != "All":
    filtered = filtered[filtered["league"] == selected_league]

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

tab_day, tab_secure, tab_risky, tab_top = st.tabs(["Day", "Most secure", "Most risky", "Top picks 2-3 days"])

with tab_day:
    for league in filtered["league"].drop_duplicates():
        league_df = filtered[filtered["league"] == league].sort_values("match_id")
        st.markdown(f"### {league}")
        for _, r in league_df.iterrows():
            with st.container(border=True):
                st.markdown(
                    f"**{r['home']}**  \n"
                    f"<span style='color:#8b93a7'>{r['home_bg']}</span>  \n"
                    f"vs  \n"
                    f"**{r['away']}**  \n"
                    f"<span style='color:#8b93a7'>{r['away_bg']}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(f"{r['tournament']} • {r['match_date'].strftime('%d.%m.%Y')}")
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
            st.markdown(f"**{r['home']}** / **{r['away']}**")
            st.markdown(f"<span style='color:#8b93a7'>{r['home_bg']} vs {r['away_bg']}</span>", unsafe_allow_html=True)
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
            st.markdown(f"**{r['home']}** / **{r['away']}**")
            st.markdown(f"<span style='color:#8b93a7'>{r['home_bg']} vs {r['away_bg']}</span>", unsafe_allow_html=True)
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
    future_df = df[(df["match_date"].dt.date >= selected_date) & (df["match_date"].dt.date <= (selected_date + timedelta(days=2)))].copy()
    if future_df.empty:
        st.info("Няма налични мачове за следващите 2-3 дни.")
    else:
        future_df["score"] = future_df.apply(top_pick_score, axis=1)
        future_df = future_df.sort_values(["score", "confidence_score"], ascending=[False, False]).head(5)
        for _, r in future_df.iterrows():
            with st.container(border=True):
                st.markdown("<div style='display:inline-block;background:#1f6feb;color:white;padding:0.35rem 0.65rem;border-radius:0.6rem;font-weight:700'>TOP PICK</div>", unsafe_allow_html=True)
                st.markdown(f"**{r['home']}** / **{r['away']}**")
                st.markdown(f"<span style='color:#8b93a7'>{r['home_bg']} vs {r['away_bg']}</span>", unsafe_allow_html=True)
                st.caption(f"{r['league']} • {r['match_date'].strftime('%d.%m.%Y')} • {r['tournament']}")
                a, b, c = st.columns(3)
                a.markdown(f"**Pick**  \n{outcome_label(r['predicted_outcome'])}")
                b.markdown(f"**Confidence**  \n{color_percent(r['confidence_score'], True)}", unsafe_allow_html=True)
                c.markdown(f"**Value**  \n{color_percent(r['raw_value_score']*100, True)}", unsafe_allow_html=True)
                with st.expander("Details"):
                    st.write(r["summary_bg"])
                    st.write(f"Odds: 1 {r['odds_1']} | X {r['odds_x']} | 2 {r['odds_2']}")
                    st.write(r["news_note"])
                    st.write("Препоръка за кратък прозорец според общия score.")
