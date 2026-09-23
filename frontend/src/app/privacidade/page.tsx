// ==============================================================================
// ARQUIVO: app/privacidade/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Página pública de Política de Privacidade da plataforma (não exige login,
// nem depende de nenhuma empresa logada — é uma página só sobre COMO A
// PLATAFORMA em si funciona). Existe por uma exigência prática da Meta: pra
// publicar o app do WhatsApp Embedded Signup (Configurações do app > Básico
// > "URL da Política de Privacidade"), é obrigatório ter uma URL real
// apontando pra uma política — sem isso, o botão "Publicar" fica bloqueado
// e a Meta não entrega webhooks de mensagens reais (só testes manuais do
// próprio painel dela), mesmo com tudo o resto configurado corretamente.
//
// Quem clonar este projeto do GitHub e subir a própria instância, com o
// próprio app na Meta, deve ADAPTAR o conteúdo abaixo pro nome/domínio
// dela antes de publicar o app dela (ver README, seção "Conectar o
// WhatsApp").
// ==============================================================================

export default function PaginaDePrivacidade() {
  return (
    <main className="max-w-3xl mx-auto px-6 py-12 text-slate-700">
      <h1 className="text-2xl font-semibold text-marca-escuro mb-2">Política de Privacidade</h1>
      <p className="text-sm text-slate-500 mb-8">Última atualização: setembro de 2026</p>

      <div className="space-y-6 text-sm leading-relaxed">
        <p>
          Esta política descreve como o <strong>Agente de Atendimento</strong> (a plataforma disponível em{" "}
          <strong>agenteatendimento.projetostechmauricio.lol</strong>) coleta, usa e protege informações
          ao operar um agente de inteligência artificial para atendimento via WhatsApp em nome das
          empresas que se cadastram na plataforma.
        </p>

        <section>
          <h2 className="text-base font-semibold text-marca-escuro mb-2">1. Quem somos</h2>
          <p>
            O Agente de Atendimento é uma plataforma que permite a uma empresa conectar o próprio número
            de WhatsApp Business e configurar um agente de IA para responder, triar e encaminhar
            atendimentos recebidos de clientes dessa empresa, com base numa base de conhecimento
            cadastrada por ela.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-marca-escuro mb-2">2. Quais dados coletamos</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li>Dados de cadastro da empresa cliente da plataforma: nome, e-mail e senha (armazenada com hash, nunca em texto puro).</li>
            <li>Conteúdo das conversas de WhatsApp entre o agente e os clientes finais de cada empresa (mensagens de texto, áudio transcrito, imagens e documentos recebidos), necessário para o agente entender e responder ao atendimento.</li>
            <li>Itens de base de conhecimento cadastrados pela empresa (títulos e conteúdos de texto), usados para o agente responder perguntas de forma fundamentada.</li>
            <li>Metadados técnicos da integração com a Meta (identificadores de número de telefone e de conta comercial do WhatsApp), necessários para operar a Cloud API do WhatsApp.</li>
          </ul>
        </section>

        <section>
          <h2 className="text-base font-semibold text-marca-escuro mb-2">3. Como usamos esses dados</h2>
          <p>
            Os dados coletados são usados exclusivamente para operar o agente de atendimento: interpretar
            mensagens recebidas, consultar a base de conhecimento da empresa, decidir e executar ações
            (responder, encaminhar para um setor humano, marcar um atendimento como resolvido) e manter o
            histórico de conversas visível para a empresa dona daquele atendimento. Trechos de conversa
            podem ser processados por provedores de IA de terceiros (para geração de texto, transcrição de
            áudio e geração de embeddings de busca) estritamente para cumprir essa finalidade.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-marca-escuro mb-2">4. Compartilhamento de dados</h2>
          <p>
            Não vendemos nem compartilhamos dados de conversas com terceiros para fins de publicidade. Os
            dados de uma empresa nunca ficam visíveis para outra empresa cadastrada na plataforma — cada
            conta acessa somente os próprios atendimentos, configurações e base de conhecimento.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-marca-escuro mb-2">5. Retenção e exclusão</h2>
          <p>
            Os dados de uma empresa são mantidos enquanto a conta dela estiver ativa na plataforma. Uma
            empresa pode solicitar a exclusão dos próprios dados a qualquer momento pelo contato abaixo.
          </p>
        </section>

        <section>
          <h2 className="text-base font-semibold text-marca-escuro mb-2">6. Contato</h2>
          <p>
            Dúvidas sobre esta política ou solicitações relacionadas aos dados podem ser enviadas para o
            e-mail de contato cadastrado no aplicativo desta plataforma junto à Meta.
          </p>
        </section>

        <p className="text-xs text-slate-400 pt-4 border-t border-slate-200">
          Este projeto é um trabalho de portfólio que demonstra uma arquitetura de agente de IA para
          atendimento ao cliente via WhatsApp. Esta política existe para cumprir o requisito da Meta de
          publicação do aplicativo de integração com o WhatsApp Business Cloud API.
        </p>
      </div>
    </main>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Página pública e estática (sem login) com a Política de Privacidade da
// plataforma, exigida pela Meta como requisito para publicar o app do
// WhatsApp Embedded Signup (Configurações do app > Básico > "URL da
// Política de Privacidade"). Descreve, de forma honesta e sucinta, quais
// dados a plataforma coleta, como usa, com quem compartilha e como pedir
// exclusão — sem depender de nenhum dado dinâmico do banco.
// ==============================================================================
