"""One-time Spotify login that writes the refresh token used by tracker.py.

On a headless server, tunnel the callback port from your laptop first:
    ssh -p 3616 -L 27150:127.0.0.1:27150 ubuntu@vvps.thomasjuldo.com
then run this there and open the printed URL in your laptop's browser.
"""

import spotipy

from tracker import TOKEN_CACHE_PATH, make_auth_manager

auth = make_auth_manager(open_browser=True)
print("If no browser opens, visit:\n\n  " + auth.get_authorize_url() + "\n")
auth.get_access_token(as_dict=False)

me = spotipy.Spotify(auth_manager=auth).current_user()
print(f"Logged in as {me['display_name']}; token saved to {TOKEN_CACHE_PATH}")
