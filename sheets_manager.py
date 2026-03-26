"""
START FINANCE — Google Sheets Manager v6.0
Métodos completos para dashboard web + API + bot
"""

import os, json, logging
from datetime import datetime, timedelta
from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MESES_PT   = ['jan.','fev.','mar.','abr.','mai.','jun.',
              'jul.','ago.','set.','out.','nov.','dez.']

LIMITES_PADRAO = {
    "Alimentação":800,"Transporte":400,"Contas":600,"Lazer":300,
    "Saúde":200,"Educação":200,"Moradia":1500,"Beleza":200,
    "Vestuário":300,"Pet":200,"Tecnologia":500,"Filhos":400,
    "Presentes":100,"Veículo":300,"Impostos":200,"Assinaturas":150,
    "Outros":200,
}

EMOJIS_CAT = {
    "Alimentação":"🍽️","Transporte":"🚗","Contas":"⚡","Lazer":"🎮",
    "Saúde":"❤️","Educação":"📚","Moradia":"🏠","Beleza":"💅",
    "Vestuário":"👗","Pet":"🐾","Tecnologia":"📱","Filhos":"👶",
    "Presentes":"🎁","Veículo":"🚘","Impostos":"🧾","Assinaturas":"📺",
    "Salário":"💰","Freelance":"💼","Investimento":"📈","Outros":"📦",
}

CORES_CAT = {
    "Alimentação":"#EF4444","Transporte":"#F97316","Contas":"#3B6FF0",
    "Lazer":"#8B5CF6","Saúde":"#10B981","Educação":"#F59E0B",
    "Moradia":"#6366F1","Beleza":"#EC4899","Vestuário":"#14B8A6",
    "Pet":"#84CC16","Tecnologia":"#0EA5E9","Filhos":"#F472B6",
    "Presentes":"#FB923C","Veículo":"#64748B","Impostos":"#78716C",
    "Assinaturas":"#A78BFA","Salário":"#10B981","Freelance":"#34D399",
    "Investimento":"#3B6FF0","Outros":"#9CA3AF",
}


def get_mes_ano(data: datetime = None) -> str:
    d = data or datetime.now()
    return f"{MESES_PT[d.month - 1]}/{d.year}"


def parsear_valor(v) -> float:
    try:
        s = str(v).replace("R$","").replace(" ","").replace(".","").replace(",",".").strip()
        return float(s)
    except (ValueError, TypeError):
        return 0.0


