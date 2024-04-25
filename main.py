from urllib.parse import urlparse
import datetime
from pyrogram import Client, filters
import config
import yt_dlp
import re
import os
import time
from pyrogram import enums

bot = Client("my_bot", api_id=config.api_id, api_hash=config.api_hash, bot_token=config.token)
last_edited = {}


def youtube_url_validation(url):
    youtube_regex = (
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')

    youtube_regex_match = re.match(youtube_regex, url)
    if youtube_regex_match:
        return youtube_regex_match

    return youtube_regex_match


@bot.on_message(filters.command(['start', 'help']))
def test(client, message):
    client.send_message(message.chat.id, "*Send me a video link* and I'll download it for you, works with **YouTube**, *Twitter*, *TikTok*, *Reddit* and more.\n\n_Powered by_ [yt-dlp](https://github.com/yt-dlp/yt-dlp/)", parse_mode=enums.ParseMode.MARKDOWN, disable_web_page_preview=True)


def download_video(client, message, url, audio=False, format_id="mp4"):
    # Your existing code...
    
        def progress(d, message, msg):  # Add message and msg as arguments
            if d['status'] == 'downloading':
                try:
                    update = False

                    if last_edited.get(f"{message.chat.id}-{msg.message_id}"):
                        if (datetime.datetime.now() - last_edited[f"{message.chat.id}-{msg.message_id}"]).total_seconds() >= 5:
                            update = True
                    else:
                        update = True

                    if update:
                        perc = round(d['downloaded_bytes'] *
                                     100 / d['total_bytes'])
                        client.edit_message_text(
                            chat_id=message.chat.id, message_id=msg.message_id, text=f"Downloading {d['info_dict']['title']}\n\n{perc}%")
                        last_edited[f"{message.chat.id}-{msg.message_id}"] = datetime.datetime.now()
                except Exception as e:
                    print(e)
                    
        msg = client.send_message(message.chat.id, 'Downloading...')
        video_title = round(time.time() * 1000)
        with yt_dlp.YoutubeDL({'format': format_id, 'outtmpl': f'outputs/{video_title}.%(ext)s', 'progress_hooks': [lambda d: progress(d, message, msg)], 'postprocessors': [{  # Extract audio using ffmpeg
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }] if audio else [], 'max_filesize': config.max_filesize}) as ydl:
            info = ydl.extract_info(url, download=True)
            try:
                client.edit_message_text(
                    chat_id=message.chat.id, message_id=message.message_id, text='Sending file to Telegram...')
                try:
                    if audio:
                        client.send_audio(message.chat.id, f'outputs/{video_title}.mp3', reply_to_message_id=message.message_id)

                    else:
                        client.send_video(message.chat.id, f'outputs/{video_title}.mp4', reply_to_message_id=message.message_id)
                    client.delete_messages(message.chat.id, message.message_id)
                except Exception as e:
                    client.edit_message_text(
                        chat_id=message.chat.id, message_id=message.message_id, text=f"Couldn't send file, make sure it's supported by Telegram and it doesn't exceed *{round(config.max_filesize / 1000000)}MB*", parse_mode=enums.ParseMode.MARKDOWN)
                    for file in info['requested_downloads']:
                        os.remove(file['filepath'])
                else:
                    for file in info['requested_downloads']:
                        os.remove(file['filepath'])
            except Exception as e:
                if isinstance(e, yt_dlp.utils.DownloadError):
                    client.edit_message_text(
                        'Invalid URL', message.chat.id, message.message_id)
                else:
                    client.edit_message_text(
                        f"There was an error downloading your video, make sure it doesn't exceed *{round(config.max_filesize / 1000000)}MB*", message.chat.id, message.message_id, parse_mode=enums.ParseMode.MARKDOWN)
                for file in os.listdir('outputs'):
                    if file.startswith(str(video_title)):
                        os.remove(f'outputs/{file}')
    else: 
        client.send_message(message.chat.id, 'Invalid URL')


def log(client, message, text: str, media: str):
    if config.logs:
        if message.chat.type == 'private':
            chat_info = "Private chat"
        else:
            chat_info = f"Group: *{message.chat.title}* (`{message.chat.id}`)"

        client.send_message(
            config.logs, f"Download request ({media}) from @{message.from_user.username} ({message.from_user.id})\n\n{chat_info}\n\n{text}")


def get_text(message):
    if len(message.text.split(' ')) < 2:
        if message.reply_to_message and message.reply_to_message.text:
            return message.reply_to_message.text

        else:
            return None
    else:
        return message.text.split(' ')[1]


@bot.on_message(filters.command(['download']))
def download_command(client, message):
    text = get_text(message)
    if not text:
        client.send_message(
            message.chat.id, 'Invalid usage, use `/download url`', parse_mode=enums.ParseMode.MARKDOWN)
        return

    log(client, message, text, 'video')
    download_video(client, message, text)


@bot.on_message(filters.command(['audio']))
def download_audio_command(client, message):
    text = get_text(message)
    if not text:
        client.send_message(
            message.chat.id, 'Invalid usage, use `/audio url`', parse_mode=enums.ParseMode.MARKDOWN)
        return

    log(client, message, text, 'audio')
    download_video(client, message, text, True)


@bot.on_message(filters.command(['custom']))
def custom(client, message):
    text = get_text(message)
    if not text:
        client.send_message(
            message.chat.id, 'Invalid usage, use `/custom url`', parse_mode=enums.ParseMode.MARKDOWN)
        return

    msg = client.send_message(message.chat.id, 'Getting formats...')

    with yt_dlp.YoutubeDL() as ydl:
        info = ydl.extract_info(text, download=False)

    data = {f"{x['resolution']}.{x['ext']}": {
        'callback_data': f"{x['format_id']}"} for x in info['formats'] if x['video_ext'] != 'none'}

    markup = [[{"text": k, "callback_data": v["callback_data"]}] for k, v in data.items()]

    client.delete_messages(message.chat.id, msg.message_id)
    client.send_message(message.chat.id, "Choose a format", reply_markup=markup)

@bot.on_callback_query()
def callback(client, call):
    if call.from_user.id == call.message.reply_to_message.from_user.id:
        url = get_text(call.message.reply_to_message)
        client.delete_messages(call.message.chat.id, call.message.message_id)
        download_video(client, call.message.reply_to_message, url, format_id=f"{call.data}+bestaudio")
    else:
        client.answer_callback_query(call.id, "You didn't send the request")


@bot.on_message(filters.text | filters.pinned_message | filters.photo | filters.audio | filters.video | filters.location | filters.contact | filters.voice | filters.document)
def handle_private_messages(client, message):
    text = message.text if message.text else message.caption if message.caption else None

    if message.chat.type == 'private':
        log(client, message, text, 'video')
        download_video(client, message, text)


bot.run()
