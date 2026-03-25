"""
START FINANCE — Extração Inteligente v7.0 "Surpreenda-me"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 18 categorias (antes eram 11)
• Detecta parcelas, método de pagamento, recorrência
• Suporta múltiplas transações na mesma mensagem
• Entende emojis financeiros
• Prompt Gemini com raciocínio em cadeia (chain-of-thought)
• Fallback por regras ultra-robusto
"""

import os, re, json, logging
from datetime import datetime, timedelta
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

CATEGORIAS = [
    "Alimentação","Transporte","Contas","Lazer","Saúde",
    "Educação","Moradia","Beleza","Vestuário","Pet",
    "Tecnologia","Filhos","Presentes","Veículo","Impostos",
    "Assinaturas","Salário","Freelance","Investimento","Outros",
]

EMOJI_MAP = {
    "🍕":"Alimentação","🍔":"Alimentação","🍟":"Alimentação",
    "🍝":"Alimentação","🍜":"Alimentação","🍣":"Alimentação",
    "🍱":"Alimentação","🍛":"Alimentação","🥗":"Alimentação",
    "🍺":"Alimentação","🍻":"Alimentação","🍷":"Alimentação",
    "☕":"Alimentação","🧃":"Alimentação","🥤":"Alimentação",
    "🍰":"Alimentação","🍦":"Alimentação","🛒":"Alimentação",
    "🧁":"Alimentação","🥐":"Alimentação","🥘":"Alimentação",
    "🚗":"Transporte","🚕":"Transporte","🚙":"Transporte",
    "🏍":"Transporte","🚌":"Transporte","✈️":"Transporte",
    "⛽":"Transporte","🚇":"Transporte","🛺":"Transporte",
    "💊":"Saúde","🏥":"Saúde","🩺":"Saúde","🦷":"Saúde",
    "💉":"Saúde","🩻":"Saúde",
    "💅":"Beleza","💇":"Beleza","💇‍♀️":"Beleza","💇‍♂️":"Beleza","✂️":"Beleza",
    "🐶":"Pet","🐱":"Pet","🐾":"Pet","🦮":"Pet",
    "👗":"Vestuário","👟":"Vestuário","👠":"Vestuário",
    "👕":"Vestuário","👖":"Vestuário","🧥":"Vestuário",
    "👜":"Vestuário","🎒":"Vestuário","👒":"Vestuário",
    "📚":"Educação","🎓":"Educação","✏️":"Educação",
    "🎁":"Presentes","💝":"Presentes","🎂":"Presentes",
    "📱":"Tecnologia","💻":"Tecnologia","🖥":"Tecnologia",
    "🎮":"Tecnologia","🕹":"Tecnologia",
    "👶":"Filhos","🍼":"Filhos","🧸":"Filhos",
    "🏠":"Moradia","🔧":"Moradia","🪑":"Moradia",
    "🎬":"Lazer","🎭":"Lazer","🎪":"Lazer","🎡":"Lazer",
    "🏖":"Lazer","⚽":"Lazer","🎵":"Lazer","🎤":"Lazer",
    "🚘":"Veículo","🔩":"Veículo",
    "📈":"Investimento","📉":"Investimento","💰":"Investimento",
    "🤑":"Salário","💵":"Salário","💸":"Salário",
    "💡":"Contas","🔌":"Contas",
    "🏛":"Impostos","📄":"Impostos",
}

PALAVRAS_RECEITA = [
    "recebi","recebimento","receita","entrada","salário","salario",
    "remuneração","remuneracao","honorários","honorarios","pagamento recebido",
    "transferência recebida","deposito","depósito","crédito","credito",
    "reembolso","restituição","restituicao","dividendo","rendimento",
    "lucro","bonificação","bonificacao","bonus","bônus","13 salário",
    "décimo terceiro","ferias","férias","pró-labore","pro labore",
    "caiu","caiu na conta","cairam","pagaram","me pagaram","me mandaram",
    "me passaram","recebi um pix","pix caiu","pix entrou","entrou na conta",
    "entrou o dinheiro","me depositaram","fiz uma grana","ganhei",
    "ganhei uma grana","veio dinheiro","veio a grana",
    "fechei um freela","fechei um projeto",
    "vendeu","vendi","me devolveram","devolveram","estorno","estornaram",
]

PALAVRAS_GASTO = [
    "gastei","paguei","comprei","adquiri","contratei","desembolsei",
    "despesa","gasto","pagamento","parcela","prestação","mensalidade",
    "anuidade","taxa","tarifa","débito","fatura","boleto","cobrança",
    "fui no","fui na","fui ao","passei no","passei na","taquei","meti",
    "botei","joguei","gastei uma grana","saiu","saiu da conta","foi embora",
    "sumiu","tive que pagar","tive que desembolsar","aproveitei e paguei",
    "acabei pagando","acabei comprando","rolou um","rolou uma",
    "comi no","jantei no","almocei no","tomei no","bebi no",
    "peguei um","chamei um","chamei o","usei o","usei a",
    "assinei","renovei","parcelei","financiei",
]

PALAVRAS_FINANCEIRAS = [
    "real","reais","r$","conto","contos","centavo","centavos","dinheiro",
    "grana","bufunfa","money","pila","pilas","toco","nota","nota de",
    "gastei","paguei","comprei","recebi","entrou","caiu","saiu",
    "uber","ifood","rappi","mercado","supermercado","farmácia","academia",
    "almoço","jantar","café","lanche","conta","boleto","fatura","luz","água",
    "internet","telefone","netflix","spotify","gasolina","estacionamento",
    "salário","salario","freela","freelance","investimento","poupança",
    "salão","salao","cabelo","unha","manicure","barbeiro","barbearia",
    "sobrancelha","depilação","depilacao","maquiagem","estética","estetica",
    "roupa","tênis","sapato","calçado","blusa","camisa","vestido","jaqueta",
    "veterinário","veterinario","ração","racao","pet shop","banho e tosa",
    "celular","notebook","fone","gadget","iphone","samsung","xiaomi",
    "fralda","brinquedo","creche","pediatra","escola do",
    "presente","doação","doacao","dízimo","dizimo","oferta",
    "ipva","licenciamento","seguro do carro","multa","detran",
    "imposto","ir","inss","cartório","cartorio",
    "parcela","parcelei","prestação","financiamento","consórcio",
    "pix","cartão","cartao","débito","crédito","dinheiro vivo",
]


