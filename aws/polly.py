from boto3 import Session
from contextlib import closing
import os
from tempfile import gettempdir, mktemp


def     create_poly_client():
    session = Session()
    return session.client("polly")

def synthesize_speech(text, output_file=None, output_format="mp3", voice_id="Ricardo"):
    polly = create_poly_client()
    response = polly.synthesize_speech(Text=text, OutputFormat=output_format, VoiceId=voice_id)
    if "AudioStream" in response:
        with closing(response["AudioStream"]) as stream:
            output = output_file if output_file else os.path.join(gettempdir(), f"{mktemp()}.{output_format}")
            with open(output, "wb") as file:
                file.write(stream.read())
            return output
    else:
        raise "Could not stream audio"

