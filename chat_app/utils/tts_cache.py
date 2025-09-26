import hashlib
import os
from gtts import gTTS
from utils.redis_client import redis_client

def make_cache_key(text, lang):
    digest = hashlib.sha256(text.encode()).hexdigest()
    return f"tts:{lang}:{digest}"

def generate_path(lang, digest):
    filename = f"{lang}_{digest}.mp3"
    return os.path.join("media", filename)

def get_tts_cached(text, lang):
    key = make_cache_key(text, lang)
    cached_path = redis_client.get(key)

    if cached_path:
        print("⚡ Redis cache hit")
        return cached_path

    print("🔄 Redis cache miss, generating")
    digest = key.split(":")[-1]
    mp3_path = generate_path(lang, digest)

    tts = gTTS(text, lang=lang)
    tts.save(mp3_path)

    redis_client.set(key, mp3_path, ex=86400)  # Cache for 1 day
    return mp3_path