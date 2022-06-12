let recently_played = [];

let currently_playing;
let is_playing = false;

let img_loaded = false;

let pattern;
let s_r;
let pattern_no = 1;

let multiplier = 1;
let x_offset = 0,
    y_offset = 0;

function setup() {
    createCanvas(windowWidth, windowHeight);

    update_pattern();

    imageMode(CENTER);
    rectMode(CENTER);
    textAlign(CENTER, CENTER);
}

function windowResized() {
    resizeCanvas(windowWidth, windowHeight);
    update_pattern();
}

function draw() {
    background(0);
    let index;
    for (let i = 0; i < recently_played.length; i++) {
        index = recently_played.length - i;
        if (index >= pattern.length) continue;
        if (pattern[index][3] == 0) {
            image(
                recently_played[i].image,
                x_offset + pattern[index][0] + pattern[index][2] / 2,
                y_offset + pattern[index][1] + pattern[index][2] / 2,
                pattern[index][2],
                pattern[index][2]
            );
        } else {
            // stroke(255);
            // strokeWeight(1);
            fill(255);
            textSize(pattern[index][2]/16);
            text(
                recently_played[i].name,
                x_offset + pattern[index][0] + pattern[index][2] / 2,
                y_offset + pattern[index][1] + pattern[index][2] / 4,
                pattern[index][2],
                pattern[index][2]/2
            )
            text(
                recently_played[i].artist,
                x_offset + pattern[index][0] + pattern[index][2] / 2,
                y_offset + pattern[index][1] + 3*pattern[index][2] / 4,
                pattern[index][2],
                pattern[index][2]/2
            )
        }
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
    if (currently_playing != undefined){
        if (pattern[0][3] == 0) {
            image(
                currently_playing.image,
                x_offset + pattern[0][0] + pattern[0][2] / 2,
                y_offset + pattern[0][1] + pattern[0][2] / 2,
                pattern[0][2] * multiplier,
                pattern[0][2] * multiplier
            );
        } else {
            // stroke(255);
            // strokeWeight(1);
            fill(255);
            textSize(pattern[0][2]/12 * multiplier);
            text(
                currently_playing.name,
                x_offset + pattern[0][0] + pattern[0][2] / 2,
                y_offset + pattern[0][1] + pattern[0][2] / 4,
                pattern[0][2] * multiplier,
                pattern[0][2] * multiplier/2
            )
            text(
                currently_playing.artist,
                x_offset + pattern[0][0] + pattern[0][2] / 2,
                y_offset + pattern[0][1] + 3*pattern[0][2] / 4,
                pattern[0][2] * multiplier,
                pattern[0][2] * multiplier/2
            )
        }
    }
}

function update_recently_played(image, name, artist, album) {
    if (recently_played.length >= 50) {
        recently_played.shift();
    }
    recently_played.push({
        image: image,
        name: name,
        artist: artist,
        album: album,
    });
    img_loaded = true;
}

function update_playing(image, name, artist, album) {
    currently_playing = {
        image: image,
        name: name,
        artist: artist,
        album: album,
    };
}

function mouseClicked() {
    if (x_offset > 0 && mouseX < x_offset) {
        fullscreen(!fullscreen());
        windowResized();
    } else if (y_offset > 0 && mouseY < y_offset) {
        fullscreen(!fullscreen());
        windowResized();
    }
    if (x_offset > 0 && mouseX > windowWidth - x_offset) {
        pattern_no = (pattern_no + 1) % 2;
        update_pattern();
    } else if (y_offset > 0 && mouseY > windowHeight - y_offset) {
        pattern_no = (pattern_no + 1) % 2;
        update_pattern();
    }
    if (
        (x_offset > 0 &&
            mouseX > x_offset &&
            mouseX < windowWidth - x_offset) ||
        (y_offset > 0 && mouseY > y_offset && mouseY < windowHeight - y_offset)
    ) {
        for (let i = 0; i < pattern.length; i++) {
            if (
                mouseX > x_offset + pattern[i][0] &&
                mouseX < x_offset + pattern[i][0] + pattern[i][2]
            ) {
                if (
                    mouseY > y_offset + pattern[i][1] &&
                    mouseY < y_offset + pattern[i][1] + pattern[i][2]
                ) {
                    pattern[i][3] = 1 - pattern[i][3];
                }
            }
        }
    }
}

function update_pattern() {
    if (pattern_no == 0) {
        if (windowHeight < windowWidth) {
            s_r = windowHeight / 10;
            x_offset = (windowWidth - windowHeight) / 2;
            y_offset = 0;
        } else {
            s_r = windowWidth /* The number of images that are loaded. */ / 10;
            x_offset = 0;
            y_offset = (windowHeight - windowWidth) / 2;
        }
        create_pattern(s_r);
    } else if (pattern_no == 1) {
        if (windowHeight < windowWidth / 2) {
            s_r = windowHeight / 8;
            x_offset = (windowWidth / 2 - windowHeight) / 2;
            y_offset = 0;
        } else {
            s_r = windowWidth / 16;
            x_offset = 0;
            y_offset = (windowHeight - windowWidth / 2) / 2;
        }
        create_pattern_2(s_r);
    }
}

function create_pattern(s_r) {
    pattern = [
        [3 * s_r, 3 * s_r, 4 * s_r, 0],
        [s_r + 0 * 2 * s_r, s_r, 2 * s_r, 0],
        [s_r + 1 * 2 * s_r, s_r, 2 * s_r, 0],
        [s_r + 2 * 2 * s_r, s_r, 2 * s_r, 0],
        [s_r + 3 * 2 * s_r, s_r + 0 * 2 * s_r, 2 * s_r, 0],
        [s_r + 3 * 2 * s_r, s_r + 1 * 2 * s_r, 2 * s_r, 0],
        [s_r + 3 * 2 * s_r, s_r + 2 * 2 * s_r, 2 * s_r, 0],
        [s_r + 3 * 2 * s_r, s_r + 3 * 2 * s_r, 2 * s_r, 0],
        [s_r + 2 * 2 * s_r, s_r + 3 * 2 * s_r, 2 * s_r, 0],
        [s_r + 1 * 2 * s_r, s_r + 3 * 2 * s_r, 2 * s_r, 0],
        [s_r, s_r + 3 * 2 * s_r, 2 * s_r, 0],
        [s_r, s_r + 2 * 2 * s_r, 2 * s_r, 0],
        [s_r, s_r + 1 * 2 * s_r, 2 * s_r, 0],
        [0, 0, s_r, 0],
        [s_r, 0, s_r, 0],
        [2 * s_r, 0, s_r, 0],
        [3 * s_r, 0, s_r, 0],
        [4 * s_r, 0, s_r, 0],
        [5 * s_r, 0, s_r, 0],
        [6 * s_r, 0, s_r, 0],
        [7 * s_r, 0, s_r, 0],
        [8 * s_r, 0, s_r, 0],
        [9 * s_r, 0, s_r, 0],
        [9 * s_r, s_r, s_r, 0],
        [9 * s_r, 2 * s_r, s_r, 0],
        [9 * s_r, 3 * s_r, s_r, 0],
        [9 * s_r, 4 * s_r, s_r, 0],
        [9 * s_r, 5 * s_r, s_r, 0],
        [9 * s_r, 6 * s_r, s_r, 0],
        [9 * s_r, 7 * s_r, s_r, 0],
        [9 * s_r, 8 * s_r, s_r, 0],
        [9 * s_r, 9 * s_r, s_r, 0],
        [8 * s_r, 9 * s_r, s_r, 0],
        [7 * s_r, 9 * s_r, s_r, 0],
        [6 * s_r, 9 * s_r, s_r, 0],
        [5 * s_r, 9 * s_r, s_r, 0],
        [4 * s_r, 9 * s_r, s_r, 0],
        [3 * s_r, 9 * s_r, s_r, 0],
        [2 * s_r, 9 * s_r, s_r, 0],
        [s_r, 9 * s_r, s_r, 0],
        [0, 9 * s_r, s_r, 0],
        [0, 8 * s_r, s_r, 0],
        [0, 7 * s_r, s_r, 0],
        [0, 6 * s_r, s_r, 0],
        [0, 5 * s_r, s_r, 0],
        [0, 4 * s_r, s_r, 0],
        [0, 3 * s_r, s_r, 0],
        [0, 2 * s_r, s_r, 0],
        [0, s_r, s_r, 0],
    ];
}

function create_pattern_2(s_r) {
    pattern = [
        [0, 0, 8 * s_r, 0],
        [8 * s_r, 0, 4 * s_r, 0],
        [12 * s_r, 0, 4 * s_r, 0],
        [8 * s_r, 4 * s_r, 4 * s_r, 0],
        [12 * s_r, 4 * s_r, 2 * s_r, 0],
        [14 * s_r, 4 * s_r, 2 * s_r, 0],
        [12 * s_r, 6 * s_r, 2 * s_r, 0],
        [14 * s_r, 6 * s_r, s_r, 0],
        [15 * s_r, 6 * s_r, s_r, 0],
        [14 * s_r, 7 * s_r, s_r, 0],
        [15 * s_r, 7 * s_r, s_r, 0],
    ];
}
