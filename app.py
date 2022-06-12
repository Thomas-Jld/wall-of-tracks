import sys
import os
import json
import time

from flask import (
    Flask,
    request,
    render_template,
    redirect,
    session,
    send_from_directory,
)
from flask_socketio import SocketIO
from flask_cors import CORS

from PIL import Image

import spotify_config as spotify
import deezer_config as deezer


images = []
albums = {}
rows, columns = 6, 6

app = Flask(__name__)
app.config['SECRET_KEY'] = "AVeryUniquePasswordL1KeThis"
CORS(app)
socketio = SocketIO(app, path='/walloftrack/socket.io')



@app.route("/walloftrack/", methods=["GET"])
def login():
    return render_template("login.html")


@app.route("/walloftrack/spotify/", methods=["GET"])
def spotify_login():
    return redirect(spotify.AUTH_URL)


@app.route("/walloftrack/spotify/callback/")
def spotify_callback():
    code = request.args["code"]
    auth_header = spotify.authorize(code)
    session["auth_header"] = auth_header
    return redirect("/walloftrack/recent_tracks/")

@app.route("/walloftrack/recent_tracks/", methods=["GET"])
def recent_tracks():
    return render_template("recent_tracks/index.html")

@app.route("/walloftrack/recent_tracks/<path:path>")
def static_path(path):
    return send_from_directory("templates/recent_tracks", path)

@socketio.on('get_recent')
def get_recent():
    client = request.sid
    try:
        options = {"limit": 3}
        recent = spotify.get_recently_played(session["auth_header"], options)["items"]
        socketio.emit('recent', recent, room=client)
    except Exception as e:
        print(e)
        socketio.emit('redirect', "/walloftrack/spotify/", room=client)


@socketio.on('get_all_recent')
def get_all_recent():
    client = request.sid
    try:
        options = {"limit": 50}
        recent = spotify.get_recently_played(session["auth_header"], options)["items"]
        socketio.emit('init_recent', recent, room=client)
    except Exception as e:
        print(e)
        socketio.emit('redirect', "/walloftrack/spotify/", room=client)

@socketio.on('get_playing')
def get_playing():
    client = request.sid
    try:
        playing = spotify.get_currently_playing(session["auth_header"])
        socketio.emit('playing', playing, room=client)
    except ValueError:
        pass
    except Exception as e:
        print(e)
        socketio.emit('redirect', "/walloftrack/spotify/", room=client)


@app.route("/deezer/", methods=["GET"])
def deezer_login():
    return redirect(deezer.AUTH_URL)


@app.route("/deezer/callback/")
def deezer_callback():
    auth_token = request.args["code"]
    auth_header, token = deezer.authorize(auth_token)
    session["auth_header"] = auth_header

    return generate_deezer_likes(deezer.get_users_top(token))


def get_dataset(code):
    auth_token = code
    auth_header = spotify.authorize(auth_token)
    session["auth_header"] = auth_header

    options = {"limit": 50, "offset": 1000}

    tops = spotify.get_users_tracks(auth_header, options)

    done = []

    with open("dataset/infos.csv", "a+") as outfile:
        for _ in range(20):
            for i, track in enumerate(tops["items"]):
                if track["track"]["album"]["name"] not in done:
                    name = track["track"]["album"]["name"]
                    done.append(name)
                    genres = []
                    artists = [artist["name"] for artist in track["track"]["artists"]]

                    for artist in track["track"]["artists"]:
                        genres.extend(
                            requests.get(artist["href"], headers=auth_header).json()[
                                "genres"
                            ]
                        )

                    artist = "_".join(artists)

                    if len(genres) == 0:
                        genre = "Unknown"
                    else:
                        genre = "_".join(genres)

                    url = track["track"]["album"]["images"][0]["url"]
                    print(f"{name}-_-{artist}-_-{genre}")
                    Image.open(requests.get(url, stream=True).raw).save(
                        f"dataset/{' '.join(name.split('/'))}-_-{' '.join(artist.split('/'))}.jpeg",
                        "JPEG",
                    )
                    outfile.write(
                        f"{' '.join(name.split('/'))};{' '.join(artist.split('/'))};{genre}\n"
                    )
            next = tops["next"]
            print(next)
            tops = requests.get(next, headers=auth_header).json()

    return "Done"


