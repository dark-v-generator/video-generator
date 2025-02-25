import os
import tempfile
from googleapiclient.discovery import build
from pytubefix import YouTube
from proglog import ProgressBarLogger, TqdmProgressBarLogger
from src.flask_server.progress import FlaskProgressBarLogger
from src.entities.editor.video_clip import VideoClip


def __get_youtube_service():
    return build("youtube", "v3", developerKey=os.environ.get("YOUTUBE_API_KEY"))

def get_video_ids(channel_id, max_results=500):
    youtube = __get_youtube_service()
    search_request = youtube.search().list(
        part="id", channelId=channel_id, maxResults=max_results
    )
    search_response = search_request.execute()
    video_ids = []
    for item in search_response.get("items", []):
        if item["id"]["kind"] == "youtube#video":
            video_ids.append(item["id"]["videoId"])
    return video_ids


def __download_youtube_stream(
    yt: YouTube,
    output_path: str,
    filename: str,
    low_quality=False,
    logger: ProgressBarLogger = TqdmProgressBarLogger(),
):
    streams = yt.streams.filter(only_video=True).order_by("bitrate").desc()
    if low_quality:
        stream = streams.last()
    else:
        stream = streams.first()

    def progress_callback(stream, chunk, bytes_remaining):
        if isinstance(logger, FlaskProgressBarLogger):
            logger.bars_callback("video_download", "index", len(chunk), None)

    if isinstance(logger, FlaskProgressBarLogger):
        logger.bars_callback("video_download", "total", stream.filesize, None)
    yt.register_on_progress_callback(progress_callback)
    stream.download(output_path=output_path, filename=filename)


def download_youtube_video(
    video_id, low_quality=False, logger: ProgressBarLogger = TqdmProgressBarLogger()
) -> VideoClip:
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmpfile:
        filename = os.path.basename(tmpfile.name)
        directory = os.path.dirname(tmpfile.name)

        url = f"https://www.youtube.com/watch?v={video_id}"
        yt = YouTube(url, "WEB_CREATOR", use_oauth=True)

        __download_youtube_stream(yt, directory, filename, low_quality, logger=logger)
        return VideoClip(tmpfile.name)
