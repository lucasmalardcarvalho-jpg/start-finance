"""
START FINANCE — Web Server v4.1
- Auth JWT multi-usuário (todos os endpoints protegidos)
- Headers de segurança HTTP
- CORS restrito ao domínio configurado
"""

import os, json, logging, threading, time
from datetime import datetime
from flask import Flask, jsonify, request, send_file
import httpx
from sheets_manager import SheetsManager, get_mes_ano, MESES_PT, parsear_valor
from auth import registrar_rotas_auth, requer_auth

logger = logging.getLogger(__name__)
app    = Flask(__name__)
sheets = None

# ── CORS e Headers de Segurança ──────────────────────────────────────
_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:8080,http://127.0.0.1:8080"
).split(",") if o.strip()]

@app.after_request
def add_security_headers(r):
    # CORS — apenas origens permitidas (não wildcard)
    origin = request.headers.get("Origin", "")
    if origin in _ALLOWED_ORIGINS:
        r.headers["Access-Control-Allow-Origin"]  = origin
        r.headers["Vary"] = "Origin"
    r.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    r.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"

    # Headers de segurança HTTP
    r.headers["X-Content-Type-Options"]  = "nosniff"
    r.headers["X-Frame-Options"]         = "DENY"
    r.headers["Referrer-Policy"]         = "strict-origin-when-cross-origin"
    # CSP básico — restringe execução de scripts externos
    r.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' https:;"
    )
    return r

@app.route("/", defaults={"path": ""}, methods=["OPTIONS"])
@app.route("/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return "", 204


def init_sheets():
    global sheets
    try:
        sheets = SheetsManager()
        logger.info("✅ Sheets conectado!")
    except Exception as e:
        logger.error(f"❌ Sheets: {e}")


def fmt_r(v):
    return f"R$ {abs(v):,.2f}"


def gerar_narrativa(entradas, saidas, saldo, n, top_cats, mes):
    txt = f"Em {mes}: {n} transações registradas. "
    txt += f"Entradas {fmt_r(entradas)} | Saídas {fmt_r(saidas)} | Saldo {fmt_r(saldo)}. "
    if top_cats:
        txt += "Maiores gastos: " + " e ".join([f"{cat} ({fmt_r(v)})" for cat, v in top_cats[:2]]) + ". "
    txt += "💚 Você está no azul!" if saldo >= 0 else "🔴 Gastos superaram as receitas."
    return txt


# ── Auth routes ──────────────────────────────────────────────────────
registrar_rotas_auth(app)


# ── Static assets ───────────────────────────────────────────────────
@app.route("/logo.svg")
def serve_logo():
    return send_file("logo.svg", mimetype="image/svg+xml")

@app.route("/logo-icon.svg")
def serve_logo_icon():
    return send_file("logo-icon.svg", mimetype="image/svg+xml")

@app.route("/manifest.json")
def serve_manifest():
    resp = send_file("manifest.json", mimetype="application/manifest+json")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp

@app.route("/sw.js")
def serve_sw():
    resp = send_file("sw.js", mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


# ── Dashboard HTML ──────────────────────────────────────────────────
@app.route("/")
@app.route("/dashboard")
def dashboard():
    try:
        resp = send_file("dashboard.html")
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    except FileNotFoundError:
        return "<h2>dashboard.html não encontrado</h2>", 404


# ── GET todas as transações ─────────────────────────────────────────
@app.route("/api/todas")
@requer_auth
def api_todas():
    try:
        if not sheets:
            return jsonify({"erro": "Sheets não conectado"}), 500

        todos     = sheets._get_todos_registros()
        todos_raw = sheets.aba_transacoes.get_all_values()
        raw_data  = todos_raw[3:] if len(todos_raw) > 3 else []

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

            cartao_val = str(col(row,"CARTÃO","CARTAO","cartao","Cartão")).strip()
            if not cartao_val and i < len(raw_data):
                raw_row = raw_data[i]
                if len(raw_row) > 14:
                    cartao_val = str(raw_row[14]).strip()

            try:
                pa = int(float(str(col(row,"PARCELA","parcela_atual") or 0)))
            except:
                pa = 0

            txs.append({
                "idx":           i,
                "data":          str(col(row,"DATA")).strip(),
                "hora":          str(col(row,"HORA")).strip(),
                "valor":         round(valor, 2),
                "tipo":          str(col(row,"TIPO")).strip(),
                "categoria":     cat,
                "subcategoria":  str(col(row,"SUBCATEGORIA")).strip(),
                "descricao":     str(col(row,"DESCRIÇÃO","DESCRICAO")).strip(),
                "localizacao":   str(col(row,"LOCALIZAÇÃO","LOCALIZACAO")).strip(),
                "metodo":        str(col(row,"MÉTODO","METODO")).strip(),
                "cartao":        cartao_val,
                "parcela_atual": pa,
                "parcelas":      pt,
                "mes_ano":       str(col(row,"MÊS/ANO","MES/ANO")).strip(),
                "emoji":         EMOJIS.get(cat,"📦"),
                "cor":           CORES.get(cat,"#9CA3AF"),
            })

        txs.reverse()
        historico = sheets.get_historico_ano()

        return jsonify({"transacoes": txs, "historico": historico})

    except Exception as e:
        logger.error(f"❌ /api/todas: {e}")
        return jsonify({"erro": str(e)}), 500


# ── GET dados do mês ────────────────────────────────────────────────
@app.route("/api/mes")
@requer_auth
def api_mes():
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
            "kpis": {"entradas":round(e,2),"saidas":round(s,2),"saldo":round(e-s,2),"registros":int(total)},
            "categorias": cats_det,
            "metodos": mets_fmt,
            "gastos_por_cartao": carts_fmt,
            "narrativa": gerar_narrativa(e, s, e-s, int(total), top_cats, mes),
        })
    except Exception as e:
        logger.error(f"❌ /api/mes: {e}")
        return jsonify({"erro": str(e)}), 500


