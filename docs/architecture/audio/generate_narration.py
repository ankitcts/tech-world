#!/usr/bin/env python3
"""Generate architecture narration MP3s with the ElevenLabs TTS API.

Reads each `<view>.txt` transcript in this directory and produces `<view>.mp3`
next to it, which docs/architecture/index.html plays on demand.

The API key comes ONLY from the ELEVENLABS_API_KEY environment variable —
never hardcode it, and never call ElevenLabs from the browser (that would
expose the key). Run at build/update time:

    ELEVENLABS_API_KEY=... python docs/architecture/audio/generate_narration.py

Optional env: ELEVENLABS_VOICE_ID (defaults to "21m00Tcm4TlvDq8ikWAM" — Rachel).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

API_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"


def main() -> int:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        print("ELEVENLABS_API_KEY is not set — skipping narration generation.\n"
              "The viewer's audio player will activate once MP3s exist here.",
              file=sys.stderr)
        return 0  # not an error: audio is optional until a key is provided

    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", DEFAULT_VOICE)
    here = Path(__file__).resolve().parent
    transcripts = sorted(here.glob("*.txt"))
    if not transcripts:
        print("no *.txt transcripts found — nothing to generate", file=sys.stderr)
        return 1

    for txt in transcripts:
        text = txt.read_text(encoding="utf-8").strip()
        if not text:
            continue
        out = txt.with_suffix(".mp3")
        req = urllib.request.Request(
            API_URL.format(voice_id=voice_id),
            data=json.dumps({
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            }).encode(),
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                out.write_bytes(resp.read())
            print(f"✓ {out.name} generated from {txt.name}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            print(f"✗ {txt.name}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
