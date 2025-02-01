from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from pathlib import Path
import azure.cognitiveservices.speech as speechsdk  # type: ignore

DEFAULT_MAX_LINE_LENGTH_SBCS = 37
DEFAULT_MAX_LINE_LENGTH_MBCS = 30


class BinaryFileReaderCallback(speechsdk.audio.PullAudioInputStreamCallback):
    def __init__(self, filename: str):
        super().__init__()
        self._file_h = open(filename, "rb")

    def read(self, buffer: memoryview) -> int:
        try:
            size = buffer.nbytes
            frames = self._file_h.read(size)
            buffer[: len(frames)] = frames
            return len(frames)
        except Exception as ex:
            print("Exception in `read`: {}".format(ex))
            raise

    def close(self) -> None:
        print("closing file")
        try:
            self._file_h.close()
        except Exception as ex:
            print("Exception in `close`: {}".format(ex))
            raise


class Read_Only_Dict(Mapping):
    def __init__(self, data):
        self._data = data

    def __getitem__(self, key):
        return self._data[key]

    def __len__(self):
        return len(self._data)

    def __iter__(self):
        return iter(self._data)


def add_time_and_timedelta(t1: time, t2: timedelta) -> time:
    return (datetime.combine(date.min, t1) + t2).time()


def subtract_times(t1: time, t2: time) -> timedelta:
    return datetime.combine(date.min, t1) - datetime.combine(date.min, t2)


# We cannot simply create time with ticks.
def time_from_ticks(ticks) -> time:
    microseconds_1 = ticks / 10
    microseconds_2 = microseconds_1 % 1000000
    seconds_1 = microseconds_1 / 1000000
    seconds_2 = seconds_1 % 60
    minutes_1 = seconds_1 / 60
    minutes_2 = minutes_1 % 60
    hours = minutes_1 / 60
    return time(int(hours), int(minutes_2), int(seconds_2), int(microseconds_2))
