import json
from time import sleep
from google import gemini

def chat_gemini_json(input, retries=3):
    exception = None
    for _ in range(retries):
        try:
            response = gemini.chat(input)
            response = response.split('```json\n')[1].split('\n```')[0]
            return json.loads(response)
        except Exception as e:
            exception = e
            print(f'Error: {e}, retrying...')
            sleep(5)
    raise exception


class HistoryModel:
    def __init__(self, history_description):
        self.history_description = history_description
        self.__generate_details()

    def __generate_details(self):
        prompt = """
            Olá, eu vou te passar uma história e eu gostaria que você retornasse em formato json os seguintes
            campos, 'title', 'subtitle','description' ,'hashtags' e 'gender', o título é um título para a história, o subtítulo é o
            subtítulo da história, a descrição é uma breve descrição da história com poucas palavras,
            as hashtags são as hashtags que você acha que são relevantes para a história e o
            gênero é o gênero do narrador da história com base nas conjugações verbais, se for feminino
            use 'feminino' e se for masculino use 'masculino'.
            A história é a seguinte:
        """
        response = chat_gemini_json(prompt + self.history_description)
        self.title = response['title']
        self.subtitle = response['subtitle']
        self.description = response['description']
        self.hashtags = response['hashtags']
        if not isinstance(self.hashtags, list):
            self.hashtags = ' '.join(self.hashtags)
        self.gender = response['gender']
        
    def social_media_description(self, background_video_creator=None):
        response = f'{self.title}\n\n{self.description}'
        response += f'\n\n{' '.join(self.hashtags)}'
        if background_video_creator:
            response += f'\n\nVideo de fundo por {background_video_creator}'
        return response
    def normalized_title(self):
        return ''.join(e for e in self.title if e.isalnum() or e == ' ' or e == '-').lower().replace(' ', '_')
    def __str__(self):
        return f'{self.title}\n\n{self.description}\n\n{self.hashtags}'


class History(HistoryModel):
    def __init__(self, story_prompt):
        self.history_description = gemini.chat(story_prompt).replace('*', '').replace('[', '').replace(']', '')
        super().__init__(self.history_description)
