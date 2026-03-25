"""
╔══════════════════════════════════════╗
║   START FINANCE — Extração com IA    ║
║   Versão 2.0 — Campos completos      ║
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
 
CATEGORIAS = [
    "Alimentação", "Transporte", "Contas", "Lazer",
    "Saúde", "Educação", "Moradia", "Salário",
    "Freelance", "Investimento", "Outros"
]
 
SUBCATEGORIAS = {
    "Alimentação": ["Almoço", "Jantar", "Café da manhã", "Lanche", "Mercado",
                    "Delivery", "Restaurante", "Padaria", "Açougue"],
    "Transporte":  ["Uber", "99", "Táxi", "Ônibus", "Metrô", "Gasolina",
                    "Estacionamento", "Pedágio", "Manutenção"],
    "Contas":      ["Luz", "Água", "Internet", "Telefone", "Gás", "Aluguel",
                    "Condomínio", "IPTU", "Streaming", "Assinatura"],
    "Lazer":       ["Cinema", "Show", "Viagem", "Hotel", "Bar", "Balada",
                    "Jogo", "Esporte", "Livro", "Hobby"],
    "Saúde":       ["Médico", "Dentista", "Farmácia", "Exame", "Academia",
                    "Plano de Saúde", "Psicólogo", "Fisioterapia"],
    "Educação":    ["Curso", "Faculdade", "Escola", "Livro", "Certificação",
                    "Workshop", "Inglês", "Pós-graduação"],
    "Moradia":     ["Aluguel", "Reforma", "Móveis", "Decoração", "Limpeza",
                    "Manutenção", "Compra"],
    "Salário":     ["Salário fixo", "13º salário", "Férias", "Bônus", "PLR"],
    "Freelance":   ["Projeto", "Consultoria", "Design", "Programação",
                    "Redação", "Aula particular"],
    "Investimento":["Ações", "Tesouro Direto", "CDB", "Fundo", "Cripto",
                    "Poupança", "Dividendos"],
    "Outros":      ["Presente", "Doação", "Multa", "Taxa", "Empréstimo",
                    "Devolução", "Variados"],
}
 
PALAVRAS_CHAVE = {
    "Alimentação": ["almoço", "jantar", "café", "lanche", "mercado", "supermercado",
                    "padaria", "restaurante", "ifood", "rappi", "hamburguer", "pizza",
                    "comida", "refeição", "marmita", "delivery", "açougue", "feira",
                    "sushi", "namorada", "namorado", "churrasco"],
    "Transporte":  ["uber", "99", "taxi", "táxi", "gasolina", "combustível", "ônibus",
                    "metrô", "passagem", "transporte", "estacionamento", "pedágio",
                    "belo horizonte", "viagem", "aeroporto", "avião"],
    "Contas":      ["conta", "luz", "água", "internet", "telefone", "gás", "aluguel",
                    "condomínio", "iptu", "fatura", "boleto", "netflix", "spotify",
                    "streaming", "assinatura"],
    "Lazer":       ["cinema", "show", "festa", "hotel", "game", "jogo", "lazer",
                    "bar", "balada", "hobby", "esporte", "parque"],
    "Saúde":       ["médico", "farmácia", "remédio", "consulta", "exame", "academia",
                    "dentista", "plano de saúde", "psicólogo", "fisio"],
    "Educação":    ["curso", "livro", "escola", "faculdade", "mensalidade",
                    "aula", "treinamento", "certificação", "inglês"],
    "Moradia":     ["reforma", "móveis", "decoração", "limpeza", "manutenção"],
    "Salário":     ["salário", "salario", "contracheque", "holerite", "13"],
    "Freelance":   ["freela", "freelance", "projeto", "consultoria", "cliente"],
    "Investimento":["ações", "tesouro", "cdb", "fundo", "cripto", "bitcoin",
                    "poupança", "investimento", "aplicação", "dividendo"],
}
 
 
class AIExtractor:
    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
 
    async def transcrever_audio(self, caminho_audio: str) -> str:
        """Retorna vazio pois Whisper não está disponível."""
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
 
        prompt = f"""Você é um extrator de dados financeiros em português brasileiro.
Analise a mensagem e retorne SOMENTE um JSON válido, sem explicações, sem markdown.
 
Data atual: {hoje}
Data de ontem: {ontem}
Hora atual: {timestamp.strftime('%H:%M')}
 
Categorias disponíveis: Alimentação, Transporte, Contas, Lazer, Saúde, Educação, Moradia, Salário, Freelance, Investimento, Outros
 
Subcategorias por categoria:
- Alimentação: Almoço, Jantar, Café da manhã, Lanche, Mercado, Delivery, Restaurante
- Transporte: Uber, 99, Táxi, Ônibus, Gasolina, Estacionamento, Pedágio
- Contas: Luz, Água, Internet, Telefone, Gás, Aluguel, Streaming, Assinatura
- Lazer: Cinema, Show, Viagem, Bar, Balada, Jogo, Esporte, Hobby
- Saúde: Médico, Dentista, Farmácia, Exame, Academia, Psicólogo
- Educação: Curso, Faculdade, Escola, Livro, Workshop, Inglês
- Moradia: Reforma, Móveis, Decoração, Limpeza, Manutenção
- Salário: Salário fixo, 13º salário, Férias, Bônus
- Freelance: Projeto, Consultoria, Design, Programação
- Investimento: Ações, Tesouro Direto, CDB, Poupança, Dividendos
- Outros: Presente, Doação, Multa, Taxa, Variados
 
