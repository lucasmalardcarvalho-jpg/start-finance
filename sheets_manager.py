"""
START FINANCE — Google Sheets Manager v5.0 Aurora
Correções: head=3, formato mes_ano consistente
"""

import os, json, logging
from datetime import datetime
from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Meses em português para formato consistente com o Apps Script
MESES_PT = ['jan.','fev.','mar.','abr.','mai.','jun.',
            'jul.','ago.','set.','out.','nov.','dez.']

def get_mes_ano(data: datetime = None) -> str:
    """Retorna o mês/ano no formato exato usado nas fórmulas: mar./2026"""
    d = data or datetime.now()
    return f"{MESES_PT[d.month - 1]}/{d.year}"


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
            nome_planilha = os.environ.get("SHEET_NAME", "Start Finance")
            self.sheet = client.open(nome_planilha)
            self.aba_transacoes = self.sheet.worksheet("Transacoes")
            logger.info("✅ Google Sheets conectado!")

        except Exception as e:
            logger.error(f"❌ Erro ao conectar Google Sheets: {e}")
            raise

    def registrar_transacao(self, dados: dict) -> float:
        """Registra uma transação na planilha com 14 colunas."""
        try:
            agora = datetime.now()
            mes_ano = get_mes_ano(agora)

            # Parcelas
            parcela_atual   = dados.get("parcela_atual", 0) or 0
            total_parcelas  = dados.get("total_parcelas", 0) or 0
            try:
                parcela_atual  = int(parcela_atual)
                total_parcelas = int(total_parcelas)
            except (ValueError, TypeError):
                parcela_atual = total_parcelas = 0

            nova_linha = [
                dados.get("data",  agora.strftime("%d/%m/%Y")),  # A - Data
                dados.get("hora",  agora.strftime("%H:%M")),     # B - Hora
                float(dados.get("valor", 0)),                    # C - Valor
                dados.get("tipo",        "Gasto"),               # D - Tipo
                dados.get("categoria",   "Outros"),              # E - Categoria
                dados.get("subcategoria",""),                    # F - Subcategoria
                dados.get("descricao",   ""),                    # G - Descrição
                dados.get("localizacao", ""),                    # H - Localização
                dados.get("metodo_pagamento", ""),               # I - Método
                parcela_atual  if total_parcelas > 0 else "",    # J - Parcela atual
                total_parcelas if total_parcelas > 0 else "",    # K - Total parcelas
                "Telegram",                                      # L - Canal
                mes_ano,                                         # M - Mês/Ano
                "✅"                                              # N - Status
            ]

            self.aba_transacoes.append_row(nova_linha, value_input_option="USER_ENTERED")
            logger.info(f"✅ Registrado: {dados.get('descricao')} | R${dados.get('valor')} | {mes_ano}")

            return self.get_saldo_mes()

        except Exception as e:
            logger.error(f"❌ Erro ao registrar: {e}")
            raise

    def _get_todos_registros(self) -> list:
        """
        Lê todos os registros da planilha.
        head=3 porque o cabeçalho está na linha 3 (Aurora Edition).
        """
        try:
            return self.aba_transacoes.get_all_records(head=3)
        except Exception:
            # Fallback: lê valores brutos e monta dicts manualmente
            try:
                valores = self.aba_transacoes.get_all_values()
                if len(valores) < 3:
                    return []
                headers = valores[2]  # linha 3 (índice 2) = cabeçalhos
                registros = []
                for row in valores[3:]:  # dados a partir da linha 4
                    if any(cell for cell in row):  # ignora linhas vazias
                        d = {}
                        for i, h in enumerate(headers):
                            d[h] = row[i] if i < len(row) else ""
                        registros.append(d)
                return registros
            except Exception as e2:
                logger.error(f"❌ Erro ao ler registros: {e2}")
                return []

    def get_saldo_mes(self) -> float:
        """Calcula o saldo do mês atual."""
        try:
            mes_atual = get_mes_ano()
            registros = self._get_todos_registros()
            saldo = 0.0
            for row in registros:
                # Tenta os dois possíveis nomes de coluna
                mes_row = str(row.get("MÊS/ANO", row.get("MES/ANO", ""))).strip()
                if mes_row == mes_atual:
                    try:
                        v = str(row.get("VALOR (R$)", row.get("VALOR", "0")))
                        v = v.replace("R$","").replace(".","").replace(",",".").strip()
                        saldo += float(v)
                    except (ValueError, TypeError):
                        pass
            return saldo

        except Exception as e:
            logger.error(f"❌ Erro ao calcular saldo: {e}")
            return 0.0

    def get_resumo_mes(self) -> dict:
        """Retorna resumo completo do mês atual."""
        try:
            mes_atual = get_mes_ano()
            registros = self._get_todos_registros()

            entradas   = 0.0
            saidas     = 0.0
            categorias = defaultdict(float)
            metodos    = defaultdict(float)
            total      = 0

            for row in registros:
                mes_row = str(row.get("MÊS/ANO", row.get("MES/ANO", ""))).strip()
                if mes_row != mes_atual:
                    continue
                try:
                    v_str = str(row.get("VALOR (R$)", row.get("VALOR", "0")))
                    v_str = v_str.replace("R$","").replace(".","").replace(",",".").strip()
                    valor = float(v_str)
                    total += 1
                    if valor > 0:
                        entradas += valor
                    else:
                        saidas += abs(valor)
                        cat = row.get("CATEGORIA", "Outros")
                        if cat:
                            categorias[cat] += abs(valor)
                        met = row.get("MÉTODO", "")
                        if met:
                            metodos[met] += abs(valor)
                except (ValueError, TypeError):
                    pass

            return {
                "entradas": entradas,
                "saidas":   saidas,
                "saldo":    entradas - saidas,
                "categorias": dict(sorted(categorias.items(), key=lambda x: x[1], reverse=True)),
                "metodos":    dict(sorted(metodos.items(),    key=lambda x: x[1], reverse=True)),
                "total_registros": total
            }

        except Exception as e:
            logger.error(f"❌ Erro no resumo: {e}")
            raise

    def get_top_categorias(self, n: int = 3) -> list:
        try:
            resumo = self.get_resumo_mes()
            return list(resumo["categorias"].items())[:n]
        except Exception as e:
            logger.error(f"❌ Erro top categorias: {e}")
            return []
