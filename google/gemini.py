import google.generativeai as genai
import os

def chat(input, model_name='gemini-pro'):
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(input)
    return response.text

