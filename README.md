# SPX Scanner Viewer

Public Streamlit front end for the SPX/QQQ/USO/SMH/DRAM scanner. Reads live
state from a Google Drive file the scanner writes locally (Drive's own sync
uploads it); this app has no access to the scanner or Robinhood -- it only
reads a public, read-only JSON snapshot.

## One-time setup after deploying

1. Deploy this repo on Streamlit Community Cloud (main file: `streamlit_app.py`).
2. Once the scanner has run at least one cycle and `state.json` exists in the
   Drive-synced folder, right-click it in Google Drive -> Share -> General
   access -> "Anyone with the link" -> Viewer -> Copy link.
3. That link looks like:
   `https://drive.google.com/file/d/AbCdEf1234.../view?usp=sharing`
   Take the id between `/d/` and `/view` and build the direct-download URL:
   `https://drive.google.com/uc?export=download&id=AbCdEf1234...`
4. On this app's Streamlit Cloud page -> Settings -> Secrets, add:
   ```
   DRIVE_STATE_URL = "https://drive.google.com/uc?export=download&id=AbCdEf1234..."
   ```
5. Save. No redeploy needed -- the app picks up the secret within 15 seconds.

## How it stays "live" without rebuilding the page

The dashboard (`dashboard_template.html`, a copy of the local scanner
dashboard's own chart code) is rendered **once**. It is never re-rendered.

A separate 1px iframe inside `@st.fragment(run_every=15)` does the
refreshing: a fragment rerun re-executes only that fragment, so every 15s the
tiny feed is rebuilt, re-fetches the Drive file, and calls `applyState(data)`
on the dashboard iframe (same origin, so it can). The numbers change in place
and the document is never destroyed -- scroll position, the open ticker and
expanded rows all survive.

This replaced `st_autorefresh`, which reran the whole script and rebuilt the
dashboard's iframe from scratch every 15 seconds, throwing away whatever you
were looking at. That is a known Streamlit limitation with no official fix
(streamlit/streamlit#9002), not something a component can opt out of.

No chart logic lives twice -- if the local dashboard changes, resync this copy
from `dashboard.html` in the main scanner repo (one swap: the `fetch('/state')`
polling tail becomes the `applyState` entry point).
