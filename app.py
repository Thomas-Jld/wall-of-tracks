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
    return get_likes(request.args['code'])


@app.route('/deezer/', methods=["GET"])
def deezer_login():
    return redirect(deezer.AUTH_URL)


@app.route('/deezer/callback/')
def deezer_callback():
    auth_token = request.args['code']
    auth_header, token = deezer.authorize(auth_token)
    session['auth_header'] = auth_header


    return deezer.get_users_top(token)


def get_dataset(code):
    auth_token = code
    auth_header = spotify.authorize(auth_token)
    session['auth_header'] = auth_header

    options = {
         "limit":50,
         "offset":1000
    }

    tops = spotify.get_users_tracks(auth_header, options)

    done = []

    with open('dataset/infos.csv', 'a+') as outfile:
        for _ in range(20):
            for i, track in enumerate(tops["items"]):
                if track["track"]["album"]["name"] not in done:
                    name = track["track"]["album"]["name"]
                    done.append(name)
                    genres = []
                    artists = [artist["name"] for artist in track["track"]["artists"]]

                    for artist in track["track"]["artists"]:
                        genres.extend(requests.get(artist["href"], headers=auth_header).json()["genres"])

                    artist = "_".join(artists)

                    if  len(genres) == 0:
                        genre = "Unknown"
                    else:
                        genre = "_".join(genres)

                    url = track["track"]["album"]["images"][0]["url"]
                    print(f"{name}-_-{artist}-_-{genre}")
                    Image.open(requests.get(url, stream=True).raw).save(f"dataset/{' '.join(name.split('/'))}-_-{' '.join(artist.split('/'))}.jpeg", "JPEG")
                    outfile.write(f"{' '.join(name.split('/'))};{' '.join(artist.split('/'))};{genre}\n")
            next = tops["next"]
            print(next)
            tops = requests.get(next, headers=auth_header).json()

    return "Done"

def get_likes(code):
    auth_token = code
    auth_header = spotify.authorize(auth_token)
    session['auth_header'] = auth_header

    options = {
         "time_range":"medium_term", 
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

def clean_dataset_infos(path):
    lines = []
    with open(path, "r+") as dataset:
        lines = dataset.readlines()
    
    with open(path, "w+") as dataset:
        unique_dataset = set(lines)
        print(unique_dataset)
        dataset.writelines(unique_dataset)

if __name__ == "__main__":
    # clean_dataset_infos("dataset/infos.csv")
    app.run(host="0.0.0.0", port=27150)