Regras de extração:
- "ontem" = {ontem}, "hoje" = {hoje}, "anteontem" = data 2 dias atrás
- "manhã" → 08:00, "tarde" → 14:00, "noite" → 20:00, "almoço" → 12:30
- Gastos/pagamentos: valor NEGATIVO, tipo "Gasto"
- Recebimentos/receitas: valor POSITIVO, tipo "Receita"
- Extraia a localização mencionada (restaurante, shopping, cidade, etc.)
- Se mencionar pessoa ("com a namorada", "com amigos") coloque na descrição
- Se não for transação financeira: {{"transacao": false}}
 
Mensagem: "{texto}"
 
JSON esperado (preencha TODOS os campos):
{{
  "transacao": true,
  "data": "DD/MM/YYYY",
  "hora": "HH:MM",
  "valor": -50.00,
  "tipo": "Gasto",
  "categoria": "Alimentação",
  "subcategoria": "Almoço",
  "descricao": "Descrição clara e curta",
  "localizacao": "Local mencionado ou vazio"
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
            texto_resposta = texto_resposta.strip()
 
            # Remove markdown se vier com ```
            if "```" in texto_resposta:
                partes = texto_resposta.split("```")
                for parte in partes:
                    parte = parte.strip()
                    if parte.startswith("json"):
                        parte = parte[4:]
                    if parte.strip().startswith("{"):
                        texto_resposta = parte.strip()
                        break
 
            resultado = json.loads(texto_resposta.strip())
 
            if not resultado.get("transacao", True):
                return None
 
            resultado.pop("transacao", None)
            return self._normalizar(resultado, timestamp)
 
        except Exception as e:
            logger.error(f"❌ Erro no Gemini: {e}")
            return None
 
    def _extrair_por_regras(self, texto: str, timestamp: datetime) -> dict | None:
        texto_lower = texto.lower()
 
        palavras_receita = ["recebi", "entrou", "salário", "salario", "pagaram",
                            "ganhei", "recebimento", "freelance", "depósito",
                            "transferência recebida", "pix recebido"]
        tipo = "Receita" if any(p in texto_lower for p in palavras_receita) else "Gasto"
 
        valor = self._extrair_valor(texto)
        if not valor:
            return None
 
        valor = abs(valor) if tipo == "Receita" else -abs(valor)
        data, hora = self._extrair_data_hora(texto, timestamp)
        categoria = self._detectar_categoria(texto_lower)
        subcategoria = self._detectar_subcategoria(texto_lower, categoria)
        localizacao = self._detectar_localizacao(texto_lower)
        descricao = texto[:100] if len(texto) > 100 else texto
 
        return {
            "data": data,
            "hora": hora,
            "valor": valor,
            "tipo": tipo,
            "categoria": categoria,
            "subcategoria": subcategoria,
            "descricao": descricao,
            "localizacao": localizacao,
        }
 
    def _extrair_valor(self, texto: str) -> float | None:
        padroes = [
            r"R\$\s*(\d+(?:[.,]\d{1,2})?)",
            r"(\d+(?:[.,]\d{1,2})?)\s*reais?",
            r"(\d+(?:[.,]\d{1,2})?)\s*conto",
            r"\b(\d{3,}(?:[.,]\d{1,2})?)\b",
            r"\b(\d{2,}(?:[.,]\d{1,2})?)\b",
        ]
        for padrao in padroes:
            match = re.search(padrao, texto, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(",", "."))
                except ValueError:
                    continue
        return None
 
    def _extrair_data_hora(self, texto: str, timestamp: datetime) -> tuple:
        texto_lower = texto.lower()
        data = timestamp.strftime("%d/%m/%Y")
        hora = timestamp.strftime("%H:%M")
 
        if "anteontem" in texto_lower:
            data = (timestamp - timedelta(days=2)).strftime("%d/%m/%Y")
        elif "ontem" in texto_lower:
            data = (timestamp - timedelta(days=1)).strftime("%d/%m/%Y")
 
        if "manhã" in texto_lower or "manha" in texto_lower:
            hora = "08:00"
        elif "almoço" in texto_lower or "almoco" in texto_lower:
            hora = "12:30"
        elif "tarde" in texto_lower:
            hora = "14:00"
        elif "noite" in texto_lower or "jantar" in texto_lower:
            hora = "20:00"
 
        return data, hora
 
    def _detectar_categoria(self, texto_lower: str) -> str:
        for categoria, palavras in PALAVRAS_CHAVE.items():
            if any(p in texto_lower for p in palavras):
                return categoria
        return "Outros"
 
    def _detectar_subcategoria(self, texto_lower: str, categoria: str) -> str:
        subs = SUBCATEGORIAS.get(categoria, [])
        for sub in subs:
            if sub.lower() in texto_lower:
                return sub
        return ""
 
    def _detectar_localizacao(self, texto_lower: str) -> str:
        locais = ["shopping", "mercado", "supermercado", "farmácia", "academia",
                  "restaurante", "padaria", "hospital", "clínica", "escola",
                  "faculdade", "banco", "posto", "aeroporto", "rodoviária"]
        for local in locais:
            if local in texto_lower:
                return local.capitalize()
        return ""
 
    def _normalizar(self, dados: dict, timestamp: datetime) -> dict:
        if not dados.get("data"):
            dados["data"] = timestamp.strftime("%d/%m/%Y")
        if not dados.get("hora"):
            dados["hora"] = timestamp.strftime("%H:%M")
        if dados.get("categoria") not in CATEGORIAS:
            dados["categoria"] = "Outros"
        if dados.get("tipo") not in ["Gasto", "Receita", "Transferência"]:
            dados["tipo"] = "Gasto" if float(dados.get("valor", 0)) < 0 else "Receita"
        return dados
