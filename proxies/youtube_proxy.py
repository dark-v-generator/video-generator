import os
from googleapiclient.discovery import build
from pytubefix import YouTube

def __get_youtube_service():
    return build('youtube', 'v3', developerKey=os.environ.get('YOUTUBE_API_KEY'))

def get_video_ids(channel_id, max_results=500):
    youtube = __get_youtube_service()
    search_request = youtube.search().list(
        part='id',
        channelId=channel_id,
        maxResults=max_results
    )
    search_response = search_request.execute()
    video_ids = []
    for item in search_response.get('items', []):
        if item['id']['kind'] == 'youtube#video':
            video_ids.append(item['id']['videoId'])
    return video_ids


def download_youtube_video(video_id, output_path):
    output_path = f'/tmp/{video_id}.mp4'
    url = f'https://www.youtube.com/watch?v={video_id}'
    yt = YouTube(url, 'WEB_CREATOR', use_oauth=True)
    if not os.path.exists(output_path):
        stream = yt.streams.get_highest_resolution()
        stream.download(output_path='.yt_cache/', filename=f'{video_id}.mp4')
    return output_path, yt.length