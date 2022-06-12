let path_parameter = window.location.pathname.split("/");
let heatmap_history = [];
path_parameter.splice(-1);
path_parameter.splice(-1);
const path = path_parameter.join("/");

const socket = io.connect(window.location.origin, {
    path: path + "/socket.io",
    cors: {
        origin: "*",
        methods: ["GET", "POST"],
    },
    agent: false,
    upgrade: false,
    rejectUnauthorized: false,
    // transports: ["websocket"],
});

let last_played = {};
let current_timestamp;

socket.on("redirect", (url) => {
    window.location.href = url;
});

socket.on("recent", (data) => {
    if ((last_played.played_at == undefined ||
        last_played.played_at != data[0].played_at)) {
        let name, artist, album, image;
        name = data[0].track.name;
        artist = data[0].track.artists[0].name;
        album = data[0].track.album.name;
        image = data[0].track.album.images[0].url;
        last_played.played_at = data[0].played_at;
        if(last_played.name != name || last_played.artist != artist) {
            last_played.name = name;
            last_played.artist = artist;
            loadImage(image, (img) => {
                update_recently_played(img, name, artist, album);
            });
        }
    }
});

socket.on("playing", (data) => {
    if (current_timestamp == undefined || current_timestamp != data.timestamp) {
        let name, artist, album, image;
        name = data.item.name;
        artist = data.item.artists[0].name;
        album = data.item.album.name;
        image = data.item.album.images[0].url;
        current_timestamp = data.timestamp;
        loadImage(image, (img) => {
            update_playing(img, name, artist, album);
        });
    }
    is_playing = data.is_playing;
});

socket.on("init_recent", async (data) => {
    let amount = data.length;
    let name, artist, album, image;
    for (let i = 0; i < amount; i++) {
        if (
            name == data[amount - i - 1].track.name &&
            album == data[amount - i - 1].track.album.name
        )
            continue;
        name = data[amount - i - 1].track.name;
        artist = data[amount - i - 1].track.artists[0].name;
        album = data[amount - i - 1].track.album.name;
        image = data[amount - i - 1].track.album.images[0].url;
        loadImage(image, (img) => {
            update_recently_played(img, name, artist, album);
        });
        while (!img_loaded) {
            await sleep(50);
        }
        img_loaded = false;
    }
    last_played.played_at = data[0].played_at;
    last_played.name = data[0].track.name;
    last_played.album_name = data[0].track.album.name;
});

setInterval(() => {
    socket.emit("get_recent");
}, 10000);

setInterval(() => {
    socket.emit("get_playing");
}, 2500);

socket.emit("get_all_recent");
socket.emit("get_playing");

//Sleep function
function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}
