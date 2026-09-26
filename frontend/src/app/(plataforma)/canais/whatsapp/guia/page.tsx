// ==============================================================================
// ARQUIVO: app/(plataforma)/canais/whatsapp/guia/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Guia "Como ativar o WhatsApp", aberto pelo ícone "?" do cartão do
// WhatsApp na aba Canais. Mesmo formato do guia do Impulso AI Agent
// (26/09/2026, pedido do usuário para padronizar os três agentes), com os
// passos adaptados ao atendimento receptivo: da conta pessoal na Meta até o
// primeiro atendimento automático.
// ==============================================================================

import Link from "next/link";
import Icone, { type NomeDoIcone } from "@/componentes/Icones";

const PASSOS: { icone: NomeDoIcone; titulo: string; descricao: string; detalhes: string[] }[] = [
  {
    icone: "pessoa",
    titulo: "Criar ou acessar uma conta pessoal da Meta",
    descricao:
      "A pessoa responsável entra com um perfil pessoal verdadeiro do Facebook. Se ainda não possuir perfil, deve criá-lo e concluir as verificações solicitadas pela Meta.",
    detalhes: [
      "O perfil pessoal precisa ter autoridade para administrar os ativos da empresa.",
      "Não crie um perfil pessoal com o nome da empresa; a identidade comercial ficará no Portfólio Empresarial e no WhatsApp Business.",
      "A senha e os códigos de acesso são informados somente nas telas oficiais da Meta.",
      "Exceção de homologação: enquanto o aplicativo da plataforma estiver em modo de desenvolvimento, o convidado precisa acessar developers.facebook.com, concluir o cadastro gratuito como desenvolvedor, aceitar os termos e depois aceitar o convite de Testador em developers.facebook.com/requests. Isso não faz parte do processo normal depois que o aplicativo for publicado e aprovado.",
    ],
  },
  {
    icone: "empresa",
    titulo: "Criar o Portfólio, a WABA e cadastrar o número",
    descricao:
      "Antes de conectar o WhatsApp à plataforma, prepare os ativos empresariais e valide o número dentro da Meta.",
    detalhes: [
      "2.1 — Acesse business.facebook.com com o perfil pessoal responsável e abra Configurações do negócio.",
      "2.2 — No seletor de empresas, escolha Criar um Portfólio Empresarial. Informe o nome real da empresa, o nome do responsável e um e-mail comercial acessível; confirme o e-mail se a Meta solicitar.",
      "2.3 — Complete os dados da empresa: em Configurações → Informações da empresa → Detalhes da empresa → Editar, preencha Razão social da empresa, País, Endereço, Cidade, Estado, CEP, Telefone comercial e Site da empresa, e clique em Salvar. A Identificação fiscal (EIN) é um número dos Estados Unidos e pode ficar em branco no Brasil. Preencha o endereço completo (rua, cidade, estado e CEP), não só o país: com dados incompletos a Meta bloqueia o envio (erros 131000 e 130497). Depois de salvar, a liberação pode levar algumas horas.",
      "2.4 — Dentro do Portfólio correto, procure Contas → Contas do WhatsApp e escolha Adicionar. Crie uma Conta do WhatsApp Business para a empresa. WABA é essa conta empresarial administrada pela Meta; não é o aplicativo WhatsApp Business instalado no celular.",
      "2.5 — Abra o WhatsApp Manager dessa WABA, acesse Números de telefone e escolha Adicionar número. Preencha o nome de exibição, categoria e descrição reais da empresa. A Meta analisa o nome de exibição: ele precisa ter relação demonstrável com a empresa, a marca, o produto ou o serviço. Evite nomes genéricos, slogans, excesso de símbolos e marcas de terceiros.",
      "2.6 — Informe um número comercial controlado pela empresa. Para celular, mantenha chip ou eSIM ativo; para fixo, use ligação quando essa opção estiver disponível. Recomendamos um número dedicado ao agente, que não esteja em uso no aplicativo do WhatsApp.",
      "2.7 — Escolha SMS ou ligação, receba o código diretamente no número e digite-o na Meta. Esse código de confirmação é diferente do PIN da verificação em duas etapas.",
      "2.8 — Confirme que o número aparece como conectado ou verificado no WhatsApp Manager. Sobre o PIN da verificação em duas etapas: não crie nem altere um PIN só para preparar a integração, porque a plataforma define o PIN ao ativar o número na Cloud API. Se o número já tiver a verificação em duas etapas ativa, desative-a temporariamente em WhatsApp Manager → Números de telefone → Configurações → Verificação em duas etapas antes de conectar. Nunca informe o PIN fora das telas oficiais da Meta.",
      "2.9 — Cadastre a forma de pagamento em WhatsApp Manager → Visão geral → Adicionar forma de pagamento (ou Configurações de pagamento), conferindo se está na WABA correta. Os avisos ao setor e o reengajamento (templates) são cobrados diretamente na conta empresarial correspondente, nunca pela plataforma; responder um cliente dentro da janela de 24 horas aberta por ele é gratuito.",
      "Se preferir, a própria janela de Conectar WhatsApp (Passo 4) também permite criar o Portfólio, a WABA e o número.",
      "A empresa não cria um aplicativo no Meta for Developers: o aplicativo técnico Agente de Atendimento já é fornecido pela plataforma.",
    ],
  },
  {
    icone: "robo",
    titulo: "Preencher a Configuração, os Setores e a Base de Conhecimento",
    descricao:
      "Crie a conta da empresa na plataforma (Criar conta) e informe os dados reais: é daqui que o agente tira as respostas e para onde ele encaminha.",
    detalhes: [
      "Configurações do Agente: nome do agente, contexto da empresa, roteiro da conversa e as Regras de Atendimento (responder só com base no conhecimento cadastrado e a mensagem para perguntas fora do escopo).",
      "Setores → Novo setor: cadastre cada setor (ex.: Financeiro, Suporte), com a descrição do que ele resolve e o WhatsApp do contato que recebe os encaminhamentos (com DDD).",
      "Base de Conhecimento → Novo item: horários, políticas, preços e dúvidas frequentes. O agente responde a partir desses itens.",
      "Os templates usam o nome do agente e o da empresa; por isso, preencha as Configurações do Agente antes de enviá-los.",
    ],
  },
  {
    icone: "conexao",
    titulo: "Clicar em Conectar WhatsApp",
    descricao:
      "Em Canais → WhatsApp, clique em Conectar WhatsApp. A plataforma abre a janela oficial da Meta para autorizar os ativos já preparados.",
    detalhes: [
      "Faça login com o perfil pessoal responsável.",
      "Selecione o Portfólio Empresarial e a WABA preparados no Passo 2.",
      "Página do Facebook e Instagram não são necessárias para operar somente o WhatsApp.",
      "Revise as permissões e confirme o compartilhamento com o aplicativo Agente de Atendimento.",
    ],
  },
  {
    icone: "escudo",
    titulo: "Confirmar o número conectado na plataforma",
    descricao:
      "Ao concluir a autorização, a plataforma consulta a Meta e preenche sozinha o Número do WhatsApp conectado, com a data e a hora da conexão.",
    detalhes: [
      "Não digite WABA ID, Phone Number ID nem token.",
      "Essas credenciais ficam protegidas no servidor e vinculadas somente à empresa autenticada.",
      "Para trocar de número ou renovar a permissão, use Renovar autorização Meta no mesmo cartão.",
    ],
  },
  {
    icone: "documento_ok",
    titulo: "Revisar e enviar os quatro templates",
    descricao:
      "O agente só responde quem escreve primeiro, então não existe template de abordagem. Os quatro templates servem para avisar o setor humano e retomar conversas paradas.",
    detalhes: [
      "Aviso ao setor humano, Reencaminhamento, Atenção por suspeita de manipulação e Reengajamento já possuem textos operacionais preparados e fixos, para facilitar a aprovação.",
      "No envio, a plataforma preenche os dados reais do cliente e, nos avisos ao setor, um resumo do atendimento.",
      "É possível enviar cada template individualmente ou usar Enviar todos os templates pendentes. O resultado é o mesmo; o envio em conjunto é mais rápido.",
      "Se a Meta rejeitar um template, o motivo aparece no cartão e o botão Reenviar para análise volta a ficar disponível.",
      "O botão Atualizar status consulta a análise na hora. A plataforma também recebe as atualizações enviadas pela Meta.",
    ],
  },
  {
    icone: "importar",
    titulo: "Divulgar o número enquanto aguarda",
    descricao:
      "O agente já responde os clientes assim que o número é conectado; a aprovação dos templates só libera os avisos ao setor e o reengajamento.",
    detalhes: [
      "Divulgue o número do WhatsApp nos canais da empresa (site, redes sociais, materiais).",
      "Cada atendimento nasce sozinho na primeira mensagem do cliente; não é preciso cadastrar nem importar contatos.",
      "Enquanto os templates não forem aprovados, o setor não recebe o aviso de encaminhamento pelo WhatsApp.",
    ],
  },
  {
    icone: "relogio",
    titulo: "Acompanhar o atendimento automático",
    descricao:
      "Não existe uma etapa adicional de ativação: com o número conectado e a base de conhecimento preenchida, o agente responde cada mensagem que chega.",
    detalhes: [
      "O agente consulta a Base de Conhecimento, responde sozinho o que estiver documentado e usa a mensagem de fora do escopo no resto.",
      "Quando o assunto exige uma pessoa, ele encaminha para o setor certo, que recebe o aviso pelo template aprovado.",
      "Tudo aparece em tempo real em Base de Atendimentos, Conversas e no Dashboard.",
    ],
  },
];

