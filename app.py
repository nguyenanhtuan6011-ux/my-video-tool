import os
import tempfile
import shutil
from pathlib import Path
from PIL import Image
import streamlit as st
from groq import Groq

# Sửa lỗi ANTIALIAS
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

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
    st.session_state.media_items = []

if "workdir" not in st.session_state:
    st.session_state.workdir = tempfile.mkdtemp(prefix="video_creator_")

WORKDIR = Path(st.session_state.workdir)
RESOLUTIONS = {
    "1080p (1920x1080)": (1920, 1080),
    "720p (1280x720)": (1280, 720),
    "Square (1080x1080)": (1080, 1080),
    "Vertical (1080x1920)": (1080, 1920),
}

def save_uploaded_file(uploaded_file) -> str:
    dest = WORKDIR / uploaded_file.name
    with open(dest, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return str(dest)

def fit_clip_to_resolution(clip, target_w, target_h):
    clip_ratio = clip.w / clip.h
    target_ratio = target_w / target_h

    if clip_ratio > target_ratio:
        resized = clip.resize(height=target_h)
        x_center = resized.w / 2
        resized = resized.crop(x_center=x_center, width=target_w, y_center=resized.h / 2, height=target_h)
    else:
        resized = clip.resize(width=target_w)
        y_center = resized.h / 2
        resized = resized.crop(x_center=resized.w / 2, width=target_w, y_center=y_center, height=target_h)
    return resized

# ---------------------------------------------------------------------------
# Sidebar & Main UI
# ---------------------------------------------------------------------------
st.sidebar.title("Video Settings")
resolution_label = st.sidebar.selectbox("Output resolution", list(RESOLUTIONS.keys()))
target_w, target_h = RESOLUTIONS[resolution_label]
fps = st.sidebar.slider("Frame rate (fps)", min_value=10, max_value=60, value=30)

st.sidebar.markdown("---")
st.sidebar.subheader("Title card (optional)")
title_text = st.sidebar.text_input("Title text", value="")
title_duration = st.sidebar.slider("Title duration (seconds)", min_value=1, max_value=10, value=3)

st.sidebar.markdown("---")
st.sidebar.subheader("Background music (optional)")
audio_file = st.sidebar.file_uploader("Upload an audio track", type=["mp3", "wav", "m4a", "aac"])
audio_volume = st.sidebar.slider("Music volume", min_value=0.0, max_value=1.0, value=0.5)

st.title("🎬 Video Creator")
uploaded_files = st.file_uploader("Upload images or video clips", type=["png", "jpg", "jpeg", "mp4", "mov", "avi", "webm"], accept_multiple_files=True)

if uploaded_files:
    existing_names = {item["name"] for item in st.session_state.media_items}
    for uploaded_file in uploaded_files:
        if uploaded_file.name not in existing_names:
            path = save_uploaded_file(uploaded_file)
            ext = Path(uploaded_file.name).suffix.lower()
            media_type = "video" if ext in (".mp4", ".mov", ".avi", ".webm") else "image"
            st.session_state.media_items.append({"name": uploaded_file.name, "type": media_type, "path": path, "duration": 3.0 if media_type == "image" else None})

st.markdown("### Timeline")
if not st.session_state.media_items:
    st.info("Upload at least one image or video clip to build your timeline.")
else:
    for idx, item in enumerate(st.session_state.media_items):
        cols = st.columns([1, 3, 2, 1, 1, 1])
        with cols[0]:
            if item["type"] == "image": st.image(item["path"], width=90)
            else: st.video(item["path"])
        with cols[1]: st.write(f"**{item['name']}**")
        with cols[2]:
            if item["type"] == "image":
                item["duration"] = st.number_input("Duration (s)", min_value=0.5, max_value=60.0, value=float(item["duration"]), step=0.5, key=f"dur_{idx}")
        with cols[3]:
            # Đã sửa key ở đây
            if st.button("↑", key=f"up_{idx}") and idx > 0:
                st.session_state.media_items[idx-1], st.session_state.media_items[idx] = st.session_state.media_items[idx], st.session_state.media_items[idx-1]
                st.rerun()
        with cols[4]:
            # Đã sửa key ở đây
            if st.button("↓", key=f"down_{idx}") and idx < len(st.session_state.media_items) - 1:
                st.session_state.media_items[idx+1], st.session_state.media_items[idx] = st.session_state.media_items[idx], st.session_state.media_items[idx+1]
                st.rerun()
        with cols[5]:
            if st.button("🗑", key=f"rem_{idx}"):
                st.session_state.media_items.pop(idx)
                st.rerun()

    if st.button("Clear all"):
        st.session_state.media_items = []
        st.rerun()

st.markdown("### Export")
if st.button("🎞️ Generate video", type="primary", disabled=not st.session_state.media_items):
    with st.spinner("Building your video..."):
        try:
            clips = []
            if title_text.strip():
                clips.append(TextClip(title_text, fontsize=70, color="white", size=(target_w, target_h), bg_color="black", method="caption").set_duration(title_duration))
            for item in st.session_state.media_items:
                clip = ImageClip(item["path"]).set_duration(item["duration"]) if item["type"] == "image" else VideoFileClip(item["path"])
                clips.append(fit_clip_to_resolution(clip, target_w, target_h))
            final = concatenate_videoclips(clips, method="compose").set_fps(fps)
            if audio_file:
                audio_clip = AudioFileClip(save_uploaded_file(audio_file)).fx(afx.volumex, audio_volume)
                final = final.set_audio(audio_clip.fx(afx.audio_loop, duration=final.duration) if audio_clip.duration < final.duration else audio_clip.subclip(0, final.duration))
            output_path = WORKDIR / "my_video.mp4"
            final.write_videofile(str(output_path), fps=fps, codec="libx264", audio_codec="aac", logger=None)
            with open(output_path, "rb") as f:
                video_bytes = f.read()
            st.success("Video generated!")
            st.download_button("⬇️ Download video", data=video_bytes, file_name="my_video.mp4", mime="video/mp4")
        except Exception as exc:
            st.error(f"Something went wrong: {exc}")
