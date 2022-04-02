import io
import os
import os.path
import math
import requests
import json
import time
import threading
from io import BytesIO
from websocket import create_connection
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from PIL import ImageColor
from PIL import Image
from packaging import version
import random

# set verbose mode to increase output (messy)
verbose = False

if os.path.exists("./.env"):
    # load env variables
    load_dotenv()
else:
    exit("No .env file found. Read the README")

# map of colors for pixels you can place
color_map = {
    "#BE0039": 1,  # dark red
    "#FF4500": 2,  # red
    "#FFA800": 3,  # orange
    "#FFD635": 4,  # yellow
    "#00A368": 6,  # darker green
    "#00CC78": 7,  # green
    "#7EED56": 8,  # lighter green
    "#00756F": 9,  # dark teal
    "#009EAA": 10, # teal
    "#2450A4": 12,  # dark blue
    "#3690EA": 13,  # blue
    "#51E9F4": 14,  # light blue
    "#493AC1": 15,  # indigo
    "#6A5CFF": 16,  # periwinkle
    "#811E9F": 18,  # darkest purple
    "#B44AC0": 19,  # normal purple
    "#FF3881": 22,  # pink
    "#FF99AA": 23,  # light pink
    "#6D482F": 24,  # dark brown
    "#9C6926": 25,  # brown
    "#000000": 27,  # black
    "#898D90": 29,  # grey
    "#D4D7D9": 30,  # light grey
    "#FFFFFF": 31,  # white
}

# map of pixel color ids to verbose name (for debugging)
name_map = {
    1: "Dark Red",
    2: "Red",
    3: "Orange",
    4: "Yellow",
    6: "Dark Green",
    7: "Green",
    8: "Light Green",
    9: "Dark Teal",
    10: "Teal",
    12: "Dark Blue",
    13: "Blue",
    14: "Light Blue",
    15: "Indigo",
    16: "Periwinkle",
    18: "Dark Purple",
    19: "Purple",
    22: "Pink",
    23: "Light Pink",
    24: "Dark Brown",
    25: "Brown",
    27: "Black",
    29: "Grey",
    30: "Light Grey",
    31: "White",
}

# color palette
rgb_colors_array = []

# auth variables
access_tokens = []
access_token_expires_at_timestamp = []

# image.jpg information
pix = None
image_width = None
image_height = None

# place a pixel immediately
# first_run = True
first_run_counter = 0


# function to convert rgb tuple to hexadecimal string
def rgb_to_hex(rgb):
    return ("#%02x%02x%02x" % rgb).upper()


# Get a more verbose color indicator from a pixel color ID
def color_id_to_name(color_id):
    if color_id in name_map.keys():
        return "{} ({})".format(name_map[color_id], str(color_id))
    return "Invalid Color ({})".format(str(color_id))


