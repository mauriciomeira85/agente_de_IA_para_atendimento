# Agente de Atendimento

Plataforma SaaS multi-tenant de um agente de IA para **atendimento receptivo** pelo WhatsApp — a empresa cadastra seus setores e sua base de conhecimento (políticas, FAQ, descrições de produto), e o agente faz a triagem de cada mensagem recebida: responde sozinho usando busca semântica na base de conhecimento, ou encaminha para o setor humano certo quando necessário.

🔗 **Aplicação em produção:** [agenteatendimento.projetostechmauricio.lol](https://agenteatendimento.projetostechmauricio.lol/)

## 1. O problema que este projeto resolve

Empresas que recebem mensagens de clientes pelo WhatsApp costumam depender de um time humano até para perguntas repetitivas — horário de funcionamento, política de troca, como usar um produto — que já estão documentadas em algum lugar, só não de um jeito que o cliente consiga achar sozinho. Este projeto automatiza a primeira linha desse atendimento: o agente lê a base de conhecimento da empresa, responde o que consegue responder com segurança, e só aciona um humano quando a pergunta foge do que está documentado ou exige uma ação humana de verdade.

O agente é **receptivo** por natureza: não existe abordagem automática nem importação de contatos — todo atendimento nasce sozinho, na primeira mensagem que o cliente manda. E o desfecho não é fixo: cada atendimento pode ser encaminhado para qualquer setor que a empresa cadastrar (Vendas, Financeiro, Suporte Técnico, ou o que fizer sentido para o negócio dela) — o roteamento é decidido caso a caso, não configurado uma vez só para toda a empresa.

## 2. Demonstração

Três vídeos mostrando o agente funcionando de ponta a ponta pelo WhatsApp de verdade — do lado do cliente e do painel em tempo real.

**2.1 Demonstração da plataforma**

https://github.com/user-attachments/assets/bca20643-888b-4f6a-83a9-8d7d71ec792c

**2.2 Demonstração do funcionamento do agente no WhatsApp**

https://github.com/user-attachments/assets/8d4763e5-7248-4c48-b068-8db9881848a6

**2.3 Outra demonstração do funcionamento do agente no WhatsApp**

https://github.com/user-attachments/assets/4a26de79-6d9d-437e-a1ff-e936331eec32

## 3. Funcionalidades

- **Dashboard** — 4 cartões de quantidade (total de atendimentos, em atendimento, encaminhados, resolvidos), 3 cartões de taxa (encaminhamento, resolução automática, reabertura), dois funis de barras (encaminhamento e resolução), um gráfico de volume de atendimentos por dia (rolagem horizontal para períodos longos), ranking dos setores mais acionados e filtro por período — a métrica central deste domínio é quanto a IA resolveu sozinha, sem gerar trabalho para um setor humano.
- **Base de Atendimentos** — todo atendimento nasce automaticamente da primeira mensagem do cliente pelo WhatsApp (sem criação/importação manual); tabela com filtro por status e busca, edição/exclusão manual, indicador de reabertura.
- **Conversas** — histórico completo de cada conversa, atualizado em tempo real via WebSocket assim que uma mensagem nova chega ou é enviada.
- **Setores** — CRUD dos setores da empresa (nome + descrição), usados pelo agente como destino de encaminhamento; o modelo só pode encaminhar para um setor que exista de verdade (validado em código, nunca confiado apenas na escolha da IA).
- **Base de Conhecimento** — CRUD de itens (título + conteúdo); cada item é convertido em embedding (busca semântica) na hora do cadastro/edição, e o agente consulta os itens mais relevantes para cada pergunta do cliente antes de responder.
- **Configuração do Agente** — perfil da empresa, roteiro de comportamento da conversa, e o bloco "Regras de Atendimento": exigir que toda resposta venha só da base de conhecimento (`responder_apenas_com_base_no_conhecimento`) e o texto a usar quando a pergunta foge do escopo cadastrado.
- **Canais** — conexão "um clique" do WhatsApp Business de cada empresa, via WhatsApp Embedded Signup da Meta, e o **painel único de templates**: lista os 4 templates usados pelo agente (notificação ao setor, reencaminhamento, alerta de tentativa de manipulação, reengajamento de atendimento silencioso) com prévia, status real na Meta e motivo de rejeição; **um clique** envia todos para análise, e o status atualiza sozinho quando a Meta decide (webhook `message_template_status_update`).
- **Integrações** — conexões de saída (notificação para sistemas externos da empresa).
- **Configurações** — dados gerais da conta da empresa na plataforma.
- **Cadastro e login** — cada empresa cria sua própria conta; os dados de uma empresa nunca ficam visíveis para outra.

## 4. Arquitetura

O frontend (Next.js) e o backend (FastAPI) ficam atrás de um único endereço público, roteado pelo Caddy — que também cuida da emissão automática do certificado HTTPS.

### 4.1 Visão geral — da mensagem do cliente até a resposta de volta

```mermaid
flowchart TD
    Cliente(["📱 Cliente no WhatsApp"])
    Meta["Meta WhatsApp Cloud API"]
    Worker["Cloudflare Worker<br/>valida assinatura HMAC do evento"]
    Backend["Backend FastAPI — webhook<br/>identifica a empresa pelo phone_number_id<br/>localiza ou cria o Atendimento/Conversa<br/>grava a mensagem (com proteção contra duplicidade)"]
    DB[("PostgreSQL + pgvector<br/>atendimentos · setores · base de conhecimento (embeddings)<br/>isolados por empresa")]
    Realtime["Redis pub/sub → WebSocket"]
    Frontend["Frontend Next.js<br/>Dashboard e Conversas em tempo real"]
    Celery["Celery Worker<br/>processamento assíncrono, com retry automático"]
    Grafo["Grafo do agente (LangGraph)<br/>ver diagrama abaixo"]

    Cliente -->|mensagem| Meta
    Meta -->|evento assinado| Worker
    Worker -->|evento validado| Backend
    Backend -->|grava| DB
    Backend -->|200 OK em milissegundos| Worker
    Backend -->|dispara tarefa em 2º plano| Celery
    Backend -.->|publica evento| Realtime
    Realtime -.-> Frontend
    Celery --> Grafo
    Grafo -->|resposta decidida| Celery
    Celery -->|grava resposta + atualiza status do atendimento| DB
    Celery -.->|publica evento| Realtime
    Celery -->|envia a resposta de verdade| Meta
    Meta -->|mensagem| Cliente
```

### 4.2 O grafo do agente — o que acontece a cada mensagem recebida

Duas etapas (nós do LangGraph), sempre na mesma ordem — sem "checkpointer": o histórico completo já mora no Postgres, então cada execução roda do zero com o histórico inteiro como entrada.

```mermaid
flowchart LR
    Inicio(["Mensagem recebida do cliente"]) --> Tipo{"Tipo de conteúdo?"}
    Tipo -->|texto| Passa["interpretar_midia<br/>repassa o texto direto, sem gastar IA"]
    Tipo -->|imagem / GIF / vídeo| Img["interpretar_midia<br/>baixa a mídia real da Graph API<br/>descreve com deepseek-flash (visão)<br/>anexa a imagem ao turno atual"]
    Tipo -->|áudio| Audio["interpretar_midia<br/>transcreve com Whisper (Together AI)"]
    Tipo -->|PDF| Pdf["interpretar_midia<br/>extrai texto localmente (PyMuPDF)<br/>só usa visão se for PDF escaneado"]
    Tipo -->|Word / Excel / txt| Doc["interpretar_midia<br/>extrai texto localmente, sem IA"]

    Passa --> Turno
    Img --> Turno
    Audio --> Turno
    Pdf --> Turno
    Doc --> Turno

    Turno["executar_turno_do_agente<br/>monta prompt + setores da empresa + ferramentas disponíveis<br/>roda o loop de turno/passo"] --> Fim(["Resultado: resposta em texto,<br/>status do atendimento, setor de encaminhamento"])
```

### 4.3 Triagem → FAQ (RAG) → roteamento — tudo dentro de UM agente

Esse fluxo inteiro acontece dentro do **mesmo** loop de turno/passo — o modelo decide, turno a turno, se consulta a base de conhecimento, se encaminha para um setor, ou se responde direto. Não é um fluxograma fixo em código escolhendo a ação — o **próprio modelo** recebe as ações disponíveis como ferramentas de verdade e decide, dentro da própria resposta, se e qual delas chamar. Quando chama, a ferramenta **executa a ação de verdade na hora** — não apenas anota uma intenção para outro código decidir depois.

```mermaid
sequenceDiagram
    participant Agente as Loop de ferramentas
    participant IA as deepseek-flash
    participant Tool as Ferramenta chamada
    participant DB as Base de Conhecimento (pgvector)
    participant Ext as WhatsApp (setor humano)

    Agente->>IA: historico completo + setores da empresa + ferramentas disponiveis
    IA-->>Agente: pediu para chamar uma ferramenta?

    alt Quer consultar a base de conhecimento
        Agente->>Tool: consultar_base_de_conhecimento(pergunta)
        Tool->>DB: busca por similaridade de embedding (top-k)
        DB-->>Tool: itens mais relevantes
        Tool-->>Agente: trechos relevantes (texto)
        Agente->>IA: trechos + historico
    else Quer encaminhar para um setor
        Agente->>Tool: encaminhar_para_setor(setor, resumo)
        Tool->>Ext: notifica o setor real pelo WhatsApp
        Ext-->>Tool: confirmacao do envio
        Tool-->>Agente: resultado da ferramenta (texto)
        Agente->>IA: resultado + historico
    else So texto
        IA-->>Agente: resposta final em texto, pronta para o cliente
    end

    Note over Agente,IA: repete ate o modelo responder so em texto, ou ate um teto de passos de seguranca
```

### 4.4 Ferramentas disponíveis para o modelo chamar

Definidas em `agente/ferramentas.py`, sempre em modo livre — nunca uma é forçada, o modelo decide sozinho se/quando/qual usar:

| Ferramenta | O que faz de verdade quando chamada |
|---|---|
| `consultar_base_de_conhecimento` | Busca por similaridade de embedding os itens mais relevantes para a pergunta do cliente |
| `encaminhar_para_setor` | Marca o atendimento como `ENCAMINHADO` e envia WhatsApp real para o setor (validado em código contra a lista real de setores da empresa) |
| `marcar_como_resolvido` | Marca o atendimento como `RESOLVIDO` — a IA respondeu sozinha, sem precisar de humano |
| `nao_responder` | Encerra o turno em silêncio proposital (ferramenta terminal — corta o loop na hora) |

## 5. Estrutura de pastas

```
agente-atendimento/
├── backend/                    # API em FastAPI
│   ├── app/
│   │   ├── modelos/             # Tabelas do banco (SQLAlchemy) — inclui Setor e ItemDeConhecimento
│   │   ├── esquemas/            # Formatos de entrada/saída da API (Pydantic)
│   │   ├── rotas/               # Endpoints da API (templates_whatsapp.py = painel único de templates)
│   │   ├── agente/               # Grafo LangGraph, prompts, guardrails e orquestração
│   │   ├── integracoes_externas/ # Clientes da DeepSeek, OpenAI (embeddings), Together AI (transcrição) e da WhatsApp Cloud API
│   │   ├── midia/                 # Leitura de arquivos recebidos em conversa (PDF etc.)
│   │   └── tarefas/              # Tarefas assíncronas do Celery
│   ├── alembic/                  # Migrações do banco de dados
│   └── testes/                   # Testes automatizados (pytest)
├── frontend/                   # Interface em Next.js
│   └── src/
│       ├── app/                  # Páginas (uma pasta por aba da plataforma, inclui setores/ e base-conhecimento/)
│       ├── componentes/          # Componentes de interface reutilizáveis
│       └── biblioteca/           # Cliente de API, tipos e autenticação
├── infra/
│   ├── cloudflare-webhook/       # Worker que valida e repassa os eventos da Meta
│   └── caddy/                    # Configuração do roteamento e HTTPS
├── scripts/
│   └── implantar_na_vm.sh        # Script de deploy
└── docker-compose.yml
```

## 6. Stack tecnológica

| Camada | Tecnologia | Por quê |
|---|---|---|
| Orquestração do agente | LangGraph | Grafo de dois nós (interpretar mídia → executar turno) — dentro do segundo, um loop de turno/passo com tool calling nativo deixa o próprio modelo decidir e EXECUTAR a ação (consultar a base de conhecimento, encaminhar para um setor etc.), em vez de um `if/elif` em Python interpretar uma saída fixa |
| Modelo de linguagem | DeepSeek (`deepseek-flash`) — conversa/ferramentas e interpretação de imagem/vídeo (multimodal nativo); PyMuPDF para texto de PDF (sem IA); Together AI (Whisper Large v3) para transcrição de áudio | Raciocínio, decisão de ferramentas e leitura de mídia enviada pelo cliente |
| Busca semântica (RAG) | OpenAI (`text-embedding-3-small`, 1536 dimensões) + pgvector | Embedding multilíngue de verdade (inclui português) para achar os itens de conhecimento mais relevantes por pergunta; reaproveita o MESMO Postgres da aplicação (extensão `pgvector`), em vez de um serviço de vetor separado — a Together AI (mesma conta usada para transcrição) parou de oferecer embeddings em modo serverless, só endpoint dedicado com custo fixo por hora |
| Backend | Python, FastAPI, WebSockets, async/await | API REST, autenticação, webhook e o canal de tempo real |
| Banco de dados | PostgreSQL (`pgvector/pgvector`) + SQLAlchemy + Alembic | Dados relacionais multi-tenant e coluna vetorial para embeddings, com migrações versionadas |
| Fila de tarefas | Celery + Redis | Processamento assíncrono das respostas da IA e da varredura de atendimentos silenciosos |
| Frontend | React, Next.js, TypeScript, Tailwind CSS | Interface do painel |
| Integração de mensagens | WhatsApp Business Cloud API (Meta) | Canal de conversa com os clientes |
| Borda/segurança do webhook | Cloudflare Workers | Validação de assinatura HMAC e resposta rápida à Meta |
| Infraestrutura | Docker, Docker Compose, Caddy (HTTPS automático) | Deploy reproduzível em qualquer VM Linux |
| Autenticação | JWT, bcrypt | Login isolado por empresa (multi-tenant) |

## 7. Conectar o WhatsApp à Meta

**Como ativar o WhatsApp**

Siga os passos na ordem. A empresa mantém seus próprios ativos e número; a plataforma cuida da conexão técnica, dos templates e da operação do agente de atendimento.

*Configuração por empresa.* Este é o mesmo guia que a plataforma mostra no ícone "?" do cartão do WhatsApp, em Canais.

**Visão geral do fluxo**

Cada etapa depende da anterior. O agente responde assim que o número é conectado; os templates aprovados liberam os avisos ao setor e o reengajamento.

Conta Meta → Portfólio + WABA → Número confirmado → Configuração do Agente → Conectar WhatsApp → Templates aprovados → Atendimento automático

**Responsabilidade de cada parte**

| Parte | Responsabilidade |
|---|---|
| Empresa | Possui a conta Meta, o Portfólio, a WABA, o número comercial, os setores e a base de conhecimento. |
| Plataforma | Conecta os ativos, protege credenciais, prepara templates e opera o agente. |
| Meta | Confirma o número, concede permissões e analisa os templates. |

**Passo 1 — Criar ou acessar uma conta pessoal da Meta**

A pessoa responsável entra com um perfil pessoal verdadeiro do Facebook. Se ainda não possuir perfil, deve criá-lo e concluir as verificações solicitadas pela Meta.

- O perfil pessoal precisa ter autoridade para administrar os ativos da empresa.
- Não crie um perfil pessoal com o nome da empresa; a identidade comercial ficará no Portfólio Empresarial e no WhatsApp Business.
- A senha e os códigos de acesso são informados somente nas telas oficiais da Meta.
- Exceção de homologação: enquanto o aplicativo da plataforma estiver em modo de desenvolvimento, o convidado precisa acessar developers.facebook.com, concluir o cadastro gratuito como desenvolvedor, aceitar os termos e depois aceitar o convite de Testador em developers.facebook.com/requests. Isso não faz parte do processo normal depois que o aplicativo for publicado e aprovado.

**Passo 2 — Criar o Portfólio, a WABA e cadastrar o número**

Antes de conectar o WhatsApp à plataforma, prepare os ativos empresariais e valide o número dentro da Meta.

- 2.1 — Acesse business.facebook.com com o perfil pessoal responsável e abra Configurações do negócio.
- 2.2 — No seletor de empresas, escolha Criar um Portfólio Empresarial. Informe o nome real da empresa, o nome do responsável e um e-mail comercial acessível; confirme o e-mail se a Meta solicitar.
- 2.3 — Complete os dados da empresa: em Configurações → Informações da empresa → Detalhes da empresa → Editar, preencha Razão social da empresa, País, Endereço, Cidade, Estado, CEP, Telefone comercial e Site da empresa, e clique em Salvar. A Identificação fiscal (EIN) é um número dos Estados Unidos e pode ficar em branco no Brasil. Preencha o endereço completo (rua, cidade, estado e CEP), não só o país: com dados incompletos a Meta bloqueia o envio (erros 131000 e 130497). Depois de salvar, a liberação pode levar algumas horas.
- 2.4 — Dentro do Portfólio correto, procure Contas → Contas do WhatsApp e escolha Adicionar. Crie uma Conta do WhatsApp Business para a empresa. WABA é essa conta empresarial administrada pela Meta; não é o aplicativo WhatsApp Business instalado no celular.
- 2.5 — Abra o WhatsApp Manager dessa WABA, acesse Números de telefone e escolha Adicionar número. Preencha o nome de exibição, categoria e descrição reais da empresa. A Meta analisa o nome de exibição: ele precisa ter relação demonstrável com a empresa, a marca, o produto ou o serviço. Evite nomes genéricos, slogans, excesso de símbolos e marcas de terceiros.
- 2.6 — Informe um número comercial controlado pela empresa. Para celular, mantenha chip ou eSIM ativo; para fixo, use ligação quando essa opção estiver disponível. Recomendamos um número dedicado ao agente, que não esteja em uso no aplicativo do WhatsApp.
- 2.7 — Escolha SMS ou ligação, receba o código diretamente no número e digite-o na Meta. Esse código de confirmação é diferente do PIN da verificação em duas etapas.
- 2.8 — Confirme que o número aparece como conectado ou verificado no WhatsApp Manager. Sobre o PIN da verificação em duas etapas: não crie nem altere um PIN só para preparar a integração, porque a plataforma define o PIN ao ativar o número na Cloud API. Se o número já tiver a verificação em duas etapas ativa, desative-a temporariamente em WhatsApp Manager → Números de telefone → Configurações → Verificação em duas etapas antes de conectar. Nunca informe o PIN fora das telas oficiais da Meta.
- 2.9 — Cadastre a forma de pagamento em WhatsApp Manager → Visão geral → Adicionar forma de pagamento (ou Configurações de pagamento), conferindo se está na WABA correta. Os avisos ao setor e o reengajamento (templates) são cobrados diretamente na conta empresarial correspondente, nunca pela plataforma; responder um cliente dentro da janela de 24 horas aberta por ele é gratuito.
- Se preferir, a própria janela de Conectar WhatsApp (Passo 4) também permite criar o Portfólio, a WABA e o número.
- A empresa não cria um aplicativo no Meta for Developers: o aplicativo técnico Agente de Atendimento já é fornecido pela plataforma.

**Passo 3 — Preencher a Configuração, os Setores e a Base de Conhecimento**

Crie a conta da empresa na plataforma (Criar conta) e informe os dados reais: é daqui que o agente tira as respostas e para onde ele encaminha.

- Configurações do Agente: nome do agente, contexto da empresa, roteiro da conversa e as Regras de Atendimento (responder só com base no conhecimento cadastrado e a mensagem para perguntas fora do escopo).
- Setores → Novo setor: cadastre cada setor (ex.: Financeiro, Suporte), com a descrição do que ele resolve e o WhatsApp do contato que recebe os encaminhamentos (com DDD).
- Base de Conhecimento → Novo item: horários, políticas, preços e dúvidas frequentes. O agente responde a partir desses itens.
- Os templates usam o nome do agente e o da empresa; por isso, preencha as Configurações do Agente antes de enviá-los.

**Passo 4 — Clicar em Conectar WhatsApp**

Em Canais → WhatsApp, clique em Conectar WhatsApp. A plataforma abre a janela oficial da Meta para autorizar os ativos já preparados.

- Faça login com o perfil pessoal responsável.
- Selecione o Portfólio Empresarial e a WABA preparados no Passo 2.
- Página do Facebook e Instagram não são necessárias para operar somente o WhatsApp.
- Revise as permissões e confirme o compartilhamento com o aplicativo Agente de Atendimento.

**Passo 5 — Confirmar o número conectado na plataforma**

Ao concluir a autorização, a plataforma consulta a Meta e preenche sozinha o Número do WhatsApp conectado, com a data e a hora da conexão.

- Não digite WABA ID, Phone Number ID nem token.
- Essas credenciais ficam protegidas no servidor e vinculadas somente à empresa autenticada.
- Para trocar de número ou renovar a permissão, use Renovar autorização Meta no mesmo cartão.

**Passo 6 — Revisar e enviar os quatro templates**

O agente só responde quem escreve primeiro, então não existe template de abordagem. Os quatro templates servem para avisar o setor humano e retomar conversas paradas.

- Aviso ao setor humano, Reencaminhamento, Atenção por suspeita de manipulação e Reengajamento já possuem textos operacionais preparados e fixos, para facilitar a aprovação.
- No envio, a plataforma preenche os dados reais do cliente e, nos avisos ao setor, um resumo do atendimento.
- É possível enviar cada template individualmente ou usar Enviar todos os templates pendentes. O resultado é o mesmo; o envio em conjunto é mais rápido.
- Se a Meta rejeitar um template, o motivo aparece no cartão e o botão Reenviar para análise volta a ficar disponível.
- O botão Atualizar status consulta a análise na hora. A plataforma também recebe as atualizações enviadas pela Meta.

**Passo 7 — Divulgar o número enquanto aguarda**

O agente já responde os clientes assim que o número é conectado; a aprovação dos templates só libera os avisos ao setor e o reengajamento.

- Divulgue o número do WhatsApp nos canais da empresa (site, redes sociais, materiais).
- Cada atendimento nasce sozinho na primeira mensagem do cliente; não é preciso cadastrar nem importar contatos.
- Enquanto os templates não forem aprovados, o setor não recebe o aviso de encaminhamento pelo WhatsApp.

**Passo 8 — Acompanhar o atendimento automático**

Não existe uma etapa adicional de ativação: com o número conectado e a base de conhecimento preenchida, o agente responde cada mensagem que chega.

- O agente consulta a Base de Conhecimento, responde sozinho o que estiver documentado e usa a mensagem de fora do escopo no resto.
- Quando o assunto exige uma pessoa, ele encaminha para o setor certo, que recebe o aviso pelo template aprovado.
- Tudo aparece em tempo real em Base de Atendimentos, Conversas e no Dashboard.

**Como funcionam as variáveis**

Não substitua os códigos por um cliente específico. O mesmo template aprovado atende todos os atendimentos, e a plataforma preenche cada envio separadamente.

```
Oi, {{1}}! Aqui é {{2}}, da {{3}}. Passando pra saber se você ainda precisa de ajuda com o seu atendimento — fico à disposição se quiser continuar.
```

- **{{1}}**: nome do cliente
- **{{2}}**: nome do agente
- **{{3}}**: nome da empresa

Exemplo (template de reengajamento): em um envio `{{1}}` vira “Ana”; no próximo, vira “João”. Nos avisos ao setor, as variáveis recebem nome e WhatsApp do cliente e um resumo do atendimento.

> **Importante sobre o período de aprovação**
>
> O agente já responde os clientes enquanto a Meta analisa os templates. O que fica bloqueado até a aprovação é o aviso ao setor pelo WhatsApp (encaminhamento, reencaminhamento e atenção) e o reengajamento de conversas paradas.

**Pronto para configurar?**

Comece pelos ativos da empresa ou volte para Canais. [Abrir Meta Business](https://business.facebook.com/) · [Ir para Canais](https://agenteatendimento.projetostechmauricio.lol/canais)

## 8. Segurança

- Senhas nunca são armazenadas em texto puro (hash com bcrypt).
- Sessões usam tokens JWT com expiração.
- Cada requisição à API é automaticamente filtrada pela empresa do usuário logado: uma empresa nunca acessa dados de outra, inclusive na busca semântica da base de conhecimento.
- O webhook do WhatsApp valida a assinatura HMAC da Meta antes de qualquer processamento, e cada mensagem é deduplicada pelo ID único atribuído pela Meta.
- O token de cada empresa fica só no backend e nunca vai para o navegador.
- O agente só encaminha para um setor que exista de verdade no banco da empresa, validado em código e nunca confiado apenas na escolha do modelo.
- O telefone de contato de cada setor é validado no backend (DDD + número).
- Se o aviso ao setor falhar, o agente é informado e não pode dizer ao cliente que encaminhou.
- Nenhuma chave de API, token ou senha fica no código-fonte: tudo vem de variáveis de ambiente, fora do controle de versão.

---

Projeto de portfólio construído para demonstrar arquitetura de agentes de IA aplicados a atendimento ao cliente, com foco em SaaS multi-tenant, busca semântica (RAG) com pgvector, orquestração de agentes com LangGraph, processamento assíncrono e integração oficial com a Meta (Embedded Signup e templates automatizados).