class AIExtractor:
    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")

    async def transcrever_audio(self, caminho_audio: str) -> str:
        return ""

    async def extrair(self, texto: str, timestamp: datetime):
        texto = texto.strip()
        if not texto:
            return None

        if self.gemini_key:
            try:
                resultado = await self._extrair_gemini(texto, timestamp)
                if resultado:
                    if isinstance(resultado, list):
                        logger.info(f"✅ Gemini: {len(resultado)} transações extraídas")
                        return resultado[0] if len(resultado) == 1 else resultado
                    logger.info(f"✅ Gemini: {resultado.get('descricao')} R${resultado.get('valor')}")
                    return resultado
            except Exception as e:
                logger.error(f"Gemini falhou: {e}")

        resultado = self._extrair_por_regras(texto, timestamp)
        if resultado:
            logger.info(f"✅ Regras: {resultado.get('descricao')} R${resultado.get('valor')}")
        return resultado

    async def _extrair_gemini(self, texto: str, timestamp: datetime):
        ontem = (timestamp - timedelta(days=1)).strftime('%d/%m/%Y')
        hoje = timestamp.strftime('%d/%m/%Y')
        hora_atual = timestamp.strftime('%H:%M')

        prompt = f"""Você é o melhor extrator de dados financeiros do Brasil. Você entende QUALQUER forma de falar — formal, informal, gíria, abreviação, com emoji, voz transcrita, erros de digitação.

━━━ CONTEXTO TEMPORAL ━━━
Agora: {hoje} às {hora_atual} | Ontem: {ontem}

━━━ CATEGORIAS (use SOMENTE estas) ━━━
Alimentação — comida, restaurante, mercado, delivery, padaria, bar (quando foco é comida/bebida)
Transporte — uber, 99, ônibus, gasolina, passagem, estacionamento, pedágio
Contas — luz, água, gás de COZINHA, internet, telefone, aluguel, condomínio, IPTU
Lazer — cinema, show, bar (quando foco é diversão), festa, viagem, hotel, parque, jogos
Saúde — médico, dentista, farmácia, exame, plano de saúde, terapia, suplemento, academia
Educação — curso, faculdade, escola, livro, idioma, mentoria, workshop
Moradia — reforma, móvel, decoração, faxina, manutenção da casa, mudança
Beleza — salão, cabelo, unha, manicure, barbeiro, sobrancelha, depilação, estética, cílios, maquiagem, skin care
Vestuário — roupa, calçado, tênis, sapato, acessório, relógio, óculos de sol, costura, lavanderia
Pet — veterinário, ração, pet shop, banho e tosa, vacina do pet, brinquedo do pet
Tecnologia — celular, notebook, PC, gadget, fone, acessório tech, reparo de eletrônico, app pago, game
Filhos — escola do filho, fralda, brinquedo, pediatra, roupa infantil, material escolar do filho
Presentes — presente, doação, caridade, dízimo, oferta religiosa, vaquinha, ajuda financeira a alguém
Veículo — IPVA, seguro auto, licenciamento, multa, revisão/manutenção do carro, pneu, autopeças, lavagem
Impostos — IR, INSS, taxa de cartório, taxa de prefeitura, alvará, DARF, guia de recolhimento
Assinaturas — Netflix, Spotify, iCloud, Game Pass, clube de assinatura, box mensal, app recorrente
Salário — salário, 13º, férias, PLR, bônus, pró-labore, adiantamento, vale
Freelance — freela, bico, projeto, consultoria, comissão, prestação de serviço, venda
Investimento — ações, cripto, tesouro, CDB, fundo, poupança, previdência, aporte, dividendo
Outros — tudo que não se encaixa nas acima

━━━ REGRAS CRÍTICAS ━━━

1. TIPO:
   • Gastos/pagamentos/compras → tipo "Gasto", valor NEGATIVO (ex: -50.00)
   • Recebimentos/receitas → tipo "Receita", valor POSITIVO (ex: 3500.00)

2. DATA: Use "{hoje}" como padrão. Mude SOMENTE se o usuário disse "ontem", "anteontem", "semana passada", "dia X", ou data explícita.

3. HORA: Use SEMPRE "{hora_atual}". NUNCA invente outro horário.

4. LOCALIZAÇÃO: Extraia SOMENTE se o usuário NOMEOU um lugar/estabelecimento/cidade. Se não nomeou → "". NUNCA invente.

5. DESCRIÇÃO: Resumo claro e útil do gasto (máx 55 chars). Mantenha contexto humano ("Salão com a esposa", "Presente pro filho", "Uber pro trabalho").

6. MÉTODO DE PAGAMENTO: Detecte se mencionou — "pix", "cartão", "crédito", "débito", "dinheiro", "parcelado". Se não mencionou → "".

7. PARCELAS: Se mencionou "3x", "em 5 vezes", "parcela 2 de 6", etc → preencha parcela_atual e total_parcelas. Se não → ambos 0.

8. MULTI-TRANSAÇÃO: Se a mensagem tem MAIS DE UMA transação ("gastei 50 no uber e 30 no ifood"), retorne um ARRAY de objetos.

9. DIFERENCIAÇÕES IMPORTANTES:
   • "salão" / "salao" / "cabelo" = BELEZA (nunca Contas, nunca Gás)
   • "gás" sozinho ou "gás de cozinha" / "botijão" = Contas
   • "gasolina" / "posto" / "combustível" = Transporte
   • "seguro do carro" / "IPVA" / "multa" / "revisão do carro" = Veículo
   • "seguro de vida" / "plano de saúde" = Saúde
   • "netflix" / "spotify" / "icloud" / "game pass" = Assinaturas
   • "roupa" / "tênis" / "sapato" = Vestuário
   • "ração" / "veterinário" / "pet shop" = Pet
   • "presente" / "doação" / "dízimo" = Presentes
   • "celular novo" / "notebook" / "fone" = Tecnologia
   • "escola do filho" / "fralda" / "brinquedo" (contexto criança) = Filhos
   • "IPVA" / "IR" / "cartório" / "INSS" (autônomo) = Impostos

━━━ RACIOCÍNIO ━━━
Antes de responder, pense internamente:
A) Qual o contexto real da mensagem?
B) É gasto ou receita?
C) Qual categoria se encaixa MELHOR?
D) O usuário mencionou local, parcela, forma de pagamento?
E) Há mais de uma transação?

━━━ EXEMPLOS ━━━
"gastei 900 com a mulher no salao" → Gasto, Beleza, Salão, "Salão com a esposa", -900
"50 uber + 35 ifood" → 2 transações: [Transporte/Uber -50, Alimentação/Delivery -35]
"paguei ipva do carro, 1800 em 3x no cartão" → Veículo, IPVA, -1800, método "Cartão crédito", parcelas 1/3
"comprei um tênis nike, 450 reais" → Vestuário, Tênis, -450
"levei o dog no vet, 280" → Pet, Veterinário, -280
"dei 200 de presente pra minha mãe" → Presentes, Presente, -200
"netflix debitou 55,90" → Assinaturas, Netflix, -55.90
"comprei um iphone, 4500 em 12x" → Tecnologia, Celular, -4500, parcelas 1/12
"paguei a escola do pedro, 1200" → Filhos, Escola, -1200
"fiz cartório pra escritura, 350" → Impostos, Cartório, -350
"comprei ração pro gato e fui no mercado, 80 e 250" → 2 transações: [Pet/Ração -80, Alimentação/Mercado -250]
"🍕 35" → Alimentação, Pizza, -35
"💅 60" → Beleza, Manicure, -60
"caiu meu salário 4200 e paguei aluguel 1500" → 2: [Salário +4200, Contas/Aluguel -1500]
"lavei o carro, 60" → Veículo, Lavagem, -60
"doei 100 pra igreja" → Presentes, Dízimo/Oferta, -100
Se não for financeiro: {{"transacao":false}}

━━━ FORMATO DE RESPOSTA ━━━
Retorne SOMENTE JSON válido. Sem markdown, sem explicação, sem texto extra.

Para UMA transação:
{{"transacao":true,"data":"{hoje}","hora":"{hora_atual}","valor":-0.00,"tipo":"Gasto","categoria":"","subcategoria":"","descricao":"","localizacao":"","metodo_pagamento":"","parcela_atual":0,"total_parcelas":0}}

Para MÚLTIPLAS transações:
[{{"transacao":true,"data":"{hoje}","hora":"{hora_atual}","valor":-0.00,"tipo":"Gasto","categoria":"","subcategoria":"","descricao":"","localizacao":"","metodo_pagamento":"","parcela_atual":0,"total_parcelas":0}},{{"transacao":true,...}}]

Mensagem do usuário: "{texto}"

JSON:"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.05, "maxOutputTokens": 800}
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)

        if resp.status_code != 200:
            logger.error(f"Gemini HTTP {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        if "```" in raw:
            for parte in raw.split("```"):
                parte = parte.strip().lstrip("json").strip()
                if parte.startswith("{") or parte.startswith("["):
                    raw = parte
                    break

        resultado = json.loads(raw)

        if isinstance(resultado, list):
            transacoes = []
            for item in resultado:
                if item.get("transacao", True):
                    item.pop("transacao", None)
                    transacoes.append(self._normalizar(item, timestamp))
            return transacoes if transacoes else None

        if not resultado.get("transacao", True):
            return None
        resultado.pop("transacao", None)
        return self._normalizar(resultado, timestamp)

    def _extrair_por_regras(self, texto: str, timestamp: datetime):
        t = texto.lower().strip()
        cat_emoji = self._detectar_emoji(texto)

        if not cat_emoji and not self._eh_financeiro(t):
            return None

        tipo = self._detectar_tipo(t)
        valor = self._extrair_valor_robusto(texto, t)
        if not valor:
            return None

        valor = abs(valor) if tipo == "Receita" else -abs(valor)
        data, hora = self._extrair_data_hora(t, timestamp)
        categoria = cat_emoji or self._detectar_categoria(t)
        subcategoria = self._detectar_subcategoria(t, categoria)
        localizacao = self._detectar_localizacao(texto, t)
        descricao = self._gerar_descricao(texto, t, categoria, subcategoria)
        metodo = self._detectar_metodo_pagamento(t)
        parcela_atual, total_parcelas = self._detectar_parcelas(t)

        return {
            "data": data, "hora": hora, "valor": valor, "tipo": tipo,
            "categoria": categoria, "subcategoria": subcategoria,
            "descricao": descricao, "localizacao": localizacao,
            "metodo_pagamento": metodo,
            "parcela_atual": parcela_atual, "total_parcelas": total_parcelas,
        }

    def _detectar_emoji(self, texto: str) -> Optional[str]:
        for emoji, cat in EMOJI_MAP.items():
            if emoji in texto:
                return cat
        return None

    def _eh_financeiro(self, t: str) -> bool:
        return any(p in t for p in PALAVRAS_FINANCEIRAS)

    def _detectar_tipo(self, t: str) -> str:
        score_receita = sum(1 for p in PALAVRAS_RECEITA if p in t)
        score_gasto = sum(1 for p in PALAVRAS_GASTO if p in t)
        return "Receita" if score_receita > score_gasto else "Gasto"

    def _extrair_valor_robusto(self, texto: str, t: str) -> Optional[float]:
        padroes = [
            r"R\$\s*(\d{1,6}(?:[.,]\d{1,2})?)",
            r"(\d{1,6}(?:[.,]\d{1,2})?)\s*reais?",
            r"(\d{1,6}(?:[.,]\d{1,2})?)\s*contos?",
            r"(\d{1,6}(?:[.,]\d{1,2})?)\s*pilas?",
            r"(\d{1,3}(?:\.\d{3})*,\d{2})\b",
            r"\b(\d{2,6}\.\d{2})\b",
            r"\b(\d{2,6})\b",
        ]
        for padrao in padroes:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                val_str = m.group(1).replace(".", "").replace(",", ".")
                try:
                    val = float(val_str)
                    if val > 0:
                        return val
                except:
                    pass
        return None

    def _extrair_data_hora(self, t: str, timestamp: datetime):
        data = timestamp.strftime("%d/%m/%Y")
        hora = timestamp.strftime("%H:%M")

        if any(p in t for p in ["anteontem", "antes de ontem"]):
            data = (timestamp - timedelta(days=2)).strftime("%d/%m/%Y")
        elif any(p in t for p in ["ontem", "dia anterior"]):
            data = (timestamp - timedelta(days=1)).strftime("%d/%m/%Y")
        elif "semana passada" in t:
            data = (timestamp - timedelta(days=7)).strftime("%d/%m/%Y")

        m_data = re.search(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b', t)
        if m_data:
            dia, mes = int(m_data.group(1)), int(m_data.group(2))
            ano = int(m_data.group(3)) if m_data.group(3) else timestamp.year
            if ano < 100:
                ano += 2000
            try:
                data = datetime(ano, mes, dia).strftime("%d/%m/%Y")
            except ValueError:
                pass
        else:
            m_dia = re.search(r'\bdia\s+(\d{1,2})\b', t)
            if m_dia:
                try:
                    data = timestamp.replace(day=int(m_dia.group(1))).strftime("%d/%m/%Y")
                except ValueError:
                    pass

        return data, hora

    def _detectar_metodo_pagamento(self, t: str) -> str:
        metodos = {
            "Pix": ["pix", "mandei pix", "fiz pix", "via pix", "no pix"],
            "Cartão crédito": ["cartão de crédito", "crédito", "credito", "no crédito", "parcelei no cartão"],
            "Cartão débito": ["cartão de débito", "débito", "debito", "no débito", "passei no débito"],
            "Cartão": ["cartão", "cartao", "passei o cartão", "maquininha"],
            "Dinheiro": ["dinheiro", "dinheiro vivo", "espécie", "em espécie", "cash"],
            "Boleto": ["boleto", "código de barras"],
            "Transferência": ["transferência", "transferencia", "ted", "doc", "transferi"],
        }
        for metodo, palavras in metodos.items():
            if any(p in t for p in palavras):
                return metodo
        return ""

    def _detectar_parcelas(self, t: str) -> tuple:
        m = re.search(r'(\d{1,2})\s*[xX]', t)
        if m:
            return 1, int(m.group(1))
        m = re.search(r'em\s+(\d{1,2})\s*vezes', t)
        if m:
            return 1, int(m.group(1))
        m = re.search(r'parcela\s+(\d{1,2})\s+de\s+(\d{1,2})', t)
        if m:
            return int(m.group(1)), int(m.group(2))
        return 0, 0

    def _detectar_categoria(self, t: str) -> str:
        mapa = {
            "Beleza": [
                "salão","salao","cabeleireiro","cabeleireira","cabelereiro",
                "cabelo","corte de cabelo","cortei cabelo","cortei o cabelo",
                "escova","escovei","progressiva","hidratação capilar","tintura",
                "pintei o cabelo","luzes","mechas","alisamento","cauterização",
                "spa capilar","tratamento capilar",
                "barbeiro","barbearia","barba","fiz a barba","aparei a barba",
                "manicure","pedicure","unha","unhas","esmaltei","nail",
                "alongamento de unha","fibra de vidro","gel nas unhas",
                "sobrancelha","design de sobrancelha","henna","micropigmentação",
                "limpeza de pele","peeling","botox","preenchimento",
                "depilação","depilacao","depilei","cera","laser",
                "cílios","cilios","extensão de cílios","fio a fio",
                "maquiagem","maquiei","make","makeup",
                "estética","estetica","esteticista","procedimento estético",
                "drenagem","massagem modeladora","criolipólise",
                "skin care","skincare","protetor solar","hidratante facial",
                "fui no salão","fui no salao","fui na manicure","fiz as unhas",
                "fui no barbeiro","dei um trato","me arrumei",
            ],
            "Pet": [
                "veterinário","veterinario","vet","consulta do pet","vacina do pet",
                "vacina do cachorro","vacina do gato",
                "ração","racao","sachê","pet shop","petshop","pet",
                "banho e tosa","banho do cachorro","banho do gato","tosador",
                "antipulgas","vermífugo","vermifugo","coleira",
                "areia de gato","areia do gato","granulado",
                "adestrador","adestramento","dog walker",
                "levei o dog","levei o cachorro","levei o gato",
            ],
            "Vestuário": [
                "roupa","roupas","camiseta","camisa","blusa","top",
                "calça","calca","jeans","bermuda","shorts","saia","vestido",
                "jaqueta","casaco","moletom","agasalho","suéter","cardigan",
                "tênis","tenis","sapato","sandália","sandalia","chinelo",
                "bota","coturno","sapatênis","rasteirinha",
                "cueca","calcinha","sutiã","meia","meias",
                "cinto","bolsa","carteira","mochila","óculos de sol",
                "relógio","relogio","pulseira","brinco","colar","acessório",
                "costura","costureira","alfaiate","ajuste","bainha",
                "lavanderia","tinturaria","sapateiro",
                "shein","renner","c&a","riachuelo","zara","hering",
                "nike","adidas","puma","new balance","mizuno",
                "comprei roupa","comprei um tênis","comprei sapato",
            ],
            "Filhos": [
                "fralda","fraldas","pampers","huggies",
                "brinquedo","brinquedos","boneca","carrinho","lego",
                "pediatra","consulta do filho","consulta da filha",
                "escola do filho","escola da filha","mensalidade escola",
                "material escolar","mochila escolar","uniforme escolar",
                "creche","jardim de infância","berçário",
                "roupa infantil","roupa de criança","roupa do bebê",
                "leite","fórmula","formula","nan","aptamil","nestogeno",
                "papinha","comida do bebê",
                "chupeta","mamadeira","cadeirinha","carrinho de bebê",
                "mesada","pro filho","pra filha","pro bebê","do neném","do nenê",
            ],
            "Presentes": [
                "presente","presentes","lembrancinha",
                "doação","doacao","doei","caridade","ong","vaquinha",
                "dízimo","dizimo","oferta","oferta da igreja","contribuição",
                "ajuda financeira","emprestei",
                "dei de presente","comprei de presente",
                "aniversário","surpresa","mimo",
            ],
            "Veículo": [
                "ipva","licenciamento","dpvat","seguro do carro","seguro auto",
                "seguro veicular","seguro do veículo",
                "multa","multa de trânsito","detran","cnh","habilitação",
                "revisão do carro","manutenção do carro","mecânico",
                "mecanico","oficina","borracharia","guincho","reboque",
                "pneu","pneus","troca de óleo","oleo","alinhamento",
                "balanceamento","pastilha de freio","amortecedor","embreagem",
                "bateria do carro","farol","autopeças","autopecas",
                "lavagem do carro","lavei o carro","lava jato","lava-jato",
                "insulfilm","película","envelopamento",
                "financiamento do carro","parcela do carro","consórcio",
                "estética automotiva","polimento","cristalização",
            ],
            "Impostos": [
                "imposto de renda","ir","irpf","irpj","darf",
                "inss","contribuição inss","guia inss",
                "iss","icms","simples nacional","das",
                "cartório","cartorio","taxa de cartório","escritura",
                "taxa de prefeitura","alvará","alvara",
                "crea","crm","oab","anuidade do conselho",
                "imposto","tributo","guia de recolhimento",
            ],
            "Assinaturas": [
                "netflix","amazon prime","disney plus","disney+","hbo","hbo max",
                "globoplay","star plus","star+","apple tv","crunchyroll","telecine",
                "deezer","spotify","youtube premium","youtube music","tidal",
                "icloud","google one","dropbox","onedrive",
                "game pass","xbox game pass","ps plus","playstation plus","ea play",
                "chatgpt","chatgpt plus","claude","copilot","midjourney",
                "canva","canva pro","adobe","creative cloud","figma",
                "notion","todoist","evernote","1password","nordvpn",
                "clube de assinatura","box mensal","tag","sem parar",
                "strava","calm","headspace","duolingo plus",
                "assinatura","renovação automática","plano mensal","plano anual",
                "debitou","debitou automático","cobrança recorrente",
            ],
            "Tecnologia": [
                "celular","smartphone","iphone","samsung","xiaomi","motorola",
                "notebook","laptop","macbook","chromebook","computador","pc","desktop",
                "tablet","ipad","kindle",
                "fone","fone de ouvido","airpods","headset","caixa de som","jbl",
                "smartwatch","apple watch","galaxy watch",
                "tv","televisão","smart tv","monitor",
                "videogame","playstation","ps5","ps4","xbox","nintendo","switch",
                "câmera","gopro","drone","ring light",
                "pendrive","hd externo","ssd","memória ram",
                "carregador","cabo","capinha","película do celular",
                "assistência técnica","conserto do celular","conserto do notebook",
                "formatei","reparo eletrônico",
                "jogo","game","steam","epic games",
                "comprei um celular","troquei de celular","comprei um fone",
            ],
            "Alimentação": [
                "almoço","almocei","almocar","jantar","jantei","jantar fora",
                "café da manhã","café","tomei café","lanche","lanchei",
                "refeição","comi","comer",
                "restaurante","lanchonete","padaria","confeitaria","bistrô",
                "hamburgueria","pizzaria","sushiaria","churrascaria","boteco",
                "food truck","cantina","quiosque","self service",
                "ifood","rappi","uber eats","delivery","pedi comida",
                "mercado","supermercado","sacolão","feira","hortifruti","açougue",
                "mercearia","atacado","atacarejo","assaí","makro",
                "cerveja","refrigerante","suco","drinks","sorvete","açaí",
                "tapioca","pastel","esfiha","coxinha",
                "comi no","jantei no","almocei no","tomei um","bebi um",
                "petisco","rodízio","buffet","combinado",
            ],
            "Transporte": [
                "uber","99","cabify","indriver","ladydriver",
                "ônibus","onibus","metro","metrô","trem","brt","van","lotação",
                "mototaxi","taxi","táxi",
                "gasolina","combustível","alcool","etanol","diesel","gnv",
                "abasteci","posto","posto de gasolina",
                "estacionamento","estacionei","manobrista","rotativo",
                "pedágio","pedagio",
                "avião","voo","passagem aérea","aeroporto",
                "rodoviária","bicicleta","patinete","scooter",
                "peguei um","chamei um","fui de","vim de",
                "taquei no uber","meti no uber",
            ],
            "Contas": [
                "conta de luz","conta de água","conta de gás","conta de internet",
                "luz","energia","energia elétrica","enel","cemig",
                "água","sabesp","copasa","saneamento",
                "gás de cozinha","gás encanado","comgas","naturgy","botijão",
                "internet","wi-fi","wifi","banda larga",
                "telefone","plano de celular","chip",
                "tv a cabo","sky",
                "aluguel","condomínio","condominio","iptu",
                "fatura","boleto","conta de","pagar a conta",
                "paguei o boleto","paguei a fatura","chegou a conta",
            ],
            "Lazer": [
                "cinema","filme","ingresso","imax",
                "show","concerto","festival","teatro","peça","musical",
                "evento","festa","balada","boate","clube","bar","pub",
                "parque","parque de diversões",
                "viagem","hotel","pousada","hostel","airbnb","booking",
                "excursão","passeio","turismo",
                "esporte","futebol","ingresso do jogo",
                "surf","skate","beach tennis",
                "saí","rolou uma","fomos ao","fomos no",
                "curtimos","festinha",
            ],
            "Saúde": [
                "médico","medico","consulta","clínica","hospital",
                "dentista","ortodontista",
                "psicólogo","psiquiatra","terapeuta","terapia",
                "fisioterapeuta","fisioterapia","nutricionista",
                "oftalmologista","óculos","ótica","lentes de contato",
                "farmácia","farmacia","remédio","remedio","medicamento",
                "droga raia","ultrafarma","drogasil",
                "vitamina","suplemento","whey","creatina","proteína",
                "plano de saúde","unimed","hapvida","amil",
                "exame","laboratorio","raio-x","ultrassom","ressonância",
                "academia","gym","crossfit","pilates","yoga","natação",
                "smart fit","bluefit","bodytech",
            ],
            "Educação": [
                "faculdade","universidade","graduação","pós-graduação",
                "mestrado","doutorado","mba","especialização",
                "escola","colégio","ensino médio",
                "curso","aula","workshop","palestra","treinamento",
                "bootcamp","imersão","mentoria","coaching",
                "inglês","espanhol","francês","idioma",
                "livro","apostila","material didático",
                "udemy","coursera","alura","hotmart",
                "mensalidade","matrícula",
                "paguei o curso","me inscrevi no","comprei um curso",
            ],
            "Moradia": [
                "reforma","reformei","obra","pedreiro","eletricista","encanador",
                "pintura","pintou","tinta","massa corrida",
                "móvel","sofá","cama","guarda-roupa","armário",
                "colchão","cozinha planejada",
                "decoração","tapete","quadro","luminária","lustre",
                "faxina","faxineira","diarista",
                "manutenção da casa","conserto","reparo","hidráulica",
                "financiamento","parcela do apartamento","imóvel",
                "mudança","frete","carreto",
            ],
            "Salário": [
                "salário","salario","vencimento","holerite","contracheque",
                "13","décimo terceiro","gratificação",
                "férias","ferias","rescisão","fgts",
                "adiantamento","vale","pró-labore","pro labore",
                "retirada de sócio",
                "caiu o salário","veio o salário","recebi meu salário",
                "entrou o salário",
            ],
            "Freelance": [
                "freela","freelance","bico","trampo","trabalho extra",
                "projeto","cliente","prestação de serviço",
                "honorários","comissão",
                "consultoria","designer","programação",
                "redação","marketing","social media","gestor de tráfego",
                "venda","vendas","vendi","negócio",
                "fechei um freela","entrou um cliente","veio um trampo",
                "fiz um serviço","me contrataram",
            ],
            "Investimento": [
                "investimento","investir","investei","apliquei","aplicação",
                "ações","bolsa","b3","ibovespa","tesouro","tesouro direto",
                "cdb","lci","lca","debenture","fii","fundo imobiliário",
                "renda fixa","renda variável",
                "cripto","criptomoeda","bitcoin","btc","ethereum","eth","usdt",
                "poupança","poupanca","caixinha","cofre",
                "previdência","pgbl","vgbl",
                "aportei","fiz um aporte","coloquei no tesouro",
            ],
        }

        for cat, palavras in mapa.items():
            if any(p in t for p in palavras):
                return cat
        return "Outros"

    def _detectar_subcategoria(self, t: str, categoria: str) -> str:
        mapa = {
            "Beleza": {
                "Corte de cabelo": ["corte","cortei cabelo","cortei o cabelo","aparar"],
                "Salão": ["salão","salao","cabeleireiro","cabeleireira"],
                "Escova": ["escova","escovei","chapinha","prancha"],
                "Progressiva": ["progressiva","alisamento","definitiva","botox capilar"],
                "Tintura": ["tintura","pintei o cabelo","luzes","mechas","coloração"],
                "Tratamento capilar": ["hidratação capilar","cauterização","spa capilar"],
                "Barbearia": ["barbeiro","barbearia","barba","fiz a barba"],
                "Manicure": ["manicure","pedicure","unha","unhas","esmaltei","nail","gel"],
                "Sobrancelha": ["sobrancelha","design de sobrancelha","henna","micropigmentação"],
                "Depilação": ["depilação","depilacao","depilei","cera","laser"],
                "Cílios": ["cílios","cilios","extensão de cílios","fio a fio"],
                "Maquiagem": ["maquiagem","maquiei","make","makeup"],
                "Skin care": ["skin care","skincare","protetor solar","hidratante facial"],
                "Estética": ["estética","estetica","limpeza de pele","peeling","botox","drenagem","criolipólise"],
            },
            "Pet": {
                "Veterinário": ["veterinário","veterinario","vet","consulta do pet"],
                "Ração": ["ração","racao","sachê","comida do pet"],
                "Pet shop": ["pet shop","petshop"],
                "Banho e tosa": ["banho e tosa","banho do cachorro","banho do gato","tosador"],
                "Vacina": ["vacina do pet","vacina do cachorro","vacina do gato"],
                "Medicamento pet": ["antipulgas","vermífugo","coleira"],
            },
            "Vestuário": {
                "Roupa": ["roupa","roupas","camiseta","camisa","blusa","calça","jeans","bermuda","saia","vestido","jaqueta","casaco","moletom"],
                "Tênis": ["tênis","tenis"],
                "Sapato": ["sapato","sandália","chinelo","bota","coturno","sapatênis","rasteirinha"],
                "Acessório": ["cinto","bolsa","carteira","mochila","óculos de sol","relógio","pulseira","brinco","colar"],
                "Costura": ["costura","costureira","alfaiate","ajuste","bainha"],
                "Lavanderia": ["lavanderia","tinturaria","sapateiro"],
            },
            "Filhos": {
                "Fralda": ["fralda","fraldas","pampers","huggies"],
                "Brinquedo": ["brinquedo","boneca","carrinho","lego"],
                "Escola": ["escola do filho","escola da filha","mensalidade escola","material escolar","uniforme"],
                "Creche": ["creche","jardim de infância","berçário"],
                "Pediatra": ["pediatra","consulta do filho"],
                "Alimentação bebê": ["leite","fórmula","nan","aptamil","papinha"],
                "Mesada": ["mesada"],
            },
            "Presentes": {
                "Presente": ["presente","presentes","lembrancinha","mimo","surpresa"],
                "Aniversário": ["aniversário"],
                "Doação": ["doação","doacao","doei","caridade","ong","vaquinha"],
                "Dízimo/Oferta": ["dízimo","dizimo","oferta","oferta da igreja","contribuição"],
                "Ajuda financeira": ["ajuda financeira","emprestei"],
            },
            "Veículo": {
                "IPVA": ["ipva"],
                "Licenciamento": ["licenciamento","dpvat"],
                "Seguro auto": ["seguro do carro","seguro auto","seguro veicular"],
                "Multa": ["multa","multa de trânsito"],
                "Revisão": ["revisão do carro","revisão","manutenção do carro"],
                "Mecânico": ["mecânico","mecanico","oficina"],
                "Pneu": ["pneu","pneus"],
                "Lavagem": ["lavagem","lavei o carro","lava jato","lava-jato"],
                "Autopeças": ["autopeças","autopecas","pastilha","amortecedor","embreagem"],
                "Estética auto": ["estética automotiva","polimento","cristalização","insulfilm","película"],
                "CNH": ["cnh","habilitação","detran"],
            },
            "Impostos": {
                "IR": ["imposto de renda","ir","irpf","darf"],
                "INSS": ["inss","contribuição inss","guia inss"],
                "Simples/DAS": ["simples nacional","das"],
                "Cartório": ["cartório","cartorio","escritura"],
                "Taxa": ["taxa de prefeitura","alvará","taxa bancária","iof"],
                "Conselho": ["crea","crm","oab","anuidade do conselho"],
            },
            "Assinaturas": {
                "Netflix": ["netflix"],
                "Spotify": ["spotify","deezer","tidal"],
                "Amazon Prime": ["amazon prime","prime video"],
                "Disney+": ["disney plus","disney+"],
                "HBO": ["hbo","hbo max","max"],
                "YouTube Premium": ["youtube premium","youtube music"],
                "iCloud": ["icloud","google one","dropbox"],
                "Game Pass": ["game pass","ps plus","ea play"],
                "IA": ["chatgpt","claude","copilot","midjourney"],
                "Design": ["canva","adobe","creative cloud","figma"],
                "Clube": ["clube de assinatura","box mensal","strava"],
            },
            "Tecnologia": {
                "Celular": ["celular","smartphone","iphone","samsung","xiaomi","motorola"],
                "Notebook": ["notebook","laptop","macbook","computador","pc"],
                "Tablet": ["tablet","ipad","kindle"],
                "Fone": ["fone","airpods","headset","caixa de som","jbl"],
                "Smartwatch": ["smartwatch","apple watch"],
                "TV": ["tv","televisão","smart tv","monitor"],
                "Console": ["videogame","playstation","ps5","xbox","nintendo","switch"],
                "Acessório tech": ["carregador","cabo","capinha","pendrive","hd externo","ssd"],
                "Reparo": ["assistência técnica","conserto do celular","conserto do notebook"],
                "Game": ["jogo","game","steam","epic games"],
            },
            "Alimentação": {
                "Almoço": ["almoço","almocei","prato do dia","self service","buffet"],
                "Jantar": ["jantar","jantei","rodízio"],
                "Café da manhã": ["café da manhã","tomei café"],
                "Lanche": ["lanche","lanchei","fast food","hamburgueria","coxinha","pastel","esfiha"],
                "Mercado": ["mercado","supermercado","sacolão","atacado","assaí","makro","carrefour"],
                "Delivery": ["ifood","rappi","uber eats","delivery","pedi comida"],
                "Restaurante": ["restaurante","lanchonete","cantina","bistrô","sushiaria","churrascaria"],
                "Padaria": ["padaria","confeitaria","pão","bolo"],
                "Churrasco": ["churrasco","carne","picanha"],
                "Açaí": ["açaí","acai"],
                "Feira": ["feira","hortifruti"],
                "Bar": ["bar","boteco","barzinho","petisco","cerveja","chopp"],
                "Pizza": ["pizza","pizzaria"],
            },
            "Transporte": {
                "Uber": ["uber"],
                "99": ["99","99pop"],
                "Táxi": ["taxi","táxi"],
                "Ônibus/Metrô": ["ônibus","onibus","brt","metro","metrô","trem","van"],
                "Gasolina": ["gasolina","combustível","etanol","diesel","abasteci","posto"],
                "Estacionamento": ["estacionamento","estacionei","manobrista","rotativo"],
                "Pedágio": ["pedágio","pedagio"],
                "Avião": ["avião","voo","passagem aérea","aeroporto"],
            },
            "Contas": {
                "Luz": ["luz","energia","enel","cemig","energia elétrica"],
                "Água": ["água","sabesp","copasa","saneamento"],
                "Gás": ["gás de cozinha","gás encanado","comgas","naturgy","botijão"],
                "Internet": ["internet","wi-fi","wifi","banda larga"],
                "Telefone": ["telefone","plano de celular","chip"],
                "Aluguel": ["aluguel"],
                "Condomínio": ["condomínio","condominio"],
                "IPTU": ["iptu"],
            },
            "Lazer": {
                "Cinema": ["cinema","filme","ingresso"],
                "Show": ["show","concerto","festival","teatro"],
                "Festa": ["festa","balada","boate"],
                "Bar": ["bar","pub"],
                "Viagem": ["viagem","hotel","pousada","hostel","airbnb"],
                "Passeio": ["passeio","excursão","turismo","parque"],
                "Esporte": ["futebol","surf","skate","beach tennis"],
            },
            "Saúde": {
                "Médico": ["médico","medico","consulta","clínica","hospital"],
                "Dentista": ["dentista","ortodontista"],
                "Farmácia": ["farmácia","farmacia","remédio","remedio","medicamento","droga raia","ultrafarma","drogasil"],
                "Exame": ["exame","laboratorio","raio-x","ultrassom","ressonância"],
                "Academia": ["academia","gym","crossfit","pilates","yoga","natação","smart fit","bluefit","bodytech"],
                "Psicólogo": ["psicólogo","psiquiatra","terapeuta","terapia"],
                "Plano de Saúde": ["plano de saúde","unimed","hapvida","amil"],
                "Suplemento": ["vitamina","suplemento","whey","creatina","proteína"],
            },
            "Educação": {
                "Curso": ["curso","workshop","bootcamp","imersão","udemy","coursera","alura","hotmart"],
                "Faculdade": ["faculdade","universidade","graduação","pós","mestrado","mba"],
                "Escola": ["escola","colégio","creche"],
                "Livro": ["livro","apostila","material"],
                "Idioma": ["inglês","espanhol","francês","idioma","duolingo"],
                "Mensalidade": ["mensalidade","matrícula"],
            },
            "Moradia": {
                "Reforma": ["reforma","obra","pedreiro","eletricista","encanador","pintura","tinta"],
                "Móvel": ["móvel","sofá","cama","guarda-roupa","armário","colchão"],
                "Decoração": ["decoração","tapete","quadro","luminária","lustre"],
                "Faxina": ["faxina","faxineira","diarista"],
                "Manutenção": ["manutenção da casa","conserto","reparo","hidráulica"],
                "Mudança": ["mudança","frete","carreto"],
            },
            "Salário": {
                "Salário fixo": ["salário","salario","vencimento","holerite"],
                "13º salário": ["13","décimo terceiro"],
                "Férias": ["férias","ferias"],
                "Bônus": ["bônus","bonus","gratificação","plr"],
                "Adiantamento": ["adiantamento","vale"],
            },
            "Freelance": {
                "Projeto": ["projeto","freela","freelance","bico","trampo"],
                "Consultoria": ["consultoria","consultor","mentoria"],
                "Design": ["design","designer","arte","criação"],
                "Programação": ["programação","desenvolvimento","dev","código"],
                "Venda": ["venda","vendas","vendi"],
            },
            "Investimento": {
                "Ações": ["ações","bolsa","b3","ibovespa"],
                "Tesouro Direto": ["tesouro","tesouro direto"],
                "CDB": ["cdb","lci","lca"],
                "Fundo": ["fundo","fii","fundo imobiliário"],
                "Cripto": ["cripto","criptomoeda","bitcoin","btc","ethereum","eth"],
                "Poupança": ["poupança","poupanca","caixinha","cofre"],
                "Previdência": ["previdência","pgbl","vgbl"],
            },
        }

        subs = mapa.get(categoria, {})
        for sub_nome, palavras in subs.items():
            if any(p in t for p in palavras):
                return sub_nome
        return ""

    def _detectar_localizacao(self, texto: str, t: str) -> str:
        locais = {
            "Shopping": ["shopping","mall","center"],
            "Supermercado": ["mercado","supermercado","extra","carrefour","assaí","pão de açúcar","atacadão","makro"],
            "Farmácia": ["farmácia","farmacia","droga raia","drogasil","ultrafarma","pacheco","panvel"],
            "Academia": ["academia","gym","smart fit","bluefit","bodytech"],
            "Restaurante": ["restaurante","lanchonete","churrascaria","sushiaria","cantina"],
            "Padaria": ["padaria","confeitaria"],
            "Hospital": ["hospital","upa","pronto socorro","ubs","posto de saúde"],
            "Aeroporto": ["aeroporto","gru","gig","cnf","sdu"],
            "Posto de Gasolina": ["posto","posto de gasolina","shell","ipiranga"],
            "Banco": ["banco","agência","bradesco","itaú","santander","caixa","nubank"],
            "Pet Shop": ["pet shop","petshop","petz","cobasi"],
        }

        for nome, palavras in locais.items():
            if any(p in t for p in palavras):
                return nome

        cidades = [
            "são paulo","sp","rio de janeiro","rj","belo horizonte","bh",
            "salvador","brasília","df","curitiba","fortaleza","recife",
            "porto alegre","goiânia","manaus","belém",
            "florianópolis","vitória","natal","joão pessoa",
            "maceió","campo grande","cuiabá","teresina",
            "contagem","betim","uberlândia","campinas","santos",
            "ribeirão preto","vespasiano","sete lagoas",
        ]
        for cidade in cidades:
            if cidade in t:
                return cidade.title()

        padroes = [
            r'\b(?:aqui\s+)?(?:no|na|do|da)\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][a-záéíóúâêîôûãõçà]+(?:\s+(?:do|da|de|dos|das)\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][a-záéíóúâêîôûãõçà]+)?)',
        ]

        ignorar = {
            "dia","mês","ano","casa","trabalho","hoje","ontem","agora",
            "vez","forma","jeito","total","conta","uber","ifood","rappi",
            "salário","salario","gasto","compra","pix","dinheiro",
            "mulher","marido","esposa","esposo","namorada","namorado",
            "amigo","amiga","mãe","pai","filho","filha","irmão","irmã",
            "manhã","tarde","noite","semana","hora","minuto",
            "cartão","crédito","débito","parcela","boleto",
            "pedro","joão","maria","ana","josé","carlos","lucas","gabriel",
            "julia","bruna","amanda","rafael","felipe","bruno","mateus",
            "dog","cachorro","gato","pet",
        }

        for padrao in padroes:
            m = re.search(padrao, texto)
            if m:
                local = m.group(1).strip()
                if local.lower() not in ignorar and len(local) > 2:
                    return local

        return ""

    def _gerar_descricao(self, texto: str, t: str, categoria: str, subcategoria: str) -> str:
        texto_limpo = texto.strip()

        if len(texto_limpo) <= 55:
            return texto_limpo

        if subcategoria:
            contextos = []
            companhia = {
                "namorad": "com namorado(a)",
                "amig": "com amigos",
                "mulher": "com a esposa",
                "esposa": "com a esposa",
                "marido": "com o marido",
                "esposo": "com o marido",
                "famili": "em família",
                "filho": "com filho(a)",
                "filha": "com filha",
                "mãe": "com a mãe",
                "pai": "com o pai",
            }
            for chave, desc in companhia.items():
                if chave in t:
                    contextos.append(desc)
                    break

            desc = subcategoria
            if contextos:
                desc += " " + contextos[0]
            return desc[:55]

        return texto_limpo[:52] + "..."

    def _normalizar(self, dados: dict, timestamp: datetime) -> dict:
        if not dados.get("data"):
            dados["data"] = timestamp.strftime("%d/%m/%Y")
        if not dados.get("hora"):
            dados["hora"] = timestamp.strftime("%H:%M")

        hora_gemini = dados.get("hora", "")
        hora_real = timestamp.strftime("%H:%M")
        if hora_gemini != hora_real:
            dados["hora"] = hora_real

        if dados.get("categoria") not in CATEGORIAS:
            dados["categoria"] = "Outros"

        if dados.get("tipo") not in ["Gasto", "Receita", "Transferência"]:
            dados["tipo"] = "Gasto" if float(dados.get("valor", 0)) < 0 else "Receita"

        loc = dados.get("localizacao", "")
        locais_invalidos = [
            "ai","ia","não informado","não mencionado",
            "não especificado","desconhecido","n/a","none",
            "null","undefined","não informada","não especificada",
            "local não informado","local não mencionado",
            "não identificado","sem local",
        ]
        if loc.lower().strip() in locais_invalidos:
            dados["localizacao"] = ""

        dados.setdefault("subcategoria", "")
        dados.setdefault("localizacao", "")
        dados.setdefault("descricao", dados.get("categoria", ""))
        dados.setdefault("metodo_pagamento", "")
        dados.setdefault("parcela_atual", 0)
        dados.setdefault("total_parcelas", 0)

        return dados