# function to find the closest rgb color from palette to a target rgb color
def closest_color(target_rgb, rgb_colors_array_in):
    r, g, b = target_rgb
    if (r == 69) and (g == 42) and (b == 0):
        return (69, 42, 0)
    if (r == 69) and (g == 41) and (b == 1):
        return (69, 42, 0)
    color_diffs = []
    for color in rgb_colors_array_in:
        cr, cg, cb = color
        color_diff = math.sqrt((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2)
        color_diffs.append((color_diff, color))
    return min(color_diffs)[1]


# method to draw a pixel at an x, y coordinate in r/place with a specific color
def set_pixel_and_check_ratelimit(
    access_token_in, x, y, color_index_in=18, canvas_index=0
):
    while x > 999:
        canvas_index += 1
        x-=1000
    print("placing " + color_id_to_name(color_index_in) + " pixel at " + str((x, y)))

    url = "https://gql-realtime-2.reddit.com/query"

    payload = json.dumps(
        {
            "operationName": "setPixel",
            "variables": {
                "input": {
                    "actionName": "r/replace:set_pixel",
                    "PixelMessageData": {
                        "coordinate": {"x": x, "y": y},
                        "colorIndex": color_index_in,
                        "canvasIndex": canvas_index,
                    },
                }
            },
            "query": "mutation setPixel($input: ActInput!) {\n  act(input: $input) {\n    data {\n      ... on BasicMessage {\n        id\n        data {\n          ... on GetUserCooldownResponseMessageData {\n            nextAvailablePixelTimestamp\n            __typename\n          }\n          ... on SetPixelResponseMessageData {\n            timestamp\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
        }
    )
    headers = {
        "origin": "https://hot-potato.reddit.com",
        "referer": "https://hot-potato.reddit.com/",
        "apollographql-client-name": "mona-lisa",
        "Authorization": "Bearer " + access_token_in,
        "Content-Type": "application/json",
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    print(response.json())
    if verbose:
        print("received response: ", response.text)
    # There are 2 different JSON keys for responses to get the next timestamp.
    # If we don't get data, it means we've been rate limited.
    # If we do, a pixel has been successfully placed.
    if response.json()["data"] == None:
        
        waitTime = math.floor(
            response.json()["errors"][0]["extensions"]["nextAvailablePixelTs"]
        )
        print("placing failed: rate limited")
    else:
        waitTime = math.floor(
            response.json()["data"]["act"]["data"][0]["data"][
                "nextAvailablePixelTimestamp"
            ]
        )
        print("placing succeeded")

    # THIS COMMENTED CODE LETS YOU DEBUG THREADS FOR TESTING
    # Works perfect with one thread.
    # With multiple threads, every time you press Enter you move to the next one.
    # Move the code anywhere you want, I put it here to inspect the API responses.

    # import code

    # code.interact(local=locals())

    # Reddit returns time in ms and we need seconds, so divide by 1000
    return waitTime / 1000


def get_board(access_token_in):
    print("Getting board")
    ws = create_connection(
        "wss://gql-realtime-2.reddit.com/query", origin="https://hot-potato.reddit.com"
    )
    ws.send(
        json.dumps(
            {
                "type": "connection_init",
                "payload": {"Authorization": "Bearer " + access_token_in},
            }
        )
    )
    ws.recv()
    ws.send(
        json.dumps(
            {
                "id": "1",
                "type": "start",
                "payload": {
                    "variables": {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category": "CONFIG",
                            }
                        }
                    },
                    "extensions": {},
                    "operationName": "configuration",
                    "query": "subscription configuration($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on ConfigurationMessageData {\n          colorPalette {\n            colors {\n              hex\n              index\n              __typename\n            }\n            __typename\n          }\n          canvasConfigurations {\n            index\n            dx\n            dy\n            __typename\n          }\n          canvasWidth\n          canvasHeight\n          __typename\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }
        )
    )
    ws.recv()
    ws.send(
        json.dumps(
            {
                "id": "2",
                "type": "start",
                "payload": {
                    "variables": {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category": "CANVAS",
                                "tag": "0",
                            }
                        }
                    },
                    "extensions": {},
                    "operationName": "replace",
                    "query": "subscription replace($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on FullFrameMessageData {\n          __typename\n          name\n          timestamp\n        }\n        ... on DiffFrameMessageData {\n          __typename\n          name\n          currentTimestamp\n          previousTimestamp\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }
        )
    )

    file = ""
    while True:
        temp = json.loads(ws.recv())
        if temp["type"] == "data":
            msg = temp["payload"]["data"]["subscribe"]
            if msg["data"]["__typename"] == "FullFrameMessageData":
                file = msg["data"]["name"]
                break
    boardimg1 = BytesIO(requests.get(file, stream=True).content)

    ws.send(
        json.dumps(
            {
                "id": "3",
                "type": "start",
                "payload": {
                    "variables": {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category": "CANVAS",
                                "tag": "1",
                            }
                        }
                    },
                    "extensions": {},
                    "operationName": "replace",
                    "query": "subscription replace($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on FullFrameMessageData {\n          __typename\n          name\n          timestamp\n        }\n        ... on DiffFrameMessageData {\n          __typename\n          name\n          currentTimestamp\n          previousTimestamp\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }
        )
    )

    file2 = ""
    while True:
        temp = json.loads(ws.recv())
        if temp["type"] == "data":
            msg = temp["payload"]["data"]["subscribe"]
            if msg["data"]["__typename"] == "FullFrameMessageData":
                file2 = msg["data"]["name"]
                break

    ws.close()

    boardimg2 = BytesIO(requests.get(file2, stream=True).content)

    images = [Image.open(x).convert("RGB") for x in [boardimg1, boardimg2]]
    widths, heights = zip(*(i.size for i in images))

    total_width = sum(widths)
    max_height = max(heights)

    new_im = Image.new('RGB', (total_width, max_height))

    x_offset = 0
    for im in images:
        new_im.paste(im, (x_offset,0))
        x_offset += im.size[0]

    boardimg = new_im


    print("Got images:", file, file2)

    return boardimg


def get_unset_pixel(boardimg, x, y):
    pixel_x_start = 0
    pixel_y_start = 0
    pix2 = boardimg.load()
    while True:
        if x >= image_width:
            y += 1
            x = 0

        if y >= image_height:
            new_rgb = (69, 42, 0)
            break
        if verbose:
            print(x + pixel_x_start, y + pixel_y_start)
            print(x, y, "boardimg", image_width, image_height)
        target_rgb = pix[x, y]

        new_rgb = closest_color(target_rgb, rgb_colors_array)
        if pix2[x + pixel_x_start, y + pixel_y_start] != new_rgb:
            if new_rgb != (69, 42, 0):
                break

        x += 1
    return x, y, new_rgb


# method to define the color palette array
def init_rgb_colors_array():
    global rgb_colors_array

    # generate array of available rgb colors we can use
    for color_hex, color_index in color_map.items():
        rgb_array = ImageColor.getcolor(color_hex, "RGB")
        rgb_colors_array.append(rgb_array)
    if verbose:
        print("available colors for palette (rgb): ", rgb_colors_array)


def load_image_url(url):
    global pix
    global image_width
    global image_height
    global image_loaded
    # read and load the image to draw and get its dimensions

    try:
        im_resp = requests.get(url, stream=True, timeout=60)
    except requests.exceptions.ReadTimeout:
        print('Image download timed out')
        print('Trying again in 1 minute. After 10 tries, the script will stop automatically.')
    else:
        if im_resp.status_code != 200:
            print('HTTP', im_resp.status_code)
            print('Image download failed')
            print('Trying again in 1 minute. After 10 tries, the script will stop automatically.')

            return 1
        else:
            im = Image.open(im_resp.raw).convert("RGB")
            pix = im.load()
            print(
                "image size: ", im.size
            )  # Get the width and height of the image for iterating over
            image_width, image_height = im.size
            image_loaded = True
            return 0


# task to draw the input image
def task(credentials_index, image_e):
    # whether image should keep drawing itself
    repeat_forever = True
    last_time_scanned_image = time.time()
    image_is_loaded = image_e.wait()
    banned = False
    while True:
        # try:
        # global variables for script
        last_time_placed_pixel = math.floor(time.time())

        # randomized nr to evade ban
        pixel_place_frequency = 0

        # pixel drawing preferences
        pixel_x_start = 0
        pixel_y_start = 0

        current_r = 0
        current_c = 0

        # string for time until next pixel is drawn
        update_str = ""

        # reference to globally shared variables such as auth token and image
        global access_tokens
        global access_token_expires_at_timestamp

        # boolean to place a pixel the moment the script is first run
        # global first_run
        global first_run_counter

        # refresh auth tokens and / or draw a pixel
        while True:
            # reduce CPU usage
            time.sleep(1)

            # get the current time
            current_timestamp = math.floor(time.time())

            # randomize time a little
            pixel_place_frequency = random.randint(1, 10)

            # log next time until drawing
            time_until_next_draw = (
                last_time_placed_pixel + pixel_place_frequency - current_timestamp
            )
            new_update_str = (
                str(time_until_next_draw) + " seconds until next pixel is drawn"
            )
            if update_str != new_update_str and time_until_next_draw % 30 == 0:
                update_str = new_update_str
                print(
                    "-------Thread #"
                    + str(credentials_index)
                    + "-------\n"
                    + update_str
                )

            if time_until_next_draw > 100000:
                banned = True
                break

            # refresh access token if necessary
            if (
                access_tokens[credentials_index] is None
                or current_timestamp
                >= access_token_expires_at_timestamp[credentials_index]
            ):
                print(
                    "-------Thread #"
                    + str(credentials_index)
                    + "-------\n"
                    + "Refreshing access token..."
                )

                # developer's reddit username and password
                try:
                    username = json.loads(os.getenv("ENV_PLACE_USERNAME"))[
                        credentials_index
                    ]
                    password = json.loads(os.getenv("ENV_PLACE_PASSWORD"))[
                        credentials_index
                    ]
                    # note: use https://www.reddit.com/prefs/apps
                    app_client_id = json.loads(os.getenv("ENV_PLACE_APP_CLIENT_ID"))[
                        credentials_index
                    ]
                    secret_key = json.loads(os.getenv("ENV_PLACE_SECRET_KEY"))[
                        credentials_index
                    ]
                except IndexError:
                    print(
                        "Array length error: are you sure your credentials have an equal amount of items?\n",
                        "Example for 2 accounts:\n",
                        'ENV_PLACE_USERNAME=\'["Username1", "Username2]\'\n',
                        'ENV_PLACE_PASSWORD=\'["Password", "Password"]\'\n',
                        'ENV_PLACE_APP_CLIENT_ID=\'["NBVSIBOPVAINCVIAVBOVV", "VNOPSNSJVQNVNJVSNVDV"]\'\n',
                        'ENV_PLACE_SECRET_KEY=\'["INSVDSINDJV_SVTNNJSNVNJV", "ANIJCINLLPJCSCOJNCA_ASDV"]\'\n',
                        "Note: There can be duplicate entries, but every array must have the same amount of items.",
                    )
                    exit(1)

                data = {
                    "grant_type": "password",
                    "username": username,
                    "password": password,
                }

                r = requests.post(
                    "https://ssl.reddit.com/api/v1/access_token",
                    data=data,
                    auth=HTTPBasicAuth(app_client_id, secret_key),
                    headers={"User-agent": f"{random.randint(1, 100000)}{random.randint(1, 100000)}"},
                )

                if verbose:
                    print("received response: ", r.text)

                response_data = r.json()
                access_tokens[credentials_index] = response_data["access_token"]
                # access_token_type = response_data["token_type"]  # this is just "bearer"
                access_token_expires_in_seconds = response_data[
                    "expires_in"
                ]  # this is usually "3600"
                # access_token_scope = response_data["scope"]  # this is usually "*"

                # ts stores the time in seconds
                access_token_expires_at_timestamp[
                    credentials_index
                ] = current_timestamp + int(access_token_expires_in_seconds)

                print(
                    "received new access token: ",
                    access_tokens[credentials_index],
                )

            # draw pixel onto screen
            if access_tokens[credentials_index] is not None and (
                current_timestamp >= last_time_placed_pixel + pixel_place_frequency
                or first_run_counter <= credentials_index
            ):

                # place pixel immediately
                # first_run = False
                first_run_counter += 1

                # get target color
                # target_rgb = pix[current_r, current_c]

                # get current pixel position from input image and replacement color
                print(
                    "-------Thread #"
                    + str(credentials_index)
                    + "-------"
                )
                current_r, current_c, new_rgb = get_unset_pixel(
                    get_board(access_tokens[credentials_index]),
                    current_r,
                    current_c,
                )
                if new_rgb == (69, 42, 0):
                    print(
                        "--------Thread #"
                        + str(credentials_index)
                        + "--------\n"
                        + "no discrepancies found\n"
                    )
                    break
                # get converted color
                new_rgb_hex = rgb_to_hex(new_rgb)

                pixel_color_index = color_map[new_rgb_hex]

                # draw the pixel onto r/place
                last_time_placed_pixel = set_pixel_and_check_ratelimit(
                    access_tokens[credentials_index],
                    pixel_x_start + current_r,
                    pixel_y_start + current_c,
                    pixel_color_index,
                )

                current_r += 1

                # go back to first column when reached end of a row while drawing
                if current_r >= (image_width-1):
                    current_r = 0
                    current_c += 1

                # exit when all pixels drawn
                if current_c >= (image_height-1):
                    print(
                        "--------Thread #"
                        + str(credentials_index)
                        + "--------\n"
                        + "done drawing image to r/place\n"
                    )
                    break
        # except:
        #     print("__________________")
        #     print("Thread #" + str(credentials_index))
        #     print("Error refreshing tokens or drawing pixel")
        #     print("Trying again in 5 minutes...")
        #     print("__________________")
        #     time.sleep(5 * 60)

        if not repeat_forever:
            break
        else:
            if not banned:
                time_scanned_image = time.time()
                if (last_time_scanned_image - time_scanned_image) < 20:
                    time.sleep(20)
                last_time_scanned_image = time_scanned_image
            else:
                print("\n--------\nAccount with index " + str(credentials_index) + " has likely been banned. Thread shutting down.\n--------\n")
                break


def image_updater(image_e):
    url = 'https://raw.githubusercontent.com/peeter-virk/rplace_img/main/update.php'
    status = "continue"
    global image_version
    tries = 0
    while True:
        if tries >= 10:
            print('Failed to update image after 10 tries. Exiting.')
            os._exit(1)
        try:
            resp = requests.get(url, timeout=5)
        except requests.exceptions.ReadTimeout:
            print('Request timed out')
            print('Trying again in 1 minute. After 10 tries, the script will stop automatically.')
            status = "retry"
        else:
            if resp.status_code != 200:
                print('HTTP', resp.status_code)
                print('Request failed')
                print('Trying again in 1 minute. After 10 tries, the script will stop automatically.')
                status = "retry"
            else:
                data = resp.json()
        if status == "continue":
            if version.parse(data["version"]) > version.parse(image_version):
                image_version = data["version"]
                print('New image version available. Downloading.')
                result = load_image_url("https://raw.githubusercontent.com/peeter-virk/rplace_img/main/" + data["filename"])
                if result:
                    tries += 1
                    time.sleep(60)
                else:
                    tries = 0
                    image_e.set()
                    time.sleep(60)
            else:
                tries = 0
                time.sleep(60)
        else:
            tries += 1
            time.sleep(60)



# get color palette
init_rgb_colors_array()

image_version = "0.0.1"
image_event = threading.Event()

# get number of concurrent threads to start
num_credentials = len(json.loads(os.getenv("ENV_PLACE_USERNAME")))

# define delay between starting new threads
if os.getenv("ENV_THREAD_DELAY") != None:
    delay_between_launches_seconds = int(os.getenv("ENV_THREAD_DELAY"))
else:
    delay_between_launches_seconds = 0

# launch a thread for each account specified in .env
img_thread = threading.Thread(target=image_updater, args=(image_event,))
img_thread.start()
for i in range(num_credentials):
    # run the image drawing task
    access_tokens.append(None)
    access_token_expires_at_timestamp.append(math.floor(time.time()))
    thread1 = threading.Thread(target=task, args=(i,image_event,))
    thread1.start()
    time.sleep(delay_between_launches_seconds)
