"""
START FINANCE — Extração Inteligente v8.0
Correções críticas:
 • hora SEMPRE usa o timestamp real (nunca fictícia)
 • data usa timestamp real por padrão
 • categorias mais precisas (Veículo, Beleza, etc.)
 • fallback ultra-robusto sem depender do Gemini
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
    "🍕":"Alimentação","🍔":"Alimentação","🍟":"Alimentação","🍝":"Alimentação",
    "🍜":"Alimentação","🍣":"Alimentação","🍱":"Alimentação","🍛":"Alimentação",
    "🥗":"Alimentação","🍺":"Alimentação","🍻":"Alimentação","🍷":"Alimentação",
    "☕":"Alimentação","🧃":"Alimentação","🥤":"Alimentação","🍰":"Alimentação",
    "🍦":"Alimentação","🛒":"Alimentação","🧁":"Alimentação","🥐":"Alimentação",
    "🚗":"Transporte","🚕":"Transporte","🚙":"Transporte","🏍":"Transporte",
    "🚌":"Transporte","✈️":"Transporte","⛽":"Transporte","🚇":"Transporte",
    "💊":"Saúde","🏥":"Saúde","🩺":"Saúde","🦷":"Saúde","💉":"Saúde",
    "💅":"Beleza","💇":"Beleza","💇‍♀️":"Beleza","💇‍♂️":"Beleza","✂️":"Beleza",
    "🐶":"Pet","🐱":"Pet","🐾":"Pet","🦮":"Pet",
    "👗":"Vestuário","👟":"Vestuário","👠":"Vestuário","👕":"Vestuário",
    "👖":"Vestuário","🧥":"Vestuário","👜":"Vestuário","🎒":"Vestuário",
    "📚":"Educação","🎓":"Educação","✏️":"Educação",
    "🎁":"Presentes","💝":"Presentes","🎂":"Presentes",
    "📱":"Tecnologia","💻":"Tecnologia","🖥":"Tecnologia","🎮":"Tecnologia",
    "👶":"Filhos","🍼":"Filhos","🧸":"Filhos",
    "🏠":"Moradia","🔧":"Moradia","🪑":"Moradia",
    "🎬":"Lazer","🏖":"Lazer","⚽":"Lazer","🎵":"Lazer",
    "🚘":"Veículo","🔩":"Veículo","🔧":"Veículo",
    "📈":"Investimento","💰":"Investimento","💵":"Salário","🤑":"Salário",
    "💡":"Contas","🔌":"Contas","🏛":"Impostos",
}

PALAVRAS_RECEITA = [
    "recebi","recebimento","receita","entrada","salário","salario",
    "remuneração","honorários","pagamento recebido","transferência recebida",
    "deposito","depósito","crédito","credito","reembolso","restituição",
    "dividendo","rendimento","lucro","bonificação","bonus","bônus",
    "13 salário","décimo terceiro","ferias","férias","pró-labore","pro labore",
    "caiu","caiu na conta","cairam","pagaram","me pagaram","me mandaram",
    "me passaram","recebi um pix","pix caiu","pix entrou","entrou na conta",
    "entrou o dinheiro","me depositaram","ganhei","ganhei uma grana",
    "veio dinheiro","veio a grana","fechei um freela","fechei um projeto",
    "vendeu","vendi","me devolveram","devolveram","estorno","estornaram",
]

PALAVRAS_FINANCEIRAS = [
    "real","reais","r$","conto","contos","grana","pila","pilas","toco",
    "gastei","paguei","comprei","recebi","entrou","caiu","saiu",
    "uber","ifood","rappi","mercado","supermercado","farmácia","academia",
    "almoço","jantar","café","lanche","conta","boleto","fatura","luz","água",
    "internet","telefone","netflix","spotify","gasolina","estacionamento",
    "salário","salario","freela","freelance","investimento","poupança",
    "salão","salao","cabelo","unha","manicure","barbeiro","barbearia",
    "roupa","tênis","sapato","calçado","blusa","camisa","vestido","jaqueta",
    "veterinário","ração","pet shop","banho e tosa",
    "celular","notebook","fone","iphone","samsung","xiaomi",
    "fralda","brinquedo","creche","pediatra",
    "presente","doação","dízimo",
    "ipva","licenciamento","seguro do carro","multa","detran","oficina",
    "peças","autopecas","autopeças","pneu","borracharia","mecânico","mecanico",
    "imposto","ir","inss","cartório",
    "parcela","parcelei","prestação","financiamento",
    "pix","cartão","débito","dinheiro vivo",
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

        # Tenta Gemini primeiro
        if self.gemini_key:
            try:
                resultado = await self._extrair_gemini(texto, timestamp)
                if resultado:
                    if isinstance(resultado, list):
                        logger.info(f"✅ Gemini: {len(resultado)} transações")
                        for r in resultado:
                            r = self._fixar_hora(r, timestamp)
                        return resultado[0] if len(resultado) == 1 else resultado
                    resultado = self._fixar_hora(resultado, timestamp)
                    logger.info(f"✅ Gemini: {resultado.get('descricao')} R${resultado.get('valor')}")
                    return resultado
            except Exception as e:
                logger.error(f"Gemini falhou: {e}")

        # Fallback por regras
        resultado = self._extrair_por_regras(texto, timestamp)
        if resultado:
            logger.info(f"✅ Regras: {resultado.get('descricao')} R${resultado.get('valor')}")
        return resultado

    def _fixar_hora(self, dados: dict, timestamp: datetime) -> dict:
        """
        CRÍTICO: Sempre usa a hora real do timestamp do Telegram.
        Nunca aceita hora inventada pela IA.
        Só muda a DATA se o usuário explicitamente disse "ontem", "anteontem" etc.
        """
        # Hora SEMPRE real
        dados["hora"] = timestamp.strftime("%H:%M")

        # Data: mantém o que a IA extraiu SÓ se o texto original tinha referência temporal
        # (isso é controlado na extração — aqui garantimos o fallback)
        if not dados.get("data"):
            dados["data"] = timestamp.strftime("%d/%m/%Y")

        return dados

    # ══════════════════════════════════════════════════════════════════
    # GEMINI
    # ══════════════════════════════════════════════════════════════════
    async def _extrair_gemini(self, texto: str, timestamp: datetime):
        hoje     = timestamp.strftime('%d/%m/%Y')
        ontem    = (timestamp - timedelta(days=1)).strftime('%d/%m/%Y')
        hora_real = timestamp.strftime('%H:%M')

        prompt = f"""Você é o melhor extrator de dados financeiros do Brasil.
