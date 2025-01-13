from moviepy import editor


class ImageClip:
    clip: editor.ImageClip

    def __init__(self, file_path, clip_width=0, clip_height=0, padding=0):
        self.clip = editor.ImageClip(file_path)

    def apply_fadein(self, duration):
        self.clip = self.clip.crossfadein(duration)

    def apply_fadeout(self, duration):
        self.clip = self.clip.crossfadeout(duration)

    def set_duration(self, duration):
        self.clip = self.clip.set_duration(duration)

    def set_start(self, start_time):
        self.clip = self.clip.set_start(start_time)

    def center(self, clip_width, clip_height):
        image_width, image_height = self.clip.size
        pos_x = (clip_width - image_width) // 2
        pos_y = (clip_height - image_height) // 2
        self.clip = self.clip.set_position((pos_x, pos_y))

    def fit_width(self, clip_width, padding=0):
        image_width, image_height = self.clip.size
        image_aspect_ratio = image_width / image_height
        new_width = clip_width - padding
        new_height = int(new_width / image_aspect_ratio)
        self.clip = self.clip.resize(newsize=(new_width, new_height))
