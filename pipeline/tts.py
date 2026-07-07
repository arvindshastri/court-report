import re
from pathlib import Path

import requests
from dotenv import dotenv_values

config = dotenv_values(Path(__file__).parent.parent / ".env")
ELEVENLABS_API_KEY = config.get("ELEVENLABS_API_KEY")

# Liam - "Energetic, Social Media Creator": American, confident, energetic, young
# male. Selected over Daniel (British, formal-broadcaster) for a punchier, more
# enthusiastic sports-analyst read.
ELEVENLABS_VOICE_ID = "TX3LPaxmHKxFdv7VOQHJ"

# Flash v2.5: cheapest per-character tier and lowest latency, vs. Multilingual v2.
ELEVENLABS_MODEL_ID = "eleven_flash_v2_5"

# Tuned for energy: low stability = more pitch/pace variation instead of a flat
# monotone read, high style = exaggerates the voice's inherent character, speed
# above 1.0 for a brisker pace (API range is 0.7-1.2).
ELEVENLABS_VOICE_SETTINGS = {
    "speed": 1.1,
    "stability": 0.2,
    "style": 0.85,
    "use_speaker_boost": True,
}

ELEVENLABS_TTS_URL = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"


def strip_markdown(text: str) -> str:
    """Remove markdown/formatting characters so TTS doesn't read symbols aloud."""
    text = re.sub(r'\*{1,3}', '', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'[_`~]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


class TTSError(Exception):
    pass


def synthesize_speech(text: str) -> bytes:
    """Send cleaned text to ElevenLabs and return raw audio bytes (audio/mpeg)."""
    if not ELEVENLABS_API_KEY:
        raise TTSError("ELEVENLABS_API_KEY is not configured")

    cleaned = strip_markdown(text)
    if not cleaned:
        raise TTSError("No text to synthesize")

    try:
        response = requests.post(
            ELEVENLABS_TTS_URL,
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": cleaned,
                "model_id": ELEVENLABS_MODEL_ID,
                "voice_settings": ELEVENLABS_VOICE_SETTINGS,
            },
            timeout=30,
        )
    except requests.RequestException as e:
        raise TTSError(f"ElevenLabs request failed: {e}") from e

    if response.status_code != 200:
        raise TTSError(f"ElevenLabs API error ({response.status_code}): {response.text[:200]}")

    return response.content
