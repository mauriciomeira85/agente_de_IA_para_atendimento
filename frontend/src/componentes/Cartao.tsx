// ==============================================================================
// ARQUIVO: componentes/Cartao.tsx
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Componente visual simples, reaproveitado por todos os cartões do
// Dashboard (tanto os de quantidade — "Total de atendimentos",
// "Encaminhados" — como os de taxa percentual — "Taxa de resolução
// automática", "Taxa de reabertura", etc.). Manter isso em um único
// componente garante que todos os cartões tenham a mesma aparência,
// mudando só o número, o rótulo e a cor de destaque.
// ==============================================================================

interface PropriedadesDoCartao {
  rotulo: string;
  valor: string;
  // "positivo" (verde) pra métricas onde mais é melhor, "negativo"
  // (âmbar) pra métricas onde mais é um sinal de alerta — ex.: Taxa de
  // reabertura, onde um número alto indica que o agente está marcando
  // "resolvido" sem o cliente realmente ter ficado satisfeito.
  destaque?: "neutro" | "positivo" | "negativo";
}

export default function Cartao({ rotulo, valor, destaque = "neutro" }: PropriedadesDoCartao) {
  const corDoValor =
    destaque === "positivo" ? "text-emerald-600" : destaque === "negativo" ? "text-amber-600" : "text-marca-escuro";
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <p className="text-sm text-slate-500">{rotulo}</p>
      <p className={`text-2xl font-semibold mt-1 ${corDoValor}`}>{valor}</p>
    </div>
  );
}

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este componente desenha um cartão com um rótulo pequeno em cima e um
// valor grande embaixo — o bloco básico usado nas duas fileiras de
// cartões do Dashboard.
// ==============================================================================
