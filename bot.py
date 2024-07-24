from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import requests
import yt_dlp
import os

TELEGRAM_TOKEN = '7287823531:AAH6EA5cs8aXD3PDd26MfKs--lf6b6LEt4g'
YOUTUBE_API_KEY = 'AIzaSyCt0zmvwXohQ0aj6cnG0OrWyVTulF74dtI'
PORT = int(os.getenv('PORT', '8443'))
DOWNLOAD_PATH = 'downloads/'  # Directory to save MP3 files

# Ensure the download path exists
if not os.path.exists(DOWNLOAD_PATH):
    os.makedirs(DOWNLOAD_PATH)

# Dictionary to store video_id and title
video_info = {}

# Global variable to store pagination state
pagination_data = {}


def search_youtube(song_title):
    search_url = f'https://www.googleapis.com/youtube/v3/search'
    params = {
        'part': 'snippet',
        'q': song_title,
        'key': YOUTUBE_API_KEY,
        'type': 'video',
        'maxResults': 50
    }
    response = requests.get(search_url, params=params)
    data = response.json()

    if 'error' in data:
        error_message = data['error']['message']
        if 'quota' in error_message:
            print(f"Quota exceeded: {error_message}")
            return []  # Handle the quota error gracefully
        else:
            print(f"API Error: {error_message}")
            return []

    if 'items' in data and len(data['items']) > 0:
        results = [
            {
                'title': item['snippet']['title'],
                'video_id': item['id']['videoId']
            }
            for item in data['items']
        ]
        global video_info
        video_info = {result['video_id']: result['title'] for result in results}
        return results
    return []


def download_mp3(video_id):
    title = video_info.get(video_id, 'Unknown Title')
    # Clean the title to ensure it's a valid filename
    sanitized_title = "".join([c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in title])
    output_file = os.path.join(DOWNLOAD_PATH, f'{sanitized_title}.mp3')

    video_url = f'https://www.youtube.com/watch?v={video_id}'

    ydl_opts = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': output_file,
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])

    return output_file


async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Send me a song title, and I will get the MP3 file for you!')


async def handle_message(update: Update, context: CallbackContext) -> None:
    song_title = update.message.text
    results = search_youtube(song_title)

    if results:
        # Initialize pagination data
        global pagination_data
        pagination_data[update.message.chat_id] = {
            'results': results,
            'current_page': 0
        }
        await send_results(update, context, 0)
    else:
        await update.message.reply_text('Song not found.')


async def send_results(update: Update, context: CallbackContext, page=0) -> None:
    if update.message:
        chat_id = update.message.chat_id
    elif update.callback_query:
        chat_id = update.callback_query.message.chat_id
    else:
        return  # Handle unexpected cases

    data = pagination_data.get(chat_id, {})
    results = data.get('results', [])
    total_results = len(results)
    results_per_page = 10
    start = page * results_per_page
    end = start + results_per_page
    paginated_results = results[start:end]

    keyboard = [[InlineKeyboardButton(result['title'], callback_data=result['video_id'])] for result in
                paginated_results]

    # Create pagination buttons
    pagination_buttons = []
    if page > 0:
        pagination_buttons.append(InlineKeyboardButton('Previous', callback_data=f'prev_{page}'))
    if end < total_results:
        pagination_buttons.append(InlineKeyboardButton('Next', callback_data=f'next_{page}'))

    reply_markup = InlineKeyboardMarkup(keyboard + [pagination_buttons])
    if update.message:
        await update.message.reply_text('Choose a song to download:', reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.edit_message_reply_markup(reply_markup=reply_markup)


async def button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    callback_data = query.data

    if callback_data.startswith('prev_') or callback_data.startswith('next_'):
        page = int(callback_data.split('_')[1])
        if 'prev' in callback_data:
            page -= 1
        else:
            page += 1
        await send_results(update, context, page)
    else:
        video_id = callback_data
        mp3_file = download_mp3(video_id)

        await query.message.reply_document(document=open(mp3_file, 'rb'))
        os.remove(mp3_file)  # Clean up after sending


def main() -> None:
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_click))

    application.run_polling()


if __name__ == '__main__':
    main()
