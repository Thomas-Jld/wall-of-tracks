from __future__ import print_function
import base64
import json
import requests
import sys

# Workaround to support both python 2 & 3
try:
    import urllib.request, urllib.error
    import urllib.parse as urllibparse
except ImportError:
    import urllib as urllibparse


DEEZER_API_BASE_URL = 'https://api.deezer.com'
API_VERSION = "v1"
DEEZER_API_URL = "{}/{}".format(DEEZER_API_BASE_URL, API_VERSION)

DEEZER_AUTH_BASE_URL = "https://connect.deezer.com/{}"
DEEZER_AUTH_URL = DEEZER_AUTH_BASE_URL.format('oauth/auth.php')
DEEZER_TOKEN_URL = DEEZER_AUTH_BASE_URL.format('oauth/access_token.php')

# client keys
CLIENT = json.load(open('conf.json', 'r+'))
CLIENT_ID = CLIENT['deezer']['id']
CLIENT_SECRET = CLIENT['deezer']['secret']

CLIENT_SIDE_URL = "http://127.0.0.1"
PORT = 27150
REDIRECT_URI = "{}:{}/deezer/callback/".format(CLIENT_SIDE_URL, PORT)
PERMS = "basic_access,email,listening_history"

auth_query_parameters = {
    "app_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "perms": PERMS,
}

#python 3
if sys.version_info[0] >= 3:
    URL_ARGS = "&".join(["{}={}".format(key, urllibparse.quote(val))
                    for key, val in list(auth_query_parameters.items())])
else: 
    URL_ARGS = "&".join(["{}={}".format(key, urllibparse.quote(val))
                    for key, val in auth_query_parameters.iteritems()])


AUTH_URL = "{}/?{}".format(DEEZER_AUTH_URL, URL_ARGS)



def authorize(auth_token):

    token_url = 'https://connect.deezer.com/oauth/access_token.php?app_id=' + CLIENT_ID +'&secret=' + CLIENT_SECRET +'&code=' + auth_token

    post_request = requests.post(token_url)
    access_token = post_request.text.split('=')[1]

    # use the access token to access DEEZER API
    auth_header = {"Authorization": "Bearer {}".format(access_token)}
    return auth_header, access_token


def get_users_top(auth_header):

    url = f"https://api.deezer.com/user/me/history" + '?access_token=' + auth_header
    resp = requests.get(url)
    return resp.json()