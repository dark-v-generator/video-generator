import os
from aws import polly
from core import cover_generator, history, video_generator
import argparse

# https://www.youtube.com/@OddlySatisfying
CHANNEL_ID = 'UCCZIevhN62jJ2gb-u__M95g'
CHANNEL_NAME = 'OddlySatisfying'
WATER_MARK_PATH = 'assets/watermark.png'

def generate_history(history_prompt_file):
    if not os.path.exists(history_prompt_file):
        raise ValueError(f'History prompt file not found: {history_prompt_file}')
    with open(history_prompt_file, 'r') as file:
        return history.History(file.read())

def generate_video(history, output_folder, background_audio):
    description_file = f'{output_folder}/{history.normalized_title()}.txt'
    output_file = f'{output_folder}/{history.normalized_title()}.mp4'
    
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        with open(description_file, 'w') as file:
            file.write(history.social_media_description(CHANNEL_NAME))
        cover_path = cover_generator.generate_cover(history.title, history.subtitle)
        voice = 'Vitoria' if history.gender == 'feminino' else 'Ricardo'
        audio_path = polly.synthesize_speech(history.history_description, voice_id=voice)
        video_generator.generate_video(
            audio_path,
            CHANNEL_ID,
            output_file,
            WATER_MARK_PATH,
            background_audio_path=background_audio,
            cover_path=cover_path
        )
    except Exception as e:
        print(f'Error generating video, removing files')
        if os.path.exists(output_file):
            os.remove(output_file)
        if os.path.exists(description_file):
            os.remove(description_file)
        raise e
        
def main():
    parser = argparse.ArgumentParser(description='Generate a video story')
    parser.add_argument('--output_folder', type=str, default='output', help='Path to the output folder')
    parser.add_argument('--count', type=int, default=1, help='Number of stories to generate')
    parser.add_argument('--history_prompt_file', type=str, default='./history_prompt.txt', help='Path to the history prompt file')
    parser.add_argument('--background_audio', type=str, default='', help='Path to the background audio file')
    args = parser.parse_args()
    for _ in range(args.count):
        history = generate_history(args.history_prompt_file)
        generate_video(history, args.output_folder, args.background_audio)

if __name__ == '__main__':
    main()