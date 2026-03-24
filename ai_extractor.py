"""
╔══════════════════════════════════════╗
║   START FINANCE — Extração com IA    ║
║   Texto + Áudio → Dados Financeiros  ║
╚══════════════════════════════════════╝
"""

import os
import re
import json
import logging
import asyncio
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

# Categorias disponíveis
CATEGORIAS = [
    "Alimentação", "Transporte", "Contas", "Lazer",
    "Saúde", "Educação", "Moradia", "Salário",
    "Freelance", "Outros"
]

# Palavras-chave por categoria (fallback sem IA)
PALAVRAS_CHAVE = {
    "Alimentação": ["almoço", "jantar", "café", "lanche", "mercado", "supermercado",
                    "padaria", "restaurante", "ifood", "rappi", "hamburguer", "pizza",
                    "comida", "alimentação", "refeição", "marmita"],
    "Transporte":  ["uber", "99", "taxi", "táxi", "gasolina", "combustível", "ônibus",
                    "metrô", "passagem", "transporte", "estacionamento", "pedágio"],
    "Contas":      ["conta", "luz", "água", "internet", "telefone", "gás", "aluguel",
                    "condomínio", "iptu", "fatura", "boleto"],
    "Lazer":       ["cinema", "show", "festa", "viagem", "hotel", "streaming", "netflix",
                    "spotify", "game", "jogo", "lazer", "bar", "balada"],
    "Saúde":       ["médico", "farmácia", "remédio", "consulta", "exame", "academia",
                    "dentista", "plano de saúde", "saúde"],
    "Educação":    ["curso", "livro", "escola", "faculdade", "mensalidade", "educação",
                    "aula", "treinamento"],
    "Moradia":     ["aluguel", "moradia", "reforma", "móveis", "decoração"],
    "Salário":     ["salário", "salario", "pagamento", "contracheque"],
    "Freelance":   ["freelance", "freela", "projeto", "cliente", "trabalho extra"],
}


