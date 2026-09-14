# AMG Logística — Cotação de Frete (v2)

Aplicação completa do pipeline comercial da AMG: da cotação (rápida ou completa) até a
Ordem de Coleta enviada à Logística, com Agenda de Carregamentos para acompanhamento.

Baseado no briefing `plano-amg-app.jpeg` (v1) e no escopo final
`AMG_Aplicativo_Frete_Escopo_Final_com_Agenda.xlsx` / `aplicativo-amg-130926.jpg` (v2).

## Stack

- **FastAPI** + **Jinja2** + HTML/CSS/JS puro (sem build step)
- **SQLAlchemy** + **SQLite** (dev) / **Postgres** (produção)
- **Resend** para e-mail (opcional — sem chave, os e-mails vão para o console)
- **fpdf2** para o PDF da cotação (Python puro, sem dependência de sistema)

## Como rodar (local)

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # ajuste SECRET_KEY, ADMIN_USER, ADMIN_PASS...
python seed.py              # cotações de exemplo em cada etapa do pipeline

uvicorn app.main:app --reload
```

Abra http://localhost:8000

## O pipeline

1. **Cotação Rápida** (mínimo de campos, uso em campo) ou **Cotação Completa**
   (comprador no escritório) — `/cotacao` deixa escolher.
2. Comercial forma o preço internamente: **FC** (motorista + pedágio + impostos + seguro
   + outros custos) → **margem (%)** → **FE** (preço de venda). O cliente nunca vê FC nem
   a margem — só o FE, os adicionais efetivamente cobrados (diária, ajudante,
   empilhadeira, guincho/Munck, carga, descarga, outros) e o valor total.
3. Cliente decide pelo site: **Aprovar**, **Solicitar negociação** (com motivo — o
   comercial reprecifica e a versão anterior fica registrada no histórico) ou o comercial
   registra a decisão manualmente.
4. Aprovada, o cliente preenche a **Solicitação de Frete** (dados fiscais/operacionais).
5. Comercial valida e gera a **Ordem de Coleta**, depois **envia à Logística** — isso cria
   automaticamente um item na **Agenda de Carregamentos** (`/admin/agenda`, lista e
   calendário), com alertas HOJE/AMANHÃ/PRÓXIMO/ATRASADO.

Sem login/cadastro: o cliente é identificado pelo nome/empresa digitados em cada
cotação, e acompanha tudo pelo e-mail (`/acompanhar`) ou pelo link assinado enviado por
e-mail.

- **Comercial:** `/admin/login` → fila (`/admin`, com filtros por empresa/tipo/status) →
  formação de preço → decisão → solicitação de frete → Ordem de Coleta → Logística →
  agenda.
- **Opções do formulário:** `/admin/opcoes/carroceria` e `/admin/opcoes/tipo_veiculo` —
  o time cria, edita, ativa/inativa e remove as opções que o cliente escolhe na cotação.
- **PDF da cotação:** "Baixar PDF" / "Visualizar PDF" no painel — mostra só o valor do
  frete (FE), os adicionais cobrados e o valor total (nunca a formação de preço interna).

## Variáveis de ambiente

| Variável | Descrição |
|---|---|
| `SECRET_KEY` | Assina sessões e tokens de link do cliente |
| `ADMIN_USER` / `ADMIN_PASS` | Credenciais do painel `/admin` |
| `RESEND_API_KEY` | Chave do Resend; vazio = e-mails no console |
| `EMAIL_FROM` / `EMAIL_COMERCIAL` | Remetente e destino comercial |
| `BASE_URL` | URL pública, usada nos links dos e-mails |
| `DATABASE_URL` | Default `sqlite:///./amg.db`; use Postgres em produção |
| `ENV` | `dev` ou `prod` (em `prod` os cookies são `https_only`) |

## Docker

```bash
docker build -t amg-cotacao .
docker run -p 8000:8000 --env-file .env -v "$PWD/data:/app" amg-cotacao
```

> SQLite grava em `./amg.db`. Em produção, monte um volume persistente **ou** aponte
> `DATABASE_URL` para um Postgres (o SQLAlchemy já abstrai).

## Testes

```bash
pytest -q
```
