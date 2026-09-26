// ==============================================================================
// ARQUIVO: biblioteca/tipos.ts
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Este arquivo define os "formatos" (tipos do TypeScript) dos dados que o
// frontend troca com o backend. Eles espelham, propositalmente, os
// esquemas Pydantic definidos no backend (pasta backend/app/esquemas/) —
// assim, o editor de código já avisa se algum componente tentar usar um
// campo que não existe, antes mesmo de rodar a aplicação.
// ==============================================================================

export type StatusAtendimento = "recebido" | "em_atendimento" | "encaminhado" | "resolvido";

export interface Atendimento {
  id: number;
  nome: string;
  email: string | null;
  telefone: string | null;
  whatsapp: string | null;
  status: StatusAtendimento;
  id_setor: number | null;
  resumo_do_atendimento: string | null;
  numero_de_reaberturas: number;
  ultima_atividade_em: string | null;
  criado_em: string;
}

export interface CartoesDeQuantidade {
  total_de_atendimentos: number;
  em_atendimento: number;
  encaminhados: number;
  resolvidos: number;
}

export interface CartoesDeTaxa {
  taxa_de_encaminhamento: number;
  taxa_de_resolucao_automatica: number;
  taxa_de_reabertura: number;
}

export interface EtapaDoFunil {
  etapa: string;
  quantidade: number;
}

export interface PontoDeVolumePorDia {
  data: string;
  quantidade: number;
}

export interface PainelDados {
  cartoes_de_quantidade: CartoesDeQuantidade;
  cartoes_de_taxa: CartoesDeTaxa;
  funil_de_encaminhamento: EtapaDoFunil[];
  funil_de_resolucao: EtapaDoFunil[];
  volume_por_dia: PontoDeVolumePorDia[];
  setores_mais_acionados: EtapaDoFunil[];
}

export interface AreaDeAtuacao {
  paises: string[];
  estados: string[];
  municipios: string[];
}

export interface ConfiguracaoAgente {
  nome_do_agente: string;
  contexto_da_empresa: string;
  area_atuacao: AreaDeAtuacao;
  endereco_cep: string | null;
  endereco_rua: string | null;
  endereco_bairro: string | null;
  endereco_numero: string | null;
  endereco_complemento: string | null;
  endereco_detalhes_adicionais: string | null;
  nome_do_template_encaminhamento: string;
  nome_do_template_reengajamento: string;
  nome_do_template_reencaminhamento: string;
  nome_do_template_atencao: string;
  roteiro_conversa: string;
  // Regras de Atendimento — o guardrail deste projeto (ver Informacoes/Arquitetura.md, seção 4.3).
  responder_apenas_com_base_no_conhecimento: boolean;
  mensagem_fora_do_escopo: string;
}

export interface MensagemConversa {
  id: number;
  remetente: "cliente" | "agente_ia" | "atendente_humano" | "sistema";
  tipo_conteudo: "texto" | "audio" | "imagem" | "documento";
  conteudo: string;
  status_entrega: "sent" | "delivered" | "read" | "failed" | null;
  criado_em: string;
  // Só preenchidos quando a mensagem tem mídia de verdade salva (ver
  // backend/app/armazenamento_midia.py) — usados para montar a URL da
  // mídia (ver obterUrlDaMidiaDaMensagem em biblioteca/api.ts) e decidir
  // como reproduzir (imagem/vídeo/áudio/link de download).
  mime_type_da_midia: string | null;
  nome_do_arquivo_da_midia: string | null;
}

export interface ConversaResumo {
  id: number;
  id_atendimento: number;
  nome_atendimento: string;
  apelido: string | null;
  fixada: boolean;
  ultima_mensagem: string | null;
  atualizado_em: string;
}

export interface ConversaDetalhe {
  id: number;
  id_atendimento: number;
  nome_atendimento: string;
  apelido: string | null;
  fixada: boolean;
  mensagens: MensagemConversa[];
}

