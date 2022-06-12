import math
import threading
import time
from random import shuffle

import cv2
import numpy as np
import tqdm
from PIL import Image, ImageStat
from skimage import io

def distance(color1, color2):
    # print(color1, color2)
    return np.sqrt(
        (color1[0] - color2[0]) ** 2
        + (color1[1] - color2[1]) ** 2
        + (color1[2] - color2[2]) ** 2
    )

def get_dominant_color(img, n_colors):
    if len(img.shape) == 3:
        pixels = np.float32(img.reshape(-1, 3))
    else:
        pixels = np.float32(img.reshape(-1, 1))

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 200, 0.1)
    flags = cv2.KMEANS_RANDOM_CENTERS

    _, labels, palette = cv2.kmeans(pixels, n_colors, None, criteria, 10, flags)
    _, counts = np.unique(labels, return_counts=True)
    return palette[np.argmax(counts)]


def brightness(img):
    stat = ImageStat.Stat(Image.fromarray(img))
    if len(stat.mean) == 3:
        r, g, b = stat.mean
        # r, g, b = color
        return math.sqrt(0.241 * (r ** 2) + 0.691 * (g ** 2) + 0.068 * (b ** 2))
    else:
        return stat.mean[0]

# exit()

# artwork = Image.new('RGB', size=(res_per_image*res,res_per_image*res))
# original = Image.new('RGB', size=(res_per_image*res,res_per_image*res))

def sort_by_brightness():
    images_brightness = []
    images_indexes = []
    chunks_brightness = []
    chunks_indexes = []

    for i in tqdm.tqdm(range(res)):
        for j in range(res):
            # print(i*res + j)
            img = io.imread(f"images/{i*res + j}.jpeg")
            images_brightness.append(brightness(img))
            images_indexes.append(i * res + j)
            chunks_brightness.append(np.mean(target[i, j]))
            chunks_indexes.append(i * res + j)

    sorted_images_indexes = [x for _, x in sorted(zip(images_brightness, images_indexes))]
    sorted_chunks_indexes = [x for _, x in sorted(zip(chunks_brightness, chunks_indexes))]
    return sorted_images_indexes, sorted_chunks_indexes


