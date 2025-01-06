from entities.history import History
import proxies.open_api_proxy as open_api_proxy
from enum import Enum

class Source(Enum):
    GPT = 'gpt'
    SAMPLE = 'sample'

sample = History(
    title='O Segredo da Árvore',
    description='Uma história sobre rivalidade familiar e um amor proibido que floresce em meio ao conflito.',
    content='Era uma vez uma pequena vila cercada por colinas verdes e uma floresta densa. No meio dessa floresta, havia uma árvore antiga, cujos ramos pareciam tocar o céu. A árvore era um símbolo de rivalidade entre duas famílias: os Oliveira e os Santos. Há gerações, as duas famílias disputavam a propriedade das terras que cercavam a árvore, sem saber que a verdadeira riqueza estava justamente ali.  \n  \nUm dia, Clara, uma jovem dos Oliveira, e Tomás, um rapaz dos Santos, se encontraram perto da árvore, buscando um refúgio do conflito familiar. Os dois se tornaram amigos e, aos poucos, o que começou como uma amizade se transformou em um amor profundo e proibido. Eles sabiam que seus pais jamais aceitariam tal relação, mas a conexão que tinham era mais forte do que qualquer rivalidade.  \n  \nEnquanto eles se encontravam à sombra da árvore, Clara e Tomás compartilhavam sonhos de um futuro em que suas famílias pudessem viver em paz. A árvore se tornava um símbolo de esperança para eles. Mas, a felicidade durou pouco tempo. Um dia, um dos irmãos de Clara, desconfiado dos encontros secretos, os viu juntos e correu para contar ao pai.  \n  \nEnfurecido, o pai de Clara decidiu confrontar o pai de Tomás. Uma briga violenta se iniciou entre as duas famílias, e a árvore, testemunha da união dos jovens, agora era o epicentro do ódio familiar. Clara e Tomás, desesperados, pediram ajuda à velha sábia da vila, que sempre conhecia as histórias da floresta.  \n  \nA sábia disse: "O amor verdadeiro é como a árvore: precisa ser nutrido para crescer. Se vocês amam um ao outro, enfrentem seus medos e juntos quebrem o ciclo de ódio." Inspirados por suas palavras, Clara e Tomás decidiram se levantar contra suas famílias.  \n  \nCom coragem, os jovens convocaram a vila para um encontro. Nervosos, eles contaram a todos sobre seu amor e sobre a disputa insensata que havia durado tanto tempo. As pessoas começaram a perceber que a verdadeira beleza estava na união, não na separação.  \n  \nCom o tempo, as duas famílias começaram a conversar entre si. As disputas se tornaram discussões e, por fim, um pacto de paz foi feito. A árvore, testemunha de tantas histórias, agora se tornou um símbolo de união entre os Oliveira e os Santos. Clara e Tomás finalmente puderam amar abertamente, e a árvore floresceu como nunca antes.  \n  \nAssim, a rivalidade deu lugar à amizade e à união, e a pequena vila se transforma em uma comunidade unida, provando que o amor pode vencer até mesmo os maiores conflitos.',
    hashtags=['#AmorProibido', '#RivalidadeFamiliar', '#União', '#Esperança', '#Paz']
)
    
def generate_history(prompt:str, source: str = Source.SAMPLE) -> History:
    if source == Source.GPT:
        return open_api_proxy.generate_history(prompt)
    else:
        return sample