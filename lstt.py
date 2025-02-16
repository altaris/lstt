#!python3

import asyncio
import os
import random
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests
import telegram
import typer
from bs4 import BeautifulSoup
from PIL import Image
from rich import print  # pylint: disable=redefined-builtin
from rich.progress import track


async def create_telegram_sticker_set(
    sticker_data: Dict[str, Dict],
    telegram_token: str,
    telegram_user_id: int,
    sticker_set_name: str,
    sticker_set_title: str,
) -> Tuple[Dict[str, Dict], Optional[str]]:
    """
    Creates the Telegram sticker set

    Returns:
        A tuple containing the sticker data dict, and the real name of the
        sticker set, or ``None`` if it wasn't created.
    """
    async with telegram.Bot(telegram_token) as bot:
        sticker_set_name += "_by_" + bot.username
        created = False
        for sid in track(sticker_data.keys(), "🔼 Uploading..."):
            path = sticker_data[sid]["resized_path"]
            if path is None:
                continue
            sticker = telegram.InputSticker(
                sticker=open(path, "rb"),
                emoji_list=[random.choice("🔴🟠🟡🟢🔵🟣")],
            )
            try:
                if created:
                    await bot.add_sticker_to_set(
                        user_id=telegram_user_id,
                        name=sticker_set_name,
                        sticker=sticker,
                    )
                else:
                    await bot.create_new_sticker_set(
                        user_id=telegram_user_id,
                        name=sticker_set_name,
                        title=sticker_set_title,
                        stickers=[sticker],
                        sticker_format="static",
                    )
            except telegram.error.TelegramError as error:
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
                    print("🔼❌ [red]Aborting...[/red]")
                    break
            created = True
    return sticker_data, sticker_set_name if created else None


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
            if not file_path.is_file():
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
    pattern = (
        r"background-image:url\((https://stickershop.line-scdn.net/"
        r"stickershop/v\d+/sticker/(\d+)/android/sticker.png)"
        r"(;compress=true)?\);"
    )
    tags = soup.find_all(
        attrs={"class": re.compile(r".*Image$"), "style": re.compile(pattern)}
    )
    sticker_data = dict()
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
        "Must begin with a letter and can't contain consecutive underscores. "
        "Must be between 1 and 64 characters. Note that the final name of the "
        "set will be suffixed with '_by_<botusername>'.",
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
    sticker_data = download_stickers(sticker_data, download_directory)
    sticker_data = resize_stickers(sticker_data, download_directory)
    sticker_data, real_sticker_set_name = asyncio.run(
        create_telegram_sticker_set(
            sticker_data,
            telegram_token,
            telegram_user_id,
            sticker_set_name,
            sticker_set_title,
        )
    )
    if real_sticker_set_name is not None:
        print("✨ All done! ✨")
        print(
            "Your sticker set if available at",
            f"https://t.me/addstickers/" + real_sticker_set_name,
        )


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
        if not resized_path.is_file():
            raw = Image.open(raw_path)
            coefficient = max(raw.width, raw.height) / 512
            size = (
                int(raw.width / coefficient),
                int(raw.height / coefficient),
            )
            resized = raw.resize(size, resample=Image.Resampling.LANCZOS)
            resized.save(resized_path)
        sticker_data[sid]["resized_path"] = resized_path
    return sticker_data


if __name__ == "__main__":
    typer.run(main)
