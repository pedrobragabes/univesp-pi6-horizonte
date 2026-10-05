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

## Evidências da fundação anterior

- 7 testes aprovados;
- integração HTTP real nos testes;
- 3 processos ativos e saudáveis na demonstração;
- 3 zonas alimentadas pela API de dispositivo;
- desktop e celular inspecionados, incluindo correção do overflow;
- dependências Python consistentes.

## Parecer

A fundação está adequada para publicação como plataforma distribuída demonstrativa. Ela não deve ser implantada para comunicação crítica antes de validação com parceiro, infraestrutura endurecida, ensaios de carga/segurança/acessibilidade e definição formal de responsabilidades.

## Revisão de contratos — 5 de outubro de 2026

- **R6:** duplicata confirmava conteúdo diferente; comparação normalizada em transação reservada agora retorna conflito, preserva original e repete o mesmo recibo após reinício.
- **R7:** limite de 30 eventos podia apagar zonas e entrega atrasada parecia atual; resumo por zona usa observação, com expiração e relógio adiantado explícitos.
- **R8:** repetição dependia de recalcular avaliação; consulta autenticada de evento permite confirmar registro existente durante falha do motor.
- **R9:** respostas HTML/JSON inválido/contrato incompleto causavam erro ou uso indevido; cliente limita tamanho, valida tipos e recibos e degrada com mensagem controlada.
- **R10:** tipos compostos, inteiros extremos e segredo não ASCII podiam causar 500; validação comum controla tipos/faixas e compara bytes UTF-8. Versão e timestamp do dispositivo são inteiros estritos.
- **R11:** simulador aparecia como hardware; origem simulada explícita e linguagem sem alegação de comunicação oficial/verificação física.
- **R12:** contraste, foco e tipografia em telas pequenas inadequados; contraste ajustado, regiões de formulário nomeadas e títulos cabem em 320 px.

Verificação: 33 Python, 7 E2E, 14 Axe sem violações nos estados testados, auditorias Python/Node sem alertas e capturas desktop/compacta inspecionadas. As chamadas HTTP dos testes Python usam servidores em threads; o E2E usa três processos separados. Fila persistente, auditoria garantida, identidades individuais, limite de tentativas, produção, sensor, cotações e validação comunitária continuam pendentes. O método de avaliação permanece experimental e simplificado, sem certificação ou validação local.
