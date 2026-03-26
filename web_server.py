"""
START FINANCE — Web Server v2.0
Dashboard + API com CRUD completo de transações
"""

import os, json, logging, threading
from flask import Flask, jsonify, request, send_file

from sheets_manager import SheetsManager, get_mes_ano

logger = logging.getLogger(__name__)
app    = Flask(__name__)
sheets = None


def init_sheets():
    global sheets
    try:
        sheets = SheetsManager()
        logger.info("✅ Sheets conectado no web server!")
    except Exception as e:
        logger.error(f"❌ Sheets erro: {e}")


def gerar_narrativa(resumo: dict) -> str:
    e  = resumo["entradas"]
    s  = resumo["saidas"]
    sd = resumo["saldo"]
    n  = resumo["total_registros"]
    cats = resumo["categorias"]
    top  = list(cats.items())[:2] if cats else []
    txt  = f"Em {get_mes_ano()}: {n} transações registradas. "
    txt += f"Entradas R$ {e:,.2f} | Saídas R$ {s:,.2f} | Saldo R$ {sd:,.2f}. "
    if top:
        txt += "Maiores gastos: " + " e ".join([f"{cat} (R$ {v:,.2f})" for cat, v in top]) + ". "
    txt += "💚 Parabéns — você está no azul!" if sd > 0 else "🔴 Atenção: gastos superaram as receitas este mês."
    return txt


# ── Dashboard HTML ───────────────────────────────────────────────────
@app.route("/")
@app.route("/dashboard")
def dashboard():
    try:
        return send_file("dashboard.html")
    except FileNotFoundError:
        return "<h2>dashboard.html não encontrado</h2>", 404


# ── GET dados completos ──────────────────────────────────────────────
@app.route("/api/data")
def api_data():
    try:
        if not sheets:
            return jsonify({"erro": "Sheets não conectado"}), 500
        resumo    = sheets.get_resumo_mes()
        ultimas   = sheets.get_ultimas_transacoes(50)
        historico = sheets.get_historico_6_meses()
        previsao  = sheets.get_previsao_proximo_mes()
        badges    = sheets.get_badges_status()

        return jsonify({
            "mes":        get_mes_ano(),
            "kpis":       {"entradas": resumo["entradas"], "saidas": resumo["saidas"],
                           "saldo": resumo["saldo"], "registros": resumo["total_registros"],
                           "economia": max(resumo["saldo"], 0)},
            "categorias": resumo["categorias_detalhadas"],
            "metodos":    resumo["metodos"],
            "transacoes": ultimas,
            "historico":  historico,
            "previsao":   previsao,
            "badges":     badges,
            "narrativa":  gerar_narrativa(resumo),
        })
    except Exception as e:
        logger.error(f"❌ API data: {e}")
        return jsonify({"erro": str(e)}), 500


# ── POST nova transação ──────────────────────────────────────────────
@app.route("/api/transacao/nova", methods=["POST"])
def nova_transacao():
    try:
        dados = request.json
        if not dados:
            return jsonify({"erro": "Dados inválidos"}), 400
        saldo = sheets.registrar_transacao(dados)
        return jsonify({"ok": True, "saldo": saldo})
    except Exception as e:
        logger.error(f"❌ Nova transação: {e}")
        return jsonify({"erro": str(e)}), 500


# ── PUT editar transação ─────────────────────────────────────────────
@app.route("/api/transacao/<int:idx>", methods=["PUT"])
def editar_transacao(idx):
    try:
        dados = request.json
        if not dados:
            return jsonify({"erro": "Dados inválidos"}), 400

        from datetime import datetime
        agora   = datetime.now()
        mes_ano = get_mes_ano(agora)

        pa = int(dados.get("parcela_atual",  1) or 1)
        pt = int(dados.get("total_parcelas", 0) or 0)

        nova_linha = [
            dados.get("data",  agora.strftime("%d/%m/%Y")),
            dados.get("hora",  agora.strftime("%H:%M")),
            float(dados.get("valor", 0)),
            dados.get("tipo",         "Gasto"),
            dados.get("categoria",    "Outros"),
            dados.get("subcategoria", ""),
            dados.get("descricao",    ""),
            dados.get("localizacao",  ""),
            dados.get("metodo_pagamento", ""),
            pa if pt > 0 else "",
            pt if pt > 0 else "",
            "Telegram",
            mes_ano,
            "✅"
        ]

        # Linha real na planilha = idx + 4 (cabeçalho linha 3 + dados a partir linha 4)
        # idx aqui é o índice dos dados retornados (0-based, mais recente primeiro)
        # Precisamos descobrir a linha real
        todos = sheets._get_todos_registros()
        total = len(todos)
        # idx é 0-based do mais recente para o mais antigo
        linha_dados = total - idx  # índice na lista (0-based do início)
        linha_sheet = linha_dados + 3  # +3 por causa das 3 linhas antes dos dados (2 decorativas + 1 cabeçalho)

        sheets.aba_transacoes.update(f"A{linha_sheet}:N{linha_sheet}",
                                      [nova_linha],
                                      value_input_option="USER_ENTERED")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"❌ Editar transação {idx}: {e}")
        return jsonify({"erro": str(e)}), 500


# ── DELETE excluir transação ─────────────────────────────────────────
@app.route("/api/transacao/<int:idx>", methods=["DELETE"])
def deletar_transacao(idx):
    try:
        todos = sheets._get_todos_registros()
        total = len(todos)
        linha_dados = total - idx
        linha_sheet = linha_dados + 3

        sheets.aba_transacoes.delete_rows(linha_sheet)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"❌ Deletar transação {idx}: {e}")
        return jsonify({"erro": str(e)}), 500


# ── Health ───────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "sheets": sheets is not None})


def start(port: int = 8080):
    init_sheets()
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True
    )
    t.start()
    logger.info(f"🌐 Dashboard em http://0.0.0.0:{port}")
    return t
