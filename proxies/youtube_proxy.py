import os
from googleapiclient.discovery import build
from pytubefix import YouTube
from tqdm import tqdm

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

def download_youtube_video(video_id, low_quality=False):
    output_path = f"/tmp/{video_id}.mp4"
    url = f"https://www.youtube.com/watch?v={video_id}"
    yt = YouTube(url, "WEB_CREATOR", use_oauth=True)
    streams = yt.streams.filter(only_video=True).order_by('bitrate').desc()
    if low_quality:
        stream = streams.last()
    else:
        stream = streams.first()

    # Define a callback function to update the progress bar
    def progress_callback(stream, chunk, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        progress_bar.update(len(chunk))

    # Create a progress bar
    with tqdm(total=stream.filesize, unit='B', unit_scale=True, desc=video_id) as progress_bar:
        yt.register_on_progress_callback(progress_callback)
        stream.download(output_path="/tmp", filename=f"{video_id}.mp4")

    return output_path, yt.length