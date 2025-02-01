import re
from typing import List
from moviepy import TextClip, VideoFileClip, CompositeVideoClip, ColorClip
from moviepy.video.fx import CrossFadeIn, CrossFadeOut
from pydantic import BaseModel, Field


class CaptionsConfig(BaseModel):
    font: str = Field("Arial")
    font_size: int = Field(18)
    color: str = Field("#FFEA00")
    stroke_color: str = Field("#242424")
    stroke_width: int = Field(1)
    fade_duration: float = Field(0.05)


class CaptionsClip:
    def _init_(self, srt_file: str, config: CaptionsConfig = CaptionsConfig()):
        self.subtitles = self.__file_to_subtitles(srt_file)
        self.config = config
        self.clips = self.__generate_clips()

    def __generate_clips(self) -> List[TextClip]:
        clips = []
        for subtitle in self.subtitles:
            times, text = subtitle
            clip = self.__make_word_clip(times, text)
            clips.append(clip)
        return clips

    def __make_word_clip(self, times: List[int], text: str) -> TextClip:
        start_time, end_time = times
        word_clip = TextClip(
            text=text.upper(),
            font=self.config.font,
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
                times = re.findall("([0-9]:[0-9]:[0-9],[0-9])", line)
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
    subs = CaptionsClip("subtitles.srt", CaptionsConfig(font="assets/bangers.ttf"))
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