class SheetsManager:
    def __init__(self):
        self.sheet = None
        self.aba_transacoes = None
        self._conectar()

    def _conectar(self):
        try:
            creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
            if creds_json:
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            else:
                creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
            client = gspread.authorize(creds)
            nome = os.environ.get("SHEET_NAME", "Start Finance")
            self.sheet = client.open(nome)
            self.aba_transacoes = self.sheet.worksheet("Transacoes")
            logger.info("✅ Google Sheets conectado!")
        except Exception as e:
            logger.error(f"❌ Erro Sheets: {e}")
            raise

    def _get_todos_registros(self) -> list:
        try:
            return self.aba_transacoes.get_all_records(head=3)
        except Exception:
            try:
                vals = self.aba_transacoes.get_all_values()
                if len(vals) < 3:
                    return []
                headers = vals[2]
                return [
                    {headers[i]: (row[i] if i < len(row) else "")
                     for i in range(len(headers))}
                    for row in vals[3:] if any(c for c in row)
                ]
            except Exception as e2:
                logger.error(f"❌ Erro leitura: {e2}")
                return []

    def _col(self, row, *nomes):
        for n in nomes:
            v = row.get(n, "")
            if v != "":
                return v
        return ""

    # ── REGISTRAR ───────────────────────────────────────────────────
    def registrar_transacao(self, dados: dict) -> float:
        try:
            agora   = datetime.now()
            mes_ano = get_mes_ano(agora)
            pa = int(dados.get("parcela_atual",  0) or 0)
            pt = int(dados.get("total_parcelas", 0) or 0)

            self.aba_transacoes.append_row([
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
            ], value_input_option="USER_ENTERED")
            logger.info(f"✅ {dados.get('descricao')} R${dados.get('valor')}")
            return self.get_saldo_mes()
        except Exception as e:
            logger.error(f"❌ Erro registrar: {e}")
            raise

    # ── SALDO ───────────────────────────────────────────────────────
    def get_saldo_mes(self) -> float:
        mes = get_mes_ano()
        return sum(
            parsear_valor(self._col(r, "VALOR (R$)", "VALOR"))
            for r in self._get_todos_registros()
            if str(self._col(r, "MÊS/ANO", "MES/ANO")).strip() == mes
        )

    # ── RESUMO ──────────────────────────────────────────────────────
    def get_resumo_mes(self) -> dict:
        mes = get_mes_ano()
        e = s = total = 0.0
        cats    = defaultdict(float)
        metodos = defaultdict(float)

        for row in self._get_todos_registros():
            if str(self._col(row, "MÊS/ANO", "MES/ANO")).strip() != mes:
                continue
            v   = parsear_valor(self._col(row, "VALOR (R$)", "VALOR"))
            cat = str(self._col(row, "CATEGORIA")).strip() or "Outros"
            met = str(self._col(row, "MÉTODO", "METODO")).strip()
            total += 1
            if v > 0:
                e += v
            else:
                s += abs(v)
                cats[cat] += abs(v)
                if met:
                    metodos[met] += abs(v)

        # Categorias detalhadas
        cats_det = []
        for cat, gasto in sorted(cats.items(), key=lambda x: x[1], reverse=True):
            lim = LIMITES_PADRAO.get(cat, 0)
            pct = (gasto / lim * 100) if lim > 0 else 0
            cats_det.append({
                "nome":    cat,
                "emoji":   EMOJIS_CAT.get(cat, "📦"),
                "cor":     CORES_CAT.get(cat, "#9CA3AF"),
                "gasto":   round(gasto, 2),
                "limite":  lim,
                "pct":     round(pct, 1),
                "status":  "estourou" if pct >= 100 else ("atencao" if pct >= 80 else ("ok" if gasto > 0 else "livre")),
            })

        # Métodos
        total_met = sum(metodos.values()) or 1
        metodos_fmt = [
            {"nome": m, "valor": round(v, 2), "pct": round(v/total_met*100, 1)}
            for m, v in sorted(metodos.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "entradas": round(e, 2), "saidas": round(s, 2),
            "saldo": round(e - s, 2), "total_registros": int(total),
            "categorias": dict(sorted(cats.items(), key=lambda x: x[1], reverse=True)),
            "categorias_detalhadas": cats_det,
            "metodos": metodos_fmt,
        }

    # ── ÚLTIMAS TRANSAÇÕES ──────────────────────────────────────────
    def get_ultimas_transacoes(self, n: int = 10) -> list:
        todos   = self._get_todos_registros()
        ultimas = []
        for row in reversed(todos[-50:]):
            v   = parsear_valor(self._col(row, "VALOR (R$)", "VALOR"))
            cat = str(self._col(row, "CATEGORIA")).strip() or "Outros"
            try:
                pt = int(float(str(self._col(row, "TOTAL PARC.", "TOTAL_PARCELAS") or 0)))
            except (ValueError, TypeError):
                pt = 0
            ultimas.append({
                "data":        str(self._col(row, "DATA")).strip(),
                "hora":        str(self._col(row, "HORA")).strip(),
                "valor":       round(v, 2),
                "tipo":        str(self._col(row, "TIPO")).strip(),
                "categoria":   cat,
                "subcategoria":str(self._col(row, "SUBCATEGORIA")).strip(),
                "descricao":   str(self._col(row, "DESCRIÇÃO", "DESCRICAO")).strip(),
                "localizacao": str(self._col(row, "LOCALIZAÇÃO", "LOCALIZACAO")).strip(),
                "metodo":      str(self._col(row, "MÉTODO", "METODO")).strip(),
                "parcelas":    pt,
                "emoji":       EMOJIS_CAT.get(cat, "📦"),
                "cor":         CORES_CAT.get(cat, "#9CA3AF"),
            })
            if len(ultimas) >= n:
                break
        return ultimas

    # ── HISTÓRICO 6 MESES ───────────────────────────────────────────
    def get_historico_6_meses(self) -> list:
        agora = datetime.now()
        todos = self._get_todos_registros()
        hist  = []
        for i in range(5, -1, -1):
            d   = (agora.replace(day=1) - timedelta(days=i*28)).replace(day=1)
            mes = get_mes_ano(d)
            e = s = 0.0
            for row in todos:
                if str(self._col(row, "MÊS/ANO", "MES/ANO")).strip() != mes:
                    continue
                v = parsear_valor(self._col(row, "VALOR (R$)", "VALOR"))
                if v > 0: e += v
                else:     s += abs(v)
            hist.append({
                "mes":      mes,
                "label":    MESES_PT[d.month-1].replace(".","").capitalize(),
                "entradas": round(e, 2),
                "saidas":   round(s, 2),
                "saldo":    round(e - s, 2),
                "atual":    (i == 0),
            })
        return hist

    # ── PREVISÃO ────────────────────────────────────────────────────
    def get_previsao_proximo_mes(self) -> dict:
        hist = self.get_historico_6_meses()
        com_dados = [h for h in hist if h["entradas"] > 0 or h["saidas"] > 0]
        if not com_dados:
            return {"entradas": 0, "saidas": 0, "saldo": 0}
        me = sum(h["entradas"] for h in com_dados) / len(com_dados)
        ms = sum(h["saidas"]   for h in com_dados) / len(com_dados)
        pe = round(me, 2)
        ps = round(ms * 1.05, 2)
        return {"entradas": pe, "saidas": ps, "saldo": round(pe - ps, 2)}

    # ── BADGES ──────────────────────────────────────────────────────
    def get_badges_status(self) -> list:
        resumo    = self.get_resumo_mes()
        n         = resumo["total_registros"]
        saldo     = resumo["saldo"]
        n_est     = sum(1 for c in resumo["categorias_detalhadas"] if c["status"] == "estourou")
        return [
            {"id":"sequencia","emoji":"🔥","nome":"Sequência de Fogo",
             "desc":"7+ registros no mês","pct":min(n/7*100,100),
             "status":"conquistado" if n>=7 else "progresso","progresso":f"{min(n,7)}/7"},
            {"id":"poupador","emoji":"🐷","nome":"Porquinho Sábio",
             "desc":"Mês com saldo positivo","pct":100 if saldo>0 else 50,
             "status":"conquistado" if saldo>0 else "progresso","progresso":"✅" if saldo>0 else "⏳"},
            {"id":"arqueiro","emoji":"🎯","nome":"Arqueiro do Orçamento",
             "desc":"Sem estourar limites","pct":100 if n_est==0 else max(0,(5-n_est)/5*100),
             "status":"conquistado" if n_est==0 else "progresso","progresso":"✅" if n_est==0 else f"{n_est} estouros"},
            {"id":"mestre","emoji":"📊","nome":"Mestre dos Registros",
             "desc":"20+ registros no mês","pct":min(n/20*100,100),
             "status":"conquistado" if n>=20 else "progresso","progresso":f"{min(n,20)}/20"},
        ]

    # ── TOP CATEGORIAS (para o bot) ──────────────────────────────────
    def get_top_categorias(self, n: int = 3) -> list:
        return list(self.get_resumo_mes()["categorias"].items())[:n]
