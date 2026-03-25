"""
╔══════════════════════════════════════╗
║   START FINANCE — Extração com IA    ║
║   Versão 3.0 — Todos os campos       ║
╚══════════════════════════════════════╝
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)

CATEGORIAS = [
    "Alimentação", "Transporte", "Contas", "Lazer",
    "Saúde", "Educação", "Moradia", "Salário",
    "Freelance", "Investimento", "Outros"
]


class AIExtractor:
    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")

    async def transcrever_audio(self, caminho_audio: str) -> str:
        return ""

    async def extrair(self, texto: str, timestamp: datetime) -> dict | None:
        texto = texto.strip()
        if not texto:
            return None
        if self.gemini_key:
            resultado = await self._extrair_gemini(texto, timestamp)
            if resultado:
                return resultado
        return self._extrair_por_regras(texto, timestamp)

    async def _extrair_gemini(self, texto: str, timestamp: datetime) -> dict | None:
        ontem = (timestamp - timedelta(days=1)).strftime('%d/%m/%Y')
        hoje = timestamp.strftime('%d/%m/%Y')

        prompt = f"""Você é um extrator de dados financeiros brasileiro.
Analise a mensagem e retorne SOMENTE JSON válido, sem markdown.

Hoje: {hoje} às {timestamp.strftime('%H:%M')}
Ontem: {ontem}

Categorias: Alimentação, Transporte, Contas, Lazer, Saúde, Educação, Moradia, Salário, Freelance, Investimento, Outros

Subcategorias:
- Alimentação: Almoço, Jantar, Café da manhã, Lanche, Mercado, Delivery, Restaurante, Padaria, Sushi, Churrasco, Feira
- Transporte: Uber, 99, Táxi, Ônibus, Metrô, Gasolina, Estacionamento, Pedágio, Avião
- Contas: Luz, Água, Internet, Telefone, Gás, Aluguel, Condomínio, Netflix, Spotify, Streaming
- Lazer: Cinema, Show, Viagem, Bar, Balada, Jogo, Esporte, Teatro, Hobby
- Saúde: Médico, Dentista, Farmácia, Exame, Academia, Psicólogo, Fisioterapia
- Educação: Curso, Faculdade, Escola, Livro, Workshop, Inglês, Certificação
- Moradia: Aluguel, Reforma, Móveis, Decoração, Limpeza, Manutenção
- Salário: Salário fixo, 13º, Férias, Bônus, Adiantamento
- Freelance: Projeto, Consultoria, Design, Programação, Redação
- Investimento: Ações, Tesouro Direto, CDB, Cripto, Poupança, Dividendos
- Outros: Presente, Doação, Multa, Devolução, Variados

Regras:
- Gastos/pagamentos = valor NEGATIVO, tipo "Gasto"
- Recebimentos/salário/receitas = valor POSITIVO, tipo "Receita"
- Extraia localização: nome do lugar, estabelecimento, cidade
- Descrição: frase curta e clara (máx 60 chars)
- Se não for transação financeira: {{"transacao": false}}

Mensagem: "{texto}"

