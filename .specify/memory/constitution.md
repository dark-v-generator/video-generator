<!--
Sync Impact Report
- Version change: (template inicial, sem versão) → 1.0.0
- Ratification: primeira adoção da constituição do projeto
- Principles defined:
  - I. Fail Fast e Simplicidade
  - II. Arquitetura Limpa em Módulos
  - III. Prompts Baseados em Racional
- Added sections:
  - Padrões de Comunicação e Idioma
  - Fluxo de Desenvolvimento
  - Governança
- Removed sections: nenhuma (template substituído integralmente)
- Templates review:
  - .specify/templates/plan-template.md ✅ (Constitution Check é dinâmico; sem alteração necessária)
  - .specify/templates/spec-template.md ✅ (sem referências a princípios; sem alteração)
  - .specify/templates/tasks-template.md ✅ (sem referências a princípios; sem alteração)
- Deferred TODOs: nenhum
-->

# Video Generator Constitution

## Core Principles

### I. Fail Fast e Simplicidade

O código deve falhar cedo e de forma explícita quando encontra um estado inesperado,
em vez de tentar contornar ou mascarar o problema. Edge cases raros NÃO devem ser
tratados de forma defensiva; a preferência é deixar o erro estourar de imediato,
com contexto suficiente para diagnóstico.

Racional: cada ramo de código adicionado para um caso improvável aumenta a superfície
de manutenção e esconde bugs. Falhar rápido mantém o fluxo principal legível e revela
problemas reais em vez de degradar silenciosamente. Robustez extra só se justifica
quando o caso é frequente ou o custo da falha é alto — e essa justificativa deve ser
explícita.

### II. Arquitetura Limpa em Módulos

O código deve ser separado em módulos bem definidos seguindo Clean Architecture (Robert
C. Martin): regras de negócio no centro, detalhes (I/O, frameworks, APIs externas, LLMs,
armazenamento) nas bordas. As dependências apontam sempre de fora para dentro — as
camadas internas não conhecem as externas. Detalhes externos são acessados por meio de
abstrações (interfaces/portas), permitindo substituição sem tocar na regra de negócio.

Racional: isolar a lógica de domínio dos detalhes torna o núcleo testável, estável e
independente de fornecedor. Um módulo tem uma responsabilidade clara e uma fronteira
explícita; quando as fronteiras se borram, mudanças em detalhes vazam para o negócio e o
sistema fica frágil.

### III. Prompts Baseados em Racional

Prompts para agentes e modelos de IA devem comunicar o objetivo e o porquê, não uma
lista de instruções casuísticas. Evite regras específicas do tipo "quando o título
contiver X, faça Y"; em vez disso, explique o motivo por trás do comportamento desejado
e deixe o agente decidir como aplicá-lo. Não use CAPS para dar ênfase — a clareza vem da
formulação, não do volume.

Racional: instruções casuísticas cobrem apenas os casos que o autor antecipou e engessam
o agente diante do inesperado. Quando o prompt carrega o racional, a instrução fica clara
e o agente tem liberdade para generalizar corretamente para situações não previstas.

## Padrões de Comunicação e Idioma

A comunicação com o usuário (respostas, explicações, documentação voltada ao usuário)
deve ser em português. Todo o código — nomes de variáveis, funções, classes, comentários
e mensagens de commit — deve ser escrito em inglês.

Racional: o time trabalha em português, mas manter o código em inglês preserva
consistência com o ecossistema de bibliotecas e facilita colaboração e leitura por
ferramentas e terceiros.

## Fluxo de Desenvolvimento

Toda mudança deve respeitar os princípios acima antes de ser considerada pronta.
Complexidade adicional — tratamento de casos raros, camadas extras, prompts prescritivos —
precisa de justificativa explícita registrada na revisão ou no plano da feature.
Revisões de código verificam aderência a esta constituição; violações sem justificativa
devem ser corrigidas ou o desvio documentado.

## Governança

Esta constituição prevalece sobre outras práticas do projeto. Emendas exigem: descrição
da mudança, justificativa e atualização dos artefatos dependentes (templates de plano,
spec e tasks, e guias de contexto de agente).

Versionamento semântico da constituição:
- MAJOR: remoção ou redefinição incompatível de princípios ou governança.
- MINOR: adição de um princípio/seção ou expansão material de orientação.
- PATCH: esclarecimentos, correções de texto e refinamentos não semânticos.

A conformidade é verificada nas revisões de código e no gate de Constitution Check dos
planos de feature. Para orientação de desenvolvimento em tempo de execução, consulte o
`AGENTS.md` e o plano atual da feature.

**Version**: 1.0.0 | **Ratified**: 2026-07-18 | **Last Amended**: 2026-07-18
