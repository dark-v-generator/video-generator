import random
from entities import config
from entities.editor import captions_clip
from proxies import youtube_proxy
from entities.editor import image_clip, audio_clip, video_clip
from proglog import ProgressBarLogger, TqdmProgressBarLogger


def create_video_compilation(
    min_duration: int,
    config: config.VideoConfig = config.VideoConfig(),
    logger: ProgressBarLogger = TqdmProgressBarLogger(),
) -> video_clip.VideoClip:
    video_ids = youtube_proxy.get_video_ids(config.youtube_channel_id, max_results=500)
    random.shuffle(video_ids)
    video = video_clip.VideoClip()
    total_duration = 0
    for video_id in video_ids:
        new_video = youtube_proxy.download_youtube_video(
            video_id, config.low_quality, logger=logger
        )
        video.concat(new_video)
        total_duration += new_video.clip.duration
        if total_duration > min_duration:
            break
    return video


def generate_video(
    audio: audio_clip.AudioClip,
    background_video: video_clip.VideoClip,
    cover: image_clip.ImageClip = None,
    captions: captions_clip.CaptionsClip = None,
    config: config.VideoConfig = config.VideoConfig(),
) -> video_clip.VideoClip:
    audio.add_end_silence(config.end_silece_seconds)
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
        water_mark = image_clip.ImageClip(config.watermark_path)
        water_mark.fit_width(width, config.padding)
        water_mark.center(width, height)
        water_mark.set_duration(audio.clip.duration)
        background_video.merge(water_mark)
    if captions is not None:
        background_video.insert_captions(captions)
    return background_video
