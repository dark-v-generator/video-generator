from services import config_service
from services import history_service
from services import speech_service
from services import video_service

if __name__ == '__main__':
    config = config_service.get_main_config()
    history = history_service.generate_history(config.history_prompt)
    
    speech = speech_service.synthesize_speech(history.content)
    background_video = video_service.create_video_compilation(speech.clip.duration)
    final_video = video_service.generate_video(speech, background_video, config.video_config)

    final_video.clip.write_videofile(config.output_path)
