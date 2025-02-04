import whisper
from entities.captions import CaptionSegment, Captions

def generate_captions(audio_path: str) -> Captions:
    model = whisper.load_model("base")
    output = model.transcribe(audio_path, word_timestamps=True)

    caption_segments = []
    for segment in output["segments"]:
        for word in segment["words"]:
            caption_segments.append(
                CaptionSegment(
                    start=word["start"],
                    end=word["end"],
                    text=word["word"]
                )
            )
    return Captions(segments=caption_segments)