Entende QUALQUER forma de falar: formal, informal, gíria, emoji, voz transcrita.

REGRA DE OURO — HORA: Use SEMPRE "{hora_real}" (hora real da mensagem). NUNCA invente outra hora.
REGRA DE OURO — DATA: Use "{hoje}" como padrão. Mude SOMENTE se o usuário disse "ontem" ({ontem}), "anteontem", "dia X" ou data explícita.

Categorias (use SOMENTE estas):
Alimentação, Transporte, Contas, Lazer, Saúde, Educação, Moradia,
Beleza, Vestuário, Pet, Tecnologia, Filhos, Presentes, Veículo,
Impostos, Assinaturas, Salário, Freelance, Investimento, Outros

Diferenciações CRÍTICAS (nunca erre estas):
• "salão"/"cabelo"/"unha"/"manicure"/"barbeiro" → BELEZA (NUNCA Contas)
• "gás de cozinha"/"botijão"/"comgas" → Contas
• "gasolina"/"posto"/"combustível" → Transporte
• "peças do carro"/"pneu"/"mecânico"/"oficina"/"borracharia"/"autopeças" → VEÍCULO
• "ipva"/"licenciamento"/"seguro do carro"/"multa de trânsito"/"revisão do carro" → VEÍCULO
• "lavagem do carro"/"lava jato" → VEÍCULO
• "roupa"/"tênis"/"sapato"/"calçado"/"blusa"/"bermuda" → VESTUÁRIO
• "ração"/"veterinário"/"pet shop"/"banho e tosa" → PET
• "fralda"/"brinquedo infantil"/"pediatra"/"escola do filho" → FILHOS
• "presente"/"doação"/"dízimo"/"vaquinha" → PRESENTES
• "celular"/"notebook"/"fone"/"gadget" → TECNOLOGIA
• "netflix"/"spotify"/"icloud"/"game pass"/"assinatura" → ASSINATURAS
• "ir"/"inss"/"iptu"/"cartório"/"alvará"/"taxa" → IMPOSTOS
• "freela"/"bico"/"projeto pago"/"consultoria recebida" → FREELANCE (receita)
• "ações"/"tesouro"/"cdb"/"cripto"/"poupança" → INVESTIMENTO

Regras:
- Gastos/pagamentos/compras → tipo "Gasto", valor NEGATIVO
- Recebimentos/receitas/salário → tipo "Receita", valor POSITIVO
- hora: SEMPRE "{hora_real}" — NUNCA mude isso
- Extraia localização SOMENTE se o usuário nomeou um lugar real
- Descrição: clara, curta (máx 55 chars), preserve contexto humano
- Método: pix/cartão crédito/cartão débito/dinheiro/boleto — só se mencionado
- Parcelas: total_parcelas se mencionou "Nx" ou "N vezes"
- Se múltiplas transações: retorne array
- Se não for financeiro: {{"transacao":false}}

