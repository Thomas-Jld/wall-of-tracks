let recently_played = [];

let currently_playing;
let is_playing = false;

let img_loaded = false;

let pattern;
let s_r;

let multiplier = 1;
let x_offset = 0,
    y_offset = 0;

function setup() {
    createCanvas(windowWidth, windowHeight);

    if (windowHeight < windowWidth) {
        s_r = windowHeight / 10;
        x_offset = (windowWidth - windowHeight) / 2;
    } else {
        s_r = windowWidth / 10;
        y_offset = (windowHeight - windowWidth) / 2;
    }
    create_pattern(s_r);
    imageMode(CENTER);
}

function windowResized() {
    resizeCanvas(windowWidth, windowHeight);

    let s_r;
    if (windowHeight < windowWidth) {
        s_r = windowHeight / 10;
        x_offset = (windowWidth - windowHeight) / 2;
    } else {
        s_r = windowWidth / 10;
        y_offset = (windowHeight - windowWidth) / 2;
    }
    create_pattern(s_r);
}

function draw() {
    background(0);
    let index;
    for (let i = 0; i < recently_played.length; i++) {
        index = recently_played.length - i;
        image(
            recently_played[i],
            x_offset + pattern[index][0] + pattern[index][2] / 2,
            y_offset + pattern[index][1] + pattern[index][2] / 2,
            pattern[index][2],
            pattern[index][2]
        );
    }
    if (is_playing) {
        multiplier = lerp(
            multiplier,
            1 - 0.025 * (Math.sin(window.performance.now() / 300) + 1),
            0.4
        );
    } else {
        multiplier = lerp(multiplier, 1, 0.1);
    }
    if (currently_playing != undefined)
        image(
            currently_playing,
            x_offset + pattern[0][0] + pattern[0][2] / 2,
            y_offset + pattern[0][1] + pattern[0][2] / 2,
            pattern[0][2] * multiplier,
            pattern[0][2] * multiplier
        );
}

function update_recently_played(image) {
    if (recently_played.length >= pattern.length - 1) {
        recently_played.shift();
    }
    recently_played.push(image);
    img_loaded = true;
}

function update_playing(image) {
    currently_playing = image;
}

function create_pattern(s_r) {
    pattern = [
        [3 * s_r, 3 * s_r, 4 * s_r],
        [s_r + 0 * 2 * s_r, s_r, 2 * s_r],
        [s_r + 1 * 2 * s_r, s_r, 2 * s_r],
        [s_r + 2 * 2 * s_r, s_r, 2 * s_r],
        [s_r + 3 * 2 * s_r, s_r + 0 * 2 * s_r, 2 * s_r],
        [s_r + 3 * 2 * s_r, s_r + 1 * 2 * s_r, 2 * s_r],
        [s_r + 3 * 2 * s_r, s_r + 2 * 2 * s_r, 2 * s_r],
        [s_r + 3 * 2 * s_r, s_r + 3 * 2 * s_r, 2 * s_r],
        [s_r + 2 * 2 * s_r, s_r + 3 * 2 * s_r, 2 * s_r],
        [s_r + 1 * 2 * s_r, s_r + 3 * 2 * s_r, 2 * s_r],
        [s_r, s_r + 3 * 2 * s_r, 2 * s_r],
        [s_r, s_r + 2 * 2 * s_r, 2 * s_r],
        [s_r, s_r + 1 * 2 * s_r, 2 * s_r],
        [0, 0, s_r],
        [s_r, 0, s_r],
        [2 * s_r, 0, s_r],
        [3 * s_r, 0, s_r],
        [4 * s_r, 0, s_r],
        [5 * s_r, 0, s_r],
        [6 * s_r, 0, s_r],
        [7 * s_r, 0, s_r],
        [8 * s_r, 0, s_r],
        [9 * s_r, 0, s_r],
        [9 * s_r, s_r, s_r],
        [9 * s_r, 2 * s_r, s_r],
        [9 * s_r, 3 * s_r, s_r],
        [9 * s_r, 4 * s_r, s_r],
        [9 * s_r, 5 * s_r, s_r],
        [9 * s_r, 6 * s_r, s_r],
        [9 * s_r, 7 * s_r, s_r],
        [9 * s_r, 8 * s_r, s_r],
        [9 * s_r, 9 * s_r, s_r],
        [8 * s_r, 9 * s_r, s_r],
        [7 * s_r, 9 * s_r, s_r],
        [6 * s_r, 9 * s_r, s_r],
        [5 * s_r, 9 * s_r, s_r],
        [4 * s_r, 9 * s_r, s_r],
        [3 * s_r, 9 * s_r, s_r],
        [2 * s_r, 9 * s_r, s_r],
        [s_r, 9 * s_r, s_r],
        [0, 9 * s_r, s_r],
        [0, 8 * s_r, s_r],
        [0, 7 * s_r, s_r],
        [0, 6 * s_r, s_r],
        [0, 5 * s_r, s_r],
        [0, 4 * s_r, s_r],
        [0, 3 * s_r, s_r],
        [0, 2 * s_r, s_r],
        [0, s_r, s_r],
    ];
}

function mousePressed() {
    fullscreen(!fullscreen());
}