const FLUXO = [
  "Conta Meta",
  "Portfólio + WABA",
  "Número confirmado",
  "Configuração do Agente",
  "Conectar WhatsApp",
  "Templates aprovados",
  "Atendimento automático",
];

const cartao = "rounded-xl border border-slate-200 bg-white";

export default function PaginaDoGuiaDoWhatsApp() {
  return (
    <div className="mx-auto max-w-5xl space-y-8 pb-12">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <Link
            href="/canais"
            className="mb-2 -ml-1 inline-flex items-center gap-2 rounded-lg px-2 py-1 text-sm text-slate-600 hover:bg-slate-100"
          >
            <Icone nome="voltar" /> Voltar para Canais
          </Link>
          <h1 className="flex items-center gap-2 text-2xl font-semibold text-marca-escuro">
            <Icone nome="mensagem" className="h-6 w-6 text-marca-500" /> Como ativar o WhatsApp
          </h1>
          <p className="mt-1 max-w-3xl text-sm leading-relaxed text-slate-500">
            Siga os passos na ordem. A empresa mantém seus próprios ativos e número; a plataforma cuida da conexão
            técnica, dos templates e da operação do agente de atendimento.
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-1 rounded-full border border-emerald-300 px-2.5 py-1 text-xs font-medium text-emerald-700">
          <Icone nome="escudo" /> Configuração por empresa
        </span>
      </div>

      <section className="rounded-xl border border-marca-100 bg-marca-50/60 p-6">
        <h2 className="text-lg font-semibold text-marca-escuro">Visão geral do fluxo</h2>
        <p className="mt-1 text-sm text-slate-500">
          Cada etapa depende da anterior. O agente responde assim que o número é conectado; os templates aprovados
          liberam os avisos ao setor e o reengajamento.
        </p>
        <div className="mt-4 flex flex-col items-stretch gap-2 lg:flex-row lg:items-center">
          {FLUXO.map((item, indice) => (
            <div key={item} className="contents">
              <div className="flex min-h-14 flex-1 items-center justify-center rounded-xl border border-slate-200 bg-white px-3 py-2 text-center text-xs font-semibold text-marca-escuro">
                {item}
              </div>
              {indice < FLUXO.length - 1 && (
                <Icone nome="seta_abaixo" className="mx-auto h-4 w-4 shrink-0 text-marca-500 lg:-rotate-90" />
              )}
            </div>
          ))}
        </div>
      </section>

      <section className={`${cartao} p-6`}>
        <h2 className="text-lg font-semibold text-marca-escuro">Responsabilidade de cada parte</h2>
        <div className="mt-4 grid gap-3 text-sm md:grid-cols-3">
          <div className="rounded-lg border border-slate-200 p-4">
            <p className="font-semibold text-marca-escuro">Empresa</p>
            <p className="mt-1 text-slate-500">Possui a conta Meta, o Portfólio, a WABA, o número comercial, os setores e a base de conhecimento.</p>
          </div>
          <div className="rounded-lg border border-slate-200 p-4">
            <p className="font-semibold text-marca-escuro">Plataforma</p>
            <p className="mt-1 text-slate-500">
              Conecta os ativos, protege credenciais, prepara templates e opera o agente.
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 p-4">
            <p className="font-semibold text-marca-escuro">Meta</p>
            <p className="mt-1 text-slate-500">Confirma o número, concede permissões e analisa os templates.</p>
          </div>
        </div>
      </section>

      <section>
        {PASSOS.map((passo, indice) => (
          <div key={passo.titulo} className="relative grid grid-cols-[3rem_1fr] gap-4">
            <div className="flex flex-col items-center">
              <span className="z-10 flex h-12 w-12 items-center justify-center rounded-full border-2 border-marca-500 bg-white font-bold text-marca-600">
                {indice + 1}
              </span>
              {indice < PASSOS.length - 1 && <span className="h-full w-px bg-slate-200" />}
            </div>
            <div className={`${cartao} mb-5 p-6`}>
              <div className="flex items-center gap-2 text-marca-600">
                <Icone nome={passo.icone} className="h-5 w-5" />
                <span className="text-xs font-bold uppercase tracking-wide">Passo {indice + 1}</span>
              </div>
              <h3 className="mt-2 text-lg font-semibold text-marca-escuro">{passo.titulo}</h3>
              <p className="mt-1 text-sm leading-relaxed text-slate-500">{passo.descricao}</p>
              <ul className="mt-4 space-y-2 text-sm text-slate-600">
                {passo.detalhes.map((detalhe) => (
                  <li key={detalhe} className="flex gap-2">
                    <Icone nome="confirmado" className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                    <span>{detalhe}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </section>

      <section className={`${cartao} p-6`}>
        <h2 className="text-lg font-semibold text-marca-escuro">Como funcionam as variáveis</h2>
        <p className="mt-1 text-sm text-slate-500">
          Não substitua os códigos por um cliente específico. O mesmo template aprovado atende todos os atendimentos,
          e a plataforma preenche cada envio separadamente.
        </p>
        <div className="mt-4 whitespace-pre-wrap rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm leading-relaxed">
          {"Oi, {{1}}! Aqui é {{2}}, da {{3}}. Passando pra saber se você ainda precisa de ajuda com o seu atendimento — fico à disposição se quiser continuar."}
        </div>
        <div className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
          <p><strong>{"{{1}}"}</strong>: nome do cliente</p>
          <p><strong>{"{{2}}"}</strong>: nome do agente</p>
          <p><strong>{"{{3}}"}</strong>: nome da empresa</p>
        </div>
        <p className="mt-3 text-xs leading-relaxed text-slate-500">
          Exemplo (template de reengajamento): em um envio <code>{"{{1}}"}</code> vira “Ana”; no próximo, vira “João”.
          Nos avisos ao setor, as variáveis recebem nome e WhatsApp do cliente e um resumo do atendimento.
        </p>
      </section>

      <section className="rounded-xl border border-amber-300 bg-amber-50 p-6 text-sm text-amber-950">
        <p className="font-semibold">Importante sobre o período de aprovação</p>
        <p className="mt-1 leading-relaxed">
          O agente já responde os clientes enquanto a Meta analisa os templates. O que fica bloqueado até a aprovação
          é o aviso ao setor pelo WhatsApp (encaminhamento, reencaminhamento e atenção) e o reengajamento de conversas
          paradas.
        </p>
      </section>

      <section className="flex flex-col justify-between gap-4 rounded-xl border border-emerald-200 bg-emerald-50/60 p-6 sm:flex-row sm:items-center">
        <div>
          <p className="font-semibold text-marca-escuro">Pronto para configurar?</p>
          <p className="text-sm text-slate-500">Comece pelos ativos da empresa ou volte para Canais.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href="https://business.facebook.com/"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Abrir Meta Business <Icone nome="link_externo" />
          </a>
          <Link
            href="/canais"
            className="inline-flex items-center rounded-lg bg-marca-600 px-4 py-2 text-sm font-medium text-white hover:bg-marca-700"
          >
            Ir para Canais
          </Link>
        </div>
      </section>
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Guia do WhatsApp no formato do Impulso AI Agent: visão geral do fluxo,
// responsabilidades (empresa, plataforma, Meta), os 8 passos da conta Meta
// até o atendimento automático, como funcionam as variáveis dos
// templates e o aviso sobre o período de aprovação.
// ==============================================================================
