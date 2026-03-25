"""
START FINANCE — Extração Inteligente v5.0
Entende linguagem formal e informal, gírias e todos os cenários.
"""

import os, re, json, logging
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)

CATEGORIAS = ["Alimentação","Transporte","Contas","Lazer","Saúde",
              "Educação","Moradia","Salário","Freelance","Investimento","Outros"]

# ── Linguagem formal e informal para RECEITAS ─────────────────────────
PALAVRAS_RECEITA = [
    # Formal
    "recebi","recebimento","receita","entrada","salário","salario",
    "remuneração","remuneracao","honorários","honorarios","pagamento recebido",
    "transferência recebida","deposito","depósito","crédito","credito",
    "reembolso","restituição","restituicao","dividendo","rendimento",
    "lucro","bonificação","bonificacao","bonus","bônus","13 salário",
    "décimo terceiro","ferias","férias","pró-labore","pro labore",
    # Informal
    "caiu","caiu na conta","cairam","pagaram","me pagaram","me mandaram",
    "me passaram","recebi um pix","pix caiu","pix entrou","entrou na conta",
    "entrou o dinheiro","me depositaram","fiz uma grana","ganhei","ganhei uma grana",
    "veio dinheiro","veio a grana","fechei um freela","fechei um projeto",
    "vendeu","vendi","me devolveram","devolveram","estorno","estornaram",
]

# ── Linguagem formal e informal para GASTOS ───────────────────────────
PALAVRAS_GASTO = [
    # Formal
    "gastei","paguei","comprei","adquiri","contratei","desembolsei",
    "despesa","gasto","pagamento","parcela","prestação","mensalidade",
    "anuidade","taxa","tarifa","débito","fatura","boleto","cobrança",
    # Informal
    "fui no","fui na","fui ao","passei no","passei na","taquei","meti",
    "botei","joguei","gastei uma grana","saiu","saiu da conta","foi embora",
    "sumiu","tive que pagar","tive que desembolsar","aproveitei e paguei",
    "acabei pagando","acabei comprando","rolou um","rolou uma",
    "comi no","jantei no","almocei no","tomei no","bebi no","fui no",
    "peguei um","chamei um","chamei o","usei o","usei a",
]

# ── Palavras que indicam contexto financeiro ──────────────────────────
PALAVRAS_FINANCEIRAS = [
    "real","reais","r$","conto","contos","centavo","centavos","dinheiro",
    "grana","bufunfa","money","pila","pilas","toco","nota","nota de",
    "gastei","paguei","comprei","recebi","entrou","caiu","saiu",
    "uber","ifood","rappi","mercado","supermercado","farmácia","academia",
    "almoço","jantar","café","lanche","conta","boleto","fatura","luz","água",
    "internet","telefone","netflix","spotify","gasolina","estacionamento",
    "salário","salario","freela","freelance","investimento","poupança",
]


