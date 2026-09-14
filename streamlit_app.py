"""
SPX scanner viewer -- Streamlit Cloud front end.

Data flow: the scanner (running on the home PC) writes its dashboard state to
a JSON file inside a Google Drive-synced folder every cycle. Drive's own sync
uploads it. This app fetches that file's public direct-download link on every
autorefresh, then renders it using the *same* chart code as the local
dashboard (dashboard_template.html is a copy of dashboard.html with its
fetch('/state') polling loop swapped for a value injected from Python) --
no chart logic is duplicated or reimplemented here.

Secrets required (this app's Settings -> Secrets on Streamlit Cloud):
    DRIVE_STATE_URL = "https://drive.google.com/uc?export=download&id=<FILE_ID>"

<FILE_ID> comes from the Drive share link for state.json once the scanner has
created it (Share -> Anyone with the link -> Viewer -> copy link -- the ID is
the long string between "/d/" and "/view" in that link).
"""

import json
import os
import time

import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="SPX Scanner", layout="wide")
st_autorefresh(interval=15_000, key="refresh")

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_template.html")

url = st.secrets.get("DRIVE_STATE_URL")
if not url:
    st.error("DRIVE_STATE_URL isn't set yet. Add it under this app's Settings -> Secrets.")
    st.stop()

try:
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
except Exception as e:                                    # noqa: BLE001
    st.warning(f"Couldn't load live data yet ({type(e).__name__}: {e}). "
               "Waiting for the scanner to publish -- this is expected before it's running.")
    st.stop()

with open(TEMPLATE_PATH, encoding="utf-8") as fh:
    template = fh.read()

# Ticker selection lives in a native Streamlit widget, not the embedded page's
# own JS. st_autorefresh reruns this whole script every 15s, which rebuilds
# and re-injects the entire HTML document into the iframe from scratch -- any
# state the *page's own* JS was holding (which ticker was selected) resets
# with it. A widget keyed into st.session_state is what Streamlit actually
# preserves across reruns, so that's the source of truth: read it here and
# feed it back in as the page's starting SELECTED value on every rebuild.
symbols = data.get("symbols") or ([data["symbol"]] if data.get("symbol") else [])
selected = None
if len(symbols) > 1:
    choice = st.radio("Ticker", ["ALL"] + symbols, horizontal=True,
                       key="selected_ticker", label_visibility="collapsed")
    selected = None if choice == "ALL" else choice

# JSON is valid JS, except a literal "</script>" inside a string would close
# the tag early -- escape it before inlining.
payload_js = json.dumps(data).replace("</", "<\\/")
selected_js = json.dumps(selected)   # None -> "null", "SPX" -> '"SPX"'
html = template.replace("__PAYLOAD__", payload_js).replace("__SELECTED__", selected_js)

st.caption(f"Last scanner update: {data.get('ts', '?')} CT  |  page refreshed {time.strftime('%H:%M:%S')}")
st.components.v1.html(html, height=2400, scrolling=True)
