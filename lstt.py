#!python3

from pathlib import Path
from typing import Dict
import os
import random
import re

from bs4 import BeautifulSoup
from PIL import Image
from rich import print
from rich.progress import track
import telegram
import requests
import typer


def create_telegram_sticker_set(
    sticker_data: Dict[str, Dict],
    telegram_token: str,
    telegram_user_id: int,
    sticker_set_name: str,
    sticker_set_title: str,
) -> Dict[str, Dict]:
    """Creates the Telegram sticker set"""
    bot = telegram.Bot(telegram_token)
    created = False
    for sid in track(sticker_data.keys(), "🔼 Uploading..."):
        path = sticker_data[sid]["resized_path"]
        if path is None:
            continue
        try:
            if created:
                bot.add_sticker_to_set(
                    telegram_user_id,
                    sticker_set_name,
                    random.choice("🔴🟠🟡🟢🔵🟣"),
                    path,
                )
            else:
                bot.create_new_sticker_set(
                    telegram_user_id,
                    sticker_set_name,
                    sticker_set_title,
                    random.choice("🔴🟠🟡🟢🔵🟣"),
                    path,
                )
        except telegram.TelegramError as error:
            if created:
                print(
                    "🔼❌ [red]Couldn't add sticker[/red]",
                    str(path),
                    "[red]to set:[/red]",
                    f"({type(error).__name__})",
                    str(error),
                )
            else:
                print(
                    "🔼❌ [red]Couldn't create sticker set:[/red]",
                    f"({type(error).__name__})",
                    str(error),
                )
                # If creation failed, abort
                print("[red]Aborting... ☹️[/red]")
                break
        created = True
    return sticker_data


def download_stickers(
    sticker_data: Dict[str, Dict],
    download_directory: Path,
) -> Dict[str, Dict]:
    """Downloads the stickers"""
    if not os.path.isdir(download_directory):
        os.mkdir(download_directory)
    for sid in track(sticker_data.keys(), "🔽 Downloading..."):
        url = sticker_data[sid]["url"]
        file_path = download_directory / f"{sid}.png"
        try:
            response = requests.get(url)
            response.raise_for_status()
            with open(file_path, "wb") as file:
                file.write(response.content)
            sticker_data[sid]["raw_path"] = file_path
        except requests.HTTPError as error:
            sticker_data[sid]["raw_path"] = None
            print(
                "🔽❌ [red]Couldn't download sticker[/red]",
                url,
                ":",
                str(error),
            )
    return sticker_data


def get_stickers_urls(line_sticker_url: str) -> Dict[str, Dict]:
    """Retrives all the sticker URLs from the sticker page"""
    response = requests.get(line_sticker_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    tags = soup.find_all(attrs={"class": re.compile(".* FnPreview$")})
    sticker_data = dict()
    pattern = (
        "background-image:url\((https://stickershop.line-scdn.net/stickershop/"
        "v\d+/sticker/(\d+)/android/sticker.png);compress=true\);"
    )
    for tag in tags:
        if match := re.search(pattern, tag["style"]):
            sticker_data[match.group(2)] = {"url": match.group(1)}
    return sticker_data


def main(
    sticker_page_url: str = typer.Argument(
        ...,
        help="URL of the LINE sticket set page.",
    ),
    sticker_set_name: str = typer.Argument(
        ...,
        help="Name (identification string) of the new Telegram sticker set. "
        "Must begin with a letter, can’t contain consecutive underscores "
        "and must end in “_by_<bot username>”. <bot_username> is case "
        "insensitive. 1-64 characters.",
    ),
    sticker_set_title: str = typer.Argument(
        ...,
        help="Title of the new Telegram sticker set, between 1 and 64 "
        "characters.",
    ),
    *,
    download_directory: Path = typer.Option(
        os.path.expanduser("~/Downloads/lstt"),
        help="Directory where the stickers will be downloaded.",
    ),
    telegram_token: str = typer.Option(
        ...,
        help="Telegram bot token.",
    ),
    telegram_user_id: int = typer.Option(
        ...,
        help="Telegram user ID.",
    ),
):
    """Main function (duh)"""
    sticker_data = get_stickers_urls(sticker_page_url)
    # TESTING
    sticker_data = {
        "12676374": sticker_data["12676374"],
        "12676375": sticker_data["12676375"],
    }
    sticker_data = download_stickers(sticker_data, download_directory)
    sticker_data = resize_stickers(sticker_data, download_directory)
    sticker_data = create_telegram_sticker_set(
        sticker_data,
        telegram_token,
        telegram_user_id,
        sticker_set_name,
        sticker_set_title,
    )
    # print(sticker_data)


def resize_stickers(
    sticker_data: Dict[str, Dict],
    download_directory: Path,
) -> Dict[str, Dict]:
    """A Telegram sticker must be a PNG image up to 512 kilobytes in size,
    dimensions must not exceed 512px, and either width or height must be
    exactly 512px. (source
    https://python-telegram-bot.readthedocs.io/en/stable/telegram.bot.html?highlight=create#telegram.Bot.add_sticker_to_set)
    """
    for sid in track(sticker_data.keys(), "📐 Resizing..."):
        raw_path = sticker_data[sid]["raw_path"]
        if raw_path is None:
            sticker_data[sid]["resized_path"] = None
            continue
        resized_path = download_directory / f"{sid}.resized.png"
        raw = Image.open(raw_path)
        coefficient = max(raw.width, raw.height) / 512
        size = (int(raw.width / coefficient), int(raw.height / coefficient))
        resized = raw.resize(size)
        resized.save(resized_path)
        sticker_data[sid]["resized_path"] = resized_path
    return sticker_data


if __name__ == "__main__":
    typer.run(main)
