from datetime import time, timedelta
from enum import Enum
from itertools import pairwise
from os import linesep, remove
import os
from os.path import exists
from time import sleep
from typing import List, Optional
import wave
import azure.cognitiveservices.speech as speechsdk
from pydantic import BaseModel, Field
import services.caption_service.caption_helper as caption_helper
import services.caption_service.helper as helper
from pathlib import Path

USAGE = """Usage: python captioning.py [...]

  HELP
    --help                           Show this help and stop.

  CONNECTION
    --key KEY                        Your Azure Speech service resource key.
                                     Overrides the SPEECH_KEY environment variable. You must set the environment variable (recommended) or use the `--key` option.
    --region REGION                  Your Azure Speech service region.
                                     Overrides the SPEECH_REGION environment variable. You must set the environment variable (recommended) or use the `--region` option.
                                     Examples: westus, eastus

  LANGUAGE
    --language LANG1                 Specify language. This is used when breaking captions into lines.
                                     Default value is en-US.
                                     Examples: en-US, ja-JP

  INPUT
    --input FILE                     Input audio from file (default input is the microphone.)
    --format FORMAT                  Use compressed audio format.
                                     If this is not present, uncompressed format (wav) is assumed.
                                     Valid only with --file.
                                     Valid values: alaw, any, flac, mp3, mulaw, ogg_opus

  MODE
    --offline                        Output offline results.
                                     Overrides --realTime.
    --realTime                       Output real-time results.
                                     Default output mode is offline.

  ACCURACY
    --phrases ""PHRASE1;PHRASE2""    Example: ""Constoso;Jessie;Rehaan""

  OUTPUT
    --output FILE                    Output captions to FILE.
    --srt                            Output captions in SubRip Text format (default format is WebVTT.)
    --maxLineLength LENGTH           Set the maximum number of characters per line for a caption to LENGTH.
                                     Minimum is 20. Default is 37 (30 for Chinese).
    --lines LINES                    Set the number of lines for a caption to LINES.
                                     Minimum is 1. Default is 2.
    --delay MILLISECONDS             How many MILLISECONDS to delay the appearance of each caption.
                                     Minimum is 0. Default is 1000.
    --remainTime MILLISECONDS        How many MILLISECONDS a caption should remain on screen if it is not replaced by another.
                                     Minimum is 0. Default is 1000.
    --quiet                          Suppress console output, except errors.
    --profanity OPTION               Valid values: raw, remove, mask
                                     Default is mask.
    --threshold NUMBER               Set stable partial result threshold.
                                     Default is 3.
"""


class CaptioningMode(Enum):
    OFFLINE = "offline"
    REALTIME = "realtime"


class CaptioningConfig(BaseModel):
    subscription_key: str = Field(os.environ.get("AZURE_TTS_SUBSCRIPTION_KEY"))
    region: str = Field(os.environ.get("AZURE_TTS_SERVICE_REGION"))
    language: str = Field("pt-BR")
    input_file: str = Field()
    format: str = Field("")
    captioning_mode: CaptioningMode = Field(CaptioningMode.OFFLINE)
    phrases: List[str] = Field([])
    output_file: str = Field(None)
    use_srt_format: bool = Field(True)
    max_line_length: int = Field(37)
    lines: int = Field(2)
    delay: int = Field(1000)
    remain_time: int = Field(1000, ge=0)
    quiet: bool = Field(False)
    profanity: str = Field("")
    threshold: int = Field(3)

    def get_compressed_audio_format(self) -> speechsdk.AudioStreamContainerFormat:
        if not self.format:
            return speechsdk.AudioStreamContainerFormat.ANY
        else:
            value = self.format.lower()
            if "alaw" == value:
                return speechsdk.AudioStreamContainerFormat.ALAW
            elif "flac" == value:
                return speechsdk.AudioStreamContainerFormat.FLAC
            elif "mp3" == value:
                return speechsdk.AudioStreamContainerFormat.MP3
            elif "mulaw" == value:
                return speechsdk.AudioStreamContainerFormat.MULAW
            elif "ogg_opus" == value:
                return speechsdk.AudioStreamContainerFormat.OGG_OPUS
            else:
                return speechsdk.AudioStreamContainerFormat.ANY

    def get_profanity_option(self) -> speechsdk.ProfanityOption:
        if self.profanity is None:
            return speechsdk.ProfanityOption.Masked
        else:
            value = self.profanity.lower()
            if "raw" == value:
                return speechsdk.ProfanityOption.Raw
            elif "remove" == value:
                return speechsdk.ProfanityOption.Removed
            else:
                return speechsdk.ProfanityOption.Masked

    def get_remain_timedelta(self):
        return timedelta(milliseconds=self.remain_time)


