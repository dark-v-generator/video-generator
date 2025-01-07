import tempfile
from boto3 import Session
from contextlib import closing
from io import BytesIO


def __create_poly_client():
    session = Session()
    return session.client("polly")


def synthesize_speech(text, output_format="mp3", voice_id="Ricardo") -> BytesIO:
    polly = __create_poly_client()
    response = polly.synthesize_speech(
        Text=text, OutputFormat=output_format, VoiceId=voice_id
    )
    metadata = response.get("ResponseMetadata")
    audio_stream = response.get("AudioStream")
    if metadata and metadata.get('HTTPStatusCode') == 200:
        with closing(audio_stream) as stream:
            audio_stream = BytesIO(stream.read())
            return audio_stream
    else:
        print(response)
        raise "Could not stream audio"
