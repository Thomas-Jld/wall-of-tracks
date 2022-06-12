# Source : https://github.com/hereismari/spotify-flask

from __future__ import print_function
import base64
import json
import requests
import sys

import urllib.request, urllib.error
import urllib.parse as urllibparse


SPOTIFY_API_BASE_URL = "https://api.spotify.com"
API_VERSION = "v1"
SPOTIFY_API_URL = f"{SPOTIFY_API_BASE_URL}/{API_VERSION}"


# spotify endpoints
SPOTIFY_AUTH_BASE_URL = "https://accounts.spotify.com"
SPOTIFY_AUTH_URL = f"{SPOTIFY_AUTH_BASE_URL}/authorize"
SPOTIFY_TOKEN_URL = f"{SPOTIFY_AUTH_BASE_URL}/api/token"

# client keys
CLIENT = json.load(open("conf.json", "r+"))
CLIENT_ID = CLIENT["spotify"]["id"]
CLIENT_SECRET = CLIENT["spotify"]["secret"]


CLIENT_SIDE_URL = "http://127.0.0.1"
PORT = 27150
CLIENT_SIDE_ADRESS = f"{CLIENT_SIDE_URL}:{PORT}"
# CLIENT_SIDE_ADRESS = "https://vps.thomasjuldo.com"
REDIRECT_URI = f"{CLIENT_SIDE_ADRESS}/walloftrack/spotify/callback/"
SCOPE = "user-read-recently-played user-top-read user-library-read user-read-currently-playing"
STATE = ""
SHOW_DIALOG_bool = True
SHOW_DIALOG_str = str(SHOW_DIALOG_bool).lower()


# https://developer.spotify.com/web-api/authorization-guide/
auth_query_parameters = {
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE,
    # "state": STATE,
    # "show_dialog": SHOW_DIALOG_str,
    "client_id": CLIENT_ID,
}


URL_ARGS = "&".join(
    [
        f"{key}={urllibparse.quote(val)}"
        for key, val in list(auth_query_parameters.items())
    ]
)


AUTH_URL = f"{SPOTIFY_AUTH_URL}/?{URL_ARGS}"


def authorize(auth_token):

    code_payload = {
        "grant_type": "authorization_code",
        "code": str(auth_token),
        "redirect_uri": REDIRECT_URI,
    }

    base64encoded = base64.b64encode(
        ("{}:{}".format(CLIENT_ID, CLIENT_SECRET)).encode()
    )
    headers = {"Authorization": "Basic {}".format(base64encoded.decode())}

    post_request = requests.post(SPOTIFY_TOKEN_URL, data=code_payload, headers=headers)

    response_data = json.loads(post_request.text)
    access_token = response_data["access_token"]

    auth_header = {"Authorization": "Bearer {}".format(access_token)}
    return auth_header


GET_ARTIST_ENDPOINT = f"{SPOTIFY_API_URL}/artists"

SEARCH_ENDPOINT = f"{SPOTIFY_API_URL}/search"

USER_PROFILE_ENDPOINT = f"{SPOTIFY_API_URL}/me"
USER_PLAYLISTS_ENDPOINT = f"{USER_PROFILE_ENDPOINT}/playlists"
USER_TOP_ARTISTS_AND_TRACKS_ENDPOINT = f"{USER_PROFILE_ENDPOINT}/top"
USER_TRACKS_ENDPOINT = f"{USER_PROFILE_ENDPOINT}/tracks"  # /<type>
USER_RECENTLY_PLAYED_ENDPOINT = f"{USER_PROFILE_ENDPOINT}/player/recently-played"
USER_CURRENTLY_PLAYING_ENDPOINT = f"{USER_PROFILE_ENDPOINT}/player/currently-playing"

BROWSE_FEATURED_PLAYLISTS = f"{SPOTIFY_API_URL}/browse/featured-playlists"


def get_users_top(auth_header, t, options={}):
    if t not in ["artists", "tracks"]:
        print("invalid type")
        return None

    url = f"{USER_TOP_ARTISTS_AND_TRACKS_ENDPOINT}/{t}"

    if "time_range" in options:
        url = f"{url}?time_range={options['time_range']}"

    if "limit" in options:
        url = f"{url}&limit={options['limit']}"

    resp = requests.get(url, headers=auth_header)
    return resp.json()

def get_recently_played(auth_header, options={}):
    url = f"{USER_RECENTLY_PLAYED_ENDPOINT}"
    if "limit" in options:
        url = f"{url}?limit={options['limit']}"
    resp = requests.get(url, headers=auth_header)
    return resp.json()

def get_currently_playing(auth_header):
    resp = requests.get(USER_CURRENTLY_PLAYING_ENDPOINT, headers=auth_header)
    return resp.json()


def get_users_tracks(auth_header, options={}):

    url = f"{USER_TRACKS_ENDPOINT}"

    if "limit" in options:
        url = f"{url}?limit={options['limit']}"

    if "offset" in options:
        url = f"{url}&offset={options['offset']}"

    resp = requests.get(url, headers=auth_header)
    return resp.json()

def get_track_info(auth_header, track_id):
    url = f"{SPOTIFY_API_URL}/tracks/{track_id}"
    resp = requests.get(url, headers=auth_header)
    return resp.json()
