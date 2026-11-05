"""Runtime settings, overridable through environment variables."""

import os
from pathlib import Path

# Amazon Nova Pro via the APAC cross-region profile, invoked from ap-southeast-2.
MODEL_ID = os.environ.get("CHECKIN_MODEL_ID", "apac.amazon.nova-pro-v1:0")
AWS_REGION = os.environ.get("CHECKIN_AWS_REGION", "ap-southeast-2")
MODEL_TIMEOUT_S = int(os.environ.get("CHECKIN_MODEL_TIMEOUT_S", "30"))

# Voice chat: Amazon Nova Sonic speech-to-speech. Nova Sonic isn't offered in ap-southeast-2,
# so it runs from Tokyo, the closest region that has it.
VOICE_MODEL_ID = os.environ.get("CHECKIN_VOICE_MODEL_ID", "amazon.nova-2-5-sonic")
VOICE_REGION = os.environ.get("CHECKIN_VOICE_REGION", "ap-northeast-1")
VOICE_ID = os.environ.get("CHECKIN_VOICE_ID", "tiffany")

# Which country's crisis lines to show (key in app/data/hotlines.json).
HOTLINE_REGION = os.environ.get("CHECKIN_HOTLINE_REGION", "IN")

# Where profiles and memory (Strands session files) are kept. Holds personal data: never commit it.
DATA_DIR = Path(os.environ.get("CHECKIN_DATA_DIR", ".lantern"))

# How many recent messages the check-in and voice agents keep from earlier conversations.
MEMORY_WINDOW = int(os.environ.get("CHECKIN_MEMORY_WINDOW", "48"))
VOICE_MEMORY_WINDOW = int(os.environ.get("CHECKIN_VOICE_MEMORY_WINDOW", "20"))
