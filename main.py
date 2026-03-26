"""
START FINANCE — Bot Principal v6.0
Inicia: Telegram Bot + Web Server (dashboard) no mesmo processo
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
import web_server

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN  = os.environ.get("TELEGRAM_TOKEN")
sheets = SheetsManager()
extractor = AIExtractor()

# ── /start ────────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.effective_user.first_name
    port = os.environ.get("PORT", "8080")
    url  = os.environ.get("RAILWAY_STATIC_URL", f"http://localhost:{port}")

    msg = (
        f"💚 Olá, *{nome}*! Bem-vindo ao *Start Finance*!\n\n"
        "Sou seu assistente financeiro via Telegram.\n\n"
        "📝 *Exemplos:*\n"
        "• \"Gastei R$45 no almoço hoje\"\n"
        "• \"50 uber + 35 ifood\"\n"
        "• \"Paguei R$350 no mecânico, 3x\"\n"
        "• \"Recebi R$3500 de salário\"\n"
        "• 🎤 Pode mandar áudio também!\n\n"
        f"📊 *Dashboard:* {url}\n\n"
        "/resumo — Resumo do mês\n"
        "/top — Top 3 gastos\n"
        "/ajuda — Como usar"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ── /resumo ──────────────────────────────────────────────────────────
async def cmd_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Buscando resumo...")
    try:
        r   = sheets.get_resumo_mes()
        mes = datetime.now().strftime("%B/%Y").capitalize()
        emoji_saldo = "💚" if r["saldo"] >= 0 else "🔴"

        msg = (
            f"📊 *Resumo de {mes}*\n\n"
            f"💰 Entradas: *R$ {r['entradas']:,.2f}*\n"
            f"💸 Saídas: *R$ {r['saidas']:,.2f}*\n"
            f"{emoji_saldo} Saldo: *R$ {r['saldo']:,.2f}*\n\n"
            f"📂 *Por categoria:*\n"
        )
        for cat, val in list(r["categorias"].items())[:6]:
            msg += f"• {cat}: R$ {val:,.2f}\n"

        msg += f"\n📝 {r['total_registros']} transações registradas"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro resumo: {e}")
        await update.message.reply_text("❌ Erro ao buscar resumo.")

# ── /top ─────────────────────────────────────────────────────────────
async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        top    = sheets.get_top_categorias(3)
        emojis = ["🥇","🥈","🥉"]
        msg    = "🏆 *Top 3 gastos do mês:*\n\n"
        for i, (cat, val) in enumerate(top):
            msg += f"{emojis[i]} {cat}: *R$ {val:,.2f}*\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro top: {e}")
        await update.message.reply_text("❌ Erro ao buscar dados.")

# ── /ajuda ────────────────────────────────────────────────────────────
async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🆘 *Como usar o Start Finance:*\n\n"
        "*📝 Texto:*\n"
        "• \"Gastei R$50 no mercado\"\n"
        "• \"Paguei conta de luz 120\"\n"
        "• \"Recebi R$3000 de salário\"\n"
        "• \"Peças do carro 600, parcelei em 3x\"\n\n"
        "*🎤 Áudio:* grave e mande!\n\n"
        "*📊 Comandos:*\n"
        "/resumo — Resumo do mês\n"
        "/top — Top 3 categorias\n"
        "/ajuda — Esta mensagem\n\n"
        "O bot entende linguagem natural — formal ou informal! 💚"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ── Handler de Texto ─────────────────────────────────────────────────
async def handle_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if texto.startswith("/"):
        return
    await update.message.reply_text("🧠 Analisando sua mensagem...")
    try:
        dados = await extractor.extrair(texto, update.message.date)
        if dados:
            if isinstance(dados, list):
                # Múltiplas transações
                for d in dados:
                    await pedir_confirmacao(update, context, d)
            else:
                await pedir_confirmacao(update, context, dados)
        else:
            await update.message.reply_text(
                "🤔 Não identifiquei uma transação financeira.\n\n"
                "Tente: *\"Gastei R$50 no mercado\"* ou *\"Recebi R$2000 de salário\"*",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Erro texto: {e}")
        await update.message.reply_text("❌ Erro ao processar. Tente novamente!")

# ── Handler de Áudio ─────────────────────────────────────────────────
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Recebi seu áudio! Transcrevendo...")
    try:
        voice = update.message.voice or update.message.audio
        file  = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        await update.message.reply_text("🧠 Entendendo o conteúdo...")
        transcricao = await extractor.transcrever_audio(tmp_path)
        os.unlink(tmp_path)

        if not transcricao:
            await update.message.reply_text("❌ Não entendi o áudio. Tente como texto!")
            return

        dados = await extractor.extrair(transcricao, update.message.date)
        if dados:
            await pedir_confirmacao(update, context, dados)
        else:
            await update.message.reply_text(
                f"🎤 Entendi: _{transcricao}_\n\nMas não encontrei transação financeira.",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Erro áudio: {e}")
        await update.message.reply_text("❌ Erro no áudio. Tente como texto!")

# ── Confirmação ───────────────────────────────────────────────────────
async def pedir_confirmacao(update: Update, context: ContextTypes.DEFAULT_TYPE, dados: dict):
    tipo_emoji = "💸" if dados.get("tipo") == "Gasto" else "💰"
    cat   = dados.get("categoria", "Outros")
    sub   = dados.get("subcategoria", "")
    cat_str = f"{cat}" + (f" · {sub}" if sub else "")
    valor = abs(float(dados.get("valor", 0)))

    msg = f"📋 *Confirma este registro?*\n\n{tipo_emoji} *R$ {valor:.2f}* em {cat_str}"

    if dados.get("localizacao"):
        msg += f"\n📍 {dados['localizacao']}"
    if dados.get("metodo_pagamento"):
        msg += f"\n💳 {dados['metodo_pagamento']}"
    pt = dados.get("total_parcelas", 0)
    if pt and int(pt) > 0:
        msg += f"\n🔢 Parcelado em *{pt}x*"
    msg += f"\n📅 {dados.get('data')} às {dados.get('hora')}"

    context.user_data["pendente"] = dados
    keyboard = [[
        InlineKeyboardButton("✅ Confirmar", callback_data="confirmar"),
        InlineKeyboardButton("❌ Cancelar",  callback_data="cancelar"),
    ]]
    await update.message.reply_text(
        msg, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ── Callback Botões ───────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirmar":
        dados = context.user_data.get("pendente")
        if not dados:
            await query.edit_message_text("❌ Dados expirados. Envie novamente.")
            return
        try:
            sheets.registrar_transacao(dados)
            tipo_emoji = "💸" if dados.get("tipo") == "Gasto" else "💰"
            cat = dados.get("categoria","Outros")
            sub = dados.get("subcategoria","")
            cat_str = cat + (f" · {sub}" if sub else "")
            valor   = abs(float(dados.get("valor",0)))

            msg = f"✅ *Registrado com sucesso!*\n\n{tipo_emoji} *R$ {valor:.2f}* em {cat_str}"

            if dados.get("localizacao"):
                msg += f"\n📍 {dados['localizacao']}"
            if dados.get("metodo_pagamento"):
                msg += f"\n💳 {dados['metodo_pagamento']}"
            pt = dados.get("total_parcelas",0)
            if pt and int(pt) > 0:
                msg += f"\n🔢 Parcelado em *{pt}x*"

            dica = gerar_dica(dados)
            if dica:
                msg += f"\n\n💡 _{dica}_"

            await query.edit_message_text(msg, parse_mode="Markdown")
            context.user_data.pop("pendente", None)

        except Exception as e:
            logger.error(f"Erro registrar: {e}")
            await query.edit_message_text("❌ Erro ao salvar. Tente novamente!")

    elif query.data == "cancelar":
        context.user_data.pop("pendente", None)
        await query.edit_message_text("❌ Cancelado. Pode mandar outro quando quiser!")

# ── Dica inteligente ─────────────────────────────────────────────────
def gerar_dica(dados: dict) -> str:
    cat   = dados.get("categoria","")
    valor = abs(float(dados.get("valor",0)))
    if cat == "Alimentação" and valor > 80:
        return "Almoços caros acumulam rápido! Que tal cozinhar em casa 2x por semana?"
    if cat == "Transporte" and valor > 50:
        return "Compare Uber com transporte público para trajetos frequentes!"
    if cat == "Veículo":
        return "Gastos com veículo podem pesar! Acompanhe no dashboard. 🚘"
    if cat == "Investimento":
        return "Ótima decisão investir! Continue construindo seu patrimônio. 📈"
    if cat == "Beleza" and valor > 150:
        return "Autocuidado é essencial! Só fique de olho na frequência. 💅"
    return ""

# ── MAIN ─────────────────────────────────────────────────────────────
def main():
    # Inicia o web server (dashboard) em thread separada
    port = int(os.environ.get("PORT", "8080"))
    web_server.start(port=port)

    logger.info("🚀 Start Finance Bot iniciando...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("resumo", cmd_resumo))
    app.add_handler(CommandHandler("top",    cmd_top))
    app.add_handler(CommandHandler("ajuda",  cmd_ajuda))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_texto))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("✅ Bot rodando! Dashboard ativo.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
