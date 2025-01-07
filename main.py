from services import config_service
from services import cover_service
from services import history_service
from services import speech_service
from services import video_service

def test_cover():
    config = config_service.get_main_config()
    history = history_service.generate_history(config.history_config)
    cover_service.__generate_svg_cover(
        history.title,
        history.subtitle,
        "output.png",
        config.cover_config
    )

if __name__ == '__main__':
    config = config_service.get_main_config()
    print('Generating history...')
    history = history_service.generate_history(config.history_config)
    history_service.save_history(history, f'{config.output_path}/{history.file_name}.json')
    print('Generating cover...')
    cover = cover_service.generate_cover(history.title, history.subtitle, config.cover_config)
    print('Generating speech...')
    speech = speech_service.synthesize_speech(history.content)
    print('Generating video compilation...')
    background_video = video_service.create_video_compilation(speech.clip.duration)
    
    final_video = video_service.generate_video(
        audio=speech, 
        background_video=background_video,
        cover=cover,
        config=config.video_config
    )
    final_video.clip.write_videofile(f'{config.output_path}/{history.file_name}.mp4')
