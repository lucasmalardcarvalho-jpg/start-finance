"""
START FINANCE — Google Sheets Manager v4.0
14 colunas: + Método de Pagamento, Parcela, Total Parcelas
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
            mes_ano = agora.strftime("%b./%Y").lower()
            # Formato: mar./2026
            mes_ano = agora.strftime("%b./").lower() + str(agora.year)

            # Formata parcelas
            parcela_atual = dados.get("parcela_atual", 0) or 0
            total_parcelas = dados.get("total_parcelas", 0) or 0
            parcela_str = f"{parcela_atual}/{total_parcelas}" if total_parcelas > 0 else ""

            nova_linha = [
                dados.get("data", agora.strftime("%d/%m/%Y")),      # A - Data
                dados.get("hora", agora.strftime("%H:%M")),          # B - Hora
                float(dados.get("valor", 0)),                        # C - Valor
                dados.get("tipo", "Gasto"),                          # D - Tipo
                dados.get("categoria", "Outros"),                    # E - Categoria
                dados.get("subcategoria", ""),                       # F - Subcategoria
                dados.get("descricao", ""),                          # G - Descrição
                dados.get("localizacao", ""),                        # H - Localização
                dados.get("metodo_pagamento", ""),                   # I - Método
                parcela_atual if total_parcelas > 0 else "",         # J - Parcela atual
                total_parcelas if total_parcelas > 0 else "",        # K - Total parcelas
                "Telegram",                                          # L - Canal
                mes_ano,                                             # M - Mês/Ano
                "✅"                                                  # N - Status
            ]

            self.aba_transacoes.append_row(nova_linha, value_input_option="USER_ENTERED")
            logger.info(f"✅ Registrado: {dados.get('descricao')} R${dados.get('valor')}")

            return self.get_saldo_mes()

        except Exception as e:
            logger.error(f"❌ Erro ao registrar: {e}")
            raise

    def get_saldo_mes(self) -> float:
        """Calcula o saldo do mês atual."""
        try:
            agora = datetime.now()
            mes_atual = agora.strftime("%b./").lower() + str(agora.year)
            todas = self.aba_transacoes.get_all_records()

            saldo = 0.0
            for row in todas:
                if str(row.get("MÊS/ANO", "")).strip().lower() == mes_atual:
                    try:
                        saldo += float(row.get("VALOR (R$)", 0))
                    except (ValueError, TypeError):
                        pass
            return saldo

        except Exception as e:
            logger.error(f"❌ Erro ao calcular saldo: {e}")
            return 0.0

    def get_resumo_mes(self) -> dict:
        """Retorna resumo completo do mês atual."""
        try:
            agora = datetime.now()
            mes_atual = agora.strftime("%b./").lower() + str(agora.year)
            todas = self.aba_transacoes.get_all_records()

            entradas = 0.0
            saidas = 0.0
            categorias = defaultdict(float)
            metodos = defaultdict(float)
            total_registros = 0

            for row in todas:
                if str(row.get("MÊS/ANO", "")).strip().lower() != mes_atual:
                    continue
                try:
                    valor = float(row.get("VALOR (R$)", 0))
                    total_registros += 1
                    if valor > 0:
                        entradas += valor
                    else:
                        saidas += abs(valor)
                        cat = row.get("CATEGORIA", "Outros")
                        if cat:
                            categorias[cat] += abs(valor)
                        metodo = row.get("MÉTODO", "")
                        if metodo:
                            metodos[metodo] += abs(valor)
                except (ValueError, TypeError):
                    pass

            return {
                "entradas": entradas,
                "saidas": saidas,
                "saldo": entradas - saidas,
                "categorias": dict(sorted(categorias.items(), key=lambda x: x[1], reverse=True)),
                "metodos": dict(sorted(metodos.items(), key=lambda x: x[1], reverse=True)),
                "total_registros": total_registros
            }

        except Exception as e:
            logger.error(f"❌ Erro no resumo: {e}")
            raise

    def get_top_categorias(self, n: int = 3) -> list:
        """Retorna as N categorias com maior gasto."""
        try:
            resumo = self.get_resumo_mes()
            return list(resumo["categorias"].items())[:n]
        except Exception as e:
            logger.error(f"❌ Erro top categorias: {e}")
            return []
