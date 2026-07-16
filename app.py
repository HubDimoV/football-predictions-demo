import os
from datetime import date, timedelta

import requests
import streamlit as st

st.set_page_config(page_title="API Debug", layout="wide")

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

st.title("API Debug")

if not API_KEY:
    st.error("Липсва API_FOOTBALL_KEY.")
    st.stop()

today = date.today()
params_list = [
    {"live": "all", "timezone": "Europe/Sofia"},
    {"date": today.strftime("%Y-%m-%d"), "timezone": "Europe/Sofia"},
    {"from": today.strftime("%Y-%m-%d"), "to": (today + timedelta(days=10)).strftime("%Y-%m-%d"), "timezone": "Europe/Sofia"},
    {"next": 10, "timezone": "Europe/Sofia"},
]

for params in params_list:
    r = requests.get(f"{BASE_URL}/fixtures", headers=HEADERS, params=params, timeout=25)
    st.subheader(str(params))
    st.write("status:", r.status_code)
    st.write("url:", r.url)
    st.text(r.text[:4000])
