"""
╔══════════════════════════════════════╗
║   START FINANCE — Bot Principal      ║
║   Telegram + Google Sheets + IA      ║
╚══════════════════════════════════════╝
"""

import os
import json
import logging
import tempfile
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler, CallbackQueryHandler,
    CommandHandler, filters, ContextTypes
)

from sheets_manager import SheetsManager
from ai_extractor import AIExtractor

# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Configurações ──────────────────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_TOKEN")
sheets = SheetsManager()
extractor = AIExtractor()

# ── Comando /start ─────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.effective_user.first_name
    msg = (
        f"💚 Olá, *{nome}*! Bem-vindo ao *Start Finance*!\n\n"
        "Eu sou seu assistente financeiro pessoal. "
        "Registre seus gastos e receitas de forma simples — "
        "basta me mandar uma mensagem de texto ou um áudio!\n\n"
        "📝 *Exemplos do que você pode me dizer:*\n"
        "• \"Gastei R$45 no almoço hoje\"\n"
        "• \"Paguei R$200 de conta de luz ontem\"\n"
        "• \"Recebi R$3500 de salário\"\n"
        "• 🎤 Pode mandar áudio também!\n\n"
        "📋 *Comandos disponíveis:*\n"
        "/resumo — Resumo do mês atual\n"
        "/metas — Suas metas financeiras\n"
        "/top — Top 3 categorias de gastos\n"
        "/ajuda — Como usar o Start Finance\n\n"
        "Vamos começar? Me conta um gasto agora! 🚀"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ── Comando /resumo ────────────────────────────────────────────────────
async def cmd_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Buscando seu resumo...")
    try:
        resumo = sheets.get_resumo_mes()
        mes_atual = datetime.now().strftime("%B/%Y").capitalize()
        saldo_emoji = "💚" if resumo["saldo"] >= 0 else "🔴"

        msg = (
            f"📊 *Resumo de {mes_atual}*\n\n"
            f"💰 Entradas: *R$ {resumo['entradas']:.2f}*\n"
            f"💸 Saídas: *R$ {resumo['saidas']:.2f}*\n"
            f"{saldo_emoji} Saldo: *R$ {resumo['saldo']:.2f}*\n\n"
            f"📂 *Por categoria:*\n"
        )
        for cat, val in resumo["categorias"].items():
            msg += f"• {cat}: R$ {val:.2f}\n"

        msg += f"\n📝 Total de registros: {resumo['total_registros']}"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro no resumo: {e}")
        await update.message.reply_text("❌ Erro ao buscar resumo. Tente novamente.")

# ── Comando /top ───────────────────────────────────────────────────────
async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        top = sheets.get_top_categorias(3)
        msg = "🏆 *Top 3 maiores gastos do mês:*\n\n"
        emojis = ["🥇", "🥈", "🥉"]
        for i, (cat, val) in enumerate(top):
            msg += f"{emojis[i]} {cat}: *R$ {val:.2f}*\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro no top: {e}")
        await update.message.reply_text("❌ Erro ao buscar dados. Tente novamente.")

# ── Comando /ajuda ─────────────────────────────────────────────────────
async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🆘 *Como usar o Start Finance:*\n\n"
        "*📝 Registrar gasto (texto):*\n"
        "Basta escrever naturalmente!\n"
        "Ex: \"Gastei 50 reais no mercado\"\n"
        "Ex: \"Paguei conta de internet 120\"\n\n"
        "*🎤 Registrar gasto (áudio):*\n"
        "Grave um áudio e mande!\n"
        "Ex: 🎤 \"Almocei no shopping, gastei 38 reais\"\n\n"
        "*💰 Registrar receita:*\n"
        "Ex: \"Recebi meu salário de 3000\"\n"
        "Ex: \"Entrou 500 reais de freelance\"\n\n"
        "*📋 Categorias disponíveis:*\n"
        "Alimentação • Transporte • Contas\n"
        "Lazer • Saúde • Educação • Moradia\n"
        "Salário • Freelance • Outros\n\n"
        "Qualquer dúvida é só perguntar! 💚"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ── Handler de Texto ───────────────────────────────────────────────────
