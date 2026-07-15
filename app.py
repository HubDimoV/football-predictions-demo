import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Discovery", page_icon="⚽", layout="wide")

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY} if API_KEY else {}

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

@st.cache_data(ttl=1800)
def load_areas():
    code, text, payload = api_get("/areas")
    rows = []
    debug = [f"/areas => {code}"]
    if code != 200 or not payload:
        debug.append(text[:300])
        return pd.DataFrame(), debug

    for a in payload.get("areas", []):
        rows.append({
            "id": a.get("id"),
            "name": a.get("name", ""),
            "code": a.get("code", ""),
            "flag": a.get("flag", ""),
        })

    return pd.DataFrame(rows), debug

@st.cache_data(ttl=1800)
def load_competitions():
    code, text, payload = api_get("/competitions")
    rows = []
    debug = [f"/competitions => {code}"]
    if code != 200 or not payload:
        debug.append(text[:300])
        return pd.DataFrame(), debug

    for c in payload.get("competitions", []):
        current = c.get("currentSeason", {}) or {}
        area = c.get("area", {}) or {}
        rows.append({
            "id": c.get("id"),
            "code": c.get("code", ""),
            "name": c.get("name", ""),
            "type": c.get("type", ""),
            "area": area.get("name", ""),
            "area_code": area.get("code", ""),
            "current_start": current.get("startDate", ""),
            "current_end": current.get("endDate", ""),
            "number_of_available_seasons": c.get("numberOfAvailableSeasons", ""),
            "emblem": c.get("emblem", ""),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["area", "name"]).reset_index(drop=True)
    return df, debug

def test_competition_matches(comp_code):
    params = {
        "status": "SCHEDULED",
        "dateFrom": date.today().strftime("%Y-%m-%d"),
        "dateTo": (date.today() + timedelta(days=21)).strftime("%Y-%m-%d"),
    }
    return api_get(f"/competitions/{comp_code}/matches", params=params)

def parse_matches(payload):
    rows = []
    if not payload or "matches" not in payload:
        return pd.DataFrame()

    for m in payload.get("matches", []):
        comp = m.get("competition", {}) or {}
        home = m.get("homeTeam", {}) or {}
        away = m.get("awayTeam", {}) or {}
        dt = m.get("utcDate")
        if not dt:
            continue

        rows.append({
            "match_id": m.get("id"),
            "match_date": pd.to_datetime(dt, utc=True).tz_convert(None),
            "competition_code": comp.get("code", ""),
            "league": comp.get("name", ""),
            "status": m.get("status", ""),
            "home": home.get("name", ""),
            "away": away.get("name", ""),
            "home_short": home.get("shortName") or home.get("name", ""),
            "away_short": away.get("shortName") or away.get("name", ""),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("match_date").reset_index(drop=True)
    return df

areas_df, areas_debug = load_areas()
comps_df, comps_debug = load_competitions()

st.title("Football Discovery")
st.caption("Find an accessible competition first, then test its matches.")

with st.expander("API debug"):
    st.subheader("Areas")
    for line in areas_debug:
        st.write(line)
    if not areas_df.empty:
        st.dataframe(areas_df, use_container_width=True, hide_index=True)

    st.subheader("Competitions")
    for line in comps_debug:
        st.write(line)
    if not comps_df.empty:
        st.dataframe(
            comps_df[["code", "name", "area", "type", "current_start", "current_end", "number_of_available_seasons"]],
            use_container_width=True,
            hide_index=True,
        )

if comps_df.empty:
    st.error("Не мога да заредя competitions.")
    st.stop()

st.subheader("Pick a competition to test")

available_codes = comps_df["code"].dropna().tolist()
selected_code = st.selectbox("Competition code", available_codes, index=0)

col1, col2 = st.columns([1, 2])
with col1:
    test_clicked = st.button("Test competition")
with col2:
    st.write("Ще тества само един competition и ще покаже дали има scheduled matches.")

if test_clicked:
    code, text, payload = test_competition_matches(selected_code)

    st.markdown(f"### Result for {selected_code}")
    st.write(f"Status: {code}")

    if code == 200 and payload:
        matches_df = parse_matches(payload)
        st.success(f"Loaded {len(matches_df)} scheduled matches")
        if matches_df.empty:
            st.info("Няма scheduled мачове за избраната лига в следващите 21 дни.")
        else:
            st.dataframe(matches_df, use_container_width=True, hide_index=True)
    else:
        st.error(text[:600])

st.markdown("### What to try first")
st.write("Избери лига от видимите competitions и натисни Test competition. Ако видиш 403, значи тази лига не е достъпна в твоя план.")