# ── POST nova transação ────────────────────────────────────────────
@app.route("/api/transacao/nova", methods=["POST"])
@requer_auth
def nova_transacao():
    try:
        dados = request.json
        if not dados: return jsonify({"erro":"Dados inválidos"}), 400
        saldo = sheets.registrar_transacao(dados)
        return jsonify({"ok": True, "saldo": saldo})
    except Exception as e:
        logger.error(f"❌ Nova tx: {e}")
        return jsonify({"erro": str(e)}), 500


# ── PUT editar ────────────────────────────────────────────────────
@app.route("/api/transacao/<int:idx>", methods=["PUT"])
@requer_auth
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
            dados.get("cartao", ""),
        ]
        linha = idx + 4
        sheets.aba_transacoes.update(f"A{linha}:O{linha}", [nova], value_input_option="USER_ENTERED")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"❌ Editar tx {idx}: {e}")
        return jsonify({"erro": str(e)}), 500


# ── DELETE ────────────────────────────────────────────────────────
@app.route("/api/transacao/<int:idx>", methods=["DELETE"])
@requer_auth
def deletar_transacao(idx):
    try:
        linha = idx + 4
        sheets.aba_transacoes.delete_rows(linha)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"❌ Delete tx {idx}: {e}")
        return jsonify({"erro": str(e)}), 500


# ── Open Finance — Pluggy API ────────────────────────────────────
PLUGGY_CLIENT_ID     = os.environ.get("PLUGGY_CLIENT_ID", "")
PLUGGY_CLIENT_SECRET = os.environ.get("PLUGGY_CLIENT_SECRET", "")
PLUGGY_AUTH_URL      = "https://api.pluggy.ai/auth"
PLUGGY_API_BASE      = "https://api.pluggy.ai"

