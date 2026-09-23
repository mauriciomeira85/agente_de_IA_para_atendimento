// ==============================================================================
// ARQUIVO: infra/cloudflare-webhook/src/index.js
// ------------------------------------------------------------------------------
// INTRODUÇÃO
//
// Este arquivo é um Worker do Cloudflare — um pequeno programa que roda
// "na borda" da internet (bem perto de quem está enviando a requisição),
// sem precisar de um servidor tradicional. Ele é a PRIMEIRA parada de
// tudo que a Meta manda sobre o WhatsApp da plataforma, antes mesmo de
// chegar ao backend (FastAPI) na VM.
//
// Por que ter esse "intermediário" em vez de mandar a Meta falar direto
// com o backend? Três motivos:
//
//   1) Endereço público estável: o Worker já nasce com um endereço HTTPS
//      público e confiável (algo.workers.dev), sem depender da VM estar
//      sempre no ar com um domínio/certificado próprio.
//   2) Segurança: ele confere a assinatura oficial da Meta
//      (X-Hub-Signature-256, calculada com o App Secret) ANTES de deixar
//      qualquer coisa passar — o backend nunca recebe um evento não
//      verificado.
//   3) Resposta rápida: a Meta exige uma resposta HTTP 200 em poucos
//      segundos. O Worker responde imediatamente e repassa o conteúdo
//      para o backend em segundo plano (ctx.waitUntil), sem fazer a Meta
//      esperar o processamento da IA.
//
// Este arquivo não faz nenhuma chamada de IA nem entende o conteúdo da
// mensagem — ele só verifica, confia e repassa. Toda a lógica de negócio
// (quem é o atendimento, o que o agente responde, etc.) mora no backend, em
// backend/app/rotas/whatsapp_webhook.py.
// ==============================================================================

const encoder = new TextEncoder();

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function hexToBytes(hex) {
  if (!/^[0-9a-f]{64}$/i.test(hex)) return null;
  const bytes = new Uint8Array(32);
  for (let i = 0; i < 32; i += 1) {
    bytes[i] = Number.parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

// Confere se a assinatura enviada pela Meta no cabeçalho
// "X-Hub-Signature-256" realmente bate com o conteúdo recebido, calculada
// com o segredo do app (META_APP_SECRET). Isso garante que o evento
// realmente veio da Meta, e não de qualquer pessoa que descobrisse a URL.
async function hasValidMetaSignature(secret, signatureHeader, rawBody) {
  if (!secret || !signatureHeader?.startsWith("sha256=")) return false;
  const signature = hexToBytes(signatureHeader.slice(7));
  if (!signature) return false;

  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"],
  );

  return crypto.subtle.verify(
    "HMAC",
    key,
    signature,
    encoder.encode(rawBody),
  );
}

// Repassa o evento já validado para o backend real (a API na VM),
// incluindo um segredo próprio (BACKEND_WEBHOOK_SECRET) para o backend
// confirmar que a chamada realmente veio deste Worker.
async function forwardToBackend(env, rawBody, signatureHeader) {
  if (!env.BACKEND_WEBHOOK_URL) return;

  const headers = {
    "content-type": "application/json",
    "x-webhook-source": "meta-whatsapp",
    "x-hub-signature-256": signatureHeader,
  };

  if (env.BACKEND_WEBHOOK_SECRET) {
    headers.authorization = `Bearer ${env.BACKEND_WEBHOOK_SECRET}`;
  }

  const response = await fetch(env.BACKEND_WEBHOOK_URL, {
    method: "POST",
    headers,
    body: rawBody,
  });

  if (!response.ok) {
    console.error("Backend forwarding failed", {
      status: response.status,
      statusText: response.statusText,
    });
  }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Rota de health check — usada para confirmar que o Worker está no ar.
    if (url.pathname === "/" || url.pathname === "/health") {
      return json({
        ok: true,
        service: "Agente de Atendimento Meta webhook",
      });
    }

    if (url.pathname !== "/webhook") {
      return json({ error: "Not found" }, 404);
    }

    // A Meta chama esta rota com GET uma única vez, ao configurar o
    // webhook no painel — é a "verificação de propriedade" do endereço.
    if (request.method === "GET") {
      const mode = url.searchParams.get("hub.mode");
      const verifyToken = url.searchParams.get("hub.verify_token");
      const challenge = url.searchParams.get("hub.challenge");

      if (
        mode === "subscribe" &&
        env.META_VERIFY_TOKEN &&
        verifyToken === env.META_VERIFY_TOKEN &&
        challenge
      ) {
        return new Response(challenge, {
          status: 200,
          headers: { "content-type": "text/plain; charset=utf-8" },
        });
      }

      return json({ error: "Verification failed" }, 403);
    }

    // A partir daqui, é o tráfego de verdade: mensagens novas e
    // atualizações de status, enviadas via POST pela Meta.
    if (request.method === "POST") {
      const rawBody = await request.text();
      const signatureHeader = request.headers.get("x-hub-signature-256") || "";
      const valid = await hasValidMetaSignature(
        env.META_APP_SECRET,
        signatureHeader,
        rawBody,
      );

      if (!valid) {
        return json({ error: "Invalid signature" }, 401);
      }

      let payload;
      try {
        payload = JSON.parse(rawBody);
      } catch {
        return json({ error: "Invalid JSON" }, 400);
      }

      console.log("Validated Meta webhook", {
        object: payload?.object ?? null,
        entries: Array.isArray(payload?.entry) ? payload.entry.length : 0,
      });

      // "ctx.waitUntil" deixa o repasse acontecer DEPOIS de já ter
      // respondido 200 para a Meta — assim o tempo do backend processar a
      // IA nunca atrasa a confirmação de recebimento exigida pela Meta.
      if (env.BACKEND_WEBHOOK_URL) {
        ctx.waitUntil(
          forwardToBackend(env, rawBody, signatureHeader).catch((error) => {
            console.error("Backend forwarding error", {
              message: error instanceof Error ? error.message : String(error),
            });
          }),
        );
      }

      return json({ received: true });
    }

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204 });
    }

    return json({ error: "Method not allowed" }, 405);
  },
};

// ==============================================================================
// RESUMO
// ------------------------------------------------------------------------------
// Este Worker responde por três frentes: confirma a verificação inicial
// da Meta (GET), valida a assinatura HMAC de cada evento recebido (POST)
// e repassa o conteúdo já validado para o backend em segundo plano,
// respondendo à Meta imediatamente. Toda a inteligência do agente (ler a
// mensagem, decidir a resposta, atualizar o status do atendimento) acontece
// depois, no backend — este arquivo só garante que só chega ali tráfego
// legítimo da Meta.
// ==============================================================================