async def handle_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    timestamp = update.message.date

    # Ignora comandos
    if texto.startswith("/"):
        return

    await update.message.reply_text("🧠 Analisando sua mensagem...")

    try:
        dados = await extractor.extrair(texto, timestamp)
        if dados:
            await pedir_confirmacao(update, context, dados)
        else:
            await update.message.reply_text(
                "🤔 Não consegui identificar uma transação financeira na sua mensagem.\n\n"
                "Tente assim: *\"Gastei R$50 no mercado\"* ou *\"Recebi R$2000 de salário\"*",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Erro ao processar texto: {e}")
        await update.message.reply_text("❌ Erro ao processar. Tente novamente!")

# ── Handler de Áudio ───────────────────────────────────────────────────
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Recebi seu áudio! Transcrevendo...")

    try:
        voice = update.message.voice or update.message.audio
        file = await context.bot.get_file(voice.file_id)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        await update.message.reply_text("🧠 Entendendo o conteúdo...")

        transcricao = await extractor.transcrever_audio(tmp_path)
        os.unlink(tmp_path)

        if not transcricao:
            await update.message.reply_text(
                "❌ Não consegui entender o áudio. Tente falar mais devagar ou envie como texto!"
            )
            return

        logger.info(f"Transcrição: {transcricao}")
        dados = await extractor.extrair(transcricao, update.message.date)

        if dados:
            await pedir_confirmacao(update, context, dados)
        else:
            await update.message.reply_text(
                f"🎤 Entendi: _{transcricao}_\n\n"
                "Mas não encontrei uma transação financeira. Tente ser mais específico!",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Erro no áudio: {e}")
        await update.message.reply_text("❌ Erro ao processar áudio. Tente enviar como texto!")

# ── Pedir Confirmação ──────────────────────────────────────────────────
async def pedir_confirmacao(update: Update, context: ContextTypes.DEFAULT_TYPE, dados: dict):
    tipo_emoji = "💸" if dados.get("tipo") == "Gasto" else "💰"
    sinal = "-" if dados.get("tipo") == "Gasto" else "+"

    msg = (
        f"📋 *Confirma este registro?*\n\n"
        f"{tipo_emoji} Tipo: *{dados.get('tipo', 'Gasto')}*\n"
        f"💵 Valor: *R$ {abs(float(dados.get('valor', 0))):.2f}*\n"
        f"📂 Categoria: *{dados.get('categoria', 'Outros')}*"
    )

    if dados.get("subcategoria"):
        msg += f" — {dados.get('subcategoria')}"

    if dados.get("descricao"):
        msg += f"\n📝 Descrição: *{dados.get('descricao')}*"

    if dados.get("localizacao"):
        msg += f"\n📍 Local: *{dados.get('localizacao')}*"

    msg += (
        f"\n📅 Data: *{dados.get('data', datetime.now().strftime('%d/%m/%Y'))}* "
        f"às *{dados.get('hora', datetime.now().strftime('%H:%M'))}*"
    )

    # Salva dados temporariamente no contexto
    context.user_data["pendente"] = dados

    keyboard = [
        [
            InlineKeyboardButton("✅ Confirmar", callback_data="confirmar"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancelar"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=reply_markup)

# ── Callback dos Botões ────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirmar":
        dados = context.user_data.get("pendente")
        if not dados:
            await query.edit_message_text("❌ Dados expirados. Envie a transação novamente.")
            return

        try:
            saldo = sheets.registrar_transacao(dados)
            saldo_emoji = "💚" if saldo >= 0 else "🔴"
            tipo_emoji = "💸" if dados.get("tipo") == "Gasto" else "💰"

            msg = (
                f"✅ *Registrado com sucesso!*\n\n"
                f"{tipo_emoji} R$ {abs(float(dados.get('valor', 0))):.2f} "
                f"em *{dados.get('categoria', 'Outros')}*\n\n"
                f"{saldo_emoji} Saldo de {datetime.now().strftime('%B').capitalize()}: "
                f"*R$ {saldo:.2f}*"
            )

            # Dica inteligente baseada na categoria
            dica = gerar_dica(dados, saldo)
            if dica:
                msg += f"\n\n💡 _{dica}_"

            await query.edit_message_text(msg, parse_mode="Markdown")
            context.user_data.pop("pendente", None)

        except Exception as e:
            logger.error(f"Erro ao registrar: {e}")
            await query.edit_message_text("❌ Erro ao salvar. Tente novamente!")

    elif query.data == "cancelar":
        context.user_data.pop("pendente", None)
        await query.edit_message_text("❌ Registro cancelado. Pode mandar outro quando quiser!")

# ── Dica Inteligente ───────────────────────────────────────────────────
def gerar_dica(dados: dict, saldo: float) -> str:
    categoria = dados.get("categoria", "")
    valor = abs(float(dados.get("valor", 0)))

    if saldo < 0:
        return "Atenção: seu saldo está negativo! Que tal revisar os gastos desta semana?"
    if categoria == "Alimentação" and valor > 80:
        return "Almoços caros acumulam rápido! Cozinhar em casa 2x por semana pode economizar muito."
    if categoria == "Transporte" and valor > 50:
        return "Dica: compare Uber com transporte público para trajetos frequentes!"
    if saldo > 500:
        return "Ótimo saldo! Que tal separar uma parte para sua reserva de emergência? 🎯"
    return ""

# ── Main ───────────────────────────────────────────────────────────────
def main():
    logger.info("🚀 Start Finance Bot iniciando...")
    app = Application.builder().token(TOKEN).build()

    # Comandos
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("resumo", cmd_resumo))
    app.add_handler(CommandHandler("top", cmd_top))
    app.add_handler(CommandHandler("ajuda", cmd_ajuda))

    # Mensagens
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_texto))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))

    # Callbacks dos botões
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("✅ Bot rodando! Aguardando mensagens...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
