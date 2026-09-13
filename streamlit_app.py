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

# JSON is valid JS, except a literal "</script>" inside a string would close
# the tag early -- escape it before inlining.
payload_js = json.dumps(data).replace("</", "<\\/")
html = template.replace("__PAYLOAD__", payload_js)

st.caption(f"Last scanner update: {data.get('ts', '?')} CT  |  page refreshed {time.strftime('%H:%M:%S')}")
st.components.v1.html(html, height=2400, scrolling=True)
