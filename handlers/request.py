import requests
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

TMDB_API_KEY = "bb5f40c5be4b24660cbdc20c2409835e"  # Replace with your actual TMDB key
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_MOVIE_DETAILS_URL = "https://api.themoviedb.org/3/movie/{}"

movie_cache = {}  # Used to store last search results for each user


async def handle_request_command(client, message: Message):
    if len(message.command) < 2:
        await message.reply("❗ Please use like this:\n`/request Interstellar`", quote=True)
        return

    query = " ".join(message.command[1:])
    await search_and_respond(client, message, query)


async def search_and_respond(client, message, query):
    params = {
        "api_key": TMDB_API_KEY,
        "query": query
    }
    r = requests.get(TMDB_SEARCH_URL, params=params)
    results = r.json().get("results", [])[:5]

    if not results:
        await message.reply("❌ No results found. Try another name.")
        return

    user_id = message.from_user.id
    movie_cache[user_id] = results

    buttons = [
        [InlineKeyboardButton(f"{i+1}. {movie['title']} ({movie.get('release_date', 'N/A')[:4]})",
                              callback_data=f"select_movie_{i}")]
        for i, movie in enumerate(results)
    ]

    await message.reply("🔍 **Select the correct movie:**", reply_markup=InlineKeyboardMarkup(buttons))


async def handle_movie_selection(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    movie_index = int(callback_query.data.split("_")[-1])

    movie_list = movie_cache.get(user_id)
    if not movie_list or movie_index >= len(movie_list):
        await callback_query.answer("❌ Movie not found in cache.", show_alert=True)
        return

    movie = movie_list[movie_index]
    movie_id = movie["id"]

    # Get full movie details
    r = requests.get(TMDB_MOVIE_DETAILS_URL.format(movie_id), params={"api_key": TMDB_API_KEY})
    data = r.json()
    poster_url = f"https://image.tmdb.org/t/p/w500{data['poster_path']}" if data.get("poster_path") else None

    caption = f"""🎬 **{data['title']}**
📅 Year: {data.get('release_date', 'N/A')[:4]}
⭐ Rating: {data.get('vote_average', 'N/A')}
📝 Overview:
{data.get('overview', 'No overview available.')}
"""

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"confirm_yes_{movie_index}"),
            InlineKeyboardButton("🔁 Try Again", callback_data=f"confirm_retry_{movie_index}")
        ]
    ])

    if poster_url:
        await callback_query.message.reply_photo(poster_url, caption=caption, reply_markup=buttons)
    else:
        await callback_query.message.reply(caption, reply_markup=buttons)

    await callback_query.answer()


async def handle_confirmation(client, callback_query: CallbackQuery):
    action, index = callback_query.data.split("_")[1:]
    user_id = callback_query.from_user.id
    movie_list = movie_cache.get(user_id)

    if not movie_list or int(index) >= len(movie_list):
        await callback_query.answer("❌ Invalid selection.", show_alert=True)
        return

    if action == "yes":
    await callback_query.message.reply("🔍 Searching in our movie channel...")
    await callback_query.message.reply("Please wait...", reply_markup=InlineKeyboardMarkup(
        [[InlineKeyboardButton("Searching...", callback_data=f"deliver_movie_{index}")]]
    ))
    else:
        # Retry flow — show selection buttons again
        buttons = [
            [InlineKeyboardButton(f"{i+1}. {movie['title']} ({movie.get('release_date', 'N/A')[:4]})",
                                  callback_data=f"select_movie_{i}")]
            for i, movie in enumerate(movie_list)
        ]
        await callback_query.message.reply("🔍 **Select the correct movie:**", reply_markup=InlineKeyboardMarkup(buttons))

    await callback_query.answer()
