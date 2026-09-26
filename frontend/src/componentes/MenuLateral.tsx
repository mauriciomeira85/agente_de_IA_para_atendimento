"use client";

// ==============================================================================
// ARQUIVO: componentes/MenuLateral.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Este componente desenha a barra lateral fixa da plataforma, com as nove
// abas da interface: Dashboard, Base de Atendimentos, Conversas, Setores e
// Base de Conhecimento (as duas novas deste projeto), Configuração do
// Agente, Canais, Integrações e Configurações. Também mostra o nome da
// empresa logada e um botão de sair.
// ==============================================================================

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAutenticacao } from "@/biblioteca/autenticacao";

const ABAS = [
  { rotulo: "Dashboard", caminho: "/painel" },
  { rotulo: "Base de Atendimentos", caminho: "/atendimentos" },
  { rotulo: "Conversas", caminho: "/conversas" },
  { rotulo: "Setores", caminho: "/setores" },
  { rotulo: "Base de Conhecimento", caminho: "/base-conhecimento" },
  { rotulo: "Configurações do Agente", caminho: "/configuracao-agente" },
  { rotulo: "Canais", caminho: "/canais" },
  { rotulo: "Integrações", caminho: "/integracoes" },
  { rotulo: "Configurações", caminho: "/configuracoes" },
];

export default function MenuLateral() {
  const caminhoAtual = usePathname();
  const { sessao, sair } = useAutenticacao();

  return (
    <aside className="w-52 shrink-0 sticky top-0 h-screen bg-marca-escuro border-r border-white/10 flex flex-col">
      <div className="px-5 py-6 border-b border-white/10 shrink-0 flex items-center gap-3">
        <span className="shrink-0 w-9 h-9 rounded-full bg-marca-400 text-marca-escuro text-sm font-bold flex items-center justify-center">
          {(sessao?.nomeFantasia || "?").trim().charAt(0).toUpperCase()}
        </span>
        <p className="text-sm font-semibold text-white truncate">{sessao?.nomeFantasia || "Sua empresa"}</p>
      </div>

      <nav className="flex-1 py-4 overflow-y-auto">
        {ABAS.map((aba) => {
          const ativo = caminhoAtual === aba.caminho || caminhoAtual.startsWith(`${aba.caminho}/`);
          return (
            <Link
              key={aba.caminho}
              href={aba.caminho}
              className={`block px-5 py-2.5 text-sm border-l-2 transition-colors ${
                ativo
                  ? "border-marca-400 text-white font-medium bg-white/10"
                  : "border-transparent text-white/60 hover:text-white hover:bg-white/5"
              }`}
            >
              {aba.rotulo}
            </Link>
          );
        })}
      </nav>

      <div className="px-5 py-4 border-t border-white/10 shrink-0">
        <button onClick={sair} className="text-sm text-white/50 hover:text-white">
          Sair da conta
        </button>
      </div>
    </aside>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este componente é a navegação principal da plataforma: lista as nove
// abas, destaca a aba atual com base na URL e oferece o botão de logout.
// ==============================================================================
