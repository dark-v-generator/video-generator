import os
import tempfile
from googleapiclient.discovery import build
from pytubefix import YouTube
from tqdm import tqdm

from entities.editor.video_clip import VideoClip


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
    yt: YouTube, output_path: str, filename: str, low_quality=False
):
    streams = yt.streams.filter(only_video=True).order_by("bitrate").desc()
    if low_quality:
        stream = streams.last()
    else:
        stream = streams.first()

    def progress_callback(stream, chunk, bytes_remaining):
        progress_bar.update(len(chunk))

    with tqdm(
        total=stream.filesize, unit="B", unit_scale=True, desc=yt.video_id
    ) as progress_bar:
        yt.register_on_progress_callback(progress_callback)
        stream.download(output_path=output_path, filename=filename)


def download_youtube_video(video_id, low_quality=False) -> VideoClip:
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmpfile:
        filename = os.path.basename(tmpfile.name)
        directory = os.path.dirname(tmpfile.name)

        url = f"https://www.youtube.com/watch?v={video_id}"
        yt = YouTube(url, "WEB_CREATOR", use_oauth=True)

        # Check if file already exists
        __download_youtube_stream(yt, directory, filename, low_quality)
        return VideoClip(tmpfile.name)