def pluggy_api_key():
    """Obtém API key (Bearer token) do Pluggy."""
    import urllib.request, json as _json
    payload = _json.dumps({"clientId": PLUGGY_CLIENT_ID, "clientSecret": PLUGGY_CLIENT_SECRET}).encode()
    req = urllib.request.Request(PLUGGY_AUTH_URL, data=payload,
                                  headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as res:
        return _json.loads(res.read())["apiKey"]

@app.route("/api/pluggy/status")
@requer_auth
def pluggy_status():
    configured = bool(PLUGGY_CLIENT_ID and PLUGGY_CLIENT_SECRET)
    return jsonify({"configured": configured})

@app.route("/api/pluggy/token", methods=["POST"])
@requer_auth
def pluggy_connect_token():
    """Cria um Connect Token para o widget Pluggy."""
    if not (PLUGGY_CLIENT_ID and PLUGGY_CLIENT_SECRET):
        return jsonify({"erro": "Pluggy não configurado. Defina PLUGGY_CLIENT_ID e PLUGGY_CLIENT_SECRET."}), 503
    try:
        import urllib.request, json as _json
        api_key = pluggy_api_key()
        payload = _json.dumps({}).encode()
        req = urllib.request.Request(
            f"{PLUGGY_API_BASE}/connect_token",
            data=payload,
            headers={"Content-Type": "application/json", "X-API-KEY": api_key},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as res:
            data = _json.loads(res.read())
        return jsonify({"accessToken": data.get("accessToken","")})
    except Exception as e:
        logger.error(f"❌ Pluggy token: {e}")
        return jsonify({"erro": str(e)}), 500

@app.route("/api/pluggy/sync/<item_id>", methods=["POST"])
@requer_auth
def pluggy_sync(item_id):
    """Busca transações de um item Pluggy e retorna para importação."""
    if not (PLUGGY_CLIENT_ID and PLUGGY_CLIENT_SECRET):
        return jsonify({"erro": "Pluggy não configurado"}), 503
    try:
        import urllib.request, json as _json
        api_key = pluggy_api_key()
        req = urllib.request.Request(
            f"{PLUGGY_API_BASE}/accounts?itemId={item_id}",
            headers={"X-API-KEY": api_key}
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            accounts = _json.loads(res.read()).get("results", [])

        all_txs = []
        for acc in accounts:
            acc_id = acc["id"]
            req2 = urllib.request.Request(
                f"{PLUGGY_API_BASE}/transactions?accountId={acc_id}&pageSize=100",
                headers={"X-API-KEY": api_key}
            )
            with urllib.request.urlopen(req2, timeout=15) as res2:
                txs = _json.loads(res2.read()).get("results", [])
            for t in txs:
                from datetime import datetime as _dt
                data_raw = t.get("date","")[:10]
                try:
                    dt = _dt.fromisoformat(data_raw)
                    data_fmt = dt.strftime("%d/%m/%Y")
                    mes_ano  = dt.strftime("%b./%Y").lower().capitalize()
                except:
                    data_fmt = data_raw
                    mes_ano  = ""
                valor = float(t.get("amount", 0))
                desc  = t.get("description","") or t.get("descriptionRaw","")
                all_txs.append({
                    "data": data_fmt,
                    "descricao": desc,
                    "valor": -abs(valor) if t.get("type","DEBIT") == "DEBIT" else abs(valor),
                    "tipo": "Receita" if t.get("type") == "CREDIT" else "Gasto",
                    "mes_ano": mes_ano,
                    "origem": "Pluggy",
                })

        return jsonify({"transacoes": all_txs, "contas": len(accounts)})
    except Exception as e:
        logger.error(f"❌ Pluggy sync {item_id}: {e}")
        return jsonify({"erro": str(e)}), 500


# ── User Data Sync — armazena dados financeiros por usuário ──────
import os as _os

_USER_DATA_DIR = _os.path.join(_os.path.dirname(__file__), 'userdata')
_user_data_mem = {}  # cache em memória: {user_id: data}
_user_data_ts  = {}  # cache de timestamps: {user_id: int (ms)}

# Supabase (opcional) — lido aqui para não depender de auth.py
_SB_URL = os.environ.get("SUPABASE_URL", "")
_SB_KEY = os.environ.get("SUPABASE_KEY", "")

def _sb_ud_headers() -> dict:
    return {
        "apikey":        _SB_KEY,
        "Authorization": f"Bearer {_SB_KEY}",
        "Content-Type":  "application/json",
    }

def _ud_path(user_id: str) -> str:
    # Sanitiza user_id para prevenir path traversal
    safe_id = "".join(c for c in user_id if c.isalnum() or c in "_-")
    _os.makedirs(_USER_DATA_DIR, exist_ok=True)
    return _os.path.join(_USER_DATA_DIR, f"{safe_id}.json")

@app.route("/api/userdata", methods=["GET"])
@requer_auth
def get_userdata():
    user_id = request.user["sub"]

    # 1. Cache em memória (mais rápido)
    if user_id in _user_data_mem:
        return jsonify(_user_data_mem[user_id])

    # 2. Tenta Supabase
    if _SB_URL and _SB_KEY:
        try:
            url = f"{_SB_URL}/rest/v1/sf_userdata?user_id=eq.{user_id}&select=data,updated_at"
            resp = httpx.get(url, headers=_sb_ud_headers(), timeout=5)
            if resp.status_code == 200:
                rows = resp.json()
                if rows:
                    data = rows[0].get("data", {})
                    ts   = rows[0].get("updated_at", 0)
                    _user_data_mem[user_id] = data
                    _user_data_ts[user_id]  = int(ts)
                    return jsonify(data)
            else:
                logger.warning(f"Supabase get_userdata HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Supabase get_userdata falhou, usando arquivo: {e}")

    # 3. Fallback: arquivo local
    path = _ud_path(user_id)
    if _os.path.exists(path):
        try:
            with open(path) as f:
                data = json.load(f)
                _user_data_mem[user_id] = data
                return jsonify(data)
        except Exception:
            pass
    return jsonify({})

@app.route("/api/userdata", methods=["POST"])
@requer_auth
def save_userdata():
    user_id = request.user["sub"]
    data = request.json or {}
    now_ms = int(time.time() * 1000)

    # Proteção anti-wipe: rejeita payload vazio quando já há dados salvos para este usuário
    incoming_has_data = any(
        isinstance(data.get(k), list) and len(data[k]) > 0
        for k in ('txs', 'fixas', 'dividas', 'metas', 'inv', 'cartoes')
    )
    if not incoming_has_data:
        existing = _user_data_mem.get(user_id)
        if existing:
            existing_has_data = any(
                isinstance(existing.get(k), list) and len(existing[k]) > 0
                for k in ('txs', 'fixas', 'dividas', 'metas', 'inv', 'cartoes')
            )
            if existing_has_data:
                logger.warning(f"🛡️ Anti-wipe: payload vazio rejeitado para user {user_id}")
                return jsonify({"ok": False, "reason": "empty_payload_rejected"}), 409

    # 1. Atualiza cache em memória
    _user_data_mem[user_id] = data
    _user_data_ts[user_id]  = now_ms

    # 2. Salva em arquivo local (síncrono)
    try:
        path = _ud_path(user_id)
        with open(path, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.warning(f"userdata write error: {e}")

    # 3. Upsert no Supabase em background
    if _SB_URL and _SB_KEY:
        dt_iso = datetime.utcnow().isoformat() + "Z"
        def _upsert():
            try:
                url = f"{_SB_URL}/rest/v1/sf_userdata"
                headers = {**_sb_ud_headers(), "Prefer": "resolution=merge-duplicates"}
                payload = {"user_id": user_id, "data": data, "updated_at": dt_iso}
                resp = httpx.post(url, headers=headers, json=payload, timeout=10)
                if resp.status_code not in (200, 201):
                    logger.warning(f"Supabase save_userdata HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.warning(f"Supabase save_userdata falhou: {e}")
        threading.Thread(target=_upsert, daemon=True).start()

    return jsonify({"ok": True})

@app.route("/api/userdata/ts", methods=["GET"])
@requer_auth
def get_userdata_ts():
    """Retorna apenas o timestamp da última atualização (leve, para polling)."""
    user_id = request.user["sub"]

    # 1. Cache de timestamp em memória
    if user_id in _user_data_ts:
        return jsonify({"ts": _user_data_ts[user_id], "user_id": user_id})

    # 2. Tenta Supabase (só o campo updated_at — leve)
    if _SB_URL and _SB_KEY:
        try:
            url = f"{_SB_URL}/rest/v1/sf_userdata?user_id=eq.{user_id}&select=updated_at"
            resp = httpx.get(url, headers=_sb_ud_headers(), timeout=5)
            if resp.status_code == 200:
                rows = resp.json()
                if rows:
                    raw_ts = rows[0].get("updated_at", "")
                    try:
                        ts = int(datetime.fromisoformat(str(raw_ts).replace("Z","+00:00")).timestamp() * 1000)
                    except Exception:
                        ts = 0
                    _user_data_ts[user_id] = ts
                    return jsonify({"ts": ts, "user_id": user_id})
            else:
                logger.warning(f"Supabase get_userdata_ts HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Supabase get_userdata_ts falhou, usando arquivo: {e}")

    # 3. Fallback: mtime do arquivo local
    path = _ud_path(user_id)
    ts = 0
    if _os.path.exists(path):
        ts = int(_os.path.getmtime(path) * 1000)
    return jsonify({"ts": ts, "user_id": user_id})


# ── PDF Import Parser ────────────────────────────────────────────────
import re as _re
import io as _io

def _detectar_banco_txt(txt: str) -> str | None:
    t = txt.lower()
    bid = _re.search(r'<bankid>0*(\d+)', txt, _re.I)
    if bid:
        codes = {'341':'Itaú','237':'Bradesco','001':'Banco do Brasil','033':'Santander',
                 '260':'Nubank','077':'Inter','104':'Caixa','336':'C6 Bank',
                 '655':'Neon','290':'PagSeguro','323':'Mercado Pago','212':'Banco Original'}
        if bid.group(1) in codes:
            return codes[bid.group(1)]
    if 'nu pagamentos' in t or 'nubank' in t: return 'Nubank'
    if 'instituição: banco inter' in t or 'banco inter' in t or 'inter s.a' in t: return 'Inter'
    if 'bradesco' in t: return 'Bradesco'
    if 'itaú' in t or 'itau' in t: return 'Itaú'
    if 'santander' in t: return 'Santander'
    if 'caixa econômica' in t or ' cef ' in t: return 'Caixa'
    if 'banco do brasil' in t: return 'Banco do Brasil'
    if 'c6 bank' in t or 'c6bank' in t or 'banco c6' in t: return 'C6 Bank'
    if 'neon' in t: return 'Neon'
    if 'mercado pago' in t: return 'Mercado Pago'
    return None

# ── Dicionários de meses (PT-BR + abreviados + inglês) ──────────────────────
_MESES_PT = {
    'janeiro':'01','fevereiro':'02','março':'03','marco':'03',
    'abril':'04','maio':'05','junho':'06','julho':'07',
    'agosto':'08','setembro':'09','outubro':'10',
    'novembro':'11','dezembro':'12',
    'jan':'01','fev':'02','mar':'03','abr':'04','mai':'05','jun':'06',
    'jul':'07','ago':'08','set':'09','out':'10','nov':'11','dez':'12',
    'jan.':'01','fev.':'02','mar.':'03','abr.':'04','mai.':'05','jun.':'06',
    'jul.':'07','ago.':'08','set.':'09','out.':'10','nov.':'11','dez.':'12',
    'january':'01','february':'02','march':'03','april':'04','may':'05','june':'06',
    'july':'07','august':'08','september':'09','october':'10','november':'11','december':'12',
}
_MESES_ABR = {k:v for k,v in _MESES_PT.items() if len(k.replace('.',''))<=4}

def _normalizar_mes(s: str) -> str:
    rep = {'ç':'c','ã':'a','â':'a','á':'a','à':'a','ê':'e','é':'e','è':'e',
           'ô':'o','ó':'o','ú':'u','ü':'u','í':'i','î':'i'}
    return ''.join(rep.get(c,c) for c in s.lower())

_parcela_re = _re.compile(r'[(\[]\s*[Pp]arcela\s+(\d+)\s+de\s+(\d+)\s*[)\]]')

# ── Helpers de parsing ───────────────────────────────────────────────────────
_AMT_RE = _re.compile(r'([+\-]?\s*R?\$?\s*\d{1,3}(?:\.\d{3})*,\d{2})', _re.I)

def _parse_valor_str(s: str):
    """(float_abs, is_negative)  — formato brasileiro 1.234,56"""
    s = str(s or '').strip()
    neg = s.startswith('-') or s.endswith('-')
    clean = _re.sub(r'[^\d,]', '', s)           # keep only digits + comma
    if ',' in clean:
        int_part, dec_part = clean.rsplit(',', 1)
        try:
            return abs(float(f"{int_part or 0}.{dec_part[:2]}")), neg
        except ValueError:
            return 0.0, False
    try:
        return abs(float(clean)), neg
    except ValueError:
        return 0.0, False

def _make_date(d, m, y=''):
    from datetime import datetime
    if not y: y = str(datetime.utcnow().year)
    if len(str(y)) == 2: y = '20' + str(y)
    try:
        d, m = int(d), int(m)
        if not (1 <= d <= 31 and 1 <= m <= 12): return None
        return f"{d:02d}/{m:02d}/{y}"
    except (ValueError, TypeError):
        return None

def _resolve_mes(s: str):
    """'março' / 'mar' / 'mar.' → '03'"""
    s = s.lower().strip().rstrip('.')
    return _MESES_PT.get(s) or _MESES_PT.get(_normalizar_mes(s)) or _MESES_PT.get(s[:3])

def _add_row(rows, seen, data, desc, valor, tipo, pa=1, pt=1):
    if not data or valor <= 0: return
    desc = _re.sub(r'\s+', ' ', str(desc).strip())[:80]
    if not desc: return
    key = f"{data}|{desc[:28]}|{round(valor,2)}"
    if key in seen: return
    seen.add(key)
    pm = _parcela_re.search(desc)
    if pm: pa, pt = int(pm.group(1)), int(pm.group(2))
    rows.append({'data': data, 'descricao': desc, 'valor': round(valor, 2),
                 'tipo': tipo, 'parcela_atual': pa, 'parcelas': pt})

# ── Strategy 1 — pdfplumber table extraction ─────────────────────────────────
def _try_table_parse(pdf_bytes: bytes, rows: list, seen: set) -> int:
    """
    Extrai transações de tabelas estruturadas (Bradesco, Itaú, Caixa, Sicredi…).
    Tenta múltiplas estratégias de detecção de tabela.
    Retorna o número de linhas adicionadas.
    """
    import pdfplumber
    from datetime import datetime
    cur_year = str(datetime.utcnow().year)

    _DATE_RE  = _re.compile(r'^(\d{1,2})[/\-\.](\d{1,2})(?:[/\-\.](\d{2,4}))?$')
    _MONEY_RE = _re.compile(r'\d{1,3}(?:\.\d{3})*,\d{2}')

    DATE_HDR = {'data','dt','dia','date','data mov','data lanç','data mov.','data lançamento','data movimentação','data movimentacao'}
    DESC_HDR = {'histórico','historico','descrição','descricao','descrição','lançamento','lancamento',
                'estabelecimento','detalhes','memo','complemento','discriminação','discriminacao','narrat'}
    VAL_HDR  = {'valor','vr','quantia','montante','value','importe'}
    DEB_HDR  = {'débito','debito','déb','deb','saída','saida','retirada','pagamento','d'}
    CRE_HDR  = {'crédito','credito','créd','cred','entrada','depósito','deposito','aplicação','c'}
    CD_HDR   = {'c/d','d/c','tipo','natureza','operação','entrada/saída','cr/db','cd','operacao'}
    BAL_HDR  = {'saldo','balance','sal'}

    added_before = len(rows)

    strategies = [
        {'vertical_strategy':'lines','horizontal_strategy':'lines'},
        {'vertical_strategy':'lines_strict','horizontal_strategy':'lines_strict'},
        {'vertical_strategy':'text','horizontal_strategy':'text'},
        {},
    ]

    with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for strat in strategies:
                try:
                    tables = page.extract_tables(strat) if strat else page.extract_tables()
                except Exception:
                    continue

                for table in (tables or []):
                    if not table or len(table) < 2: continue
                    ncols = max((len(r) for r in table if r), default=0)
                    if ncols < 2: continue

                    # ── Identificar colunas ──────────────────────────────
                    date_c = desc_c = val_c = deb_c = cre_c = cd_c = bal_c = None

                    hdr = [str(c or '').lower().strip() for c in (table[0] or [])]
                    for j, h in enumerate(hdr):
                        h_clean = _re.sub(r'[^\w/]','',h)
                        if date_c is None and (h in DATE_HDR or h_clean in DATE_HDR): date_c = j
                        elif cd_c is None and (h in CD_HDR or h_clean in CD_HDR): cd_c = j
                        elif cre_c is None and (h in CRE_HDR or h_clean in CRE_HDR): cre_c = j
                        elif deb_c is None and (h in DEB_HDR or h_clean in DEB_HDR): deb_c = j
                        elif val_c is None and (h in VAL_HDR or h_clean in VAL_HDR): val_c = j
                        elif bal_c is None and (h in BAL_HDR or h_clean in BAL_HDR): bal_c = j
                        elif desc_c is None and any(k in h for k in DESC_HDR): desc_c = j

                    # Auto-detect via dados se header não ajudou
                    if date_c is None and val_c is None and deb_c is None:
                        date_cnt  = [0]*ncols
                        money_cnt = [0]*ncols
                        text_len  = [0]*ncols
                        for row in table[1:8]:
                            if not row: continue
                            for j, cell in enumerate(row[:ncols]):
                                c = str(cell or '').strip()
                                if _DATE_RE.match(c.replace(' ','/').replace('.','/') if c else ''): date_cnt[j] += 1
                                if _MONEY_RE.search(c): money_cnt[j] += 1
                                text_len[j] += len(c)
                        if max(date_cnt, default=0) > 0:
                            date_c = date_cnt.index(max(date_cnt))
                        mcols = sorted([j for j in range(ncols) if money_cnt[j]>0], key=lambda j: -money_cnt[j])
                        if len(mcols)==1:   val_c = mcols[0]
                        elif len(mcols)==2: deb_c,bal_c = mcols[0],mcols[1]
                        elif len(mcols)>=3: cre_c,deb_c,bal_c = mcols[0],mcols[1],mcols[2]
                        if desc_c is None and date_c is not None:
                            cands = [j for j in range(ncols) if j not in (date_c,)+tuple(mcols) and j!=cd_c]
                            if cands: desc_c = max(cands, key=lambda j: text_len[j] if j<ncols else 0)

                    if date_c is None and val_c is None and deb_c is None: continue

                    # ── Processar linhas ─────────────────────────────────
                    for row in table[1:]:
                        if not row: continue
                        cells = [str(c or '').strip() for c in row] + ['']*(ncols+2)

                        # Data
                        dstr = cells[date_c] if date_c is not None else cells[0]
                        dstr = dstr.replace(' ','/').replace('.','/').strip()
                        dm = _DATE_RE.match(dstr)
                        if not dm:
                            # Tentar data por extenso dentro da célula: "19 jan 2025"
                            tm = _re.match(r'(\d{1,2})\s+([a-zA-ZÀ-ÿ]{3,})\.?\s*(\d{4})?', dstr)
                            if tm:
                                mo = _resolve_mes(tm.group(2))
                                if mo:
                                    data = _make_date(tm.group(1), mo, tm.group(3) or cur_year)
                                else: continue
                            else: continue
                        else:
                            dd, mm, yy = dm.group(1), dm.group(2), dm.group(3) or cur_year
                            if not mm.isdigit():
                                mo = _resolve_mes(mm)
                                if not mo: continue
                                mm = mo
                            data = _make_date(dd, mm, yy)
                            if not data: continue

                        # Descrição
                        if desc_c is not None:
                            desc = cells[desc_c]
                        else:
                            skip_j = {date_c, val_c, deb_c, cre_c, cd_c, bal_c} - {None}
                            desc = ' '.join(cells[j] for j in range(ncols) if j not in skip_j and cells[j] and not _MONEY_RE.search(cells[j]))

                        # Valor e tipo
                        valor, tipo = 0.0, 'gasto'
                        if cre_c is not None and deb_c is not None:
                            dv, _ = _parse_valor_str(cells[deb_c])
                            cv, _ = _parse_valor_str(cells[cre_c])
                            if dv > 0:   valor, tipo = dv, 'gasto'
                            elif cv > 0: valor, tipo = cv, 'receita'
                        elif val_c is not None:
                            valor, neg = _parse_valor_str(cells[val_c])
                            if cd_c is not None:
                                cd = cells[cd_c].upper().strip().lstrip('(').rstrip(')')
                                tipo = 'receita' if cd[:1] in ('C','+') else 'gasto'
                            else:
                                tipo = 'gasto' if neg else 'receita'
                        elif deb_c is not None:
                            valor, _ = _parse_valor_str(cells[deb_c])
                            if cd_c is not None:
                                cd = cells[cd_c].upper().strip()
                                tipo = 'receita' if cd[:1] in ('C','+') else 'gasto'

                        # Fallback: varre células buscando qualquer valor monetário
                        if valor <= 0:
                            for j in range(ncols):
                                if j == bal_c: continue
                                m = _MONEY_RE.search(cells[j])
                                if m:
                                    valor, neg = _parse_valor_str(cells[j])
                                    if valor > 0:
                                        tipo = 'gasto' if neg else 'receita'
                                        break

                        if not desc or valor <= 0: continue
                        _add_row(rows, seen, data, desc, valor, tipo)

                if len(rows) - added_before >= 3:
                    return len(rows) - added_before  # achou dados suficientes

    return len(rows) - added_before

# ── Strategy 2 — line-based heuristics ──────────────────────────────────────
def _line_parse(txt: str, rows: list, seen: set):
    """
    Parser linha a linha — suporta Inter, Nubank, formatos livres.
    Detecta: DD/MM/YYYY, DD/MM, DD de Mês de YYYY, DD de mes. YYYY
    """
    from datetime import datetime
    cur_year = str(datetime.utcnow().year)
    lines = [l.strip() for l in txt.splitlines() if l.strip()]

    # Padrões de data
    re_long = _re.compile(r'\b(\d{1,2})\s+de\s+([a-zA-ZÀ-ÿ]+)\s+de\s+(\d{4})\b', _re.I)  # DD de Mês de YYYY
    re_abr  = _re.compile(r'^(\d{1,2})\s+de\s+([a-zA-ZÀ-ÿ]{3,})\.?\s+(\d{4})\b', _re.I)  # DD de mes. YYYY
    re_iso  = _re.compile(r'^(\d{2})[/\-](\d{2})[/\-](\d{2,4})\s+(.+)')                   # DD/MM/YYYY resto
    re_short = _re.compile(r'^(\d{2})[/\-](\d{2})\s+(.+)')                                 # DD/MM resto

    skip = {
        'saldo total','saldo anterior','saldo disponível','saldo do dia',
        'data movimenta','beneficiário','beneficiario','fatura atual',
        'próxima fatura','saldo em aberto','limite de crédito',
        'pagamento mínimo','encargos','valor do documento','data de vencimento',
        'movimentação','total cartão','parcelamento','próximo período',
        'data corte','saldo demais','compras parceladas','extrato de conta',
        'agência','conta corrente','período','página','page','emissão',
        'saldo inicial','saldo final','total de débitos','total de créditos',
    }
    tx_starts = [
        'compra','pix','pagamento','depósito','deposito','saque',
        'transferência','transferencia','rendimento','iof','tarifa',
        'ted','doc','estorno','reembolso','resgate','débito','crédito',
    ]

    extrato_date = None
    i = 0
    while i < len(lines):
        line = lines[i]; i += 1
        low = line.lower()
        if len(line) < 4: continue
        if any(p in low for p in skip): continue

        # ── DD de Mês de YYYY como cabeçalho de data ──
        m = re_long.search(line)
        if m and ('saldo' in low or 'dia' in low or 'moviment' in low or 'extrato' in low):
            mo = _resolve_mes(m.group(2))
            if mo:
                extrato_date = _make_date(m.group(1), mo, m.group(3))
            continue

        # ── DD de mes. YYYY + transação na mesma linha ──
        m = re_abr.match(line)
        if m:
            mo = _resolve_mes(m.group(2))
            if mo:
                data = _make_date(m.group(1), mo, m.group(3))
                if data:
                    rest = line[m.end():].strip()
                    if not _AMT_RE.search(rest) and i < len(lines):
                        rest = rest + ' ' + lines[i]; i += 1
                    amounts = _AMT_RE.findall(rest)
                    if amounts:
                        tx_str = amounts[-1]
                        valor, _ = _parse_valor_str(tx_str)
                        fm = _AMT_RE.search(rest)
                        desc = (rest[:fm.start()] if fm else rest).strip()
                        desc = _re.sub(r'\s*[-–—]\s*$', '', desc).strip()
                        tipo = 'receita' if tx_str.strip().startswith('+') else 'gasto'
                        _add_row(rows, seen, data, desc, valor, tipo)
            continue

        # ── DD/MM/YYYY resto ──
        m = re_iso.match(line)
        if m:
            data = _make_date(m.group(1), m.group(2), m.group(3))
            if data:
                rest = m.group(4)
                if not _AMT_RE.search(rest) and i < len(lines):
                    rest = rest + ' ' + lines[i]; i += 1
                amounts = _AMT_RE.findall(rest)
                if amounts:
                    tx_str = amounts[-2] if len(amounts) >= 2 else amounts[-1]
                    valor, neg = _parse_valor_str(tx_str)
                    if valor > 0:
                        fm = _AMT_RE.search(rest)
                        desc = (rest[:fm.start()] if fm else rest).strip().strip('"')
                        # Indicador C/D no final da descrição (ex: Caixa, Sicredi)
                        cd_m = _re.search(r'\s+([CD])\s*$', desc, _re.I)
                        if cd_m:
                            tipo = 'receita' if cd_m.group(1).upper()=='C' else 'gasto'
                            desc = desc[:cd_m.start()].strip()
                        else:
                            tipo = 'gasto' if neg else 'receita'
                        _add_row(rows, seen, data, desc, valor, tipo)
            continue

        # ── DD/MM resto (sem ano — Itaú fatura, etc.) ──
        m = re_short.match(line)
        if m:
            data = _make_date(m.group(1), m.group(2), cur_year)
            if data:
                rest = m.group(3)
                if not _AMT_RE.search(rest) and i < len(lines):
                    rest = rest + ' ' + lines[i]; i += 1
                amounts = _AMT_RE.findall(rest)
                if amounts:
                    tx_str = amounts[-2] if len(amounts) >= 2 else amounts[-1]
                    valor, neg = _parse_valor_str(tx_str)
                    if valor > 0:
                        fm = _AMT_RE.search(rest)
                        desc = (rest[:fm.start()] if fm else rest).strip()
                        cd_m = _re.search(r'\s+([CD])\s*$', desc, _re.I)
                        if cd_m:
                            tipo = 'receita' if cd_m.group(1).upper()=='C' else 'gasto'
                            desc = desc[:cd_m.start()].strip()
                        else:
                            tipo = 'gasto' if neg else 'receita'
                        _add_row(rows, seen, data, desc, valor, tipo)
            continue

        # ── Modo extrato (palavras-chave após cabeçalho de data) ──
        if not extrato_date: continue
        if not any(low.startswith(k) for k in tx_starts): continue
        full = line
        if not _AMT_RE.search(full) and i < len(lines):
            full = full + ' ' + lines[i]; i += 1
        amounts = _AMT_RE.findall(full)
        if not amounts: continue
        tx_str = amounts[-2] if len(amounts) >= 2 else amounts[-1]
        neg = tx_str.strip().startswith('-')
        valor, _ = _parse_valor_str(tx_str)
        if valor <= 0: continue
        fm = _AMT_RE.search(full)
        desc = (full[:fm.start()] if fm else full).strip()
        desc = _re.sub(r'^[^:]+:\s*"?', '', desc).strip('"').strip()
        desc = _re.sub(r'^No estabelecimento\s+', '', desc, flags=_re.I).strip()
        _add_row(rows, seen, extrato_date, desc or 'Transação', valor, 'gasto' if neg else 'receita')


def _parse_pdf_rows(txt: str, pdf_bytes: bytes = None) -> list:
    """
    Parser universal de extratos bancários.
    Estratégia 1: extração de tabelas pdfplumber (Bradesco, Itaú, Caixa, Sicredi…)
    Estratégia 2: heurística linha a linha (Inter, Nubank, formatos livres)
    """
    rows = []
    seen = set()

    # Tenta extração estruturada via tabelas
    if pdf_bytes:
        try:
            n = _try_table_parse(pdf_bytes, rows, seen)
            if n >= 2:
                return rows
        except Exception as _e:
            logger.debug(f"table parse falhou, usando line parse: {_e}")
        rows.clear(); seen.clear()

    # Fallback: parser linha a linha
    _line_parse(txt, rows, seen)
    return rows

@app.route("/api/parse-pdf", methods=["POST"])
@requer_auth
def parse_pdf():
    if 'file' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
    f = request.files['file']
    try:
        import pdfplumber
        pdf_bytes = f.read()
        full_text = []
        with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text(x_tolerance=3, y_tolerance=3)
                if txt:
                    full_text.append(txt)
        combined = '\n'.join(full_text)
        banco = _detectar_banco_txt(combined)
        rows = _parse_pdf_rows(combined, pdf_bytes=pdf_bytes)
        return jsonify({"banco": banco, "rows": rows, "total": len(rows)})
    except ImportError:
        return jsonify({"erro": "pdfplumber não instalado no servidor"}), 500
    except Exception as e:
        logger.error(f"parse_pdf error: {e}")
        return jsonify({"erro": f"Erro ao ler PDF: {str(e)}"}), 500


# ── Health ────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status":"ok","sheets": sheets is not None})


def start(port=8080):
    init_sheets()
    # Seed de perfil de demonstração (roda em background, idempotente)
    try:
        from seed_test_user import run_seed_background
        run_seed_background()
    except Exception as _e:
        logger.warning(f"Seed import falhou: {_e}")
    t = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True
    )
    t.start()
    logger.info(f"🌐 Dashboard em http://0.0.0.0:{port}")
    return t
