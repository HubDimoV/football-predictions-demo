import os
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Football Discovery", page_icon="⚽", layout="centered")

API_KEY = os.getenv("API_FOOTBALL_KEY", "")
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY} if API_KEY else {}

FREE_HINTS = {"PL", "PD", "BL1", "SA", "FL1", "DED", "PPL", "CL", "EL", "WC", "EC"}

def api_get(path, params=None):
    try:
        resp = requests.get(f"{BASE_URL}{path}", headers=HEADERS, params=params or {}, timeout=20)
        try:
            payload = resp.json()
        except Exception:
            payload = None
        return resp.status_code, resp.text, payload
    except Exception as e:
        return None, str(e), None

@st.cache_data(ttl=1800)
def load_competitions():
    code, text, payload = api_get("/competitions")
    rows = []
    debug = []
    debug.append(f"/competitions => {code}")

    if code != 200 or not payload:
        debug.append(text[:300])
        return pd.DataFrame(), debug

    comps = payload.get("competitions", [])
    for c in comps:
        cid = c.get("code") or str(c.get("id"))
        area = c.get("area", {}).get("name", "")
        name = c.get("name", "Unknown")
        typ = c.get("type", "")
        current_season = c.get("currentSeason", {}) or {}
        start = current_season.get("startDate", "")
        end = current_season.get("endDate", "")
        status_flag = "free_hint" if cid in FREE_HINTS else "unknown"

        rows.append({
            "id": c.get("id"),
            "code": cid,
            "name": name,
            "area": area,
            "type": typ,
            "current_start": start,
            "current_end": end,
            "emblem": c.get("emblem", ""),
            "status_flag": status_flag,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["area", "name"]).reset_index(drop=True)
    return df, debug

def try_competition_matches(comp_code):
    params = {
        "status": "SCHEDULED",
        "dateFrom": date.today().strftime("%Y-%m-%d"),
        "dateTo": (date.today() + timedelta(days=14)).strftime("%Y-%m-%d"),
    }
    return api_get(f"/competitions/{comp_code}/matches", params=params)

def parse_matches(payload):
    rows = []
    if not payload or "matches" not in payload:
        return pd.DataFrame(rows)

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
            "league": comp.get("name", "Unknown"),
            "competition_code": comp.get("code", ""),
            "home": home.get("name", "Unknown"),
            "away": away.get("name", "Unknown"),
            "status": m.get("status", ""),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("match_date").reset_index(drop=True)
    return df

competitions_df, debug_lines = load_competitions()

st.title("Football Discovery")

with st.expander("API debug"):
    for line in debug_lines:
        st.write(line)

if competitions_df.empty:
    st.error("Не можах да заредя competitions. Провери токена и достъпа.")
    st.stop()

st.subheader("Available competitions")

view = competitions_df.copy()
view["availability"] = view["status_flag"].map({
    "free_hint": "Likely free / common coverage",
    "unknown": "Needs test"
})

st.dataframe(
    view[["code", "name", "area", "type", "availability", "current_start", "current_end"]],
    use_container_width=True,
    hide_index=True,
)

codes = view["code"].dropna().tolist()
selected_code = st.selectbox("Choose competition code", codes)

test_btn = st.button("Test selected competition")

if test_btn and selected_code:
    code, text, payload = try_competition_matches(selected_code)

    st.markdown(f"### Test result for {selected_code}")
    st.write(f"Status: {code}")

    if code == 200 and payload:
        matches_df = parse_matches(payload)
        st.success(f"Loaded {len(matches_df)} scheduled matches")
        if not matches_df.empty:
            st.dataframe(matches_df, use_container_width=True, hide_index=True)
        else:
            st.info("Няма scheduled мачове за този competition в следващите 2 седмици.")
    else:
        st.error(text[:500])

st.markdown("### Suggested next step")
st.write("Избери competition от таблицата и натисни Test selected competition. Ако върне 403, този competition не е в твоя план.")
