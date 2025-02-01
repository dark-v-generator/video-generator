import math
import re
from typing import List, Tuple
from moviepy import TextClip, VideoFileClip, CompositeVideoClip
from moviepy.video.fx import CrossFadeIn, CrossFadeOut
from pydantic import BaseModel, Field


class CaptionsConfig(BaseModel):
    font_path: str = Field("assets/kite_one.ttf")
    font_size: int = Field(18)
    color: str = Field("#FFEA00")
    stroke_color: str = Field("#242424")
    stroke_width: int = Field(1)
    fade_duration: float = Field(0.05)
    one_word: bool = Field(True)
    upper_text: bool = Field(False)


class CaptionsClip:
    def __init__(self, srt_file: str, config: CaptionsConfig = CaptionsConfig()):
        self.subtitles = self.__file_to_subtitles(srt_file)
        self.config = config
        self.clips = self.__generate_clips()

    def __generate_clips(self) -> List[TextClip]:
        clips = []
        subtitles = self.subtitles
        if self.config.one_word:
            new_subs = []
            for subtitle in self.subtitles:
                new_subs += CaptionsClip.__split_subtitle(*subtitle)
            subtitles = new_subs
        for subtitle in subtitles:
            times, text = subtitle
            clip = self.__make_word_clip(times, text)
            clips.append(clip)
        return clips

    def __make_word_clip(self, times: List[float], text: str) -> TextClip:
        start_time, end_time = times
        show_text = text.upper() if self.config.upper_text else text
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

        word_clip = CrossFadeIn(duration=self.config.fade_duration).apply(word_clip)
        word_clip = CrossFadeOut(duration=self.config.fade_duration).apply(word_clip)
        word_clip: TextClip = word_clip.with_position(["center", "center"])
        return word_clip

    @staticmethod
    def __split_subtitle(
        times: List[float], text: str
    ) -> List[Tuple[List[float], str]]:
        start_time, end_time = times
        duration = end_time - start_time
        nc = len(text) - text.count(" ")
        c_time = float(duration) / nc
        subs = []
        curr = start_time
        for word in text.split():
            t = [curr, curr + c_time * len(word)]
            curr = curr + c_time * len(word)
            subs.append((t, word))
        return subs

    @staticmethod
    def __convert_to_seconds(time):
        factors = (1, 60, 3600)
        if isinstance(time, str):
            time = [float(part.replace(",", ".")) for part in time.split(":")]
        if not isinstance(time, (tuple, list)):
            return time
        return sum(mult * part for mult, part in zip(factors, reversed(time)))

    @staticmethod
    def __file_to_subtitles(filename, encoding=None):
        times_texts = []
        current_times = None
        current_text = ""
        with open(filename, "r", encoding=encoding) as file:
            for line in file:
                times = re.findall("([0-9]*:[0-9]*:[0-9]*,[0-9]*)", line)
                if times:
                    current_times = [
                        CaptionsClip.__convert_to_seconds(t) for t in times
                    ]
                elif line.strip() == "":
                    times_texts.append((current_times, current_text.strip("\n")))
                    current_times, current_text = None, ""
                elif current_times:
                    current_text += line
        return times_texts


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
