import random
from entities import config
from proxies import youtube_proxy
from entities.editor import image_clip, audio_clip, video_clip
from entities.history import History
from entities.config import MainConfig
from os import path

from services import cover_service, speech_service


def __create_video_compilation(
    min_duration: int, config: config.VideoConfig = config.VideoConfig()
) -> video_clip.VideoClip:
    video_ids = youtube_proxy.get_video_ids(config.youtube_channel_id, max_results=500)
    random.shuffle(video_ids)
    video = video_clip.VideoClip()
    total_duration = 0
    for video_id in video_ids:
        video_path, duration = youtube_proxy.download_youtube_video(
            video_id, config.low_quality
        )
        new_video = video_clip.VideoClip(video_path)
        video.concat(new_video)
        total_duration += duration
        if total_duration > min_duration:
            break
    return video


def __generate_video(
    audio: audio_clip.AudioClip,
    background_video: video_clip.VideoClip,
    cover: image_clip.ImageClip = None,
    config: config.VideoConfig = config.VideoConfig(),
) -> video_clip.VideoClip:
    audio.add_end_silence(config.end_silece_seconds)
    if config.background_audio_path is not None:
        audio.merge(audio_clip.AudioClip(config.background_audio_path, volume=0.1))

    if config.low_quality:
        aspect_ratio = config.width / config.height
        background_video.resize(int(400 * aspect_ratio), 400)
    else:
        background_video.resize(config.width, config.height)
    background_video.ajust_duration(audio.clip.duration)
    background_video.set_audio(audio)

    width, height = background_video.clip.size
    if cover is not None:
        cover.fit_width(width, config.padding)
        cover.center(width, height)
        cover.set_duration(config.cover_duration)
        cover.apply_fadeout(1)
        background_video.merge(cover)
    if config.watermark_path is not None:
        water_mark = image_clip.ImageClip(
            config.watermark_path,
            clip_width=width,
            clip_height=height,
            padding=config.padding,
        )
        water_mark.fit_width(width, config.padding)
        water_mark.center(width, height)
        water_mark.set_duration(audio.clip.duration)
        background_video.merge(water_mark)
    return background_video


def generate_history_video(history: History, config: MainConfig) -> None:
    print("Generating cover...")
    cover = cover_service.generate_cover(
        history,
        config.cover_config,
    )
    print("Generating speech...")
    speech = speech_service.synthesize_speech(
        history.title + "\n\n" + history.content,
    )
    print("Generating video compilation...")
    background_video = __create_video_compilation(
        speech.clip.duration,
        config.video_config,
    )

    final_video = __generate_video(
        audio=speech,
        background_video=background_video,
        cover=cover,
        config=config.video_config,
    )
    file_name = path.join(config.output_path, "{history.file_name}.mp4")
    if config.video_config.low_quality:
        final_video.clip.write_videofile(
            file_name,
            threads=16,
            preset="ultrafast",
            fps=15,
        )
    else:
        final_video.clip.write_videofile(
            file_name,
            threads=16,
        )
