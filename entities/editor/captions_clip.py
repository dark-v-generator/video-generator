import math
import re
from typing import List, Tuple
from moviepy import TextClip, VideoFileClip, CompositeVideoClip
from moviepy.video.fx import CrossFadeIn, CrossFadeOut
from pydantic import BaseModel, Field
from entities.captions import CaptionSegment, Captions


class CaptionsConfig(BaseModel):
    font_path: str = Field("")
    font_size: int = Field(100)
    color: str = Field("#000000")
    stroke_color: str = Field("#000000")
    stroke_width: int = Field(0)
    fade_duration: float = Field(0)
    upper_text: bool = Field(False)


class CaptionsClip:
    def __init__(self, captions: Captions, config: CaptionsConfig = CaptionsConfig()):
        self.captions = captions
        self.config = config
        self.clips = self.__generate_clips()

    def __generate_clips(self) -> List[TextClip]:
        clips = []
        for caption_segment in self.captions.segments:
            clip = self.__make_word_clip(caption_segment)
            clips.append(clip)
        return clips

    def __make_word_clip(self, caption_segment: CaptionSegment) -> TextClip:
        start_time, end_time = [caption_segment.start, caption_segment.end]
        text = caption_segment.text
        show_text = text.upper() if self.config.upper_text else text
        show_text = show_text.replace(",", "").replace(".", "").strip()
        word_clip = TextClip(
            text=show_text,
            font=self.config.font_path,
            font_size=self.config.font_size,
            color=self.config.color,
            stroke_color=self.config.stroke_color,
            stroke_width=self.config.stroke_width,
            text_align="center",
        ).with_start(start_time)
        word_clip = word_clip.with_duration(end_time - start_time)

        if self.config.fade_duration > 0:
            word_clip = CrossFadeIn(duration=self.config.fade_duration).apply(word_clip)
            word_clip = CrossFadeOut(duration=self.config.fade_duration).apply(
                word_clip
            )
        word_clip: TextClip = word_clip.with_position(["center", "center"])
        return word_clip


if __name__ == "__main__":
    subs = CaptionsClip("subtitles.srt", CaptionsConfig(font_path="assets/bangers.ttf"))
    video = VideoFileClip("input.mp4")
    result = CompositeVideoClip([video, *subs.clips])

    result.write_videofile(
        "output.mp4",
        fps=video.fps,
        temp_audiofile="temp-audio.m4a",
        remove_temp=True,
        codec="libx264",
        audio_codec="aac",
    )
