import requests
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import TMDB_API_KEY

movie_cache = {}

def search_tmdb(query):
    url = f"https://api.themoviedb.org/3/search/movie"
    params = {"api_key": TMDB_API_KEY, "query": query}
    res = requests.get(url, params=params).json()
    return res.get("results", [])[:5]

def get_tmdb_details(movie_id):
    url = f"https://api.themoviedb.org/3/movie/{movie_id}"
    params = {"api_key": TMDB_API_KEY}
    return requests.get(url, params=params).json()

async def handle_request_command(client, message: Message):
    query = message.text.split(maxsplit=1)
    if len(query) < 2:
        await message.reply("❌ Please type the movie name after `/request`.")
        return

    keyword = query[1]
    results = search_tmdb(keyword)

    if not results:
        await message.reply("❌ No movies found.")
        return

    movie_cache[message.from_user.id] = results

    buttons = [
        [InlineKeyboardButton(f"{movie['title']} ({movie['release_date'][:4]})", callback_data=f"movie_{i}")]
        for i, movie in enumerate(results)
    ]

    await message.reply(
        "**🔍 Select the movie you're looking for:**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def handle_movie_selection(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    movie_index = int(callback_query.data.split("_")[1])
    movies = movie_cache.get(user_id)

    if not movies or movie_index >= len(movies):
        await callback_query.answer("Invalid selection.")
        return

    movie = movies[movie_index]
    details = get_tmdb_details(movie["id"])

    poster = f"https://image.tmdb.org/t/p/w500{movie['poster_path']}" if movie.get("poster_path") else None
    caption = f"**🎬 {details['title']}**\n\n" \
              f"📅 Release: {details.get('release_date', 'N/A')}\n" \
              f"⭐ Rating: {details.get('vote_average', 'N/A')}/10\n\n" \
              f"{details.get('overview', '')}"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=f"confirm_yes_{movie_index}"),
            InlineKeyboardButton("❌ No", callback_data="confirm_no")
        ]
    ])

    if poster:
        await callback_query.message.reply_photo(poster, caption=caption, reply_markup=keyboard)
    else:
        await callback_query.message.reply(caption, reply_markup=keyboard)

    await callback_query.answer()

async def handle_confirmation(client, callback_query: CallbackQuery):
    if callback_query.data.startswith("confirm_yes"):
        await callback_query.message.reply("✅ Your request was received! We will process it soon.")
    elif callback_query.data == "confirm_no":
        user_id = callback_query.from_user.id
        results = movie_cache.get(user_id, [])

        if not results:
            await callback_query.answer("No previous search to go back to.")
            return

        buttons = [
            [InlineKeyboardButton(f"{movie['title']} ({movie['release_date'][:4]})", callback_data=f"movie_{i}")]
            for i, movie in enumerate(results)
        ]

        await callback_query.message.reply(
            "**🔁 Please choose another movie:**",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    await callback_query.answer()
