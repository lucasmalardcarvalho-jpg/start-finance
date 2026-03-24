# 💚 Start Finance — Bot de Finanças no Telegram

Bot inteligente que registra seus gastos e receitas diretamente pelo Telegram,
com transcrição de áudio e integração com Google Sheets.

---

## 🚀 Como configurar (passo a passo)

### 1. Variáveis de Ambiente no Railway

Configure estas variáveis no painel do Railway → seu projeto → Variables:

| Variável | Valor |
|---|---|
| `TELEGRAM_TOKEN` | Token do seu bot (do BotFather) |
| `GEMINI_API_KEY` | Chave da API do Google Gemini (gratuita) |
| `GOOGLE_CREDENTIALS_JSON` | JSON das credenciais do Google Sheets |
| `SHEET_NAME` | `Start Finance` |

### 2. Estrutura da Planilha Google Sheets

Crie uma planilha chamada **"Start Finance"** com uma aba chamada **"Transações"**
e esses cabeçalhos na linha 1:

```
Data | Hora | Valor | Tipo | Categoria | Subcategoria | Descrição | Localização | Canal | Mês/Ano | Status
```

### 3. Como usar o bot

Abra o Telegram, encontre seu bot e mande mensagens como:
- "Gastei R$45 no almoço hoje"
- "Paguei R$200 de conta de luz ontem à noite"
- "Recebi R$3500 de salário"
- 🎤 Ou mande um áudio falando o gasto!

### 4. Comandos disponíveis

| Comando | Função |
|---|---|
| `/start` | Mensagem de boas-vindas |
| `/resumo` | Resumo do mês atual |
| `/top` | Top 3 categorias de gastos |
| `/ajuda` | Como usar o bot |

---

## 🛠️ Tecnologias

- **python-telegram-bot** — Integração com Telegram
- **OpenAI Whisper** — Transcrição de áudios (local, gratuito)
- **Google Gemini API** — Extração inteligente de dados (gratuito)
- **gspread** — Integração com Google Sheets
- **Railway** — Hospedagem gratuita

---

Feito com 💚 para o Start Finance
