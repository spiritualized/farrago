from __future__ import annotations
import argparse
import hashlib
import json
import os
import pathlib
import sys
from collections import OrderedDict
from typing import Optional, Dict

import bs4
import cv2
import numpy as np
import requests
from lastfmcache import LastfmCache, pylast

from errors import CollageError
from functions import normalize_path_chars

MIN_PYTHON = (3, 7)
lastfm_api_key = ""
lastfm_shared_secret = ""


def main() -> None:
    if sys.version_info < MIN_PYTHON:
        sys.exit("Python %s.%s or later is required.\n" % MIN_PYTHON)

    argparser = argparse.ArgumentParser()
    argparser.add_argument("--bandcamp-username", help="specify a bandcamp username")
    argparser.add_argument("--lastfm-username", help="specify a lastfm username")
    argparser.add_argument("--width", help="width of the output image, in pixels", type=int, default=7021)
    argparser.add_argument("--height", help="height of the output image, in pixels", type=int, default=4967)
    argparser.add_argument("--max-covers", help="maximum number of covers to show", type=int, default=1000)

    args = argparser.parse_args()

    if not args.bandcamp_username and not args.lastfm_username:
        print("You must specify at one or both: last.fm username, bandcamp username")

    username = args.lastfm_username
    if not username:
        username = args.bandcamp_username

    releases = OrderedDict()

    grid = Grid.find_max(args.width, args.height, args.max_covers)

    if args.bandcamp_username:
        fetch_bandcamp(args.bandcamp_username, releases, grid.get_squares())

    if args.lastfm_username:
        fetch_lastfm(args.lastfm_username, releases, grid.get_squares())

    if grid.get_squares() > len(releases):
        grid = Grid.find_max(args.width, args.height, len(releases))

    print(grid)

    cells = [GridCell(grid.square_x_pixels, grid.square_y_pixels, x.get_path()) for x in releases.values()]

    grid_2d = []

    for i in range(0, grid.squares_y):
        grid_2d.append([])
        for j in range(0, grid.squares_x):
            grid_2d[i].append(cells[i * grid.squares_x + j])

    # pad out any spare pixels
    for i in range(grid.spare_x):
        for j in range(grid.squares_y):
            grid_2d[j][i].width += 1
    for i in range(grid.spare_y):
        for j in range(grid.squares_x):
            grid_2d[i][j].height += 1

    rows = []
    for row in grid_2d:
        curr_row = []
        for item in row:
            curr_img = load_image_file(item.path)
            curr_row.append(cv2.resize(curr_img, dsize=(item.width, item.height), interpolation=cv2.INTER_CUBIC))
        rows.append(cv2.hconcat(curr_row))

    final = cv2.vconcat(rows)

    filename = "{username} [{width}x{height}] {squares} tiles [{squares_x}x{squares_y}].png".format(
        username=username, width=args.width, height=args.height, squares=grid.get_squares(),
        squares_x=grid.squares_x, squares_y=grid.squares_y)

    path = pathlib.Path(pathlib.Path(__file__).parent.resolve(), 'collages', filename)

    cv2.imwrite(str(path), final)


class Release:
    def __init__(self, source: str, artist: str, title: str) -> None:
        self.source = source
        self.artist = artist
        self.title = title

    def get_filename(self):
        return normalize_path_chars("{artist} - {title}.jpeg".format(artist=self.artist, title=self.title))

    def get_path(self):
        return os.path.join("img", self.source, self.get_filename())

    def __repr__(self):
        return "{artist} - {title}".format(artist=self.artist, title=self.title)

    def __eq__(self, other):
        return self.artist == other.artist and self.title == other.title


class GridCell:
    def __init__(self, width: int, height: int, path: str) -> None:
        self.width = width
        self.height = height
        self.path = path


class Grid:

    def __init__(self, width: int, height: int, short_side_length) -> None:
        short_axis = min(width, height)
        long_axis = max(width, height)

        short_side_squares = short_side_length
        long_side_squares = short_side_squares

        square_side_length = int(short_axis / short_side_squares)

        # pack as many squares as possible along the long axis
        while (long_side_squares + 1) * square_side_length < long_axis:
            long_side_squares += 1

        # if there's over half the side-length of a square
        if (long_axis - (square_side_length * long_side_squares)) / square_side_length:
            long_side_squares += 1

        square_side_short = square_side_length
        square_side_long = int(long_axis / long_side_squares)

        self.squares_x = short_side_squares
        self.squares_y = long_side_squares
        self.square_x_pixels = square_side_short
        self.square_y_pixels = square_side_long

        if height < width:
            temp = self.squares_x
            self.squares_x = self.squares_y
            self.squares_y = temp
            temp = self.square_x_pixels
            self.square_x_pixels = self.square_y_pixels
            self.square_y_pixels = temp

        self.spare_x = width - self.squares_x * self.square_x_pixels
        self.spare_y = height - self.squares_y * self.square_y_pixels

    def __repr__(self):

        num_squares = self.squares_x * self.squares_y

        return "{num_squares} {squares_x}x{squares_y} squares of {square_x_pixels}x{square_y_pixels} " \
               "({spare_x} spare X, {spare_y} spare Y)"\
               .format(squares_x=self.squares_x, squares_y=self.squares_y, square_x_pixels=self.square_x_pixels,
                       square_y_pixels=self.square_y_pixels, spare_x=self.spare_x, spare_y=self.spare_y,
                       num_squares=num_squares)

    def get_squares(self):
        return self.squares_x * self.squares_y

    @staticmethod
    def find_max(width: int, height: int, n: int) -> Grid:

        short_side = 1
        grid = Grid(width, height, short_side)

        while True:
            grid2 = Grid(width, height, short_side + 1)

            if grid2.get_squares() > n:
                return grid

            grid = grid2
            short_side += 1


