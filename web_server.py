"""
START FINANCE — Web Server v3.0
- Endpoint /api/todas retorna TODAS as transações (para filtro por mês no frontend)
- CRUD completo com índice real no Sheets
- Narrativa por mês
"""

import os, json, logging, threading
from datetime import datetime
from flask import Flask, jsonify, request, send_file
from sheets_manager import SheetsManager, get_mes_ano, MESES_PT, parsear_valor

logger = logging.getLogger(__name__)
app    = Flask(__name__)
sheets = None


def init_sheets():
    global sheets
    try:
        sheets = SheetsManager()
        logger.info("✅ Sheets conectado!")
    except Exception as e:
        logger.error(f"❌ Sheets: {e}")


def gerar_narrativa(entradas, saidas, saldo, n, top_cats, mes):
    txt = f"Em {mes}: {n} transações registradas. "
    txt += f"Entradas {fmt_r(entradas)} | Saídas {fmt_r(saidas)} | Saldo {fmt_r(saldo)}. "
    if top_cats:
        txt += "Maiores gastos: " + " e ".join([f"{cat} ({fmt_r(v)})" for cat, v in top_cats[:2]]) + ". "
    txt += "💚 Você está no azul!" if saldo >= 0 else "🔴 Gastos superaram as receitas."
    return txt

def fmt_r(v):
    return f"R$ {abs(v):,.2f}"


# ── Dashboard HTML ────────────────────────────────────────────────────
@app.route("/")
@app.route("/dashboard")
def dashboard():
    try:
        return send_file("dashboard.html")
    except FileNotFoundError:
        return "<h2>dashboard.html não encontrado</h2>", 404


# ── GET todas as transações (para filtro por mês no frontend) ─────────
@app.route("/api/todas")
def api_todas():
    """Retorna TODAS as transações da planilha — o frontend filtra por mês."""
    try:
        if not sheets:
            return jsonify({"erro": "Sheets não conectado"}), 500

        todos = sheets._get_todos_registros()
        EMOJIS = {"Alimentação":"🍽️","Transporte":"🚗","Contas":"⚡","Lazer":"🎮","Saúde":"❤️","Educação":"📚","Moradia":"🏠","Beleza":"💅","Vestuário":"👗","Pet":"🐾","Tecnologia":"📱","Filhos":"👶","Presentes":"🎁","Veículo":"🚘","Impostos":"🧾","Assinaturas":"📺","Salário":"💰","Freelance":"💼","Investimento":"📈","Outros":"📦"}
        CORES  = {"Alimentação":"#EF4444","Transporte":"#F97316","Contas":"#3B6FF0","Lazer":"#8B5CF6","Saúde":"#10B981","Educação":"#F59E0B","Moradia":"#6366F1","Beleza":"#EC4899","Vestuário":"#14B8A6","Pet":"#84CC16","Tecnologia":"#0EA5E9","Filhos":"#F472B6","Presentes":"#FB923C","Veículo":"#64748B","Impostos":"#78716C","Assinaturas":"#A78BFA","Salário":"#10B981","Freelance":"#34D399","Investimento":"#3B6FF0","Outros":"#9CA3AF"}

        def col(row, *nomes):
            for n in nomes:
                v = row.get(n, "")
                if v != "": return v
            return ""

        txs = []
        for i, row in enumerate(todos):
            cat   = str(col(row,"CATEGORIA")).strip() or "Outros"
            valor = parsear_valor(col(row,"VALOR (R$)","VALOR"))
            try:
                pt = int(float(str(col(row,"TOTAL PARC.","TOTAL_PARCELAS") or 0)))
            except:
                pt = 0

            txs.append({
                "idx":         i,   # índice real para editar/deletar
                "data":        str(col(row,"DATA")).strip(),
                "hora":        str(col(row,"HORA")).strip(),
                "valor":       round(valor, 2),
                "tipo":        str(col(row,"TIPO")).strip(),
                "categoria":   cat,
                "subcategoria":str(col(row,"SUBCATEGORIA")).strip(),
                "descricao":   str(col(row,"DESCRIÇÃO","DESCRICAO")).strip(),
                "localizacao": str(col(row,"LOCALIZAÇÃO","LOCALIZACAO")).strip(),
                "metodo":      str(col(row,"MÉTODO","METODO")).strip(),
                "cartao":      str(col(row,"CARTÃO","CARTAO")).strip(),
                "parcelas":    pt,
                "mes_ano":     str(col(row,"MÊS/ANO","MES/ANO")).strip(),
                "emoji":       EMOJIS.get(cat,"📦"),
                "cor":         CORES.get(cat,"#9CA3AF"),
            })

        # Inverte para mostrar mais recentes primeiro
        txs.reverse()

        # Histórico 6 meses para o gráfico
        historico = sheets.get_historico_6_meses()

        return jsonify({"transacoes": txs, "historico": historico})

    except Exception as e:
        logger.error(f"❌ /api/todas: {e}")
        return jsonify({"erro": str(e)}), 500


