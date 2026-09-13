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
5. Save. No redeploy needed -- the app picks up the secret on its next run
   (within the 15s autorefresh).

## How it stays "live"

`streamlit_autorefresh` reruns the page every 15 seconds. Each rerun re-fetches
the Drive file and re-renders `dashboard_template.html` (a copy of the local
scanner dashboard's own chart code, unmodified) with the fresh data injected
in. No chart logic lives twice -- if the local dashboard changes, resync this
copy from `dashboard.html` in the main scanner repo.