def load_image_file(path: str) -> str:
    try:
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_ANYCOLOR)[:, :, :3]
    except cv2.error:
        print("Error reading image file {path}".format(path=path), file=sys.stderr)


def fetch_bandcamp(username: str, releases: Dict[str, Release], max_releases: int):
    if len(releases) == max_releases:
        return

    resp = requests.get("https://bandcamp.com/{0}/".format(username))
    if resp.status_code == 404:
        raise CollageError("Bandcamp user '{0}' not found.".format(username))
    elif resp.status_code != 200:
        raise CollageError(
            "HTTP error {0} fetching Bandcamp user '{1}'".format(resp.status_code, username))

    soup = bs4.BeautifulSoup(resp.text, 'html5lib')

    if not soup.find(id="pagedata"):
        raise CollageError("Could not find Bandcamp data")

    item = soup.find(id="collection-items").find(class_="collection-item-container")
    title = str(item.find(class_="collection-item-title").contents[0]).strip()
    artist = str(item.find(class_="collection-item-artist").contents[0])[3:]
    img_src = item.find(class_="collection-item-art")["src"]
    older_than_token = item["data-token"]
    fan_id = int(str(soup.find(class_="follow-unfollow")["id"])[16:])

    curr_release = Release("bandcamp", artist, title)
    fetch_and_add_image(releases, curr_release, img_src)

    get_release_image(curr_release, img_src)

    req = json.dumps({"fan_id": fan_id, "count": 1000000, "older_than_token": older_than_token})
    r = requests.post("https://bandcamp.com/api/fancollection/1/collection_items", data=req)
    if r.status_code != 200:
        raise CollageError("Could not retrieve bandcamp JSON")

    bandcamp_releases = json.loads(r.content)

    for release_bandcamp in bandcamp_releases['items']:
        if len(releases) == max_releases:
            break

        img_src = release_bandcamp['item_art_url'].replace("_9.jpg", "_16.jpg")
        curr_release = Release("bandcamp", release_bandcamp['band_name'], release_bandcamp['album_title'])

        fetch_and_add_image(releases, curr_release, img_src)

    user_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users", username)
    if not os.path.exists(user_path):
        os.makedirs(user_path)

    with open(os.path.join(user_path, "bandcamp.txt"), "w", encoding='utf-8') as data_file:
        data_file.writelines("\n".join([r.__repr__() for r in releases]))


def fetch_lastfm(username: str, releases: Dict[str, Release], max_releases: int):
    if len(releases) == max_releases:
        return

    lastfm = LastfmCache(lastfm_api_key, lastfm_shared_secret)
    lastfm.enable_file_cache(86400*365)

    lastfm_releases = lastfm.get_top_user_releases(username)

    r = None

    for r in lastfm_releases:
        if len(releases) == max_releases:
            break

        pylast_retries = 0

        while True:
            try:
                release_lastfm = lastfm.get_release(r.artist, r.title)
                if release_lastfm.cover_image:
                    fetch_and_add_image(releases, Release("lastfm", r.artist, r.title), release_lastfm.cover_image)

                break

            except (pylast.WSError, pylast.MalformedResponseError):
                print("Failed to fetch '{artist} - {title}', retrying...".format(artist=r.artist, title=r.title),
                      file=sys.stderr)
                pylast_retries += 1

                if pylast_retries == 5:
                    break

                continue

            except LastfmCache.LastfmCacheError:
                print(
                    "Error retrieving user release #{index}: {artist} - {title}".format(index=r.index, artist=r.artist,
                                                                                        title=r.title), file=sys.stderr)
                break

    print("Fewest scrobbles: {scrobbles}".format(scrobbles=r.scrobbles))


def fetch_and_add_image(releases: Dict[str, Release], release: Release, img_src: str) -> None:
    """Fetches an image if it hasn't been fetched from another source,
    then adds it to the input 'releases' list if successful"""

    if release in releases.values():
        return

    img_hash = get_release_image(release, img_src)

    if img_hash and img_hash not in releases:
        releases[img_hash] = release


def get_release_image(release: Release, img_src: str) -> Optional[str]:
    """Fetches a release's cover art, returns a boolean indicating whether the image was downloaded/already present"""

    image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "img", release.source)

    if not os.path.exists(image_path):
        os.makedirs(image_path)

    path = os.path.join(image_path, release.get_filename())
    if os.path.exists(path):
        with open(path, "rb") as img_file:
            return hashlib.sha1(img_file.read()).hexdigest()

    r = requests.get(img_src, stream=True)
    if r.status_code != 200:
        return None

    # verify that opencv can decode the file
    if cv2.imdecode(np.asarray(bytearray(r.content), dtype=np.uint8), cv2.IMREAD_UNCHANGED) is None:
        return None

    with open(path, "wb") as img_file:
        img_file.write(r.content)

    print("Fetched from {source}: '{artist} - {title}'".format(source=release.source,
                                                               artist=release.artist, title=release.title))

    return hashlib.sha1(r.content).hexdigest()


if __name__ == "__main__":
    main()