# ── GET dados calculados para um mês específico ───────────────────────
@app.route("/api/mes")
def api_mes():
    """Calcula KPIs, categorias, etc. para o mês informado."""
    try:
        mes = request.args.get("mes", get_mes_ano())
        todos = sheets._get_todos_registros()

        LIMITES = {"Alimentação":800,"Transporte":400,"Contas":600,"Lazer":300,"Saúde":200,"Educação":200,"Moradia":1500,"Beleza":200,"Vestuário":300,"Pet":200,"Tecnologia":500,"Filhos":400,"Presentes":100,"Veículo":300,"Impostos":200,"Assinaturas":150,"Outros":200}
        EMOJIS  = {"Alimentação":"🍽️","Transporte":"🚗","Contas":"⚡","Lazer":"🎮","Saúde":"❤️","Educação":"📚","Moradia":"🏠","Beleza":"💅","Vestuário":"👗","Pet":"🐾","Tecnologia":"📱","Filhos":"👶","Presentes":"🎁","Veículo":"🚘","Impostos":"🧾","Assinaturas":"📺","Salário":"💰","Freelance":"💼","Investimento":"📈","Outros":"📦"}
        CORES   = {"Alimentação":"#EF4444","Transporte":"#F97316","Contas":"#3B6FF0","Lazer":"#8B5CF6","Saúde":"#10B981","Educação":"#F59E0B","Moradia":"#6366F1","Beleza":"#EC4899","Vestuário":"#14B8A6","Pet":"#84CC16","Tecnologia":"#0EA5E9","Filhos":"#F472B6","Presentes":"#FB923C","Veículo":"#64748B","Impostos":"#78716C","Assinaturas":"#A78BFA","Salário":"#10B981","Freelance":"#34D399","Investimento":"#3B6FF0","Outros":"#9CA3AF"}

        def col(row, *nomes):
            for n in nomes:
                v = row.get(n,"")
                if v != "": return v
            return ""

        from collections import defaultdict
        e = s = total = 0.0
        cats = defaultdict(float)
        metodos = defaultdict(float)
        cartoes = defaultdict(float)

        for row in todos:
            if str(col(row,"MÊS/ANO","MES/ANO")).strip() != mes:
                continue
            v   = parsear_valor(col(row,"VALOR (R$)","VALOR"))
            cat = str(col(row,"CATEGORIA")).strip() or "Outros"
            met = str(col(row,"MÉTODO","METODO")).strip()
            ct  = str(col(row,"CARTÃO","CARTAO")).strip()
            total += 1
            if v > 0: e += v
            else:
                s += abs(v)
                cats[cat] += abs(v)
                if met: metodos[met] += abs(v)
                if ct:  cartoes[ct]  += abs(v)

        cats_det = []
        for cat, gasto in sorted(cats.items(), key=lambda x: x[1], reverse=True):
            lim = LIMITES.get(cat, 0)
            pct = (gasto/lim*100) if lim > 0 else 0
            cats_det.append({
                "nome": cat, "emoji": EMOJIS.get(cat,"📦"), "cor": CORES.get(cat,"#9CA3AF"),
                "gasto": round(gasto,2), "limite": lim, "pct": round(pct,1),
                "status": "estourou" if pct>=100 else "atencao" if pct>=80 else "ok" if gasto>0 else "livre",
            })

        tot_met = sum(metodos.values()) or 1
        mets_fmt = [{"nome":m,"valor":round(v,2),"pct":round(v/tot_met*100,1)} for m,v in sorted(metodos.items(),key=lambda x:x[1],reverse=True)]
        carts_fmt = {k: round(v,2) for k,v in cartoes.items()}

        top_cats = list(cats.items())[:3]
        return jsonify({
            "mes": mes,
            "kpis": {"entradas": round(e,2), "saidas": round(s,2), "saldo": round(e-s,2), "registros": int(total)},
            "categorias": cats_det,
            "metodos": mets_fmt,
            "gastos_por_cartao": carts_fmt,
            "narrativa": gerar_narrativa(e, s, e-s, int(total), top_cats, mes),
        })
    except Exception as e:
        logger.error(f"❌ /api/mes: {e}")
        return jsonify({"erro": str(e)}), 500


