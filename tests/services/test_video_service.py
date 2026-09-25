from src.entities.editor.video_clip import VideoClip


def test_adjust_duration_trims_from_beginning():
    class FakeClip:
        duration = 100

        def __init__(self):
            self.subclip_args = None

        def subclipped(self, start, end):
            self.subclip_args = (start, end)
            return self

    wrapped = VideoClip.__new__(VideoClip)
    wrapped.clip = FakeClip()

    wrapped.ajust_duration(30)

    assert wrapped.clip.subclip_args == (0, 30)
