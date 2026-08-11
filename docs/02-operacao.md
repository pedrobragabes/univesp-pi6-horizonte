# Operação e continuidade

## Papéis

| Papel | Pode | Não pode |
|---|---|---|
| público | consultar situação, origem e boletins | registrar medição ou boletim |
| operador | autenticar, registrar medição identificada e publicar orientação | alterar algoritmo ou apagar auditoria |
| mantenedor técnico | configurar, atualizar, restaurar e investigar falhas | definir sozinho a comunicação comunitária |
| parceiro responsável | aprovar linguagem, rotina e canais | transferir responsabilidade crítica ao protótipo |

O código implementa público e operador. Mantenedor e parceiro são responsabilidades organizacionais a formalizar.

## Variáveis obrigatórias

| Variável | Finalidade |
|---|---|
| `HORIZONTE_SERVICE_KEY` | autenticação entre serviços |
| `HORIZONTE_DEVICE_KEY` | autenticação do protótipo físico |
| `HORIZONTE_SESSION_SECRET` | assinatura das sessões |
| `HORIZONTE_OPERATOR_PASSWORD` | acesso operacional inicial |
| `HORIZONTE_STORE_URL` | endereço interno do registro |
| `HORIZONTE_RISK_URL` | endereço interno do motor |

Valores padrão existem apenas para desenvolvimento e geram aviso na interface operacional.

## Saúde e incidentes

`GET /health` no gateway verifica registro e risco. Resultado `degraded` e HTTP 503 significam que novas informações não devem ser consideradas completas.

Ordem de resposta:

1. confirmar qual dependência falhou;
2. preservar banco e logs;
3. não apagar nem reconstruir dados durante investigação;
4. restaurar o serviço;
5. enviar nova medição e confirmar saúde;
6. registrar duração, impacto e ação corretiva;
7. informar o público por canal alternativo se houver piloto ativo.

## Backup e recuperação

No MVP, interromper gravações e copiar `data/horizonte.db` para armazenamento protegido, registrando data e hash. A periodicidade depende do piloto. Uma implantação contínua deve migrar para banco com backup transacional, teste de restauração e política de retenção aprovada.

## Publicação

Não expor os servidores de desenvolvimento diretamente. Usar HTTPS, proxy, WSGI, firewall, conta sem privilégio, segredos fora do código e logs com rotação. Cookies devem receber `Secure` quando houver HTTPS. Definir responsável, horário de suporte e canal de escalonamento antes do piloto.

## Encerramento

O plano precisa incluir exportação dos boletins e medições permitidas, revogação de credenciais, remoção de infraestrutura e comunicação ao público. Sustentabilidade inclui saber desligar o sistema com segurança.