# ── POST nova transação ───────────────────────────────────────────────
@app.route("/api/transacao/nova", methods=["POST"])
def nova_transacao():
    try:
        dados = request.json
        if not dados: return jsonify({"erro":"Dados inválidos"}), 400
        saldo = sheets.registrar_transacao(dados)
        return jsonify({"ok": True, "saldo": saldo})
    except Exception as e:
        logger.error(f"❌ Nova tx: {e}")
        return jsonify({"erro": str(e)}), 500


# ── PUT editar transação ──────────────────────────────────────────────
@app.route("/api/transacao/<int:idx>", methods=["PUT"])
def editar_transacao(idx):
    try:
        dados = request.json
        if not dados: return jsonify({"erro":"Dados inválidos"}), 400
        agora   = datetime.now()
        mes_ano = get_mes_ano()
        pa = int(dados.get("parcela_atual",1) or 1)
        pt = int(dados.get("total_parcelas",0) or 0)

        nova = [
            dados.get("data",  agora.strftime("%d/%m/%Y")),
            dados.get("hora",  agora.strftime("%H:%M")),
            float(dados.get("valor", 0)),
            dados.get("tipo",          "Gasto"),
            dados.get("categoria",     "Outros"),
            dados.get("subcategoria",  ""),
            dados.get("descricao",     ""),
            dados.get("localizacao",   ""),
            dados.get("metodo_pagamento",""),
            pa if pt > 0 else "",
            pt if pt > 0 else "",
            "Telegram",
            dados.get("mes_ano", mes_ano),
            "✅",
            dados.get("cartao", ""),   # coluna O
        ]

        todos = sheets._get_todos_registros()
        total = len(todos)
        linha_sheet = (total - idx) + 3  # +3: 2 decorativas + 1 cabeçalho

        # Se a planilha tem menos de 15 colunas, ajusta
        sheets.aba_transacoes.update(
            f"A{linha_sheet}:O{linha_sheet}", [nova],
            value_input_option="USER_ENTERED"
        )
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"❌ Editar tx {idx}: {e}")
        return jsonify({"erro": str(e)}), 500


# ── DELETE excluir transação ──────────────────────────────────────────
@app.route("/api/transacao/<int:idx>", methods=["DELETE"])
def deletar_transacao(idx):
    try:
        todos  = sheets._get_todos_registros()
        total  = len(todos)
        linha  = (total - idx) + 3
        sheets.aba_transacoes.delete_rows(linha)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"❌ Delete tx {idx}: {e}")
        return jsonify({"erro": str(e)}), 500


# ── Health ────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status":"ok","sheets": sheets is not None})


def start(port=8080):
    init_sheets()
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True
    )
    t.start()
    logger.info(f"🌐 Dashboard em http://0.0.0.0:{port}")
    return t
