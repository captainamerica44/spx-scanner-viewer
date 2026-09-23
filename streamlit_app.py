"""
SPX scanner viewer -- Streamlit Cloud front end.

Data flow: the scanner (running on the home PC) writes its dashboard state to
a JSON file inside a Google Drive-synced folder every cycle. Drive's own sync
uploads it. This app reads that file and renders it using the *same* chart
code as the local dashboard (dashboard_template.html is a copy of
dashboard.html with its fetch('/state') polling loop swapped for an
applyState() entry point) -- no chart logic is duplicated or reimplemented.

HOW THE REFRESH WORKS (and why it is not the obvious thing)

The obvious thing -- st_autorefresh rerunning the whole script every 15s --
is what this app used to do, and it made the page hard to actually read: a
rerun rebuilds the component's iframe from scratch, so every 15 seconds the
document being read was destroyed and replaced. Scroll position, the ticker
that was open, expanded alert rows: all gone. That is a known Streamlit
limitation with no official fix (streamlit/streamlit#9002 and years of forum
threads); an embedded page cannot opt out of being re-rendered.

So the dashboard is no longer re-rendered at all. It is drawn ONCE, and a
separate, invisible fragment does the refreshing:

    dashboard iframe  (height 2400, rendered once, never touched again)
    feed iframe       (1px, inside @st.fragment(run_every=15))

A fragment rerun re-executes ONLY that fragment and leaves the rest of the
page untouched -- that is what fragments are for. So every 15s just the tiny
feed is rebuilt. Its script reaches into the dashboard's iframe (same origin,
so this is allowed) and calls applyState(newData), which updates the numbers
in place without rebuilding anything.

The page therefore behaves like a real scanner: it stays put and the numbers
move. Ticker selection is handled by the page's own ticker bar again, not by
a Streamlit radio, because the page's own JS state now survives -- which is
also why the radio and its CSS reskin are gone.

Why not let the browser fetch the JSON itself, and skip Python? Google does
not allow it. Tested 2026-09-22 from a browser: drive.google.com/uc and
drive.usercontent.google.com both fail CORS outright, and the Drive v3 API
answers 403 without an API key -- which would mean a Google credential
sitting in public page source. Fetching server-side has none of those
problems.

Secrets required (this app's Settings -> Secrets on Streamlit Cloud):
    DRIVE_STATE_URL = "https://drive.google.com/uc?export=download&id=<FILE_ID>"

<FILE_ID> comes from the Drive share link for state.json once the scanner has
created it (Share -> Anyone with the link -> Viewer -> copy link -- the ID is
the long string between "/d/" and "/view" in that link). A plain filesystem
path also works, which is handy for running this viewer on the home PC
straight against the synced folder.
"""

import json
import os

import requests
import streamlit as st

st.set_page_config(page_title="SPX Scanner", layout="wide")

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "dashboard_template.html")
REFRESH_SECONDS = 15
DASHBOARD_HEIGHT = 2400


def _source() -> str | None:
    try:
        src = st.secrets.get("DRIVE_STATE_URL")
    except Exception:                                     # noqa: BLE001
        src = None                                        # no secrets.toml at all
    return src or os.environ.get("DRIVE_STATE_URL")


def _load(src: str) -> dict:
    """The scanner's state, from Drive over HTTP or from a local path."""
    if src.lower().startswith(("http://", "https://")):
        resp = requests.get(src, timeout=10)
        resp.raise_for_status()
        return resp.json()
    with open(src, encoding="utf-8") as fh:
        return json.load(fh)


def _js_payload(data: dict) -> str:
    # JSON is valid JS, except a literal "</script>" inside a string would
    # close the tag early -- escape it before inlining.
    return json.dumps(data).replace("</", "<\\/")


src = _source()
if not src:
    st.error("DRIVE_STATE_URL isn't set yet. Add it under this app's Settings -> Secrets.")
    st.stop()

try:
    first = _load(src)
except Exception as e:                                    # noqa: BLE001
    st.warning(f"Couldn't load live data yet ({type(e).__name__}: {e}). "
               "Waiting for the scanner to publish -- this is expected before it's running.")
    st.stop()

st.markdown("""<style>
  /* the dashboard brings its own padding; the feed is invisible plumbing */
  .stMain .block-container{padding:0 !important;max-width:100% !important}
  .stMain iframe[height="1"]{display:block;height:1px !important;border:0}
</style>""", unsafe_allow_html=True)

# ---- the dashboard itself: drawn once, then never re-rendered --------------
with open(TEMPLATE_PATH, encoding="utf-8") as fh:
    template = fh.read()
st.iframe(template.replace("__PAYLOAD__", _js_payload(first)),
          height=DASHBOARD_HEIGHT)


# ---- the feed: the only thing that reruns ---------------------------------
@st.fragment(run_every=REFRESH_SECONDS)
def _feed():
    """Push fresh state into the dashboard iframe without rebuilding it.

    Rendered 1px tall -- there is nothing to look at. On a fragment rerun
    only this iframe is replaced, so its <script> runs again with new data
    while the dashboard's document, and everything the reader was doing in
    it, stays exactly as it was.
    """
    try:
        data = _load(src)
    except Exception as e:                                # noqa: BLE001
        # A failed poll is not worth tearing the page down for: the dashboard
        # keeps showing the last good state and marks itself stale on its own.
        st.iframe(f"<script>console.warn('viewer: state fetch failed: "
                  f"{type(e).__name__}');</script>", height=1)
        return

    st.iframe(f"""<script>
// Hand the new state to the dashboard. st.iframe embeds HTML same-origin
// with the app page (its own docs say so), so this reach-across is allowed.
// The dashboard is identified by the function it exposes rather than by
// position, because Streamlit decides the DOM order, not us.
(function(){{
  const payload = {_js_payload(data)};
  let tries = 0;
  (function push(){{
    try{{
      for(const f of window.parent.document.querySelectorAll('iframe')){{
        const w = f.contentWindow;
        if(w && typeof w.applyState === 'function'){{ w.applyState(payload); return; }}
      }}
    }}catch(e){{ /* dashboard not up yet */ }}
    if(++tries < 40) setTimeout(push, 250);        // ~10s of grace on first load
  }})();
}})();
</script>""", height=1)


_feed()
