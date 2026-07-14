"""
Video Creator — a Streamlit app for assembling videos from images, video clips,
and audio.

Features:
- Upload multiple images and/or video clips and arrange their order
- Set a per-image display duration
- Add background music (optional), trimmed/looped to match total length
- Add an optional text overlay/title card
- Choose output resolution and export as MP4

Run with:
    pip install -r requirements.txt
    streamlit run app.py --server.port 5000

Requires ffmpeg to be installed on the system (moviepy depends on it).
"""

import os
import tempfile
import shutil
from pathlib import Path

import streamlit as st
from moviepy.editor import (
    ImageClip,
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    TextClip,
    concatenate_videoclips,
    afx,
)

st.set_page_config(page_title="Video Creator", layout="wide")

# ---------------------------------------------------------------------------
# Session state setup
# ---------------------------------------------------------------------------
if "media_items" not in st.session_state:
    # Each item: {"name": str, "type": "image"|"video", "path": str, "duration": float}
    st.session_state.media_items = []

if "workdir" not in st.session_state:
    st.session_state.workdir = tempfile.mkdtemp(prefix="video_creator_")