class AIExtractor:
    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.whisper_disponivel = self._verificar_whisper()

    def _verificar_whisper(self) -> bool:
        """Verifica se o Whisper está disponível localmente."""
        try:
            import whisper
            return True
        except ImportError:
            logger.warning("⚠️ Whisper não disponível. Áudio usará transcrição alternativa.")
            return False

    async def transcrever_audio(self, caminho_audio: str) -> str:
        """Transcreve um arquivo de áudio para texto."""
        if self.whisper_disponivel:
            return await self._transcrever_whisper(caminho_audio)
        else:
            logger.warning("Whisper indisponível, áudio não transcrito.")
            return ""

    async def _transcrever_whisper(self, caminho_audio: str) -> str:
        """Usa Whisper local para transcrever."""
        try:
            import whisper

            # Roda em thread separada para não bloquear o bot
            loop = asyncio.get_event_loop()
            modelo = await loop.run_in_executor(None, whisper.load_model, "base")
            resultado = await loop.run_in_executor(
                None,
                lambda: modelo.transcribe(caminho_audio, language="pt")
            )
            return resultado.get("text", "").strip()

        except Exception as e:
            logger.error(f"❌ Erro no Whisper: {e}")
            return ""

    async def extrair(self, texto: str, timestamp: datetime) -> dict | None:
        """Extrai dados financeiros do texto usando IA ou regras."""
        texto = texto.strip()
        if not texto:
            return None

        # Tenta com Gemini primeiro
        if self.gemini_key:
            resultado = await self._extrair_gemini(texto, timestamp)
            if resultado:
                return resultado

        # Fallback: extração por regras
        return self._extrair_por_regras(texto, timestamp)

    async def _extrair_gemini(self, texto: str, timestamp: datetime) -> dict | None:
        """Extrai dados via Gemini 1.5 Flash (gratuito)."""
        prompt = f"""Você é um extrator de dados financeiros. Analise a mensagem e retorne SOMENTE um JSON válido, sem explicações.

Data/hora atual: {timestamp.strftime('%d/%m/%Y %H:%M')}
Categorias disponíveis: {', '.join(CATEGORIAS)}

Mensagem: "{texto}"

Regras:
- "ontem" = data de ontem, "hoje" = data atual
- "manhã" → hora ~08:00, "tarde" → ~14:00, "noite" → ~20:00
- Gastos: valor NEGATIVO. Receitas: valor POSITIVO.
- Se não for uma transação financeira, retorne: {{"transacao": false}}

JSON esperado:
{{
  "transacao": true,
  "data": "DD/MM/YYYY",
  "hora": "HH:MM",
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

            texto_resposta = data["candidates"][0]["content"]["parts"][0]["text"]

            # Limpa o JSON da resposta
            texto_resposta = texto_resposta.strip()
            if "```" in texto_resposta:
                texto_resposta = texto_resposta.split("```")[1]
                if texto_resposta.startswith("json"):
                    texto_resposta = texto_resposta[4:]

            resultado = json.loads(texto_resposta.strip())

            if not resultado.get("transacao", True):
                return None

            resultado.pop("transacao", None)
            return self._normalizar(resultado, timestamp)

        except Exception as e:
            logger.error(f"❌ Erro no Gemini: {e}")
            return None

    def _extrair_por_regras(self, texto: str, timestamp: datetime) -> dict | None:
        """Extração baseada em regras regex (fallback sem IA)."""
        texto_lower = texto.lower()

        # Detecta se é receita ou gasto
        palavras_receita = ["recebi", "entrou", "salário", "salario", "pagaram",
                            "ganhei", "recebimento", "freelance", "depósito"]
        tipo = "Receita" if any(p in texto_lower for p in palavras_receita) else "Gasto"

        # Extrai valor
        valor = self._extrair_valor(texto)
        if not valor:
            return None

        if tipo == "Gasto":
            valor = -abs(valor)
        else:
            valor = abs(valor)

        # Extrai data
        data, hora = self._extrair_data_hora(texto, timestamp)

        # Detecta categoria
        categoria = self._detectar_categoria(texto_lower)

        # Descrição simples
        descricao = texto[:80] if len(texto) > 80 else texto

        return {
            "data": data,
            "hora": hora,
            "valor": valor,
            "tipo": tipo,
            "categoria": categoria,
            "subcategoria": "",
            "descricao": descricao,
            "localizacao": ""
        }

    def _extrair_valor(self, texto: str) -> float | None:
        """Extrai valor monetário do texto."""
        padroes = [
            r"R\$\s*(\d+(?:[.,]\d{1,2})?)",
            r"(\d+(?:[.,]\d{1,2})?)\s*reais?",
            r"(\d+(?:[.,]\d{1,2})?)\s*conto",
            r"\b(\d{2,}(?:[.,]\d{1,2})?)\b",
        ]
        for padrao in padroes:
            match = re.search(padrao, texto, re.IGNORECASE)
            if match:
                valor_str = match.group(1).replace(",", ".")
                try:
                    return float(valor_str)
                except ValueError:
                    continue
        return None

    def _extrair_data_hora(self, texto: str, timestamp: datetime) -> tuple[str, str]:
        """Extrai data e hora do texto."""
        texto_lower = texto.lower()
        data = timestamp.strftime("%d/%m/%Y")
        hora = timestamp.strftime("%H:%M")

        if "ontem" in texto_lower:
            ontem = timestamp - timedelta(days=1)
            data = ontem.strftime("%d/%m/%Y")
        elif "anteontem" in texto_lower:
            anteontem = timestamp - timedelta(days=2)
            data = anteontem.strftime("%d/%m/%Y")

        if "manhã" in texto_lower or "manha" in texto_lower:
            hora = "08:00"
        elif "tarde" in texto_lower:
            hora = "14:00"
        elif "noite" in texto_lower:
            hora = "20:00"

        return data, hora

    def _detectar_categoria(self, texto_lower: str) -> str:
        """Detecta categoria baseado em palavras-chave."""
        for categoria, palavras in PALAVRAS_CHAVE.items():
            if any(p in texto_lower for p in palavras):
                return categoria
        return "Outros"

    def _normalizar(self, dados: dict, timestamp: datetime) -> dict:
        """Normaliza e valida os dados extraídos."""
        # Garante data válida
        if not dados.get("data"):
            dados["data"] = timestamp.strftime("%d/%m/%Y")

        # Garante hora válida
        if not dados.get("hora"):
            dados["hora"] = timestamp.strftime("%H:%M")

        # Garante categoria válida
        if dados.get("categoria") not in CATEGORIAS:
            dados["categoria"] = "Outros"

        # Garante tipo válido
        if dados.get("tipo") not in ["Gasto", "Receita", "Transferência"]:
            dados["tipo"] = "Gasto" if float(dados.get("valor", 0)) < 0 else "Receita"

        return dados
