# -*- coding: utf-8 -*-
import addict

WELCOME = "Welcome to Noiseblend! If you want to hear some instructions, ask, how do I use this."
PLAYING_RANDOM = "Playing something you might like."
PLAYING_RADIO = "Playing Spotify radio."
PLAYING_BLEND = "Playing your {} blend."
WHAT_DO_YOU_WANT = "What blend do you want to play?"
NOTIFY_LINK_ACCOUNT = "Please link your Noiseblend account in the Amazon Alexa app."
NOTIFY_RELINK_ACCOUNT = "There was an authentication issue. Please unlink and relink your Noiseblend account in the Amazon Alexa app."
NO_DEVICES = "No Spotify devices found for playback."
ERROR = "Uh Oh. Looks like something went wrong."
BLEND_FAILURE = "Something's wrong with this blend. Please try again in a few minutes."
GOODBYE = "Thanks for using Noiseblend!"
UNHANDLED = "Noiseblend doesn't support that. Please ask something else"
HELP = """
You can play any music blend by saying things like: play my morning blend, or, play some workout music.
You can also Ask Noiseblend to just play something, and let Noiseblend find the music you'll like.
If the music is not really what you'd like to hear, adjust your music by saying things like, add more acousticness, or, I need some groovy music.
You can also dislike artists and never hear from them again by saying, I don't like this artist.
For more information, read the skill description in the Alexa app.
"""
AFTER_HELP_QUESTION = "So, what would you like to play?"
MISSING_DEVICE = "The device {} is not available."
WHAT_DEVICE = "What device should I play on?"
CHOOSE_DEVICE = "Choose one of: {}"
WHAT_ARTIST = "What artist?"
CHOOSE_ARTIST = "Choose one of: {}"
DISLIKED_ARTIST = (
    "I added {} to your dislikes. A new playlist will begin playing shortly."
)
NOT_IMPLEMENTED_YET = "This feature is not implemented yet."
SAVING_TRACK = "Saving currently playing track."
NOTHING_PLAYING = "There's nothing playing at the moment."
TUNEABLE_LIST = """
You can change attributes like Acousticness, Danceability, Energy, Instrumentalness,
<phoneme alphabet='ipa' ph='laɪvness'>liveness</phoneme>, Loudness, Popularity,
Speechiness, Tempo, Happiness and Duration."""
RESET_TUNEABLE = "I've reset your tuning."
RESET_TUNEABLE_ANNOUNCE = "{tuneable} has been reset to its default value. A new playlist will begin playing shortly."
SET_TUNEABLE_ANNOUNCE = (
    "{tuneable} is at {value} now. A new playlist will begin playing shortly."
)
UNKNOWN_SLOT = "I don't know that {slot}."
NOISEBLEND_IMG = "https://static.noiseblend.com/img"
EMPTY_TUNING = "You haven't tuned anything yet."
CHANGE_TUNING = "What would you like to change?"

FADE_LIMIT = 60
FADE_LIMIT_EXCEEDED = f"Fading has a limit of {FADE_LIMIT} minutes."

TUNEABLE_DEFAULTS = addict.Dict(
    {
        "acousticness": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.2},
        "danceability": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.2},
        "energy": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.2},
        "instrumentalness": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.2},
        "liveness": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.2},
        "loudness": {"default": -30.0, "min": -60.0, "max": 0.0, "step": 10.0},
        "popularity": {"default": 50, "min": 0, "max": 100, "step": 20},
        "speechiness": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.2},
        "tempo": {"default": 120, "min": 0, "max": 320, "step": 60},
        "valence": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.2},
        "duration_ms": {"default": 3.0, "min": 0.0, "max": 10.0, "step": 2.0},
    }
)
TUNEABLE_NAMES = {
    "acousticness": "Acousticness",
    "danceability": "Danceability",
    "energy": "Energy",
    "instrumentalness": "Instrumentalness",
    "liveness": "Liveness",
    "loudness": "Loudness",
    "popularity": "Popularity",
    "speechiness": "Speechiness",
    "tempo": "Tempo",
    "valence": "Happiness",
    "duration_ms": "Duration",
}
