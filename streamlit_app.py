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
#
# The radio itself is reskinned via CSS below to look like dashboard.html's
# ticker-bar boxes (symbol + regime letter + lean value, bordered box,
# highlighted border when selected) -- purely cosmetic, the underlying
# mechanism is still the same session_state-backed st.radio that survives
# the autorefresh. This targets Streamlit's current BaseWeb radio markup
# (label[data-baseweb="radio"]), which is NOT a public/stable API -- if a
# future Streamlit upgrade changes that markup, the boxes may need re-tuning
# (it'll just fall back to looking like a plain radio list, still functional).
symbols = data.get("symbols") or ([data["symbol"]] if data.get("symbol") else [])
tickers = data.get("tickers") or {}
selected = None

if len(symbols) > 1:
    options = ["ALL"] + symbols
    labels = {"ALL": "ALL"}
    directions = {"ALL": "flat"}
    for sym in symbols:
        t = tickers.get(sym) or {}
        gex = t.get("gex") or {}
        lean = t.get("lean") or {}
        regime_letter = (gex.get("regime") or "?")[:1]
        sc = lean.get("score_smoothed") if lean.get("score_smoothed") is not None else lean.get("score")
        lean_txt = f"{sc:+.1f}" if sc is not None else "--"
        labels[sym] = f"{sym}  {regime_letter}  {lean_txt}"
        directions[sym] = "up" if (sc or 0) > 0.5 else "down" if (sc or 0) < -0.5 else "flat"

    # Real markup verified live against the deployed app (Streamlit 1.62):
    # each option is <label data-testid="stRadioOption" data-selected="true|false">,
    # NOT data-baseweb="radio" (that was a guess from an older version and
    # silently didn't match anything -- confirmed by inspecting the live DOM
    # before shipping this). The native input sits in a visually-hidden
    # <span>; the visible circle is the first *div* child.
    dir_css = "\n".join(
        f'div[data-testid="stRadio"] label[data-testid="stRadioOption"]:nth-of-type({i}) '
        f'{{ --box-accent: {"#3fb950" if directions[opt]=="up" else "#f85149" if directions[opt]=="down" else "#8b949e"}; }}'
        for i, opt in enumerate(options, start=1)
    )
    st.markdown(f"""
    <style>
      div[data-testid="stRadio"] > div {{ gap: 6px; flex-wrap: wrap; }}
      div[data-testid="stRadio"] label[data-testid="stRadioOption"] {{
        background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        padding: 6px 14px; margin: 0 !important; transition: border-color .15s;
      }}
      div[data-testid="stRadio"] label[data-testid="stRadioOption"] > div:first-of-type {{ display: none; }}
      div[data-testid="stRadio"] label[data-testid="stRadioOption"] div[data-testid="stMarkdownContainer"] p {{
        color: #8b949e; font: 13px/1.2 -apple-system,Segoe UI,Roboto,sans-serif;
      }}
      div[data-testid="stRadio"] label[data-testid="stRadioOption"][data-selected="true"] {{
        border-color: #58a6ff; background: #1c2430;
      }}
      div[data-testid="stRadio"] label[data-testid="stRadioOption"][data-selected="true"] div[data-testid="stMarkdownContainer"] p {{
        color: #e6edf3;
      }}
      div[data-testid="stRadio"] label[data-testid="stRadioOption"] {{ border-left: 3px solid var(--box-accent, #30363d); }}
      {dir_css}
    </style>
    """, unsafe_allow_html=True)

    choice = st.radio("Ticker", options, format_func=lambda o: labels.get(o, o),
                       horizontal=True, key="selected_ticker", label_visibility="collapsed")
    selected = None if choice == "ALL" else choice

# JSON is valid JS, except a literal "</script>" inside a string would close
# the tag early -- escape it before inlining.
payload_js = json.dumps(data).replace("</", "<\\/")
selected_js = json.dumps(selected)   # None -> "null", "SPX" -> '"SPX"'
html = template.replace("__PAYLOAD__", payload_js).replace("__SELECTED__", selected_js)

st.caption(f"Last scanner update: {data.get('ts', '?')} CT  |  page refreshed {time.strftime('%H:%M:%S')}")
st.components.v1.html(html, height=2400, scrolling=True)
