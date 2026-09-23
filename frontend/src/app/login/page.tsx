"use client";

// ==============================================================================
// ARQUIVO: app/login/page.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Tela de Login: onde uma empresa que já tem conta na plataforma entra
// com e-mail e senha. Ao dar certo, o token de acesso devolvido pela API
// é salvo no navegador (ver biblioteca/api.ts) e o usuário é levado direto
// para o Dashboard.
// ==============================================================================

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { entrar, salvarToken, ErroDaApi } from "@/biblioteca/api";
import { useAutenticacao } from "@/biblioteca/autenticacao";

export default function PaginaDeLogin() {
  const roteador = useRouter();
  const { definirSessao } = useAutenticacao();

  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  async function aoEnviarFormulario(evento: React.FormEvent) {
    evento.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      const resultado = await entrar({ email, senha });
      salvarToken(resultado.token_de_acesso);
      definirSessao({ nomeFantasia: resultado.nome_fantasia, nomeDoAgente: resultado.nome_do_agente });
      roteador.push("/painel");
    } catch (e) {
      setErro(e instanceof ErroDaApi ? e.message : "Não foi possível entrar. Tente novamente.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center px-4 bg-marca-escuro">
      <div className="w-full max-w-sm bg-white border border-slate-200 rounded-xl shadow-lg p-8">
        <h1 className="text-xl font-semibold text-marca-escuro mb-1">Entrar na plataforma</h1>
        <p className="text-sm text-slate-500 mb-6">Acesse o painel do seu Agente de Atendimento.</p>

        <form onSubmit={aoEnviarFormulario} className="space-y-4">
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
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-marca-600"
            />
          </div>

          {erro && <p className="text-sm text-red-600">{erro}</p>}

          <button
            type="submit"
            disabled={carregando}
            className="w-full rounded-lg bg-marca-600 text-white text-sm font-medium py-2.5 hover:bg-marca-700 disabled:opacity-60"
          >
            {carregando ? "Entrando..." : "Entrar"}
          </button>
        </form>

        <p className="text-sm text-slate-500 mt-6 text-center">
          Ainda não tem conta?{" "}
          <Link href="/cadastro" className="text-marca-700 font-medium hover:underline">
            Cadastre sua empresa
          </Link>
        </p>
      </div>
    </main>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este arquivo implementa a tela de Login: formulário de e-mail/senha,
// chamada à API de autenticação e redirecionamento para o Dashboard
// assim que o login é bem-sucedido.
// ==============================================================================
