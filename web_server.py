"""
START FINANCE — Web Server
Serve o dashboard HTML + API JSON com dados reais do Google Sheets
Roda junto com o bot Telegram no mesmo processo
"""

import os
import json
import logging
import threading
from flask import Flask, jsonify, send_from_directory

from sheets_manager import SheetsManager, get_mes_ano

logger = logging.getLogger(__name__)

app = Flask(__name__)
sheets = None  # será inicializado em start()


def init_sheets():
    global sheets
    try:
        sheets = SheetsManager()
        logger.info("✅ Sheets conectado no web server!")
    except Exception as e:
        logger.error(f"❌ Sheets erro no web server: {e}")


# ── ROTA: Dashboard HTML ─────────────────────────────────────────────
@app.route("/")
@app.route("/dashboard")
def dashboard():
    """Serve o dashboard HTML."""
    try:
        with open("dashboard.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h2>dashboard.html não encontrado. Faça upload do arquivo.</h2>", 404


# ── ROTA: API dados completos ─────────────────────────────────────────
@app.route("/api/data")
def api_data():
    """Retorna todos os dados financeiros do mês como JSON."""
    try:
        if not sheets:
            return jsonify({"erro": "Sheets não conectado"}), 500

        resumo    = sheets.get_resumo_mes()
        ultimas   = sheets.get_ultimas_transacoes(10)
        historico = sheets.get_historico_6_meses()
        previsao  = sheets.get_previsao_proximo_mes()
        badges    = sheets.get_badges_status()
        mes_atual = get_mes_ano()

        return jsonify({
            "mes": mes_atual,
            "kpis": {
                "entradas":    resumo["entradas"],
                "saidas":      resumo["saidas"],
                "saldo":       resumo["saldo"],
                "registros":   resumo["total_registros"],
                "economia":    max(resumo["saldo"], 0),
            },
            "categorias":   resumo["categorias_detalhadas"],
            "metodos":      resumo["metodos"],
            "transacoes":   ultimas,
            "historico":    historico,
            "previsao":     previsao,
            "badges":       badges,
            "narrativa":    gerar_narrativa(resumo),
        })

    except Exception as e:
        logger.error(f"❌ Erro na API: {e}")
        return jsonify({"erro": str(e)}), 500


# ── ROTA: Health check ────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "bot": "Start Finance", "sheets": sheets is not None})


def gerar_narrativa(resumo: dict) -> str:
    """Gera narrativa textual baseada nos dados do mês."""
    e  = resumo["entradas"]
    s  = resumo["saidas"]
    sd = resumo["saldo"]
    n  = resumo["total_registros"]

    cats = resumo["categorias"]
    top  = list(cats.items())[:2] if cats else []

    texto = f"Em {get_mes_ano()}: {n} transações registradas. "
    texto += f"Entradas R$ {e:,.2f} | Saídas R$ {s:,.2f} | Saldo R$ {sd:,.2f}. "

    if top:
        nomes = " e ".join([f"{cat} (R$ {val:,.2f})" for cat, val in top])
        texto += f"Maiores gastos: {nomes}. "

    if sd > 0:
        texto += "💚 Parabéns — você está no azul!"
    else:
        texto += "🔴 Atenção: gastos superaram as receitas este mês."

    return texto


def start(port: int = 8080):
    """Inicia o servidor web em thread separada."""
    init_sheets()
    t = threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False
        ),
        daemon=True
    )
    t.start()
    logger.info(f"🌐 Dashboard disponível em http://0.0.0.0:{port}")
    return t
