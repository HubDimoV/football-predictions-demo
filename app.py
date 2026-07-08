import streamlit as st
import pandas as pd
from io import StringIO

st.set_page_config(
    page_title="Football Predictions",
    page_icon="⚽",
    layout="centered",
)

DATA_CSV = """match_id,match_date,league,tournament,home,away,home_bg,away_bg,predicted_outcome,confidence_score,risk_score,odds_1,odds_x,odds_2,news_note,summary_bg,market_flag,raw_value_score
1,2026-07-08,Champions League,Club,Real Madrid,Manchester City,Реал Мадрид,Манчестър Сити,1,81.2,18.8,1.72,3.65,4.60,City have key defensive doubts.,Реал Мадрид изглежда по-стабилен, а Сити имат колебания в защитата.,normal,0.74
2,2026-07-08,Champions League,Club,Bayern Munich,Inter,Байерн Мюнхен,Интер,1,77.9,22.1,1.61,3.75,5.10,Inter rotation expected after a busy run.,Байерн има леко по-добър момент и по-ясен път към успех.,normal,0.69
3,2026-07-08,European Championship,National,France,Portugal,Франция,Португалия,X,63.5,36.5,2.18,3.10,3.85,Very even matchup with strong midfield control.,Мачът е изравнен и X изглежда напълно реален вариант.,normal,0.58
4,2026-07-08,World Cup,National,Argentina,Brazil,Аржентина,Бразилия,1,66.2,33.8,2.05,3.20,3.55,Argentina have slightly better recent stability.,Аржентина е по-стабилна в последните мачове, но рискът остава.,normal,0.61
5,2026-07-08,Bulgarian League,Club,Ludogorets,CSKA Sofia,Лудогорец,ЦСКА София,1,84.1,15.9,1.48,3.30,6.20,Home form is strong and odds are compressed.,Лудогорец има ясен домакински плюс и нисък риск.,value,0.81
6,2026-07-08,Bulgarian League,Club,Levski Sofia,Botev Plovdiv,Левски София,Ботев Пловдив,1,71.4,28.6,1.85,3.15,4.05,Levski squad looks more balanced today.,Левски е по-стабилен, но не е без риск.,normal,0.66
7,2026-07-08,Primeira Liga,Club,Benfica,Porto,Бенфика,Порто,X,58.7,41.3,2.42,3.25,2.95,Derby context usually raises variance.,Дербито е непредвидимо и X е логичен сценарий.,normal,0.52
8,2026-07-08,Eredivisie,Club,Feyenoord,Ajax,Фейенорд,Аякс,1,60.8,39.2,2.22,3.45,3.10,Form is mixed for both sides.,Формата е колеблива и това увеличава риска.,normal,0.55
9,2026-07-09,Champions League,Club,Arsenal,PSG,Арсенал,ПСЖ,1,67.1,32.9,2.60,3.20,2.68,Strong tactical battle expected.,Арсенал има шанс, но мачът е труден за прогнозиране.,high_value,0.63
10,2026-07-09,World Cup,National,England,Spain,X,57.9,42.1,2.80,3.05,2.62,Even odds and strong balance from bookmakers.,Мачът е балансиран и високият коефициент носи шанс.,high_value,0.59
11,2026-07-09,European Championship,National,Germany,Italy,Германия,Италия,1,62.4,37.6,2.32,3.05,3.15,Recent form slightly favors Germany.,Германия е малко по-стабилна в момента.,normal,0.57
12,2026-07-09,Bulgarian League,Club,Arda,Slavia Sofia,Арда,Славия София,1,74.2,25.8,1.92,3.10,3.75,Arda looks fitter with fewer absences.,Арда има добър баланс и по-нисък риск.,value,0.72
"""

@st.cache_data
def load_data():
    return pd.read_csv(StringIO(DATA_CSV))

def color_percent(value, green_if_high=True):
    if green_if_high:
        color = "#1a7f37" if value >= 50 else "#d1242f"
    else:
        color = "#1a7f37" if value <= 50 else "#d1242f"
    return f"<span style='color:{color}; font-weight:700'>{value:.1f}%</span>"

def outcome_label(x):
    return {"1": "Home win", "X": "Draw", "2": "Away win"}.get(str(x), str(x))

def market_reason(row):
    if row["market_flag"] == "value":
        return "Има добър value за кратък прозорец."
    if row["market_flag"] == "high_value":
        return "Коефициентът е по-висок от обичайното и носи потенциал."
    return "Коефициентите са в нормален диапазон."

df = load_data()
all_dates = sorted(df["match_date"].dropna().unique())
selected_date = st.selectbox(
    "Date",
    all_dates,
    index=len(all_dates) - 1,
    format_func=lambda d: d
)

day_df = df[df["match_date"] == selected_date].copy()

st.markdown(
    f"""
    <div style="font-size:1.8rem;font-weight:800">Football Predictions</div>
    <div style="color:#5b6573;margin-top:0.15rem">Прогнози за {selected_date}</div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Matches", len(day_df))
with col2:
    st.metric("Leagues", day_df["league"].nunique())
with col3:
    st.metric("Tags", day_df["tournament"].nunique())

search = st.text_input("Search team or league", placeholder="Напр. Ливърпул, Champions League, Левски")
league_options = ["All"] + list(day_df["league"].drop_duplicates())
selected_league = st.selectbox("League / tournament", league_options)