Exemplos:
"gastei 900 com a mulher no salao" → Beleza, Salão, -900
"peças do carro 350 parcelei em 3x" → Veículo, Autopeças, -350, total_parcelas:3
"50 uber + 35 ifood" → [{Transporte/Uber -50}, {Alimentação/Delivery -35}]
"lavagem do carro 60 reais" → Veículo, Lavagem, -60
"comprei um tênis, 450" → Vestuário, Tênis, -450
"levei o dog no vet, 280" → Pet, Veterinário, -280
"ipva do carro 1800 em 3x" → Veículo, IPVA, -1800, total_parcelas:3
"netflix debitou 55,90" → Assinaturas, Netflix, -55.90

Mensagem: "{texto}"

Retorne SOMENTE JSON válido (sem markdown):
{{"transacao":true,"data":"{hoje}","hora":"{hora_real}","valor":-50.00,"tipo":"Gasto","categoria":"","subcategoria":"","descricao":"","localizacao":"","metodo_pagamento":"","parcela_atual":0,"total_parcelas":0}}"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.05, "maxOutputTokens": 600}
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)

        if resp.status_code != 200:
            logger.error(f"Gemini HTTP {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Remove markdown
        if "```" in raw:
            for parte in raw.split("```"):
                parte = parte.strip().lstrip("json").strip()
                if parte.startswith("{") or parte.startswith("["):
                    raw = parte
                    break

        resultado = json.loads(raw)

        # Array = múltiplas transações
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

    # ══════════════════════════════════════════════════════════════════
    # FALLBACK POR REGRAS (robusto)
    # ══════════════════════════════════════════════════════════════════
    def _extrair_por_regras(self, texto: str, timestamp: datetime):
        t = texto.lower().strip()
        cat_emoji = self._detectar_emoji(texto)

        if not cat_emoji and not self._eh_financeiro(t):
            return None

        tipo     = self._detectar_tipo(t)
        valor    = self._extrair_valor(texto, t)
        if not valor:
            return None

        valor    = abs(valor) if tipo == "Receita" else -abs(valor)
        data     = self._extrair_data(t, timestamp)
        hora     = timestamp.strftime("%H:%M")  # SEMPRE real
        categoria    = cat_emoji or self._detectar_categoria(t)
        subcategoria = self._detectar_subcategoria(t, categoria)
        localizacao  = self._detectar_localizacao(texto, t)
        descricao    = self._gerar_descricao(texto, t, categoria, subcategoria)
        metodo       = self._detectar_metodo(t)
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
        score_r = sum(1 for p in PALAVRAS_RECEITA if p in t)
        score_g = len(re.findall(r'\b(gastei|paguei|comprei|saiu|taquei|meti|botei)\b', t))
        return "Receita" if score_r > score_g else "Gasto"

    def _extrair_valor(self, texto: str, t: str) -> Optional[float]:
        padroes = [
            r"R\$\s*(\d{1,6}(?:[.,]\d{1,2})?)",
            r"(\d{1,6}(?:[.,]\d{1,2})?)\s*reais?",
            r"(\d{1,6}(?:[.,]\d{1,2})?)\s*contos?",
            r"(\d{1,6}(?:[.,]\d{1,2})?)\s*pilas?",
            r"(\d{1,3}(?:\.\d{3})*,\d{2})\b",
            r"\b(\d{2,6}\.\d{2})\b",
            r"\b(\d{2,6})\b",
        ]
        for p in padroes:
            m = re.search(p, texto, re.IGNORECASE)
            if m:
                v = m.group(1).replace(".", "").replace(",", ".")
                try:
                    val = float(v)
                    if val > 0:
                        return val
                except ValueError:
                    pass
        return None

    def _extrair_data(self, t: str, timestamp: datetime) -> str:
        """Data: usa timestamp real, só muda se usuário disse explicitamente."""
        if any(p in t for p in ["anteontem", "antes de ontem"]):
            return (timestamp - timedelta(days=2)).strftime("%d/%m/%Y")
        elif any(p in t for p in ["ontem", "dia anterior"]):
            return (timestamp - timedelta(days=1)).strftime("%d/%m/%Y")
        elif "semana passada" in t:
            return (timestamp - timedelta(days=7)).strftime("%d/%m/%Y")

        # Data explícita formato DD/MM ou DD/MM/YYYY
        m = re.search(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b', t)
        if m:
            try:
                dia = int(m.group(1))
                mes = int(m.group(2))
                ano = int(m.group(3)) if m.group(3) else timestamp.year
                if ano < 100: ano += 2000
                from datetime import datetime as dt
                return dt(ano, mes, dia).strftime("%d/%m/%Y")
            except ValueError:
                pass

        return timestamp.strftime("%d/%m/%Y")  # padrão: hoje

    def _detectar_categoria(self, t: str) -> str:
        # ORDEM IMPORTA: categorias mais específicas primeiro
        mapa_ordenado = [
            # Veículo — ANTES de Transporte para não confundir
            ("Veículo", [
                "peças do carro","peças para o carro","peças pra o carro","autopeças","autopecas",
                "pneu","pneus","troca de óleo","troca de pneu","amortecedor","pastilha de freio",
                "embreagem","bateria do carro","farol","revisão do carro","revisão no carro",
                "manutenção do carro","manutenção no carro","mecânico","mecanico","oficina",
                "borracharia","guincho","reboque",
                "ipva","licenciamento","dpvat","seguro do carro","seguro auto","seguro veicular",
                "multa de trânsito","multa do carro","detran","cnh","habilitação",
                "lavagem do carro","lavei o carro","lava jato","lava-jato",
                "estética automotiva","polimento","insulfilm","envelopamento",
                "financiamento do carro","parcela do carro","consórcio do carro",
            ]),
            # Beleza — antes de outros para pegar "salão" corretamente
            ("Beleza", [
                "salão","salao","cabeleireiro","cabeleireira","cabelereiro",
                "corte de cabelo","cortei cabelo","cortei o cabelo","escova","progressiva",
                "hidratação capilar","tintura","pintei o cabelo","luzes","mechas","alisamento",
                "cauterização","spa capilar","tratamento capilar",
                "barbeiro","barbearia","barba","fiz a barba","aparei a barba",
                "manicure","pedicure","unha","unhas","esmaltei","nail","alongamento de unha",
                "fibra de vidro","gel nas unhas",
                "sobrancelha","design de sobrancelha","henna","micropigmentação",
                "limpeza de pele","peeling","botox","preenchimento",
                "depilação","depilacao","depilei","cera","laser",
                "cílios","cilios","extensão de cílios",
                "maquiagem","maquiei","make","makeup",
                "estética","estetica","esteticista","procedimento estético",
                "drenagem","massagem modeladora","criolipólise",
                "skin care","skincare","protetor solar","hidratante facial",
                "fui no salão","fui na manicure","fiz as unhas","fui no barbeiro",
            ]),
            # Assinaturas — antes de Contas
            ("Assinaturas", [
                "netflix","amazon prime","disney plus","disney+","hbo","hbo max",
                "globoplay","star plus","star+","apple tv","crunchyroll","telecine",
                "deezer","spotify","youtube premium","youtube music","tidal",
                "icloud","google one","dropbox","onedrive",
                "game pass","xbox game pass","ps plus","playstation plus","ea play",
                "chatgpt plus","midjourney","canva pro","adobe","creative cloud","figma pro",
                "clube de assinatura","box mensal","strava","calm","headspace",
                "assinatura","renovação automática","plano mensal","cobrança recorrente",
                "debitou automático",
            ]),
            # Pet
            ("Pet", [
                "veterinário","veterinario","vet","consulta do pet","vacina do pet",
                "vacina do cachorro","vacina do gato",
                "ração","racao","sachê","pet shop","petshop",
                "banho e tosa","banho do cachorro","banho do gato","tosador",
                "antipulgas","vermífugo","vermifugo","coleira",
                "areia de gato","adestrador","adestramento","dog walker",
                "levei o dog","levei o cachorro","levei o gato",
                "petz","cobasi","agropet",
            ]),
            # Vestuário
            ("Vestuário", [
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
            ]),
            # Tecnologia
            ("Tecnologia", [
                "celular","smartphone","iphone","samsung","xiaomi","motorola","apple",
                "notebook","laptop","macbook","computador","pc","desktop",
                "tablet","ipad","kindle",
                "fone","fone de ouvido","airpods","headset","caixa de som","jbl",
                "smartwatch","apple watch","galaxy watch",
                "tv","televisão","smart tv","monitor",
                "videogame","playstation","ps5","ps4","xbox","nintendo","switch",
                "câmera","gopro","drone","ring light",
                "pendrive","hd externo","ssd","memória ram",
                "carregador","cabo","capinha","película do celular",
                "assistência técnica","conserto do celular","conserto do notebook",
                "comprei um celular","troquei de celular","comprei um fone",
            ]),
            # Filhos
            ("Filhos", [
                "fralda","fraldas","pampers","huggies",
                "brinquedo infantil","boneca","carrinho de brinquedo","lego",
                "pediatra","consulta do filho","consulta da filha",
                "escola do filho","escola da filha","mensalidade escola",
                "material escolar","mochila escolar","uniforme escolar",
                "creche","jardim de infância","berçário",
                "roupa infantil","roupa de criança","roupa do bebê",
                "leite materno","fórmula infantil","nan","aptamil","nestogeno",
                "papinha","comida do bebê",
                "chupeta","mamadeira","cadeirinha de bebê","carrinho de bebê",
                "mesada para filho","mesada para filha",
            ]),
            # Presentes
            ("Presentes", [
                "presente","presentes","lembrancinha","mimo","surpresa",
                "doação","doacao","doei","caridade","ong","vaquinha",
                "dízimo","dizimo","oferta","oferta da igreja","contribuição religiosa",
                "ajuda financeira","emprestei para","dei de presente","comprei de presente",
            ]),
            # Impostos
            ("Impostos", [
                "imposto de renda","ir","irpf","irpj","darf",
                "inss autônomo","guia inss","contribuição inss",
                "iss","icms","simples nacional","das","mei",
                "cartório","cartorio","taxa de cartório","escritura",
                "taxa de prefeitura","alvará","alvara",
                "crea","crm","oab","anuidade do conselho",
            ]),
            # Alimentação
            ("Alimentação", [
                "almoço","almocei","jantar","jantei","café da manhã","lanche","lanchei",
                "refeição","comi","restaurante","lanchonete","padaria","confeitaria",
                "hamburgueria","pizzaria","sushiaria","churrascaria","boteco","barzinho",
                "food truck","cantina","quiosque","self service",
                "ifood","rappi","uber eats","ubereats","delivery","pedi comida",
                "mercado","supermercado","sacolão","feira","hortifruti","açougue",
                "mercearia","atacado","atacarejo","assaí","makro","carrefour","extra",
                "cerveja","sorvete","açaí","tapioca","pastel","esfiha","coxinha",
                "pizza","hamburguer","sushi","churrasco","rodízio",
            ]),
            # Transporte
            ("Transporte", [
                "uber","99","cabify","indriver","ladydriver",
                "ônibus","onibus","metro","metrô","trem","brt","van","lotação",
                "mototaxi","taxi","táxi",
                "gasolina","combustível","alcool","etanol","diesel","gnv",
                "abasteci","posto de gasolina",
                "estacionamento","estacionei","manobrista","rotativo",
                "pedágio","pedagio","sem parar",
                "avião","voo","passagem aérea","aeroporto","rodoviária",
                "bicicleta","patinete","scooter","tembici","yellow","grow",
            ]),
            # Contas
            ("Contas", [
                "conta de luz","conta de água","conta de gás","conta de internet",
                "luz","energia elétrica","enel","cemig","copel","coelba",
                "água","sabesp","copasa","sanepar","saneamento",
                "gás de cozinha","gás encanado","comgas","naturgy","botijão",
                "internet","wi-fi","wifi","banda larga","net claro","vivo fibra",
                "telefone fixo","plano de celular","chip","linha",
                "tv a cabo","sky","claro tv",
                "aluguel","condomínio","condominio","iptu",
                "fatura do cartão","paguei o boleto","paguei a fatura",
                "chegou a conta","venceu o boleto",
            ]),
            # Lazer
            ("Lazer", [
                "cinema","filme","ingresso","imax",
                "show","concerto","festival","teatro","peça","musical",
                "evento","festa","balada","boate","clube","bar","pub",
                "parque","parque de diversões",
                "viagem","hotel","pousada","hostel","airbnb","booking",
                "excursão","passeio","turismo",
                "futebol","surf","skate","beach tennis","esporte",
                "saí","fomos ao","fomos no","curtimos","festinha",
            ]),
            # Saúde
            ("Saúde", [
                "médico","medico","consulta médica","clínica","hospital",
                "dentista","ortodontista",
                "psicólogo","psicologo","psiquiatra","terapeuta","terapia",
                "fisioterapeuta","fisioterapia","nutricionista",
                "oftalmologista","óculos","ótica","lentes de contato",
                "farmácia","farmacia","remédio","remedio","medicamento","comprimido",
                "droga raia","ultrafarma","drogasil","drogaria",
                "vitamina","suplemento","whey","creatina","proteína",
                "plano de saúde","unimed","hapvida","amil","sulamerica",
                "exame","laboratorio","raio-x","ultrassom","ressonância",
                "academia","gym","crossfit","pilates","yoga","natação",
                "smart fit","bluefit","bodytech",
            ]),
            # Educação
            ("Educação", [
                "faculdade","universidade","graduação","pós-graduação",
                "mestrado","doutorado","mba","especialização",
                "escola","colégio","ensino médio",
                "curso","aula","workshop","palestra","treinamento","bootcamp",
                "imersão","mentoria","coaching",
                "inglês","espanhol","francês","idioma","escola de idiomas",
                "material didático","apostila",
                "udemy","coursera","alura","hotmart",
                "mensalidade","matrícula","taxa escolar",
            ]),
            # Moradia
            ("Moradia", [
                "reforma","reformei","obra","pedreiro","eletricista","encanador",
                "pintura","pintou","tinta","massa corrida",
                "sofá","cama","guarda-roupa","armário","colchão","cozinha planejada",
                "decoração","tapete","quadro","luminária","lustre",
                "faxina","faxineira","diarista","empregada doméstica",
                "manutenção da casa","conserto em casa","reparo hidráulico",
                "mudança","frete","carreto",
            ]),
            # Salário
            ("Salário", [
                "salário","salario","vencimento","holerite","contracheque",
                "13","décimo terceiro","gratificação","férias","ferias","rescisão",
                "adiantamento","vale salário","pró-labore","pro labore","retirada de sócio",
                "caiu o salário","veio o salário","recebi meu salário","entrou o salário",
            ]),
            # Freelance
            ("Freelance", [
                "freela","freelance","bico","trampo","trabalho extra",
                "projeto pago","cliente pagou","prestação de serviço",
                "honorários recebidos","comissão recebida",
                "consultoria paga","fechei um freela","entrou um cliente",
                "vendi um projeto","me contrataram",
            ]),
            # Investimento
            ("Investimento", [
                "investimento","investir","investei","apliquei","aplicação",
                "ações","bolsa","b3","ibovespa","tesouro","tesouro direto",
                "cdb","lci","lca","debenture","fii","fundo imobiliário",
                "renda fixa","renda variável",
                "cripto","criptomoeda","bitcoin","btc","ethereum","eth","usdt",
                "poupança","poupanca","caixinha","cofre",
                "previdência","pgbl","vgbl",
                "aportei","fiz um aporte","coloquei no tesouro",
            ]),
        ]

        for cat, palavras in mapa_ordenado:
            if any(p in t for p in palavras):
                return cat
        return "Outros"

    def _detectar_subcategoria(self, t: str, categoria: str) -> str:
        mapa = {
            "Veículo": {
                "IPVA": ["ipva"],
                "Licenciamento": ["licenciamento","dpvat"],
                "Seguro auto": ["seguro do carro","seguro auto","seguro veicular"],
                "Multa": ["multa de trânsito","multa do carro"],
                "Revisão": ["revisão do carro","revisão","manutenção do carro","manutenção no carro"],
                "Mecânico": ["mecânico","mecanico","oficina"],
                "Autopeças": ["peças","autopecas","autopeças","pneu","pastilha","amortecedor","embreagem","bateria do carro"],
                "Borracharia": ["borracharia"],
                "Lavagem": ["lavagem do carro","lavei o carro","lava jato","lava-jato"],
                "Estética auto": ["estética automotiva","polimento","cristalização","insulfilm","película"],
                "Guincho": ["guincho","reboque"],
                "CNH": ["cnh","habilitação","detran"],
            },
            "Beleza": {
                "Salão": ["salão","salao","cabeleireiro","cabeleireira"],
                "Corte de cabelo": ["corte","cortei cabelo","cortei o cabelo"],
                "Escova": ["escova","escovei"],
                "Progressiva": ["progressiva","alisamento","definitiva","botox capilar"],
                "Tintura": ["tintura","pintei o cabelo","luzes","mechas","coloração"],
                "Barbearia": ["barbeiro","barbearia","barba","fiz a barba"],
                "Manicure": ["manicure","pedicure","unha","unhas","esmaltei","nail","gel"],
                "Sobrancelha": ["sobrancelha","design de sobrancelha"],
                "Depilação": ["depilação","depilacao","depilei","cera","laser"],
                "Cílios": ["cílios","cilios","extensão de cílios"],
                "Maquiagem": ["maquiagem","maquiei","make","makeup"],
                "Skin care": ["skin care","skincare","protetor solar","hidratante facial"],
                "Estética": ["estética","estetica","limpeza de pele","peeling","botox","drenagem"],
            },
            "Assinaturas": {
                "Netflix": ["netflix"],"Spotify": ["spotify","deezer"],
                "Amazon Prime": ["amazon prime","prime video"],
                "Disney+": ["disney plus","disney+"],"HBO": ["hbo","max"],
                "YouTube Premium": ["youtube premium","youtube music"],
                "iCloud": ["icloud","google one","dropbox"],
                "Game Pass": ["game pass","ps plus","ea play"],
                "IA": ["chatgpt","claude","copilot","midjourney"],
            },
            "Pet": {
                "Veterinário": ["veterinário","veterinario","vet","consulta do pet"],
                "Ração": ["ração","racao","sachê"],"Pet shop": ["pet shop","petshop"],
                "Banho e tosa": ["banho e tosa","banho do cachorro","banho do gato"],
                "Vacina": ["vacina do pet","vacina do cachorro","vacina do gato"],
            },
            "Vestuário": {
                "Roupa": ["roupa","roupas","camiseta","camisa","blusa","calça","jeans","bermuda","vestido","jaqueta","casaco"],
                "Tênis": ["tênis","tenis"],"Sapato": ["sapato","sandália","chinelo","bota","coturno"],
                "Acessório": ["cinto","bolsa","carteira","óculos de sol","relógio","pulseira","brinco"],
                "Lavanderia": ["lavanderia","tinturaria","sapateiro"],
            },
            "Alimentação": {
                "Almoço": ["almoço","almocei","prato do dia","self service","buffet"],
                "Jantar": ["jantar","jantei","rodízio"],"Café da manhã": ["café da manhã","tomei café"],
                "Lanche": ["lanche","lanchei","fast food","hamburgueria","coxinha","pastel","esfiha"],
                "Mercado": ["mercado","supermercado","sacolão","atacado","assaí","makro","carrefour","extra"],
                "Delivery": ["ifood","rappi","uber eats","delivery","pedi comida"],
                "Restaurante": ["restaurante","lanchonete","cantina","bistrô","sushiaria","churrascaria"],
                "Padaria": ["padaria","confeitaria","pão","bolo"],"Churrasco": ["churrasco","carne","picanha"],
                "Açaí": ["açaí","acai"],"Feira": ["feira","hortifruti"],
                "Bar": ["bar","boteco","barzinho","petisco","cerveja","chopp"],
                "Pizza": ["pizza","pizzaria"],"Delivery": ["ifood","rappi","delivery"],
            },
            "Transporte": {
                "Uber": ["uber"],"99": ["99","99pop"],"Táxi": ["taxi","táxi"],
                "Ônibus/Metrô": ["ônibus","metro","metrô","trem","brt","van"],
                "Gasolina": ["gasolina","combustível","etanol","diesel","abasteci","posto"],
                "Estacionamento": ["estacionamento","estacionei","manobrista"],
                "Pedágio": ["pedágio","pedagio","sem parar"],"Avião": ["avião","voo","aeroporto"],
            },
            "Contas": {
                "Luz": ["luz","energia","enel","cemig"],"Água": ["água","sabesp","copasa"],
                "Gás": ["gás de cozinha","gás encanado","comgas","botijão"],
                "Internet": ["internet","wi-fi","wifi","banda larga"],
                "Telefone": ["telefone","celular","plano","chip"],
                "Aluguel": ["aluguel"],"Condomínio": ["condomínio","condominio"],"IPTU": ["iptu"],
            },
            "Saúde": {
                "Médico": ["médico","medico","consulta","hospital"],
                "Dentista": ["dentista","ortodontista"],
                "Farmácia": ["farmácia","farmacia","remédio","remedio","medicamento","drogasil"],
                "Exame": ["exame","laboratorio","raio-x","ultrassom"],
                "Academia": ["academia","gym","crossfit","pilates","yoga","natação","smart fit"],
                "Psicólogo": ["psicólogo","psiquiatra","terapeuta","terapia"],
                "Plano de Saúde": ["plano de saúde","unimed","hapvida","amil"],
            },
            "Salário": {
                "Salário fixo": ["salário","salario","vencimento","holerite"],
                "13º salário": ["13","décimo terceiro"],
                "Férias": ["férias","ferias"],"Bônus": ["bônus","bonus","gratificação"],
                "Adiantamento": ["adiantamento","vale"],
            },
        }
        for sub_nome, palavras in mapa.get(categoria, {}).items():
            if any(p in t for p in palavras):
                return sub_nome
        return ""

    def _detectar_localizacao(self, texto: str, t: str) -> str:
        locais = {
            "Shopping":      ["shopping","mall","center"],
            "Supermercado":  ["supermercado","extra","carrefour","assaí","makro"],
            "Mercado":       ["mercado","hortifruti"],
            "Farmácia":      ["farmácia","farmacia","droga raia","drogasil","ultrafarma","pacheco","panvel"],
            "Academia":      ["academia","gym","smart fit","bluefit","bodytech"],
            "Restaurante":   ["restaurante","lanchonete","churrascaria","sushiaria"],
            "Padaria":       ["padaria","confeitaria"],
            "Hospital":      ["hospital","upa","pronto socorro","ubs","posto de saúde"],
            "Aeroporto":     ["aeroporto","gru","gig","cnf","sdu"],
            "Posto de Gasolina":["posto de gasolina","shell","ipiranga","br ","ale combustíveis"],
            "Banco":         ["banco","agência","bradesco","itaú","santander","caixa"],
            "Pet Shop":      ["pet shop","petshop","petz","cobasi"],
            "Oficina":       ["oficina","mecânico","borracharia"],
            "Lava Jato":     ["lava jato","lava-jato"],
        }
        for nome, palavras in locais.items():
            if any(p in t for p in palavras):
                return nome

        cidades = [
            "são paulo","sp","rio de janeiro","rj","belo horizonte","bh",
            "contagem","betim","vespasiano","sete lagoas","uberlândia",
            "salvador","brasília","curitiba","fortaleza","recife",
            "porto alegre","goiânia","campinas","florianópolis","vitória",
        ]
        for cidade in cidades:
            if cidade in t:
                return cidade.title()

        ignorar = {
            "dia","mês","ano","casa","trabalho","hoje","ontem","agora",
            "vez","forma","total","conta","pix","dinheiro","salário",
            "mulher","marido","esposa","namorada","namorado","amigo","mãe","pai",
            "manhã","tarde","noite","semana","hora","carro","dog","cachorro","gato",
        }
        for padrao in [r'\b(?:aqui\s+)?(?:no|na)\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇa-záéíóúâêîôûãõçà]{3,}(?:\s+[A-ZÁÉÍÓÚa-záéíóú]{3,})?)',
                       r'\bem\s+([A-ZÁÉÍÓÚa-záéíóú]{3,}(?:\s+[A-ZÁÉÍÓÚa-záéíóú]{3,})?)']:
            m = re.search(padrao, texto)
            if m:
                local = m.group(1).strip()
                if local.lower() not in ignorar and len(local) > 2:
                    return local.title()
        return ""

    def _detectar_metodo(self, t: str) -> str:
        if any(p in t for p in ["cartão de crédito","crédito","credito","no crédito","parcelei no cartão","cartão crédito"]):
            return "Cartão crédito"
        if any(p in t for p in ["cartão de débito","débito","debito","no débito","cartão débito"]):
            return "Cartão débito"
        if any(p in t for p in ["pix","mandei pix","via pix","no pix","fiz pix"]):
            return "Pix"
        if any(p in t for p in ["dinheiro","dinheiro vivo","espécie","em espécie","cash"]):
            return "Dinheiro"
        if any(p in t for p in ["boleto","código de barras"]):
            return "Boleto"
        if any(p in t for p in ["cartão","cartao","passei o cartão","maquininha"]):
            return "Cartão"
        return ""

    def _detectar_parcelas(self, t: str):
        m = re.search(r'(\d{1,2})\s*[xX]\b', t)
        if m: return 1, int(m.group(1))
        m = re.search(r'\bem\s+(\d{1,2})\s*vezes', t)
        if m: return 1, int(m.group(1))
        m = re.search(r'parcela(?:do)?\s+em\s+(\d{1,2})', t)
        if m: return 1, int(m.group(1))
        m = re.search(r'parcela\s+(\d{1,2})\s+de\s+(\d{1,2})', t)
        if m: return int(m.group(1)), int(m.group(2))
        return 0, 0

    def _gerar_descricao(self, texto: str, t: str, categoria: str, subcategoria: str) -> str:
        texto_limpo = texto.strip()
        if len(texto_limpo) <= 55:
            return texto_limpo
        if subcategoria:
            companhia = {
                "namorad":"com namorado(a)","mulher":"com a esposa","esposa":"com a esposa",
                "marido":"com o marido","esposo":"com o marido","famili":"em família",
                "filho":"com filho","filha":"com filha","mãe":"com a mãe","pai":"com o pai",
                "amig":"com amigos",
            }
            for chave, desc in companhia.items():
                if chave in t:
                    return f"{subcategoria} {desc}"[:55]
            return subcategoria[:55]
        return texto_limpo[:52] + "..."

    def _normalizar(self, dados: dict, timestamp: datetime) -> dict:
        # Data padrão
        if not dados.get("data"):
            dados["data"] = timestamp.strftime("%d/%m/%Y")

        # HORA SEMPRE REAL — nunca aceita hora da IA
        dados["hora"] = timestamp.strftime("%H:%M")

        if dados.get("categoria") not in CATEGORIAS:
            dados["categoria"] = "Outros"
        if dados.get("tipo") not in ["Gasto","Receita","Transferência"]:
            dados["tipo"] = "Gasto" if float(dados.get("valor",0)) < 0 else "Receita"

        # Localização inválida → limpa
        loc = str(dados.get("localizacao","")).strip()
        invalidos = {"","ai","não informado","não mencionado","não especificado",
                     "desconhecido","n/a","none","null","local não informado","sem local"}
        if loc.lower() in invalidos:
            dados["localizacao"] = ""

        dados.setdefault("subcategoria","")
        dados.setdefault("localizacao","")
        dados.setdefault("descricao", dados.get("categoria",""))
        dados.setdefault("metodo_pagamento","")
        dados.setdefault("parcela_atual",0)
        dados.setdefault("total_parcelas",0)
        return dados