JSON (preencha TODOS):
{{
  "transacao": true,
  "data": "{hoje}",
  "hora": "{timestamp.strftime('%H:%M')}",
  "valor": -50.00,
  "tipo": "Gasto",
  "categoria": "Alimentação",
  "subcategoria": "Almoço",
  "descricao": "Almoço no shopping",
  "localizacao": "Shopping"
}}"""

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500}
            }
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(url, json=payload)
                data = response.json()

            raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()

            # Remove markdown
            if "```" in raw:
                for parte in raw.split("```"):
                    parte = parte.strip().lstrip("json").strip()
                    if parte.startswith("{"):
                        raw = parte
                        break

            resultado = json.loads(raw)
            if not resultado.get("transacao", True):
                return None
            resultado.pop("transacao", None)
            return self._normalizar(resultado, timestamp)

        except Exception as e:
            logger.error(f"❌ Gemini erro: {e}")
            return None

    def _extrair_por_regras(self, texto: str, timestamp: datetime) -> dict | None:
        t = texto.lower()
        palavras_receita = ["recebi", "entrou", "salário", "salario", "pagaram",
                            "ganhei", "reembolso", "dividendo", "rendimento", "depósito"]
        tipo = "Receita" if any(p in t for p in palavras_receita) else "Gasto"
        valor = self._extrair_valor(texto)
        if not valor:
            return None
        valor = abs(valor) if tipo == "Receita" else -abs(valor)
        data, hora = self._extrair_data_hora(t, timestamp)
        categoria = self._detectar_categoria(t)
        subcategoria = self._detectar_subcategoria(t, categoria)
        localizacao = self._detectar_localizacao(t)
        descricao = texto[:60] if len(texto) > 60 else texto
        return {"data": data, "hora": hora, "valor": valor, "tipo": tipo,
                "categoria": categoria, "subcategoria": subcategoria,
                "descricao": descricao, "localizacao": localizacao}

    def _extrair_valor(self, texto):
        for padrao in [r"R\$\s*(\d+(?:[.,]\d{1,2})?)", r"(\d+(?:[.,]\d{1,2})?)\s*reais?",
                       r"(\d+(?:[.,]\d{1,2})?)\s*conto", r"\b(\d{3,}(?:[.,]\d{1,2})?)\b"]:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1).replace(",", "."))
                except:
                    pass
        return None

    def _extrair_data_hora(self, t, timestamp):
        data = timestamp.strftime("%d/%m/%Y")
        hora = timestamp.strftime("%H:%M")
        if "anteontem" in t:
            data = (timestamp - timedelta(days=2)).strftime("%d/%m/%Y")
        elif "ontem" in t:
            data = (timestamp - timedelta(days=1)).strftime("%d/%m/%Y")
        if any(p in t for p in ["manhã", "cafe", "café"]):
            hora = "08:00"
        elif any(p in t for p in ["almoço", "almoco", "meio-dia"]):
            hora = "12:30"
        elif "tarde" in t:
            hora = "15:00"
        elif any(p in t for p in ["noite", "jantar", "janta"]):
            hora = "20:00"
        return data, hora

    def _detectar_categoria(self, t):
        mapa = {
            "Alimentação": ["almoço", "jantar", "café", "lanche", "mercado", "supermercado",
                           "padaria", "restaurante", "ifood", "rappi", "hamburguer", "pizza",
                           "comida", "refeição", "delivery", "sushi", "churrasco", "feira", "beber", "boteco"],
            "Transporte":  ["uber", "99", "taxi", "táxi", "gasolina", "combustível", "ônibus",
                           "metrô", "passagem", "estacionamento", "pedágio", "avião", "aeroporto"],
            "Contas":      ["conta", "luz", "água", "internet", "telefone", "gás", "aluguel",
                           "condomínio", "iptu", "fatura", "boleto", "netflix", "spotify", "streaming"],
            "Lazer":       ["cinema", "show", "teatro", "viagem", "hotel", "game", "jogo", "balada", "hobby", "esporte"],
            "Saúde":       ["médico", "farmácia", "remédio", "consulta", "exame", "academia", "dentista", "psicólogo"],
            "Educação":    ["curso", "livro", "escola", "faculdade", "mensalidade", "aula", "inglês", "certificação"],
            "Moradia":     ["reforma", "móveis", "decoração", "limpeza", "manutenção"],
            "Salário":     ["salário", "salario", "contracheque", "13", "férias", "bonus", "adiantamento"],
            "Freelance":   ["freela", "freelance", "projeto", "consultoria", "cliente"],
            "Investimento":["ações", "tesouro", "cdb", "fundo", "cripto", "bitcoin", "poupança", "investimento", "dividendo"],
        }
        for cat, palavras in mapa.items():
            if any(p in t for p in palavras):
                return cat
        return "Outros"

    def _detectar_subcategoria(self, t, categoria):
        mapa = {
            "Alimentação": {"almoço": "Almoço", "almoco": "Almoço", "jantar": "Jantar", "janta": "Jantar",
                           "café": "Café da manhã", "lanche": "Lanche", "mercado": "Mercado",
                           "supermercado": "Mercado", "padaria": "Padaria", "ifood": "Delivery",
                           "rappi": "Delivery", "delivery": "Delivery", "sushi": "Restaurante",
                           "pizza": "Restaurante", "hamburguer": "Restaurante", "restaurante": "Restaurante",
                           "churrasco": "Churrasco", "feira": "Feira"},
            "Transporte":  {"uber": "Uber", "99": "99", "taxi": "Táxi", "táxi": "Táxi",
                           "gasolina": "Gasolina", "combustível": "Gasolina", "ônibus": "Ônibus",
                           "metrô": "Metrô", "estacionamento": "Estacionamento", "pedágio": "Pedágio", "avião": "Avião"},
            "Contas":      {"luz": "Luz", "água": "Água", "internet": "Internet", "telefone": "Telefone",
                           "celular": "Telefone", "gás": "Gás", "aluguel": "Aluguel",
                           "condomínio": "Condomínio", "netflix": "Netflix", "spotify": "Spotify"},
            "Saúde":       {"médico": "Médico", "dentista": "Dentista", "farmácia": "Farmácia",
                           "remédio": "Farmácia", "exame": "Exame", "academia": "Academia", "psicólogo": "Psicólogo"},
        }
        for palavra, sub in mapa.get(categoria, {}).items():
            if palavra in t:
                return sub
        return ""

    def _detectar_localizacao(self, t):
        locais = ["shopping", "mercado", "supermercado", "farmácia", "academia", "restaurante",
                  "padaria", "hospital", "clínica", "escola", "faculdade", "banco", "posto",
                  "aeroporto", "rodoviária", "praça", "parque", "centro"]
        for local in locais:
            if local in t:
                return local.capitalize()

        cidades = ["são paulo", "rio de janeiro", "belo horizonte", "salvador", "brasília",
                   "curitiba", "fortaleza", "recife", "porto alegre", "goiânia", "contagem",
                   "betim", "uberlândia", "campinas", "florianópolis"]
        for cidade in cidades:
            if cidade in t:
                return cidade.title()

        for padrao in [r'\bno\s+(\w+)', r'\bna\s+(\w+)', r'\bno\s+(\w+\s+\w+)', r'\bem\s+(\w+)']:
            m = re.search(padrao, t)
            if m:
                local = m.group(1).strip()
                if local not in ["dia", "mês", "ano", "casa", "trabalho", "hoje", "ontem"]:
                    return local.title()
        return ""

    def _normalizar(self, dados, timestamp):
        if not dados.get("data"):
            dados["data"] = timestamp.strftime("%d/%m/%Y")
        if not dados.get("hora"):
            dados["hora"] = timestamp.strftime("%H:%M")
        if dados.get("categoria") not in CATEGORIAS:
            dados["categoria"] = "Outros"
        if dados.get("tipo") not in ["Gasto", "Receita", "Transferência"]:
            dados["tipo"] = "Gasto" if float(dados.get("valor", 0)) < 0 else "Receita"
        dados.setdefault("subcategoria", "")
        dados.setdefault("localizacao", "")
        dados.setdefault("descricao", dados.get("categoria", ""))
        return dados
