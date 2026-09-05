# AMG Logística — Cotação Rápida de Frete

Site responsivo para o cliente solicitar cotações de frete de forma rápida, simples e
padronizada, e para o time comercial responder com uma proposta.

Baseado no briefing `plano-amg-app.jpeg`.

## Stack

- **FastAPI** + **Jinja2** + HTML/CSS/JS puro (sem build step)
- **SQLAlchemy** + **SQLite** (`amg.db`)
- **Resend** para e-mail (opcional — sem chave, os e-mails vão para o console)

## Como rodar (local)

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # ajuste SECRET_KEY, ADMIN_USER, ADMIN_PASS...
python seed.py              # opcional: cotações de exemplo

uvicorn app.main:app --reload
```

Abra http://localhost:8000

- **Cliente:** `/` → `/cotacao` (formulário em 3 etapas) → confirmação → `/acompanhar`
- **Comercial:** `/admin/login` (credenciais do `.env`) → fila → responder proposta
- **Opções do formulário:** `/admin/opcoes/carroceria` e `/admin/opcoes/tipo_veiculo` —
  o time cria, edita (renomeia), ativa/inativa e remove as opções de carroceria e de
  tipo de veículo que o cliente escolhe na cotação (lista inicial criada automaticamente
  para cada categoria; guardadas na tabela genérica `opcoes`)
- **PDF da cotação:** na tela da cotação no painel, "Baixar PDF" / "Visualizar PDF" e
  "Enviar PDF ao cliente" (anexa o documento e dispara o e-mail via Resend). O PDF
  segue a identidade visual da AMG (gerado com `fpdf2`, sem dependências de sistema)

## Fluxo

1. Cliente preenche origem/destino, dados da carga e do transporte e envia.
2. A cotação é salva, o time comercial recebe um e-mail e o cliente recebe a confirmação
   com o código (`COT-2025-000001`) e um link de acompanhamento.
3. No painel, o comercial abre a cotação e lança a proposta (frete, pedágio, seguro 0,2%,
   prazo, validade). O cliente é avisado por e-mail.
4. O cliente abre a proposta e **Aceita** ou **Solicita ajuste**.

O cliente acompanha a cotação sem cadastro: pelo link do e-mail (token assinado) ou
informando código + e-mail em `/acompanhar`. O rascunho do formulário é salvo no
`localStorage` do navegador.

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
