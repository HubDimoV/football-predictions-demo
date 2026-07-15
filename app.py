import streamlit as st
import requests
import json

st.set_page_config(page_title="API Debug", page_icon="🔧", layout="wide")

API_KEY = "ed0e57191db04c7cbff309df66644f9a"
BASE_URL = "https://api.football-data.org/4.0"
HEADERS = {"X-Auth-Token": API_KEY}

st.title("🔧 Football-Data.org API Debug")

# Test 1: Competitions
st.header("1. Testing /competitions")
try:
    resp = requests.get(f"{BASE_URL}/competitions", headers=HEADERS, timeout=10)
    st.write(f"**Status:** {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        st.write(f"**Competitions count:** {len(data.get('competitions', []))}")
        st.write("**First 3:**")
        for comp in data.get("competitions", [])[:3]:
            st.write(f"- {comp['name']} ({comp.get('code', 'N/A')})")
    else:
        st.error(f"Error: {resp.text}")
except Exception as e:
    st.error(f"Exception: {e}")

# Test 2: Specific competition (Premier League)
st.header("2. Testing /competitions/PL/matches")
try:
    resp2 = requests.get(f"{BASE_URL}/competitions/PL/matches", headers=HEADERS, timeout=10)
    st.write(f"**Status:** {resp2.status_code}")
    if resp2.status_code == 200:
        data2 = resp2.json()
        st.write(f"**Matches count:** {len(data2.get('matches', []))}")
        if data2.get("matches"):
            st.write("**First match:**")
            st.json(data2["matches"][0])
    else:
        st.error(f"Error: {resp2.text}")
except Exception as e:
    st.error(f"Exception: {e}")

# Test 3: Today's matches
st.header("3. Testing /matches?date=today")
try:
    from datetime import date
    today = date.today().strftime("%Y-%m-%d")
    resp3 = requests.get(f"{BASE_URL}/matches", headers=HEADERS, params={"date": today}, timeout=10)
    st.write(f"**Status:** {resp3.status_code}")
    if resp3.status_code == 200:
        data3 = resp3.json()
        st.write(f"**Matches today:** {len(data3.get('matches', []))}")
        if data3.get("matches"):
            for m in data3["matches"][:3]:
                st.write(f"- {m['homeTeam']['name']} vs {m['awayTeam']['name']}")
    else:
        st.error(f"Error: {resp3.text}")
except Exception as e:
    st.error(f"Exception: {e}")

st.header("✅ Done")
