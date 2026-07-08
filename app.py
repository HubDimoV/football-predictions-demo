import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Football Predictions",
    page_icon="⚽",
    layout="centered",
)

DATA_CSV = """match_id,league,kickoff,home,away,predicted_outcome,confidence_score,risk_score,odds_1,odds_x,odds_2,news_note
1,Bulgarian First League,2026-07-08 12:00,Ludogorets,CSKA Sofia,1,82.4,17.6,1.55,3.25,5.40,Stable lineups expected.
2,Bulgarian First League,2026-07-08 13:00,Levski Sofia,Botev Plovdiv,1,76.1,23.9,1.78,3.10,4.10,Recent injury update affecting one side.
3,Scottish Premiership,2026-07-08 14:00,Hearts,Rangers,2,68.5,31.5,4.20,3.55,1.82,Strong market movement today.
4,Primeira Liga,2026-07-08 15:00,Benfica,Porto,X,61.3,38.7,2.05,3.15,3.45,Mixed recent form with tactical changes.
5,Eredivisie,2026-07-08 16:00,Feyenoord,Ajax,1,57.8,42.2,2.40,3.40,2.75,Limited fresh news; odds remain stable.
"""

@st.cache_data
def load_data():
    from io import StringIO
    return pd.read_csv(StringIO(DATA_CSV))

df = load_data()

st.markdown("<div style='font-size:1.7rem;font-weight:700'>Football Predictions</div>", unsafe_allow_html=True)
st.markdown("<div style='color:#5b6573;margin-bottom:0.9rem'>Mobile-first prototype for daily match predictions.</div>", unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.metric("All matches", len(df))
with col2:
    st.metric("Categories", "3")

query = st.text_input("Search by team or league", placeholder="Type team, league, or match name")
mode = st.segmented_control("View", ["All", "Most secure", "Most risky"], default="All")

filtered = df.copy()
if query:
    q = query.lower()
    filtered = filtered[
        filtered["home"].str.lower().str.contains(q)
        | filtered["away"].str.lower().str.contains(q)
        | filtered["league"].str.lower().str.contains(q)
    ]

if mode == "Most secure":
    filtered = filtered.sort_values(["confidence_score", "risk_score"], ascending=[False, True]).head(max(1, round(len(df) * 0.25)))
elif mode == "Most risky":
    filtered = filtered.sort_values(["risk_score", "confidence_score"], ascending=[False, True]).head(max(1, round(len(df) * 0.25)))
else:
    filtered = filtered.sort_values(["kickoff", "match_id"])

st.caption(f"Results: {len(filtered)}")

for _, r in filtered.iterrows():
    with st.container(border=True):
        st.markdown(f"**{r['home']} vs {r['away']}**")
        st.markdown(f"{r['league']} • {r['kickoff']}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Pick", r["predicted_outcome"])
        c2.metric("Confidence", f"{r['confidence_score']}%")
        c3.metric("Risk", f"{r['risk_score']}%")
        with st.expander("Details"):
            st.write(f"Odds: 1 {r['odds_1']} | X {r['odds_x']} | 2 {r['odds_2']}")
            st.write(r["news_note"])
