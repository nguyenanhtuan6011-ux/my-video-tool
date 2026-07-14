import os
import tempfile
import streamlit as st
from PIL import Image
from groq import Groq
from pathlib import Path
from moviepy.editor import (
    ImageClip,
    VideoFileClip,
    AudioFileClip,
    CompositeVideoClip,
    TextClip,
    concatenate_videoclips,
    afx,
)

# Sửa lỗi ANTIALIAS cho phiên bản Pillow mới
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.Resampling.LANCZOS

st.set_page_config(page_title="Video Creator", layout="wide")

GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)



# --- Session state ---
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

# --- Sidebar & AI ---
st.sidebar.title("Video Settings")
st.sidebar.subheader("AI Assistant (Groq)")
user_prompt = st.sidebar.text_input("Gợi ý ý tưởng video:")
if st.sidebar.button("Generate title with AI"):
    if client:
        with st.sidebar.spinner("AI is thinking..."):
            completion = client.chat.completions.create(
                messages=[{"role": "user", "content": f"Viết tiêu đề ngắn cho: {user_prompt}"}],
                model="llama3-8b-8192",
            )
            st.sidebar.info(completion.choices[0].message.content)
    else:
        st.sidebar.error("API Key not found in secrets!")

st.sidebar.markdown("---")
resolution_label = st.sidebar.selectbox("Output resolution", list(RESOLUTIONS.keys()))
target_w, target_h = RESOLUTIONS[resolution_label]
fps = st.sidebar.slider("Frame rate (fps)", 10, 60, 30)

title_text = st.sidebar.text_input("Title text", value="")
title_duration = st.sidebar.slider("Title duration (s)", 1, 10, 3)

audio_file = st.sidebar.file_uploader("Upload audio", type=["mp3", "wav", "m4a", "aac"])
audio_volume = st.sidebar.slider("Music volume", 0.0, 1.0, 0.5)

# --- Main UI ---
st.title("🎬 Video Creator")
uploaded_files = st.file_uploader("Upload images or video clips", accept_multiple_files=True)

if uploaded_files:
    existing_names = {item["name"] for item in st.session_state.media_items}
    for uploaded_file in uploaded_files:
        if uploaded_file.name not in existing_names:
            path = save_uploaded_file(uploaded_file)
            ext = Path(uploaded_file.name).suffix.lower()
            media_type = "video" if ext in (".mp4", ".mov", ".avi", ".webm") else "image"
            st.session_state.media_items.append({"name": uploaded_file.name, "type": media_type, "path": path, "duration": 3.0})

st.markdown("### Timeline")
if not st.session_state.media_items:
    st.info("Upload at least one image or video clip.")
else:
    for idx, item in enumerate(st.session_state.media_items):
        cols = st.columns([1, 3, 2, 1, 1, 1])
        with cols[0]: st.image(item["path"], width=90) if item["type"] == "image" else st.video(item["path"])
        with cols[1]: st.write(f"**{item['name']}**")
        with cols[2]: 
            if item["type"] == "image": item["duration"] = st.number_input("Duration", 0.5, 60.0, float(item["duration"]), key=f"d_{idx}")
        with cols[3]:
            if st.button("↑", key=f"up_{idx}") and idx > 0:
                st.session_state.media_items[idx-1], st.session_state.media_items[idx] = st.session_state.media_items[idx], st.session_state.media_items[idx-1]
                st.rerun()
        with cols[4]:
            if st.button("↓", key=f"down_{idx}") and idx < len(st.session_state.media_items)-1:
                st.session_state.media_items[idx+1], st.session_state.media_items[idx] = st.session_state.media_items[idx], st.session_state.media_items[idx+1]
                st.rerun()
        with cols[5]:
            if st.button("🗑", key=f"rem_{idx}"):
                st.session_state.media_items.pop(idx)
                st.rerun()

if st.button("🎞️ Generate video"):
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
                st.download_button("⬇️ Download video", data=f.read(), file_name="my_video.mp4", mime="video/mp4")
            st.success("Video generated!")
        except Exception as e:
            st.error(f"Error: {e}")