class Captioning(object):
    def __init__(self, config: CaptioningConfig):
        self._config = config
        self._srt_sequence_number = 1
        self._previous_caption: Optional[caption_helper.Caption] = None
        self._previous_end_time: Optional[time] = None
        self._previous_result_is_recognized = False
        self._recognized_lines: List[str] = []
        self._offline_results: List[speechsdk.SpeechRecognitionResult] = []

    def get_timestamp(self, start: time, end: time) -> str:
        time_format = ""
        if self._config.use_srt_format:
            # SRT format requires ',' as decimal separator rather than '.'.
            time_format = "%H:%M:%S,%f"
        else:
            time_format = "%H:%M:%S.%f"
        # Truncate microseconds to milliseconds.
        return "{} --> {}".format(
            start.strftime(time_format)[:-3], end.strftime(time_format)[:-3]
        )

    def string_from_caption(self, caption: caption_helper.Caption) -> str:
        retval = ""
        if self._config.use_srt_format:
            retval += str(caption.sequence) + linesep
        retval += self.get_timestamp(caption.begin, caption.end) + linesep
        retval += caption.text + linesep + linesep
        return retval

    def __write_to_file(self, text: str):
        if self._config.output_file is None:
            self.__write_to_console(text, end="", flush=True)
        else:
            file_path = Path(self._config.output_file)
            with open(file_path, mode="a", newline="", encoding="utf-8") as f:
                f.write(text)

    def __write_to_console(self, text: str):
        if not self._config.quiet:
            print(text, end="", flush=True)

    def adjust_real_time_caption_text(
        self, text: str, is_recognized_result: bool
    ) -> str:
        # Split the caption text into multiple lines based on max_line_length and lines.
        temp_caption_helper = caption_helper.CaptionHelper(
            self._config.language, self._config.max_line_length, self._config.lines, []
        )
        lines = temp_caption_helper.lines_from_text(text)

        # Recognizing results can change with each new result, so we do not save previous Recognizing results.
        # Recognized results are final, so we save them in a member value.
        recognizing_lines: List[str] = []
        if is_recognized_result:
            self._recognized_lines = self._recognized_lines + lines
        else:
            recognizing_lines = lines

        caption_lines = self._recognized_lines + recognizing_lines
        return "\n".join(caption_lines[-self._config.lines :])

    def caption_from_real_time_result(
        self, result: speechsdk.SpeechRecognitionResult, is_recognized_result: bool
    ) -> Optional[str]:
        retval: Optional[str] = None

        start_time = helper.time_from_ticks(result.offset)
        end_time = helper.time_from_ticks(result.offset + result.duration)

        # If the end timestamp for the previous result is later
        # than the end timestamp for this result, drop the result.
        # This sometimes happens when we receive a lot of Recognizing results close together.
        if self._previous_end_time is not None and self._previous_end_time > end_time:
            pass
        else:
            # Record the end timestamp for this result.
            self._previous_end_time = end_time

            # Convert the SpeechRecognitionResult to a caption.
            # We are not ready to set the text for this caption.
            # First we need to determine whether to clear _recognizedLines.
            caption = caption_helper.Caption(
                self._config.language,
                self._srt_sequence_number,
                helper.add_time_and_timedelta(start_time, self._config.delay),
                helper.add_time_and_timedelta(end_time, self._config.delay),
                "",
            )
            # Increment the sequence number.
            self._srt_sequence_number += 1

            # If we have a previous caption...
            if self._previous_caption is not None:
                # If the previous result was type Recognized...
                if self._previous_result_is_recognized:
                    # Set the end timestamp for the previous caption to the earliest of:
                    # - The end timestamp for the previous caption plus the remain time.
                    # - The start timestamp for the current caption.
                    previous_end = helper.add_time_and_timedelta(
                        self._previous_caption.end, self._config.get_remain_timedelta()
                    )
                    self._previous_caption.end = (
                        previous_end if previous_end < caption.begin else caption.begin
                    )
                    # If the gap between the original end timestamp for the previous caption
                    # and the start timestamp for the current caption is larger than remainTime,
                    # clear the cached recognized lines.
                    # Note this needs to be done before we call AdjustRealTimeCaptionText
                    # for the current caption, because it uses _recognizedLines.
                    if previous_end < caption.begin:
                        self._recognized_lines.clear()
                # If the previous result was type Recognizing, simply set the start timestamp
                # for the current caption to the end timestamp for the previous caption.
                # Note this presumes there will not be a large gap between Recognizing results,
                # because such a gap would cause the previous Recognizing result to be succeeded
                # by a Recognized result.
                else:
                    caption.begin = self._previous_caption.end

                retval = self.string_from_caption(self._previous_caption)

            # Break the caption text into lines if needed.
            caption.text = self.adjust_real_time_caption_text(
                result.text, is_recognized_result
            )
            # Save the current caption as the previous caption.
            self._previous_caption = caption
            # Save the result type as the previous result type.
            self._previous_result_is_recognized = is_recognized_result

        return retval

    def captions_from_offline_results(self) -> List[caption_helper.Caption]:
        captions = caption_helper.get_captions(
            self._config.language,
            self._config.max_line_length,
            self._config.lines,
            list(self._offline_results),
        )
        # Save the last caption.
        last_caption = captions[-1]
        last_caption.end = helper.add_time_and_timedelta(
            last_caption.end, self._config.get_remain_timedelta()
        )
        # In offline mode, all captions come from RecognitionResults of type Recognized.
        # Set the end timestamp for each caption to the earliest of:
        # - The end timestamp for this caption plus the remain time.
        # - The start timestamp for the next caption.
        captions_2: List[caption_helper.Caption] = []
        for caption_1, caption_2 in pairwise(captions):
            end = helper.add_time_and_timedelta(
                caption_1.end, self._config.get_remain_timedelta()
            )
            caption_1.end = end if end < caption_2.begin else caption_2.begin
            captions_2.append(caption_1)
        # Re-add the last caption.
        captions_2.append(last_caption)
        return captions_2

    def finish(self) -> None:
        if CaptioningMode.OFFLINE == self._config.captioning_mode:
            for caption in self.captions_from_offline_results():
                self.__write_to_file(text=self.string_from_caption(caption))
        elif CaptioningMode.REALTIME == self._config.captioning_mode:
            # Show the last "previous" caption, which is actually the last caption.
            if self._previous_caption is not None:
                self._previous_caption.end = helper.add_time_and_timedelta(
                    self._previous_caption.end, self._config.get_remain_timedelta()
                )
                self.__write_to_file(
                    text=self.string_from_caption(self._previous_caption)
                )

    def initialize(self):
        if self._config.output_file is not None and exists(self._config.output_file):
            remove(self._config.output_file)
        if not self._config.use_srt_format:
            self.__write_to_file(text="WEBVTT{}{}".format(linesep, linesep))
        return

    def audio_config_from_user_config(self) -> helper.Read_Only_Dict:
        if self._config.input_file is None:
            return helper.Read_Only_Dict(
                {
                    "audio_config": speechsdk.AudioConfig(use_default_microphone=True),
                    "audio_stream_format": None,
                    "pull_input_audio_stream_callback": None,
                    "pull_input_audio_stream": None,
                }
            )
        else:
            audio_stream_format = None
            if self._config.format == "wav":
                reader = wave.open(self._config.input_file, mode=None)
                audio_stream_format = speechsdk.audio.AudioStreamFormat(
                    samples_per_second=reader.getframerate(),
                    bits_per_sample=reader.getsampwidth() * 8,
                    channels=reader.getnchannels(),
                )
                reader.close()
            else:
                audio_stream_format = speechsdk.audio.AudioStreamFormat(
                    compressed_stream_format=self._config.get_compressed_audio_format()
                )
            callback = helper.BinaryFileReaderCallback(filename=self._config.input_file)
            stream = speechsdk.audio.PullAudioInputStream(
                pull_stream_callback=callback, stream_format=audio_stream_format
            )
            # We return the BinaryFileReaderCallback, AudioStreamFormat, and PullAudioInputStream
            # because we need to keep them in scope until they are actually used.
            return helper.Read_Only_Dict(
                {
                    "audio_config": speechsdk.audio.AudioConfig(stream=stream),
                    "audio_stream_format": audio_stream_format,
                    "pull_input_audio_stream_callback": callback,
                    "pull_input_audio_stream": stream,
                }
            )

    def speech_config_from_user_config(self) -> speechsdk.SpeechConfig:
        speech_config = None
        speech_config = speechsdk.SpeechConfig(
            subscription=self._config.subscription_key, region=self._config.region
        )

        speech_config.set_profanity(self._config.get_profanity_option())

        if self._config.threshold is not None:
            speech_config.set_property(
                property_id=speechsdk.PropertyId.SpeechServiceResponse_StablePartialResultThreshold,
                value=str(self._config.threshold),
            )

        speech_config.set_property(
            property_id=speechsdk.PropertyId.SpeechServiceResponse_PostProcessingOption,
            value="TrueText",
        )
        speech_config.speech_recognition_language = self._config.language

        return speech_config

    def __get_speech_recognizer_data(self) -> speechsdk.SpeechRecognizer:
        audio_config_data = self.audio_config_from_user_config()
        speech_config = self.speech_config_from_user_config()
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config, audio_config=audio_config_data["audio_config"]
        )

        if len(self._config.phrases) > 0:
            grammar = speechsdk.PhraseListGrammar.from_recognizer(
                recognizer=speech_recognizer
            )
            for phrase in self._config.phrases:
                grammar.addPhrase(phrase)

        return helper.Read_Only_Dict(
            {
                "speech_recognizer": speech_recognizer,
                "audio_stream_format": audio_config_data["audio_stream_format"],
                "pull_input_audio_stream_callback": audio_config_data[
                    "pull_input_audio_stream_callback"
                ],
                "pull_input_audio_stream": audio_config_data["pull_input_audio_stream"],
            }
        )

    def recognize_continuous(self):
        speech_recognizer_data = self.__get_speech_recognizer_data()
        speech_recognizer: speechsdk.SpeechRecognizer = speech_recognizer_data[
            "speech_recognizer"
        ]

        done = False

        def recognizing_handler(e: speechsdk.SpeechRecognitionEventArgs):
            if (
                speechsdk.ResultReason.RecognizingSpeech == e.result.reason
                and len(e.result.text) > 0
            ):
                # This seems to be the only way we can get information about
                # exceptions raised inside an event handler.
                try:
                    caption = self.caption_from_real_time_result(e.result, False)
                    if caption is not None:
                        self.__write_to_file(caption)
                except Exception as ex:
                    print("Exception in recognizing_handler: {}".format(ex))
            elif speechsdk.ResultReason.NoMatch == e.result.reason:
                self.__write_to_console(
                    "NOMATCH: Speech could not be recognized.{}".format(linesep)
                )

        def recognized_handler(e: speechsdk.SpeechRecognitionEventArgs):
            if (
                speechsdk.ResultReason.RecognizedSpeech == e.result.reason
                and len(e.result.text) > 0
            ):
                self.__write_to_console('.')
                try:
                    if CaptioningMode.OFFLINE == self._config.captioning_mode:
                        self._offline_results.append(e.result)
                    else:
                        caption = self.caption_from_real_time_result(e.result, True)
                        if caption is not None:
                            self.__write_to_file(caption)
                except Exception as ex:
                    print("Exception in recognized_handler: {}".format(ex))
            elif speechsdk.ResultReason.NoMatch == e.result.reason:
                self.__write_to_console(
                    "NOMATCH: Speech could not be recognized.{}".format(linesep)
                )

        def canceled_handler(e: speechsdk.SpeechRecognitionCanceledEventArgs):
            nonlocal done
            # Notes:
            # SpeechRecognitionCanceledEventArgs inherits the result property from SpeechRecognitionEventArgs. See:
            # https://docs.microsoft.com/python/api/azure-cognitiveservices-speech/azure.cognitiveservices.speech.speechrecognitioncanceledeventargs
            # https://docs.microsoft.com/python/api/azure-cognitiveservices-speech/azure.cognitiveservices.speech.speechrecognitioneventargs
            # result is type SpeechRecognitionResult, which inherits the reason property from RecognitionResult. See:
            # https://docs.microsoft.com/python/api/azure-cognitiveservices-speech/azure.cognitiveservices.speech.speechrecognitionresult
            # https://docs.microsoft.com/python/api/azure-cognitiveservices-speech/azure.cognitiveservices.speech.recognitionresult
            # e.result.reason is ResultReason.Canceled. To get the cancellation reason, see e.cancellation_details.reason.
            if (
                speechsdk.CancellationReason.EndOfStream
                == e.cancellation_details.reason
            ):
                self.__write_to_console("End of stream reached.{}".format(linesep))
                done = True
            elif (
                speechsdk.CancellationReason.CancelledByUser
                == e.cancellation_details.reason
            ):
                self.__write_to_console(text="User canceled request.{}".format(linesep))
                done = True
            elif speechsdk.CancellationReason.Error == e.cancellation_details.reason:
                # Error output should not be suppressed, even if suppress output flag is set.
                print(
                    "Encountered error. Cancellation details: {}{}".format(
                        e.cancellation_details, linesep
                    )
                )
                done = True
            else:
                print(
                    "Request was cancelled for an unrecognized reason. Cancellation details: {}{}".format(
                        e.cancellation_details, linesep
                    )
                )
                done = True

        def stopped_handler(e: speechsdk.SessionEventArgs):
            nonlocal done
            self.__write_to_console(text="Session stopped.{}".format(linesep))
            done = True

        # We only use Recognizing results in real-time mode.
        if CaptioningMode.REALTIME == self._config.captioning_mode:
            speech_recognizer.recognizing.connect(recognizing_handler)
        speech_recognizer.recognized.connect(recognized_handler)
        speech_recognizer.session_stopped.connect(stopped_handler)
        speech_recognizer.canceled.connect(canceled_handler)

        speech_recognizer.start_continuous_recognition()

        while not done:
            sleep(5)
        speech_recognizer.stop_continuous_recognition()

        return


if __name__ == "__main__":
    config = CaptioningConfig(
        input_file="../sample.mp3",
        format="mp3",
        profanity="raw",
        output_file="../output.srt",
    )
    captioning = Captioning(config)
    captioning.initialize()
    captioning.recognize_continuous()
    captioning.finish()
