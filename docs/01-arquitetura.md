# Arquitetura e decisões

## Contexto

O Horizonte trata um recorte próprio: comunicação comunitária durante episódios de calor em espaços locais. Ele não agrega automaticamente os PIs anteriores. A interface de telemetria aproveita apenas o conceito versionado e idempotente experimentado no Sentinela.

## Componentes

| Componente | Responsabilidade | Estado mantido |
|---|---|---|
| Gateway | interface, sessão, CSRF, papéis, dispositivo e orquestração | sessão assinada no cliente |
| Risk service | validar temperatura/umidade e calcular índice/nível | nenhum |
| Store service | leituras, boletins e eventos mínimos de auditoria | SQLite |

### Contratos

- gateway → risco: `POST /v1/evaluate` com temperatura e umidade;
- gateway → registro: leituras, boletins, auditoria e snapshot;
- dispositivo → gateway: mensagem v1 identificada por dispositivo, boot e sequência;
- interface → gateway: páginas HTML e estado JSON.

As chamadas internas usam `X-Service-Key`; dispositivos usam outra credencial. A separação reduz o impacto de expor a chave de um nó, embora o MVP ainda use uma chave compartilhada por classe de cliente.

## Decisões

### D1 — serviços separados, implantação inicialmente simples

Separar avaliação e registro demonstra contratos distribuídos e permite evolução independente. Para o piloto, três processos na mesma máquina reduzem custo e operação. Distribuição física só deve ocorrer quando disponibilidade, volume ou responsabilidade justificarem a complexidade.

### D2 — algoritmo explicável e versionado

O índice de calor usa temperatura e umidade e retorna explicação, versão e aviso. A interface não publica suas ações automáticas como boletim oficial: um operador autorizado precisa redigir a comunicação contextual.

### D3 — expiração em vez de confiança infinita

Uma observação ou entrega com mais de cinco minutos deixa de sustentar o estado da zona. O painel mostra `indisponível`, preservando a distinção entre ausência de alerta e ausência de dados.

### D4 — ausência de dados pessoais

O MVP não registra nome, endereço, condição de saúde, IP ou texto livre do público. Auditoria contém tipo de evento, papel, resultado e instante, suficientes para rastrear ações sem criar um cadastro desnecessário.

### D5 — falha visível

Se o registro cair, a página pública continua disponível com aviso, enquanto a API retorna 503. Se o risco cair, novas medições não são classificadas nem armazenadas como válidas. A plataforma não inventa resultado de contingência.

## Evolução

Antes de escala real: PostgreSQL, fila/outbox, identidades individuais, segredo por dispositivo, observabilidade central, múltiplas instâncias sem estado e cache de conteúdo público. Cada mudança precisa de critério mensurável; “microserviços” não é um objetivo isolado.

## Contratos revisados em 5 de outubro de 2026

O snapshot inclui `latest_readings`, independente dos últimos 30 registros, selecionado por instante observado por zona. O registro também fornece consulta autenticada de evento em `GET /v1/readings/<event_id>`. O gateway valida ambos os contratos e exige recibo com evento, ID positivo e status correspondente ao HTTP. Atualizar primeiro o registro e depois o gateway.

A chave de idempotência identifica conteúdo imutável: repetição exata mantém ID; conflito retorna 409 sem sobrescrita. Datas equivalentes em fusos diferentes são normalizadas em UTC. O gateway confirma evento existente antes de chamar o motor; uma nova leitura não é armazenada quando falta avaliação válida. Origens `simulado`, `experimental` e `hardware` são declarações do emissor, não certificações.

## Limites da regra experimental de avaliação

O `heat-index-v1` usa o polinômio de Rothfusz somente com temperatura de pelo menos 26,7 °C e umidade de pelo menos 40%; nos demais casos retorna a temperatura. Essa simplificação omite ajustes e seleção completa descritos pelo [NWS](https://www.weather.gov/tbw/heatindex), que também registra limites da regressão. O método não deve ser apresentado como implementação completa do NWS, previsão oficial ou avaliação clínica. Os cortes de 32/40 °C são hipóteses do protótipo, sem validação para a comunidade. Resultados fora do contrato interno não são utilizados como avaliação válida. O procedimento e as fontes precisam ser revistos com responsáveis antes de qualquer piloto real.
