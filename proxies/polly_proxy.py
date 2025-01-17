import tempfile
from boto3 import Session
from contextlib import closing
from io import BytesIO
from entities.editor.audio_clip import AudioClip


def __create_poly_client():
    session = Session()
    return session.client("polly")


def synthesize_speech(text, output_format="mp3", voice_id="Ricardo") -> AudioClip:
    polly = __create_poly_client()
    response = polly.synthesize_speech(
        Text=text, OutputFormat=output_format, VoiceId=voice_id
    )
    metadata = response.get("ResponseMetadata")
    audio_stream = response.get("AudioStream")
    if metadata and metadata.get("HTTPStatusCode") == 200:
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_file.write(audio_stream.read())
            return AudioClip(temp_file.name)
    else:
        print(response)
        raise "Could not stream audio"
