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

let last_played;
let current_timestamp;

socket.on("recent", (data) => {
    if(last_played == undefined || last_played != data[0].played_at) {
        last_played = data[0].played_at;
        loadImage(data[0].track.album.images[0].url, update_recently_played)
    }
});

socket.on("playing", (data) => {
    if(current_timestamp == undefined || current_timestamp != data.timestamp) {
        current_timestamp = data.timestamp;
        loadImage(data.item.album.images[0].url, update_playing);
    }
    is_playing = data.is_playing;
})

socket.on("init_recent", async (data) => {
    let amount = min(data.length, 48);
    for(let i = 0; i < amount; i++) {
        loadImage(data[amount-i-1].track.album.images[0].url, update_recently_played);
        while(!img_loaded) {
            await sleep(100);
        }
        img_loaded = false;
    }
    last_played = data[0].played_at;
})

setInterval(() => {
    socket.emit("get_recent");
}
, 10000);

setInterval(() => {
    socket.emit("get_playing");
}
, 2500);

socket.emit("get_all_recent");
socket.emit("get_playing");

//Sleep function
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
