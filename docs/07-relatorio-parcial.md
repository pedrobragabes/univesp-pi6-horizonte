# Relatório parcial técnico — PI VI / PIE VI

> Revisão de software em 5 de outubro de 2026. Dados e boletins dos testes são sintéticos; esta etapa não comprova validação extensionista, sensores ou viabilidade econômica. Modalidade, cronograma e identificação dependem do AVA.

## Identificação e contexto extensionista

- Equipe, polo, semestre e orientador: [PREENCHER]
- Comunidade, parceiro e termo de aceite: [PREENCHER]

## Problema, justificativa e objetivos

Objetivo técnico: demonstrar contratos entre gateway, avaliação e registro, com informação identificada, validade temporal, registro operacional e degradação explícita. O problema comunitário e a justificativa são hipóteses do projeto; entrevistas, local e necessidade real: [PREENCHER com o parceiro].

## Requisitos e design centrado no usuário

| Requisito técnico | Decisão implementada | Evidência de software | Limite |
|---|---|---|---|
| RF1 — consulta pública por zona | resumo separado do histórico de 30 eventos | zona Central preservada após 31 entregas na Norte | zonas fictícias, sem co-design |
| RF2 — informação atual | instante observado prevalece; observação e entrega expiram após 5 min | entrega atrasada não substitui observação recente; dado antigo recém-entregue indisponível | sensor e relógio físicos não ensaiados |
| RF3 — ingestão identificada | origem explícita e recibo por evento | simulado preservado; identidade/conteúdo conflitantes recebem 409 | origem declarada não é certificação de hardware |
| RF4 — operação restrita | senha, sessão, papel e CSRF | login, medição, boletim e logout nos testes Python e navegador | credencial compartilhada, sem identidades individuais ou limite de tentativas |
| RNF1 — comunicação distribuída | três aplicações e processos HTTP separados na fixture E2E | saúde agregada e fluxo operacional pelos serviços reais locais | nenhum ensaio de carga/HA em produção |
| RNF2 — confiabilidade do recibo | transação reservada, comparação normalizada e busca de evento antes de avaliar novamente | concorrência, reinício, equivalência de fuso; repetição confirmada com avaliação indisponível | sem fila/outbox; leitura nova é recusada se dependência falha |
| RNF3 — resposta inválida deve degradar | objetos JSON e contratos internos validados; limites de entrada/resposta | HTML, JSON não objeto e dados inválidos recusados; erros internos não publicados | sem pentest ou avaliação de terceiros |
| RNF4 — acesso por teclado e telas pequenas | foco no conteúdo, regiões nomeadas e contraste ajustado | 7 E2E em 1440/390/320 px, 14 Axe sem violações, login sem JS | Axe não certifica acessibilidade; leitor de tela/usuários pendentes |

Participantes, jornadas reais, necessidades, critérios sociais e consentimento: [PREENCHER].

## Arquitetura integrada

Gateway Flask recebe consultas, sessões/formulários e telemetria v1. O serviço de avaliação calcula a regra experimental versionada; o registro persiste leituras, boletins e auditoria mínima em SQLite. Chamadas internas autenticam por chave própria, distinta da chave do dispositivo. A demonstração inicia três processos em loopback e banco temporário exclusivo, sem acessar dados do parceiro.

O evento de dispositivo combina identificador, boot e sequência. O gateway consulta primeiro o evento armazenado: repetição idêntica recebe seu recibo, mesmo sem o serviço de avaliação; diferença em origem, zona, instante ou medição é conflito. A inserção/comparação no registro é transacional. Horários são normalizados em UTC, inclusive ao comparar registros anteriores com outro fuso.

Corpos têm limite de 8192 bytes, respostas internas de 1 MiB e timeout de 3 segundos por chamada. Sem registro válido, a interface degrada e a API informa indisponibilidade. A auditoria continua best effort e não bloqueia a ação; isso exige evolução antes de responsabilização operacional real. A implantação deve atualizar primeiro o serviço de registro e depois o gateway, pois o contrato acrescentou resumo por zona e consulta de evento.

Hardware, fontes externas autorizadas, redundância, monitoramento/backup operacional e escala: pendentes. O `heat-index-v1` não foi alterado nesta revisão; sua simplificação, limites e ausência de validação local estão registrados na [arquitetura](01-arquitetura.md).

## Viabilidade preliminar

A alternativa implementada para demonstração usa três processos na mesma máquina. Ela reduz necessidades iniciais de infraestrutura, mas continua com um ponto de falha, chamadas síncronas, senha compartilhada e SQLite. Uma alternativa distribuída em hosts distintos acrescenta rede, operação, observabilidade e custo; nenhuma dessas despesas foi cotada nesta etapa.

| Dimensão | Hipótese ou evidência atual | Condição para avançar |
|---|---|---|
| proposta de valor | origem/validade visíveis e comunicação operacional separada da avaliação | confirmar necessidade e compreensão com comunidade |
| infraestrutura | três processos HTTP locais reproduzidos nos testes | dimensionar volume, disponibilidade e recuperação no ambiente escolhido |
| custo direto | categorias e fórmula em [viabilidade](04-viabilidade.md); sem preços preenchidos | obter cotações datadas de kit, conectividade, hospedagem e backup |
| trabalho recorrente | precisa de operador para boletins e mantenedor para incidentes | estimar horas, responsabilidades e financiamento com parceiro |
| continuidade | alternativa institucional, edital, serviço ou não implantação | responsável, recursos, canal alternativo e encerramento aceitos |
| risco | falsa atualidade, orientação indevida, exclusão e dependência | ensaios físicos, acessibilidade com usuários e protocolo de comunicação |

Recomendação preliminar: manter como demonstração técnica. A viabilidade econômica e institucional permanece não validada; não há recomendação de contratação ou implantação pública. A issue técnica registra esta análise preliminar, enquanto validação final e cotações continuam na atividade de campo.

## Estado e plano de ação

| Frente | Evidência atual | Lacuna | Prazo do AVA |
|---|---|---|---|
| Técnica | 33 testes Python aprovados; 7 E2E e 14 Axe sem violações; auditorias Python/Node sem alertas | CI, ambiente endurecido, carga, backup/restore operacional e sensores | [CONFIRMAR AVA] |
| Usuários | hipóteses e riscos documentados | parceiro, consentimento, co-design e tarefas com participantes | [CONFIRMAR AVA] |
| Viabilidade | alternativas, categorias de custo e responsabilidades comparadas | cotações, horas, recursos, aceite e decisão do responsável | [CONFIRMAR AVA] |

As capturas desktop e compacta foram inspecionadas. Os testes E2E verificam processos separados; os testes Python de integração usam servidores HTTP locais em threads para os serviços e o test client do gateway. Nenhum desses resultados equivale a piloto público ou capacidade sob carga.

## Referências

- [Arquitetura e decisões](01-arquitetura.md).
- [Operação e continuidade](02-operacao.md).
- [Validação técnica](03-validacao.md).
- [Viabilidade preliminar](04-viabilidade.md) e [ética](05-etica-e-impacto.md).
- [Revisão de código](06-revisao-de-codigo.md).
- [NWS — Heat Index, procedimento e limites](https://www.weather.gov/tbw/heatindex).
- Material do AVA, dados autorizados e referências locais: [PREENCHER].
