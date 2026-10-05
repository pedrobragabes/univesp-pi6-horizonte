# Validação técnica

## Evidências da fundação anterior

- 7 testes automatizados aprovados;
- chamadas HTTP reais entre três aplicações durante os testes;
- três leituras de demonstração aceitas de ponta a ponta;
- níveis normal, atenção e alerta apresentados em zonas fictícias;
- repetição de evento do dispositivo sem duplicar registro;
- login com senha, sessão e CSRF;
- medição operacional, boletim e auditoria persistidos;
- saúde agregada com as duas dependências ativas;
- painel público permanece disponível e informa falha quando o registro cai;
- leitura vencida deixa de aparecer como situação atual;
- páginas pública e operacional verificadas em 1280 px e 390 px;
- rolagem horizontal móvel encontrada e corrigida durante a revisão;
- dependências Python sem inconsistências.

## O que os testes não provam

- capacidade de atender usuários simultâneos em produção;
- disponibilidade sob falhas de rede prolongadas;
- precisão do DHT22 ou do índice para um local real;
- compreensão, acessibilidade prática ou confiança do público;
- adequação das zonas e das orientações;
- segurança contra ataque especializado;
- custo, suporte ou sustentabilidade organizacional.

## Plano para o semestre

1. definir tarefas públicas e operacionais com o parceiro;
2. realizar teste de teclado, leitor de tela, contraste e zoom com registro;
3. medir carga-alvo, latência p95 e taxa de erro em ambiente de homologação;
4. ensaiar desligamento de cada serviço e recuperação;
5. comparar fonte experimental com referência apropriada;
6. conduzir tarefas com participantes e registrar barreiras sem coletar dados desnecessários;
7. apresentar resultados e obter decisão do parceiro: adotar, pilotar com condições ou não adotar.

Critérios numéricos só devem ser fechados depois de conhecer volume, público, infraestrutura e responsabilidade do piloto.

## Revisão de software — 5 de outubro de 2026

- 33 testes Python aprovados no Windows; integração HTTP local entre gateway e serviços, além de contratos isolados;
- 7 E2E com três processos HTTP separados e SQLite temporário;
- 14 análises Axe sem violações em estados público, login, vazio, degradado e operação autenticada;
- 1440/390/320 px, teclado, login sem JavaScript e capturas desktop/compacta inspecionados;
- conflitos em conteúdo do evento, duas gravações concorrentes, reinício e equivalência de fuso testados;
- 31 entregas em uma zona não removem outra do resumo; entrega atrasada não substitui observação mais recente;
- leitura antiga recém-entregue fica indisponível; repetição já armazenada é confirmada sem serviço de avaliação;
- entradas excessivas, tipos inválidos, segredos não ASCII e respostas internas inválidas controlados;
- demonstrador declara dados simulados; nenhum sensor ou comunicado real;
- auditorias Python e Node sem vulnerabilidades conhecidas.

As fixtures de páginas vazia/degradada exercitam a renderização. Falha de dependência é ensaiada separadamente nos testes Python; as capturas não representam uma falha de produção. Não foram medidos carga-alvo, p95, disponibilidade de campo, custos ou aceite comunitário.