// Painel único de templates (aba Canais) — ver
// backend/app/rotas/templates_whatsapp.py.
export interface TemplateDoPainel {
  chave: string;
  titulo: string;
  descricao: string;
  categoria: string;
  nome: string;
  editavel: boolean;
  texto: string | null; // texto real enviado à Meta, com as variáveis {{n}}
  previa: string;
  status: string | null; // null = ainda não enviado | PENDING | APPROVED | REJECTED ...
  motivo: string | null;
  exemplos: string[] | null;
  legenda: string; // o que cada variável {{n}} recebe no envio
  id: string | null; // ID do template na Meta (usado para reenviar um rejeitado)
  texto_padrao: string | null; // só no editável: o modelo recomendado
}

export interface RascunhoDeTemplate {
  texto: string;
  previa: string;
  gerado_pela_ia: boolean;
  aviso: string | null;
}

export interface ResultadoDoEnvioDeTemplate {
  chave: string;
  nome: string;
  resultado: "enviado" | "ja_existia" | "erro";
  detalhe: string | null;
}

export interface CanalWhatsApp {
  id_numero_telefone_meta: string;
  numero_exibicao: string | null;
  conectado_em: string;
}

// Dados públicos que o botão "Conectar WhatsApp" (aba Canais) usa para
// montar a janela de login da Meta — ver biblioteca/embeddedSignup.ts.
export interface ConfiguracaoEmbeddedSignup {
  app_id: string;
  id_configuracao: string;
  versao_api: string;
  // true só para a conta autorizada a usar a conexão manual (ver
  // backend/app/configuracoes.py) — decide se o formulário extra aparece.
  mostrar_conexao_manual: boolean;
}

// Status de um dos quatro templates na Meta — null enquanto ainda não foi
// submetido; depois disso, "PENDING" | "APPROVED" | "REJECTED".
export interface TemplateWhatsApp {
  nome: string;
  status: string | null;
}

// Texto pronto de um dos quatro templates (com {{1}}..{{3}} já preenchidos
// com um exemplo) — só para conferência antes de submeter para análise da
// Meta. Diferente dos outros dois projetos da linhagem, nenhum desses
// templates é editável pela empresa (ver esquemas/canal.py no backend).
export interface PreviaDoTemplate {
  texto: string;
}

// Um departamento humano cadastrado pela empresa (ex.: Vendas, Financeiro,
// Suporte Técnico) — o destino real para onde o agente encaminha um
// atendimento (ver backend/app/modelos/setor.py).
export interface Setor {
  id: number;
  nome: string;
  contato_nome: string;
  contato_telefone: string;
  criado_em: string;
}

// Um item da Base de Conhecimento (FAQ, política, descrição de produto)
// que o agente consulta para responder dúvidas — o embedding usado na
// busca por similaridade é um detalhe interno, nunca aparece aqui (ver
// backend/app/esquemas/base_de_conhecimento.py).
export interface ItemDeConhecimento {
  id: number;
  titulo: string;
  conteudo: string;
  criado_em: string;
  atualizado_em: string;
}

/** Conexão de saída (aba Integrações): envia os dados do Dashboard para um CRM/aplicação externa. */
export interface IntegracaoSaida {
  id: number;
  nome_da_conexao: string;
  url_webhook: string;
  criado_em: string;
  ultimo_envio_em: string | null;
  ultimo_envio_com_sucesso: boolean | null;
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo centraliza todos os tipos de dados usados pelo frontend,
// espelhando os esquemas do backend: Atendimento, os formatos do Dashboard
// (PainelDados), a ConfiguracaoAgente (o formulário grande), as
// Conversas/Mensagens, Setor e ItemDeConhecimento (as duas peças novas
// deste projeto) e a IntegracaoSaida (envio de dados do Dashboard pra
// fora).
// ==============================================================================