class AIExtractor:
    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY","")

    async def transcrever_audio(self, caminho_audio: str) -> str:
        return ""

    async def extrair(self, texto: str, timestamp: datetime):
        texto = texto.strip()
        if not texto:
            return None

        # Tenta Gemini
        if self.gemini_key:
            try:
                resultado = await self._extrair_gemini(texto, timestamp)
                if resultado:
                    logger.info(f"✅ Gemini: {resultado.get('descricao')} R${resultado.get('valor')}")
                    return resultado
            except Exception as e:
                logger.error(f"Gemini falhou: {e}")

        # Fallback inteligente por regras
        resultado = self._extrair_por_regras(texto, timestamp)
        if resultado:
            logger.info(f"✅ Regras: {resultado.get('descricao')} R${resultado.get('valor')}")
        return resultado

    # ══════════════════════════════════════════════════════════════════
    # GEMINI
    # ══════════════════════════════════════════════════════════════════
    async def _extrair_gemini(self, texto: str, timestamp: datetime):
        ontem = (timestamp - timedelta(days=1)).strftime('%d/%m/%Y')
        hoje = timestamp.strftime('%d/%m/%Y')

        prompt = f"""Você é um extrator de dados financeiros brasileiro especialista.
Entende linguagem formal e informal, gírias e expressões do dia a dia.

Contexto: Hoje {hoje} {timestamp.strftime('%H:%M')} | Ontem {ontem}

Exemplos de mensagens que você deve reconhecer:
- "fui no mercado hoje, gastei 85" → Gasto R$85 Alimentação/Mercado
- "taquei 50 no uber" → Gasto R$50 Transporte/Uber
- "caiu o salário, 3500" → Receita R$3500 Salário/Salário fixo
- "almocei no shopping, saiu 45" → Gasto R$45 Alimentação/Almoço
- "paguei a luz, 120 reais" → Gasto R$120 Contas/Luz
- "recebi um pix de 200" → Receita R$200 Outros/Pix
- "netflix debitou 55,90" → Gasto R$55.90 Contas/Netflix
- "fechei um freela de 800" → Receita R$800 Freelance/Projeto
- "meti 30 no posto" → Gasto R$30 Transporte/Gasolina
- "jantei fora com a namorada, 120" → Gasto R$120 Alimentação/Jantar
- "comprei uns remédios, 75 reais" → Gasto R$75 Saúde/Farmácia
- "investei 500 no tesouro" → Gasto R$500 Investimento/Tesouro Direto

Categorias: Alimentação, Transporte, Contas, Lazer, Saúde, Educação, Moradia, Salário, Freelance, Investimento, Outros

Regras:
- Gastos/pagamentos/compras = valor NEGATIVO, tipo "Gasto"
- Recebimentos/receitas/salário = valor POSITIVO, tipo "Receita"
- Extraia localização se mencionada (lugar, estabelecimento, cidade)
- Subcategoria: seja específico
- Descrição: clara e curta (máx 55 chars)
- Se não for financeiro: {{"transacao":false}}

Mensagem: "{texto}"

Retorne SOMENTE JSON (sem markdown, sem explicação):
{{"transacao":true,"data":"{hoje}","hora":"{timestamp.strftime('%H:%M')}","valor":-50.00,"tipo":"Gasto","categoria":"Alimentação","subcategoria":"Almoço","descricao":"Almoço no shopping","localizacao":"Shopping"}}"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.gemini_key}"
        payload = {
            "contents":[{"parts":[{"text":prompt}]}],
            "generationConfig":{"temperature":0.1,"maxOutputTokens":300}
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)

        if resp.status_code != 200:
            logger.error(f"Gemini HTTP {resp.status_code}: {resp.text[:200]}")
            return None

        data = resp.json()
        raw = data["candidates"][0]["content"]["parts"][0]["text"].strip()

        # Remove markdown se vier
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

    # ══════════════════════════════════════════════════════════════════
    # EXTRAÇÃO POR REGRAS (FALLBACK ROBUSTO)
    # ══════════════════════════════════════════════════════════════════
    def _extrair_por_regras(self, texto: str, timestamp: datetime):
        t = texto.lower().strip()

        # Verifica se é financeiro
        if not self._eh_financeiro(t):
            return None

        # Detecta tipo
        tipo = self._detectar_tipo(t)

        # Extrai valor (muito mais robusto)
        valor = self._extrair_valor_robusto(texto, t)
        if not valor:
            return None

        valor = abs(valor) if tipo == "Receita" else -abs(valor)

        data, hora = self._extrair_data_hora(t, timestamp)
        categoria = self._detectar_categoria(t)
        subcategoria = self._detectar_subcategoria(t, categoria)
        localizacao = self._detectar_localizacao(t)
        descricao = self._gerar_descricao(texto, t, categoria, subcategoria)

        return {
            "data": data, "hora": hora, "valor": valor, "tipo": tipo,
            "categoria": categoria, "subcategoria": subcategoria,
            "descricao": descricao, "localizacao": localizacao
        }

    def _eh_financeiro(self, t: str) -> bool:
        """Verifica se a mensagem tem contexto financeiro."""
        return any(p in t for p in PALAVRAS_FINANCEIRAS)

    def _detectar_tipo(self, t: str) -> str:
        """Detecta se é receita ou gasto."""
        score_receita = sum(1 for p in PALAVRAS_RECEITA if p in t)
        score_gasto = sum(1 for p in PALAVRAS_GASTO if p in t)
        return "Receita" if score_receita > score_gasto else "Gasto"

    def _extrair_valor_robusto(self, texto: str, t: str) -> float:
        """Extrai valor monetário com múltiplos padrões — formal e informal."""
        padroes = [
            # Com R$ (formal)
            r"R\$\s*(\d{1,6}(?:[.,]\d{1,2})?)",
            # Com "reais" depois
            r"(\d{1,6}(?:[.,]\d{1,2})?)\s*reais?",
            # Com "conto(s)" — informal
            r"(\d{1,6}(?:[.,]\d{1,2})?)\s*contos?",
            # Com "pila(s)" — informal
            r"(\d{1,6}(?:[.,]\d{1,2})?)\s*pilas?",
            # Valor grande com vírgula (ex: 1.500,00 ou 1,500.00)
            r"(\d{1,3}(?:\.\d{3})*,\d{2})\b",
            # Valor com ponto decimal (ex: 45.90)
            r"\b(\d{2,6}\.\d{2})\b",
            # Número solto de 2+ dígitos (ex: "gastei 50 no uber")
            r"\b(\d{2,5})\b",
        ]

        for padrao in padroes:
            m = re.search(padrao, texto, re.IGNORECASE)
            if m:
                val_str = m.group(1)
                # Normaliza separadores
                val_str = val_str.replace(".", "").replace(",", ".")
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

        # Data
        if any(p in t for p in ["anteontem","antes de ontem"]):
            data = (timestamp - timedelta(days=2)).strftime("%d/%m/%Y")
        elif any(p in t for p in ["ontem","dia anterior"]):
            data = (timestamp - timedelta(days=1)).strftime("%d/%m/%Y")
        elif any(p in t for p in ["semana passada"]):
            data = (timestamp - timedelta(days=7)).strftime("%d/%m/%Y")

        # Hora
        if any(p in t for p in ["manhã","manha","cedo","café da manhã","de manhã","pela manhã"]):
            hora = "08:00"
        elif any(p in t for p in ["almoço","almoco","meio-dia","meio dia","na hora do almoço"]):
            hora = "12:30"
        elif any(p in t for p in ["tarde","à tarde","de tarde","pela tarde"]):
            hora = "15:00"
        elif any(p in t for p in ["noite","à noite","de noite","pela noite","jantar","janta"]):
            hora = "20:00"
        elif any(p in t for p in ["agora pouco","agora","acabei de"]):
            hora = timestamp.strftime("%H:%M")

        return data, hora

    def _detectar_categoria(self, t: str) -> str:
        """Detecta categoria com vocabulário formal e informal."""
        mapa = {
            "Alimentação": [
                # Refeições
                "almoço","almocei","almocar","jantar","jantei","jantar fora",
                "café da manhã","café","tomei café","lanche","lanchei","lanchou",
                "café da tarde","lanche da tarde","refeição","comi","comer",
                # Estabelecimentos
                "restaurante","lanchonete","padaria","confeitaria","bistrô","bistro",
                "hamburgueria","pizzaria","sushiaria","churrascaria","boteco","barzinho",
                "food truck","cantina","quiosque","trailer de","self service",
                # Apps e delivery
                "ifood","rappi","uber eats","ubereats","james","loggi","zé delivery",
                "delivery","pedi comida","pedí","pedido","pedi no","mandei buscar",
                # Compras
                "mercado","supermercado","sacolão","feira","hortifruti","açougue",
                "peixaria","mercearia","empório","atacado","atacarejo","assaí","makro",
                # Bebidas e snacks
                "cerveja","refrigerante","suco","água","drinks","drinque","coquetel",
                "sorvete","açaí","acai","tapioca","pastel","esfiha","coxinha",
                # Gírias
                "comi no","jantei no","almocei no","tomei um","bebi um","bebi no",
                "petisco","tira-gosto","rodízio","buffet","combinado",
            ],
            "Transporte": [
                # Apps
                "uber","99","cabify","indriver","in driver","ladydriver",
                "uber black","uber x","uber comfort","uber flash",
                # Transporte público
                "ônibus","onibus","metro","metrô","trem","brt","van","lotação",
                "mototaxi","moto táxi","taxi","táxi","táxi convencional",
                # Próprio
                "gasolina","combustível","alcool","etanol","diesel","gnv",
                "abasteci","posto","posto de gasolina","shell","ipiranga","br","ale",
                "estacionamento","estacionei","manobrista","rotativo",
                "pedágio","pedagio","sem parar","conectcar",
                # Outros
                "avião","voo","passagem aérea","aeroporto","embarque",
                "rodoviária","ônibus intermunicipal","ônibus interestadual",
                "bicicleta","patinete","scooter","tembici","yellow","grow",
                "manutenção do carro","revisão","borracharia","guincho",
                # Gírias
                "peguei um","chamei um","chame o","chame a","fui de","vim de",
                "taquei no uber","meti no uber","botei no uber",
            ],
            "Contas": [
                # Utilidades
                "luz","energia","energia elétrica","enel","cemig","copel","coelba",
                "água","agua","sabesp","copasa","sanepar","saneamento",
                "gás","gas","comgas","naturgy","cegás",
                "internet","wi-fi","wifi","net","claro","vivo","tim","oi","embratel",
                "telefone","telefonia","linha fixa","celular","plano","chip",
                "tv a cabo","sky","claro tv","oi tv","net tv",
                # Moradia (contas fixas)
                "aluguel","condomínio","condominio","iptu","seguro do imóvel",
                # Streaming
                "netflix","amazon prime","disney plus","disney+","hbo","hbo max",
                "globoplay","star plus","star+","apple tv","crunchyroll","telecine",
                "deezer","spotify","youtube premium","youtube music",
                # Assinaturas
                "assinatura","mensalidade do","anuidade","plano anual","renovação",
                # Fatura
                "fatura","boleto","conta de","pagar a conta","venceu","vencimento",
                # Gírias
                "paguei o boleto","paguei a fatura","chegou a conta","veio a conta",
            ],
            "Lazer": [
                # Entretenimento
                "cinema","filme","ingresso","cinema","imax","drive-in",
                "show","concerto","festival","teatro","peça","musical","ópera",
                "evento","festa","balada","boate","clube","bar","pub",
                "parque","parque de diversões","hopi hari","beto carrero",
                # Hobbies
                "jogo","game","videogame","playstation","xbox","nintendo","steam",
                "livro","mangá","hq","quadrinho","gibi",
                "hobby","coleção","colecionável",
                # Viagem
                "viagem","hotel","pousada","hostel","airbnb","booking",
                "excursão","passeio","turismo","atração turística",
                # Esporte
                "esporte","academia","futebol","jogo de futebol","ingresso do jogo",
                "surf","skate","crossfit","pilates","yoga","natação","tênis","beach tennis",
                # Gírias
                "saí","rolou uma","fomos ao","fomos no","fui ao","fui no",
                "aproveitamos","curtimos","balada","festinha","jogo de bola",
            ],
            "Saúde": [
                # Consultas
                "médico","medico","consulta","clínica","clinica","hospital",
                "dentista","ortodontista","otorrinolaringologista","dermatologista",
                "psicólogo","psicologo","psiquiatra","terapeuta","terapia",
                "fisioterapeuta","fisioterapia","fisio","nutricionista","nutrição",
                "oftalmologista","óculos","ótica","otica","lentes de contato",
                # Remédios e farmácia
                "farmácia","farmacia","remédio","remedio","medicamento","comprimido",
                "droga raia","ultrafarma","panvel","pacheco","drogasil","drogaria",
                "vitamina","suplemento","whey","creatina","proteína",
                # Planos e exames
                "plano de saúde","plano","unimed","hapvida","sulamérica","amil",
                "exame","laboratorio","laboratório","raio-x","ultrassom","ressonância",
                # Bem-estar
                "academia","gym","crossfit","pilates","yoga","natação",
                "spa","massagem","estética","cirurgia estética",
                # Gírias
                "fui ao médico","fui na farmácia","comprei remédio","tive consulta",
            ],
            "Educação": [
                # Formação
                "faculdade","universidade","uni","graduação","graduacao","pós-graduação",
                "mestrado","doutorado","mba","especialização","especializacao",
                "escola","colégio","colegio","ensino médio","eja",
                "creche","jardim de infância","escola infantil",
                # Cursos
                "curso","aula","workshop","palestra","treinamento","capacitação",
                "bootcamp","imersão","mentoría","mentoria","coaching",
                "inglês","ingles","espanhol","francês","alemão","idioma","escola de idiomas",
                # Materiais
                "livro","apostila","material didático","caneta","caderno","mochila",
                # Plataformas
                "udemy","coursera","alura","hotmart","monetizze","eduzz",
                "duo lingo","duolingo","babbel","rosetta stone",
                # Mensalidades
                "mensalidade","matrícula","matricula","rematrícula","taxa escolar",
                # Gírias
                "paguei o curso","me inscrevi no","comprei um curso","fiz um curso",
            ],
            "Moradia": [
                "reforma","reformei","reformar","obra","pedreiro","eletricista","encanador",
                "pintura","pintou","pintei","tinta","massa corrida",
                "móvel","movel","moveis","móveis","sofá","cama","guarda-roupa","armário",
                "colchão","colchao","travesseiro","roupa de cama","cozinha planejada",
                "decoração","decoracao","tapete","quadro","luminária","lustre",
                "limpeza","faxina","faxineira","diarista","empregada","camareira",
                "manutenção","manutencao","conserto","reparo","hidráulica",
                "financiamento","parcela do apartamento","parcela da casa","imóvel",
                # Gírias
                "arrumei a casa","fiz uma reforma","contratei um","chamar o",
            ],
            "Salário": [
                "salário","salario","vencimento","holerite","contracheque","contra-cheque",
                "13","décimo terceiro","decimo terceiro","gratificação","gratificacao",
                "férias","ferias","rescisão","rescisao","fgts",
                "adiantamento","vale","pró-labore","pro labore","retirada","retirada de sócio",
                # Gírias
                "caiu o salário","veio o salário","recebi meu salário","pagaram meu salário",
                "caiu a grana","entrou o salário","bateu o salário",
            ],
            "Freelance": [
                "freela","freelance","freelas","bico","trampo","trabalho extra",
                "projeto","projetos","cliente","clientes","prestação de serviço",
                "honorários","honorarios","comissão","comissao",
                "consultoria","consultor","designer","programação","programacao",
                "redação","redacao","marketing","social media","gestor de tráfego",
                "venda","vendas","vendi","empreendimento","negócio","negocio",
                # Gírias
                "fechei um freela","bati a meta","entrou um cliente","veio um trampo",
                "fiz um serviço","prestei um serviço","me contrataram",
            ],
            "Investimento": [
                "investimento","investir","investei","apliquei","aplicação","aplicacao",
                "ações","acoes","bolsa","b3","ibovespa","tesouro","tesouro direto",
                "cdb","lci","lca","debenture","debênture","fii","fundo imobiliário",
                "renda fixa","renda variável","variável","variavel",
                "cripto","criptomoeda","bitcoin","btc","ethereum","eth","usdt",
                "poupança","poupanca","caixinha","cofre","porquinho",
                "previdência","previdencia","pgbl","vgbl","fundo de pensão",
                # Gírias
                "botei na poupança","meti na bolsa","comprei ações","comprei bitcoin",
                "aportei","fiz um aporte","coloquei no tesouro",
            ],
        }

        for cat, palavras in mapa.items():
            if any(p in t for p in palavras):
                return cat
        return "Outros"

    def _detectar_subcategoria(self, t: str, categoria: str) -> str:
        """Detecta subcategoria com vocabulário expandido."""
        mapa = {
            "Alimentação": {
                "Almoço": ["almoço","almocei","almocar","almocamos","na hora do almoço","prato do dia","self service","buffet"],
                "Jantar": ["jantar","jantei","jantamos","jantar fora","jantei fora","rodízio","pizzaria à noite"],
                "Café da manhã": ["café da manhã","café","tomei café","tomei um café","padaria de manhã","café da tarde"],
                "Lanche": ["lanche","lanchei","lanchamos","fast food","hamburgueria","x-burguer","coxinha","pastel","esfiha"],
                "Mercado": ["mercado","supermercado","sacolão","atacado","atacarejo","assaí","makro","extra","carrefour","pão de açúcar","hortifruti"],
                "Delivery": ["ifood","rappi","uber eats","ubereats","delivery","pedi comida","mandei buscar","james"],
                "Restaurante": ["restaurante","lanchonete","cantina","bistrô","bistro","sushiaria","churrascaria","self service"],
                "Padaria": ["padaria","confeitaria","pão","bolo","pãozinho"],
                "Churrasco": ["churrasco","churrascaria","carne","picanha"],
                "Açaí": ["açaí","acai"],
                "Feira": ["feira","sacolão","hortifruti","orgânico"],
                "Bar": ["bar","boteco","barzinho","petisco","tira-gosto","cerveja","chopp"],
            },
            "Transporte": {
                "Uber": ["uber","uber black","uber x","uber comfort","uber flash","uberx"],
                "99": ["99","99pop","99taxi"],
                "Táxi": ["taxi","táxi","táxi convencional"],
                "Ônibus": ["ônibus","onibus","brt","metro","metrô","trem","van","lotação"],
                "Gasolina": ["gasolina","combustível","alcool","etanol","diesel","gnv","abasteci","posto"],
                "Estacionamento": ["estacionamento","estacionei","manobrista","rotativo"],
                "Pedágio": ["pedágio","pedagio","sem parar","conectcar"],
                "Avião": ["avião","voo","passagem aérea","aeroporto"],
                "Manutenção": ["manutenção do carro","revisão","borracharia","guincho","mecânico"],
                "Patinete": ["patinete","scooter","tembici","yellow","grow","bicicleta"],
            },
            "Contas": {
                "Luz": ["luz","energia","enel","cemig","copel","coelba","energia elétrica"],
                "Água": ["água","agua","sabesp","copasa","sanepar","saneamento"],
                "Gás": ["gás","gas","comgas","naturgy"],
                "Internet": ["internet","wi-fi","wifi","net","banda larga"],
                "Telefone": ["telefone","celular","plano","chip","linha"],
                "Aluguel": ["aluguel","mensalidade do apartamento","mensalidade da casa"],
                "Condomínio": ["condomínio","condominio"],
                "Netflix": ["netflix"],
                "Spotify": ["spotify","deezer"],
                "Streaming": ["amazon prime","disney","hbo","globoplay","apple tv","crunchyroll","telecine","star"],
                "IPTU": ["iptu"],
            },
            "Saúde": {
                "Médico": ["médico","medico","consulta","clínica","hospital","dr","dra"],
                "Dentista": ["dentista","ortodontista"],
                "Farmácia": ["farmácia","farmacia","remédio","remedio","medicamento","comprimido","droga raia","ultrafarma","drogasil"],
                "Exame": ["exame","laboratorio","raio-x","ultrassom","ressonância"],
                "Academia": ["academia","gym","crossfit","pilates","yoga","natação"],
                "Psicólogo": ["psicólogo","psicologo","psiquiatra","terapeuta","terapia"],
                "Plano de Saúde": ["plano de saúde","plano","unimed","hapvida","amil"],
                "Suplemento": ["vitamina","suplemento","whey","creatina","proteína"],
            },
            "Educação": {
                "Curso": ["curso","workshop","bootcamp","imersão","capacitação","udemy","coursera","alura","hotmart"],
                "Faculdade": ["faculdade","universidade","graduação","pós","mestrado","mba"],
                "Escola": ["escola","colégio","ensino médio","creche"],
                "Livro": ["livro","apostila","material"],
                "Inglês": ["inglês","ingles","espanhol","francês","idioma","duolingo","babbel"],
                "Mensalidade": ["mensalidade","matrícula","taxa"],
            },
            "Salário": {
                "Salário fixo": ["salário","salario","vencimento","holerite"],
                "13º salário": ["13","décimo terceiro","decimo terceiro"],
                "Férias": ["férias","ferias"],
                "Bônus": ["bônus","bonus","gratificação","plr"],
                "Adiantamento": ["adiantamento","vale"],
            },
            "Freelance": {
                "Projeto": ["projeto","freela","freelance","bico","trampo"],
                "Consultoria": ["consultoria","consultor","mentoria","coaching"],
                "Design": ["design","designer","arte","criação"],
                "Programação": ["programação","programacao","desenvolvimento","dev","código"],
                "Redação": ["redação","redacao","texto","conteúdo","copywriting"],
            },
            "Investimento": {
                "Ações": ["ações","acoes","bolsa","b3","ibovespa"],
                "Tesouro Direto": ["tesouro","tesouro direto"],
                "CDB": ["cdb","lci","lca"],
                "Fundo": ["fundo","fii","fundo imobiliário"],
                "Cripto": ["cripto","criptomoeda","bitcoin","btc","ethereum","eth"],
                "Poupança": ["poupança","poupanca","caixinha","cofre"],
                "Dividendos": ["dividendo","dividendos","rendimento"],
            },
        }

        subs = mapa.get(categoria, {})
        for sub_nome, palavras in subs.items():
            if any(p in t for p in palavras):
                return sub_nome
        return ""

    def _detectar_localizacao(self, t: str) -> str:
        """Detecta localização com padrões formais e informais."""
        # Locais comuns
        locais = {
            "Shopping": ["shopping","shoppings","mall","center"],
            "Supermercado": ["mercado","supermercado","extra","carrefour","walmart","assaí",
                            "pão de açúcar","bh","atacadão","makro"],
            "Farmácia": ["farmácia","farmacia","droga raia","drogasil","ultrafarma","pacheco","panvel"],
            "Academia": ["academia","gym","smart fit","bluefit","bodytech"],
            "Restaurante": ["restaurante","lanchonete","churrascaria","sushiaria","cantina"],
            "Padaria": ["padaria","confeitaria"],
            "Hospital": ["hospital","upa","pronto socorro","pronto-socorro","ubs","posto de saúde"],
            "Aeroporto": ["aeroporto","gru","gig","cnf","sdu"],
            "Posto de Gasolina": ["posto","posto de gasolina","shell","ipiranga","br","ale"],
            "Banco": ["banco","agência","bradesco","itaú","santander","caixa","bb","nubank"],
        }

        for nome, palavras in locais.items():
            if any(p in t for p in palavras):
                return nome

        # Cidades brasileiras
        cidades = [
            "são paulo","sp","rio de janeiro","rj","belo horizonte","bh","salvador","ba",
            "brasília","df","curitiba","pr","fortaleza","ce","recife","pe",
            "porto alegre","rs","goiânia","go","manaus","am","belém","pa",
            "florianópolis","sc","vitória","es","natal","rn","joão pessoa","pb",
            "maceió","al","campo grande","ms","cuiabá","mt","teresina","pi",
            "contagem","betim","uberlândia","campinas","santos","ribeirão preto",
        ]
        for cidade in cidades:
            if cidade in t:
                return cidade.title()

        # Padrões textuais: "no X", "na X", "em X", "aqui no X"
        padroes = [
            r'\b(?:aqui\s+)?no\s+([a-záéíóúâêîôûãõçà]{3,}(?:\s+[a-záéíóúâêîôûãõçà]{3,})?)',
            r'\b(?:aqui\s+)?na\s+([a-záéíóúâêîôûãõçà]{3,}(?:\s+[a-záéíóúâêîôûãõçà]{3,})?)',
            r'\b(?:aqui\s+)?em\s+([a-záéíóúâêîôûãõçà]{3,}(?:\s+[a-záéíóúâêîôûãõçà]{3,})?)',
            r'\bperto\s+d[oa]\s+([a-záéíóúâêîôûãõçà]{3,})',
        ]

        ignorar = {"dia","mês","ano","casa","trabalho","hoje","ontem","agora",
                   "vez","forma","jeito","total","conta","uber","ifood","rappi",
                   "salário","salario","gasto","compra","pix","dinheiro"}

        for padrao in padroes:
            m = re.search(padrao, t)
            if m:
                local = m.group(1).strip()
                if local not in ignorar and len(local) > 2:
                    return local.title()

        return ""

    def _gerar_descricao(self, texto: str, t: str, categoria: str, subcategoria: str) -> str:
        """Gera descrição limpa e clara."""
        # Limpa o texto original
        texto_limpo = texto.strip()

        # Se curto o suficiente, usa direto
        if len(texto_limpo) <= 55:
            return texto_limpo

        # Tenta construir descrição baseada na subcategoria + contexto
        if subcategoria:
            # Procura contexto adicional (com quem, onde)
            contextos = []
            if any(p in t for p in ["namorad","amig","famili","esposo","esposa","marido","mulher","filho","filha"]):
                if "namorad" in t:
                    contextos.append("com namorado(a)")
                elif "amig" in t:
                    contextos.append("com amigos")
                elif "famili" in t or "filho" in t or "filha" in t:
                    contextos.append("em família")

            desc = subcategoria
            if contextos:
                desc += " " + ", ".join(contextos)
            return desc

        return texto_limpo[:52] + "..." if len(texto_limpo) > 55 else texto_limpo

    def _normalizar(self, dados: dict, timestamp: datetime) -> dict:
        """Normaliza e valida todos os campos."""
        if not dados.get("data"):
            dados["data"] = timestamp.strftime("%d/%m/%Y")
        if not dados.get("hora"):
            dados["hora"] = timestamp.strftime("%H:%M")
        if dados.get("categoria") not in CATEGORIAS:
            dados["categoria"] = "Outros"
        if dados.get("tipo") not in ["Gasto","Receita","Transferência"]:
            dados["tipo"] = "Gasto" if float(dados.get("valor",0)) < 0 else "Receita"
        dados.setdefault("subcategoria","")
        dados.setdefault("localizacao","")
        dados.setdefault("descricao", dados.get("categoria",""))
        return dados
