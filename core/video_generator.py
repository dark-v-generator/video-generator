import os
import random
from editor import audio_clip, video_clip
from google import youtube
from editor import image_clip, audio_clip, video_clip

WIDTH = 720
HEIGHT = 1280

def create_video_compilation(channel_id, min_duration):
    video_ids = youtube.get_video_ids(channel_id, max_results=500)
    random.shuffle(video_ids)
    video = video_clip.VideoClip()
    total_duration = 0
    for video_id in video_ids:
        video_path, duration = youtube.download_youtube_video(video_id)
        new_video = video_clip.VideoClip(video_path)
        new_video.resize(WIDTH, HEIGHT)
        video.concat(new_video)
        total_duration += duration
        if total_duration > min_duration:
            break
    return video

def generate_video(
        audio_path, 
        youtube_channel_id, 
        output_file_path,
        water_mark_path=None,
        background_audio_path=None,
        cover_path=None,
        end_silece_seconds=3,
        padding=50,
        cover_duration=5
    ):
    audio = audio_clip.AudioClip(audio_path)
    audio.add_end_silence(end_silece_seconds)
    if os.path.exists(background_audio_path):
        audio.merge(audio_clip.AudioClip(background_audio_path, volume=0.1))

    background_video = create_video_compilation(youtube_channel_id, audio.clip.duration)
    background_video.ajust_duration(audio.clip.duration)
    background_video.set_audio(audio)

    width, height = background_video.clip.size
    if cover_path:
        cover = image_clip.ImageClip(
            cover_path,
            clip_width=width,
            clip_height=height,
            padding=padding
        )
        cover.center()
        cover.set_duration(cover_duration)
        cover.apply_fadeout(1)
        background_video.merge(cover)
    if water_mark_path:
        water_mark = image_clip.ImageClip(
            water_mark_path,
            clip_width=width,
            clip_height=height,
            padding=padding
        )
        water_mark.center()
        water_mark.set_duration(audio.clip.duration)
        background_video.merge(water_mark)
    background_video.clip.write_videofile(output_file_path)