def create_from_brightness(sorted_images_indexes, sorted_chunks_indexes):
    result = Image.new("RGB", size=(res_per_image * res, res_per_image * res))

    for i in tqdm.tqdm(range(res * res)):
        index = sorted_chunks_indexes[i]
        result.paste(
            Image.open(f"images/{sorted_images_indexes[i]}.jpeg"),
            (index % res * res_per_image, index // res * res_per_image),
        )

    result = result.resize((4000, 4000))
    result.save(f"result_{target_id}_by_brightness.jpeg")

def get_images_color(amount):
    images_color = []

    with open(f"dominant_colors_{dominant_colors_amount}.csv", "a+") as f:
        f.seek(0)
        data = f.readlines()
        saved_colors = {str(k):[float(r),float(g),float(b)] for k,r,g,b in [line.strip().split(";") for line in data if line.strip()]}
        for i in tqdm.tqdm(range(amount)):
            if str(i) in saved_colors.keys():
                images_color.append(saved_colors[str(i)])
            else:
                img = io.imread(f"images/{i}.jpeg")
                dominant_color = get_dominant_color(img, dominant_colors_amount)
                if len(dominant_color) == 1:
                    dominant_color = [dominant_color[0], dominant_color[0], dominant_color[0]]

                images_color.append(list(dominant_color))
                f.write(f"{i};{dominant_color[0]};{dominant_color[1]};{dominant_color[2]}\n")

    return images_color

def add_closest_image(usages, images_color, result, i, target, res, final_res):
    distances = []
    for usage, color in zip(usages, images_color):
        if len(target.shape) == 3:
            dist = distance(color, target[i % res, i // res])
        else:
            dist = distance(color, [target[i % res, i // res] for _ in range(3)] )
        if usage > 0:
            distances.append(60*usage*dist)
            # distances.append(10e10)
        else:
            distances.append(dist)#/(usage+1))
        # distances.append(dist)
    closest = np.argmin(distances)
    usages[closest] += 1
    result.paste(
        Image.open(f"images/{closest}.jpeg").resize((final_res//res, final_res//res)),
        (i // res * final_res//res, i % res * final_res//res),
    )

def create_from_color(images_color):
    # num_colors = len(images_color)
    # result = Image.new("RGB", size=(res_per_image * res, res_per_image * res))
    result = Image.new("RGB", size=(final_res, final_res))

    usages = [0 for _ in range(len(images_color))]
    candidates = list(range(res * res))
    shuffle(candidates)
    threads = []
    for i in tqdm.tqdm(candidates):
        add_closest_image(usages, images_color, result, i, target, res, final_res)
        # t = threading.Thread(target=add_closest_image, args=(usages, images_color, result, i, target, res, final_res))
        # threads.append(t)
        # t.start()
        # while len(threads) > 5:
        #     for thread in threads:
        #         if not thread.is_alive():
        #             threads.remove(thread)
        #     time.sleep(0.01)

    # result = result.resize((4000, 4000))
    result.save(f"res_{target_id}_{num_colors}_{res}_{dominant_colors_amount}.jpeg")


def create_best():
    # s_r = 400

    # spots = [[3*s_r, 3*s_r, 4*s_r]] + \
    #         [[s_r + i*2*s_r, s_r, 2*s_r] for i in range(3)] + \
    #         [[s_r + 3*2*s_r, s_r + i*2*s_r, 2*s_r] for i in range(3)] + \
    #         [[s_r + (3-i)*2*s_r, s_r + 3*2*s_r, 2*s_r] for i in range(3)] + \
    #         [[s_r, s_r + (3-i)*2*s_r, 2*s_r] for i in range(3)] + \
    #         [[i*s_r, 0, s_r] for i in range(9)] + \
    #         [[9*s_r, i*s_r, s_r] for i in range(9)] + \
    #         [[(9-i)*s_r, 9*s_r, s_r] for i in range(9)] + \
    #         [[0, (9-i)*s_r, s_r] for i in range(9)]

    s_r = 200

    spots = [[7*s_r, 7*s_r, 8*s_r]] + \
            [[3*s_r + i*4*s_r, 3*s_r, 4*s_r] for i in range(3)] + \
            [[3*s_r + 3*4*s_r, 3*s_r + i*4*s_r, 4*s_r] for i in range(3)] + \
            [[3*s_r + (3-i)*4*s_r, 3*s_r + 3*4*s_r, 4*s_r] for i in range(3)] + \
            [[3*s_r, 3*s_r + (3-i)*4*s_r, 4*s_r] for i in range(3)] + \
            [[s_r + i*2*s_r, s_r, 2*s_r] for i in range(9)] + \
            [[s_r + 9*2*s_r, s_r + i*2*s_r, 2*s_r] for i in range(9)] + \
            [[s_r + (9-i)*2*s_r, s_r + 9*2*s_r, 2*s_r] for i in range(9)] + \
            [[s_r, s_r + (9-i)*2*s_r, 2*s_r] for i in range(9)] + \
            [[i*s_r, 0, s_r] for i in range(21)] + \
            [[21*s_r, i*s_r, s_r] for i in range(21)] + \
            [[(21-i)*s_r, 21*s_r, s_r] for i in range(21)] + \
            [[0, (21-i)*s_r, s_r] for i in range(21)]



    result = Image.new("RGB", size=(s_r*22, s_r*22))
    for i in tqdm.tqdm(range(len(spots))):
        result.paste(
            Image.open(f"images/{i}.jpeg").resize((spots[i][2], spots[i][2])),
            (spots[i][0], spots[i][1]),
        )

    result.save(f"top_albums_117.jpeg")

# create_best()


def reduced_color_palette():
    color_resolutions = 32
    resolution = 1024
    result = Image.new("RGB", size=(resolution, resolution))
    target_id = "gradient2"
    target = Image.open(f"{target_id}.jpg").resize((resolution, resolution))
    for i in tqdm.tqdm(range(resolution)):
        for j in range(resolution):
            color = target.getpixel((i, j))
            color = [int(color_resolutions*np.ceil(col/color_resolutions)) for col in color]
            result.putpixel((i, j), tuple(color))

    result.save(f"reduced_color_palette_{target_id}_{resolution}_{color_resolutions}.jpeg")

reduced_color_palette()

if __name__ == "__main__":
    num_colors = 10000
    dominant_colors_amount = 1

    # images_color = get_images_color(num_colors)
    # with open("images_color.txt", "w") as f:
    #     f.write(str(images_color))

    res_per_image = 640
    final_res = 4000
    res = 32
    step = res_per_image // res

    # target_id = 6
    # for target_id in tqdm.tqdm(range(3, 100), position=1):
    target_id = "0"
    target = io.imread(f"images/{target_id}.jpeg")
    target = Image.fromarray(target)
    # target.save(f"target_{target_id}_original.jpeg")
    target = target.resize((res, res))
    # target.save(f"target_{target_id}.jpeg")
    target = np.array(target)


    # sorted_images_indexes, sorted_chunks_indexes = sort_by_brightness()
    # create_from_brightness(sorted_images_indexes, sorted_chunks_indexes)


    # with open("images_color.txt", "r") as f:
    #     images_color = eval(f.read())
    # create_from_color(images_color)






#         color_image = Image.new('RGB', size=(res_per_image,res_per_image), color=tuple(dominant_color))
#         artwork.paste(color_image, (j*res_per_image, i*res_per_image))
#         original.paste(Image.fromarray(img), (j*res_per_image, i*res_per_image))

# original.save("original.jpeg", "JPEG")
# artwork.save(f"test3.jpeg", "JPEG")

# chunk = target[
#     i*step : (i+1)*step,
#     j*step : (j+1)*step,
#     :
# ]
# get_dominant_color(chunk, 3)