def get_likes(code):
    width, height = 640, 640
    auth_token = code
    auth_header = spotify.authorize(auth_token)
    session["auth_header"] = auth_header

    options = {"time_range": "long_term", "limit": 50, "offset": 0}

    tops = spotify.get_users_top(auth_header, "tracks", options)
    albums = []
    banned = ["Lost Cause"]

    with open("result.json", "w") as outfile:
        json.dump(tops, outfile)

    while len(albums) < rows * columns:
        for i, track in enumerate(tops["items"]):
            print(len(albums))
            if (
                track["album"]["name"][0:10] not in albums
                and track["album"]["name"][0:10] not in banned
            ):
                albums.append(track["album"]["name"][0:10])
                url = track["album"]["images"][0]["url"]
                name = track["name"]
                print(f"{track['album']['name'][0:10]}: {url}")
                images.append(Image.open(requests.get(url, stream=True).raw))
                # images[-1].save(f"results/{options['time_range']}/{i+1}-{''.join(name.split('/'))}.jpeg", "JPEG")

    artwork = Image.new("RGB", size=(width * columns, height * rows))
    for i in range(columns):
        for j in range(rows):
            artwork.paste(images[j * rows + i], (width * i, height * j))
    artwork.save(f"static/{options['time_range']}/top_tracks.jpeg", "JPEG")

    return send_from_directory("./static", f"{options['time_range']}/top_tracks.jpeg")


def generate_deezer_likes(likes):
    width, height = 500, 500
    tops = likes["data"]
    albums = []
    banned = ["Lost Cause"]

    if len(tops) < rows * columns:
        return f"Not enough albums: {len(tops)}"

    with open("result.json", "w") as outfile:
        json.dump(tops, outfile)

    while len(albums) < rows * columns:
        for i, track in enumerate(tops):
            print(len(albums))
            if (
                track["album"]["title"][0:10] not in albums
                and track["album"]["title"][0:10] not in banned
            ):
                albums.append(track["album"]["title"][0:10])
                url = track["album"]["cover_big"]
                name = track["title"]
                print(f"{track['album']['title'][0:10]}: {url}")
                images.append(Image.open(requests.get(url, stream=True).raw))
                # images[-1].save(f"results/{options['time_range']}/{i+1}-{''.join(name.split('/'))}.jpeg", "JPEG")

    artwork = Image.new("RGB", size=(width * columns, height * rows))
    for i in range(columns):
        for j in range(rows):
            artwork.paste(images[j * rows + i], (width * i, height * j))
    artwork.save(f"static/deezer/top_tracks.jpeg", "JPEG")

    return send_from_directory("./static", f"deezer/top_tracks.jpeg")


def clean_dataset_infos(path):
    lines = []
    with open(path, "r+") as dataset:
        lines = dataset.readlines()

    with open(path, "w+") as dataset:
        unique_dataset = set(lines)
        print(unique_dataset)
        dataset.writelines(unique_dataset)


def get_albums_images(code):
    auth_token = code
    auth_header = spotify.authorize(auth_token)
    session["auth_header"] = auth_header

    albums_data = {}
    albums_name = []
    albums_count = []

    for i in range(0, 7):
        with open(f"data/endsong_{i}.json") as json_file:
            endsong = json.load(json_file)
            for album in endsong:
                name = album["master_metadata_album_album_name"]
                if name is None:
                    continue
                if name not in albums_name:
                    albums_name.append(name)
                    albums_count.append(1)
                    albums_data[name] = album["spotify_track_uri"]
                else:
                    albums_count[albums_name.index(name)] += 1

    print(len(albums_name))
    albums_name_sorted = [
        (name, count)
        for count, name in sorted(zip(albums_count, albums_name), reverse=True)
    ]
    print(albums_name_sorted[:5])

    images = []
    last_img = Image.open(f"images/0.jpeg")
    for i, (name, count) in enumerate(albums_name_sorted):
        if os.path.exists(f"images/{i}.jpeg"):
            continue
        id = albums_data[albums_name_sorted[i][0]].split(":")[-1]
        data = spotify.get_track_info(auth_header, id)
        album_images = data["album"]["images"]
        try:
            if len(album_images) > 0:
                image_url = album_images[0]["url"]
                last_img = Image.open(requests.get(image_url, stream=True).raw)
            last_img.save(f"images/{i}.jpeg", "JPEG")
        except Exception as e:
            print(i)
            print(id)
            print(name)
            print(data)
            print(e)
            break

    # create_image(640, 640, 15, 15, images)

    return "Done"


def create_image(width, height, columns, rows, images):
    artwork = Image.new("RGB", size=(width * columns, height * rows))
    for i in range(columns):
        for j in range(rows):
            artwork.paste(images[j * rows + i], (width * i, height * j))
    artwork.save(f"test.jpeg", "JPEG")


if __name__ == "__main__":
    # clean_dataset_infos("dataset/infos.csv")
    app.run(host="0.0.0.0", port=27150)
