import tempfile
from moviepy import ImageClip as MoviepyImageClip
from moviepy.video.fx import CrossFadeIn, CrossFadeOut


class ImageClip:
    clip: MoviepyImageClip

    def __init__(self, file_path: str = None, bytes: bytes = None):
        if bytes:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmpfile:
                tmpfile.write(bytes)
                tmpfile.seek(0)
                self.clip = MoviepyImageClip(tmpfile.name)
        else:
            self.clip = MoviepyImageClip(file_path)

    def apply_fadein(self, duration):
        self.clip = CrossFadeIn(duration=duration).apply(self.clip)

    def apply_fadeout(self, duration):
        self.clip = CrossFadeOut(duration=duration).apply(self.clip)

    def set_duration(self, duration):
        self.clip = self.clip.with_duration(duration)

    def set_start(self, start_time):
        self.clip = self.clip.with_start(start_time)

    def center(self, clip_width, clip_height):
        image_width, image_height = self.clip.size
        pos_x = (clip_width - image_width) // 2
        pos_y = (clip_height - image_height) // 2
        self.clip = self.clip.with_position((pos_x, pos_y))

    def fit_width(self, clip_width, padding=0):
        image_width, image_height = self.clip.size
        image_aspect_ratio = image_width / image_height
        new_width = clip_width - padding
        new_height = int(new_width / image_aspect_ratio)
        self.clip = self.clip.resized(new_size=(new_width, new_height))
