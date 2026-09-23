# Webhook do WhatsApp (Cloudflare Worker)

Este Worker é a porta de entrada dos eventos da Meta (WhatsApp Cloud API). Ele confere a assinatura oficial da Meta, responde rápido (exigência da própria Meta) e repassa o conteúdo já validado para o backend, que fica na VM.

## Por que um Worker separado, em vez de a Meta falar direto com o backend?

- **Endereço público estável**: o Worker já sobe com uma URL HTTPS confiável (`*.workers.dev`), independente da VM ter ou não um domínio/certificado configurado.
- **Segurança**: a verificação da assinatura HMAC (`X-Hub-Signature-256`) acontece aqui, então o backend nunca recebe tráfego não verificado.
- **Velocidade**: a Meta exige uma resposta HTTP 200 em poucos segundos — o Worker responde na hora e repassa o conteúdo em segundo plano.

## Como implantar

```bash
cd infra/cloudflare-webhook
npm install
npx wrangler login

# Segredos (nunca ficam no código nem no repositório):
npx wrangler secret put META_APP_SECRET
npx wrangler secret put META_VERIFY_TOKEN
npx wrangler secret put BACKEND_WEBHOOK_SECRET   # o mesmo valor de backend_webhook_secret no .env do backend

npx wrangler deploy
```

Depois do backend estar publicado, configure também:

```bash
npx wrangler secret put BACKEND_WEBHOOK_URL   # ex.: https://seu-endereco-publico/api/webhooks/whatsapp
```

## Configuração no painel da Meta for Developers

1. Produto **WhatsApp** → **Configuration** → **Webhook**.
2. **Callback URL**: `https://<seu-worker>.workers.dev/webhook`
3. **Verify token**: o mesmo valor cadastrado em `META_VERIFY_TOKEN`.
4. Assine o campo **messages**.
