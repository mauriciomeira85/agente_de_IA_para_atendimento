"use client";

// ==============================================================================
// ARQUIVO: app/cadastro/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Tela de Cadastro: onde uma NOVA empresa começa a usar a plataforma. É
// aqui que a arquitetura multi-tenant do produto entra em ação — ao
// preencher este formulário, o backend cria, em uma única operação, a
// empresa, o primeiro usuário e uma configuração de agente em branco,
// pronta para ser preenchida na aba "Configuração do Agente" (ver
// backend/app/rotas/autenticacao.py). Isso é o que permite "cinco novos
// clientes entrando simultaneamente" sem nenhum trabalho manual.
//
// Como este projeto fica público para qualquer pessoa testar, o
// formulário pede só o essencial (Nome, E-mail, Senha) — sem um campo
// separado de "Nome da empresa". O mesmo nome digitado é enviado para os
// dois campos que a API espera (nome_fantasia e nome_do_responsavel);
// quem quiser um nome de empresa diferente do seu nome pode ajustar
// depois, na aba "Configuração do Agente".
// ==============================================================================

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { cadastrarEmpresa, salvarToken, ErroDaApi } from "@/biblioteca/api";
import { useAutenticacao } from "@/biblioteca/autenticacao";

export default function PaginaDeCadastro() {
  const roteador = useRouter();
  const { definirSessao } = useAutenticacao();

  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function aoEnviarFormulario(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      const resultado = await cadastrarEmpresa({
        nome_fantasia: nome,
        nome_do_responsavel: nome,
        email,
        senha,
      });
      salvarToken(resultado.token_de_acesso);
      definirSessao({ nomeFantasia: resultado.nome_fantasia, nomeDoAgente: resultado.nome_do_agente });
      roteador.push("/painel");
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Não foi possível concluir o cadastro. Tente novamente.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-4 py-10 bg-marca-escuro">
      <div className="w-full max-w-sm bg-white border border-slate-200 rounded-xl shadow-lg p-8">
        <h1 className="text-xl font-semibold text-marca-escuro mb-1">Criar sua conta</h1>
        <p className="text-sm text-slate-500 mb-6">Cada empresa tem seu próprio Agente de Atendimento, isolado das demais.</p>

        <form onSubmit={aoEnviarFormulario} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Nome</label>
            <input
              required
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-marca-600"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">E-mail</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-marca-600"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Senha</label>
            <input
              type="password"
              required
              minLength={8}
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-marca-600"
            />
            <p className="text-xs text-slate-400 mt-1">Mínimo de 8 caracteres.</p>
          </div>

          {erro && <p className="text-sm text-red-600">{erro}</p>}

          <button
            type="submit"
            disabled={carregando}
            className="w-full rounded-lg bg-marca-600 text-white text-sm font-medium py-2.5 hover:bg-marca-700 disabled:opacity-60"
          >
            {carregando ? "Criando conta..." : "Criar conta"}
          </button>
        </form>

        <p className="text-sm text-slate-500 mt-6 text-center">
          Já tem conta?{" "}
          <Link href="/login" className="text-marca-700 font-medium hover:underline">
            Entrar
          </Link>
        </p>
      </div>
    </main>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo implementa a tela de Cadastro: cria a conta da empresa
// (dados de nome/e-mail/senha), salva o token devolvido pela API e leva
// o usuário direto ao Dashboard — de onde ele pode ir configurar o
// agente, cadastrar os Setores e a Base de Conhecimento e conectar o
// WhatsApp.
// ==============================================================================
