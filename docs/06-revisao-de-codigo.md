# Revisão de código

## Escopo

- contratos e falhas entre os três serviços;
- motor de risco e proveniência da decisão;
- autenticação, papéis, sessão e CSRF;
- ingestão de dispositivo e idempotência;
- validação, persistência e auditoria;
- atualização dos dados e degradação;
- acessibilidade, responsividade e segurança do navegador;
- testes e integração contínua.

## Achados corrigidos

### R1 — leitura antiga aparentava situação atual

**Severidade:** alta.

O painel selecionava a última leitura sem verificar sua idade. Agora medições recebidas há mais de cinco minutos são marcadas como indisponíveis, com mensagem específica.

### R2 — serviço interno aceitava valores pouco validados

**Severidade:** alta.

Uma chave interna válida permitia gravar texto no lugar de números, datas sem fuso e identificadores arbitrários. Foram adicionados tipos finitos, faixas, padrões de identificador, versão do algoritmo e data ISO consciente de fuso.

### R3 — contrato de dispositivo aceitava coerções perigosas

**Severidade:** média.

Booleanos e identificadores sem formato poderiam virar número ou chave de idempotência. Dispositivo, boot, sequência e medições agora têm tipos e limites explícitos antes da orquestração.

### R4 — resposta HTTP de erro não era fechada

**Severidade:** baixa.

O cliente lia `HTTPError`, mas não fechava seu stream, gerando aviso de recurso. O fechamento passou a ocorrer em `finally`.

### R5 — título principal causava rolagem horizontal móvel

**Severidade:** média.

“Informação” ultrapassava a largura disponível em 390 px. Foi aplicado ajuste tipográfico no breakpoint e quebra segura; a página passou de 517 px para 375 px de largura rolável.

## Controles existentes

- chaves distintas para serviços e dispositivos;
- comparação de segredos em tempo constante;
- papel operador em sessão assinada;
- CSRF em todas as ações de formulário;
- CSP, `nosniff`, negação de frames e política sem referenciador;
- contratos fechados e queries parametrizadas;
- evento de dispositivo idempotente;
- auditoria sem conteúdo sensível;
- falha do registro exibida e propagada como 503 na API;
- algoritmo explicável e versionado.

## Riscos aceitos

- credenciais compartilhadas e sem rotação automática;
- login sem limitador de tentativas;
- SQLite e chamadas síncronas adequados apenas ao protótipo;
- auditoria pode falhar sem bloquear uma ação, para evitar indisponibilidade em cascata;
- ausência de fila: indisponibilidade de dependência recusa nova medição;
- cookies sem `Secure` no ambiente HTTP local;
- algoritmo e sensor sem validação para uso real;
- sem teste de carga, pentest ou usuários nesta fundação.

## Evidências

- 7 testes aprovados;
- integração HTTP real nos testes;
- 3 processos ativos e saudáveis na demonstração;
- 3 zonas alimentadas pela API de dispositivo;
- desktop e celular inspecionados, incluindo correção do overflow;
- dependências Python consistentes.

## Parecer

A fundação está adequada para publicação como plataforma distribuída demonstrativa. Ela não deve ser implantada para comunicação crítica antes de validação com parceiro, infraestrutura endurecida, ensaios de carga/segurança/acessibilidade e definição formal de responsabilidades.
