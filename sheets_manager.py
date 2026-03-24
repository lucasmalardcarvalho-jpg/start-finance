"""
╔══════════════════════════════════════╗
║   START FINANCE — Google Sheets      ║
║   Gerenciador de Planilha            ║
╚══════════════════════════════════════╝
"""

import os
import json
import logging
from datetime import datetime
from collections import defaultdict

import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

# Escopos necessários para Google Sheets + Drive
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
        """Conecta ao Google Sheets usando credenciais do ambiente."""
        try:
            # Credenciais via variável de ambiente (JSON como string)
            creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
            if creds_json:
                creds_dict = json.loads(creds_json)
                creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
            else:
                # Fallback: arquivo local (para testes)
                creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)

            client = gspread.authorize(creds)
            nome_planilha = os.environ.get("SHEET_NAME", "Start Finance")
            self.sheet = client.open(nome_planilha)
            self.aba_transacoes = self.sheet.worksheet("Transacoes")
            logger.info("✅ Google Sheets conectado com sucesso!")

        except Exception as e:
            logger.error(f"❌ Erro ao conectar Google Sheets: {e}")
            raise

    def registrar_transacao(self, dados: dict) -> float:
        """Registra uma transação na planilha e retorna o saldo do mês."""
        try:
            agora = datetime.now()
            mes_ano = agora.strftime("%b/%Y").capitalize()

            nova_linha = [
                dados.get("data", agora.strftime("%d/%m/%Y")),
                dados.get("hora", agora.strftime("%H:%M")),
                float(dados.get("valor", 0)),
                dados.get("tipo", "Gasto"),
                dados.get("categoria", "Outros"),
                dados.get("subcategoria", ""),
                dados.get("descricao", ""),
                dados.get("localizacao", ""),
                "Telegram",
                mes_ano,
                "✅"
            ]

            self.aba_transacoes.append_row(nova_linha, value_input_option="USER_ENTERED")
            logger.info(f"✅ Transação registrada: {dados.get('descricao')} - R${dados.get('valor')}")

            return self.get_saldo_mes()

        except Exception as e:
            logger.error(f"❌ Erro ao registrar transação: {e}")
            raise

    def get_saldo_mes(self) -> float:
        """Calcula o saldo do mês atual."""
        try:
            mes_atual = datetime.now().strftime("%b/%Y").capitalize()
            todas = self.aba_transacoes.get_all_records()

            saldo = 0.0
            for row in todas:
                if str(row.get("Mês/Ano", "")).strip() == mes_atual:
                    try:
                        saldo += float(row.get("Valor", 0))
                    except (ValueError, TypeError):
                        pass

            return saldo

        except Exception as e:
            logger.error(f"❌ Erro ao calcular saldo: {e}")
            return 0.0

    def get_resumo_mes(self) -> dict:
        """Retorna resumo completo do mês atual."""
        try:
            mes_atual = datetime.now().strftime("%b/%Y").capitalize()
            todas = self.aba_transacoes.get_all_records()

            entradas = 0.0
            saidas = 0.0
            categorias = defaultdict(float)
            total_registros = 0

            for row in todas:
                if str(row.get("Mês/Ano", "")).strip() != mes_atual:
                    continue

                try:
                    valor = float(row.get("Valor", 0))
                    total_registros += 1

                    if valor > 0:
                        entradas += valor
                    else:
                        saidas += abs(valor)
                        cat = row.get("Categoria", "Outros")
                        if cat:
                            categorias[cat] += abs(valor)
                except (ValueError, TypeError):
                    pass

            # Ordena categorias por valor (maior primeiro)
            cats_ordenadas = dict(
                sorted(categorias.items(), key=lambda x: x[1], reverse=True)
            )

            return {
                "entradas": entradas,
                "saidas": saidas,
                "saldo": entradas - saidas,
                "categorias": cats_ordenadas,
                "total_registros": total_registros
            }

        except Exception as e:
            logger.error(f"❌ Erro no resumo: {e}")
            raise

    def get_top_categorias(self, n: int = 3) -> list:
        """Retorna as N categorias com maior gasto no mês."""
        try:
            resumo = self.get_resumo_mes()
            cats = list(resumo["categorias"].items())
            return cats[:n]
        except Exception as e:
            logger.error(f"❌ Erro no top categorias: {e}")
            return []
