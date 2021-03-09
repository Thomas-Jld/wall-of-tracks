import sys
import os
import json
import requests

import matplotlib.pyplot as plt

from flask import Flask, request, render_template, redirect, session
from PIL import Image

import spotify_config as spotify
import deezer_config as deezer


images = []
albums = {}
rows,columns = 7, 7
width, height = 640,640

app = Flask(__name__)
app.secret_key = "AVeryUniquePasswordL1KeThis"



@app.route('/', methods=["GET"])
def login():
    return render_template("login.html")


@app.route('/spotify/', methods=["GET"])
def spotify_login():
    return redirect(spotify.AUTH_URL)


@app.route('/spotify/callback/')
def spotify_callback():
    auth_token = request.args['code']
    auth_header = spotify.authorize(auth_token)
    session['auth_header'] = auth_header

    options = {
         "time_range":"long_term", 
         "limit":49
    }

    tops = spotify.get_users_top(auth_header, "tracks", options)

    with open('result.json', 'w') as outfile:
        json.dump(tops, outfile)
        
    for i, track in enumerate(tops["items"]):
        if track["album"]["name"] not in albums:
            url = track["album"]["images"][0]["url"]
            name = track["name"]
            print(f"{name}: {url}")
            images.append(Image.open(requests.get(url, stream=True).raw))
            # images[-1].save(f"results/{options['time_range']}/{i+1}-{''.join(name.split('/'))}.jpeg", "JPEG")

    artwork = Image.new('RGB', size=(width*columns,height*rows))
    for i in range(columns):
        for j in range(rows):
            artwork.paste(images[j*rows + i], (width*i, height*j))
    artwork.save(f"results/{options['time_range']}/top_tracks.jpeg", "JPEG")

    return "Done !"


@app.route('/deezer/', methods=["GET"])
def deezer_login():
    return redirect(deezer.AUTH_URL)


@app.route('/deezer/callback/')
def deezer_callback():
    auth_token = request.args['code']
    auth_header, token = deezer.authorize(auth_token)
    session['auth_header'] = auth_header


    return deezer.get_users_top(token)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=27150)
