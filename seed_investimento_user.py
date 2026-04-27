"""
Seed do usuário de teste para Investimentos & Consórcios — Start Finance
Cria o usuário investimento01@gmail.com com dados extensivos em TODOS os tipos
de investimento + 4 consórcios diferentes integrados com despesas fixas.
Roda automaticamente no startup do servidor (idempotente).
"""
import os, json, hashlib, logging, threading
import httpx

logger = logging.getLogger(__name__)

_SB_URL = os.environ.get("SUPABASE_URL", "")
_SB_KEY = os.environ.get("SUPABASE_KEY", "")

TEST_EMAIL    = "investimento01@gmail.com"
TEST_PASSWORD = "1234567"
TEST_NAME     = "Maria Investidora"
TEST_ID       = "u_demo_invest01"
# Versão do seed — bump quando mudar a estrutura dos dados mockados
# pra forçar re-seed em usuários existentes
SEED_VERSION  = 2  # v2: removidas TXs duplicadas de consórcio (já cobertas por fixas)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _sb_headers() -> dict:
    return {
        "apikey":        _SB_KEY,
        "Authorization": f"Bearer {_SB_KEY}",
        "Content-Type":  "application/json",
    }


def _build_mock_data() -> dict:
    """Carteira de investimentos completa + 4 consórcios + fixas integradas."""

    # ── INVESTIMENTOS — todos os tipos com dados realistas ───────────
    inv = [
        # ─── RENDA FIXA (6 ativos) ──────────────────────────────────
        {"nome": "Tesouro Selic 2029", "tipo": "Renda Fixa", "subtipo": "Tesouro Selic",
         "ticker": "", "qtd": 0, "corretora": "XP Investimentos", "objetivo": "Reserva de emergência",
         "valor": 15000, "atual": 16240, "rent": 8.27,
         "dataEntrada": "2024-03-15", "dataVenc": "2029-03-01",
         "indexador": "Selic", "liquidez": "Diária (D+0)", "risco": "Baixo",
         "notas": "Reserva de emergência — liquidez total"},
        {"nome": "Tesouro IPCA+ 2035", "tipo": "Renda Fixa", "subtipo": "Tesouro IPCA+",
         "ticker": "", "qtd": 0, "corretora": "Rico", "objetivo": "Aposentadoria",
         "valor": 25000, "atual": 28450, "rent": 13.80,
         "dataEntrada": "2023-08-10", "dataVenc": "2035-08-15",
         "indexador": "IPCA+", "liquidez": "Mercado secundário", "risco": "Baixo",
         "notas": "IPCA+6.2% a.a. — protegido da inflação"},
        {"nome": "CDB Banco Master 130% CDI", "tipo": "Renda Fixa", "subtipo": "CDB",
         "ticker": "", "qtd": 0, "corretora": "Nuinvest", "objetivo": "Curto prazo",
         "valor": 10000, "atual": 10780, "rent": 7.80,
         "dataEntrada": "2025-02-01", "dataVenc": "2027-02-01",
         "indexador": "CDI", "liquidez": "No vencimento", "risco": "Médio",
         "notas": "FGC garantido até 250k"},
        {"nome": "LCI Itaú 96% CDI", "tipo": "Renda Fixa", "subtipo": "LCI",
         "ticker": "", "qtd": 0, "corretora": "Itaú", "objetivo": "Renda passiva",
         "valor": 20000, "atual": 21240, "rent": 6.20,
         "dataEntrada": "2024-11-01", "dataVenc": "2026-11-01",
         "indexador": "CDI", "liquidez": "No vencimento", "risco": "Baixo",
         "notas": "Isento de IR (crédito imobiliário)"},
        {"nome": "LCA Sicoob 95% CDI", "tipo": "Renda Fixa", "subtipo": "LCA",
         "ticker": "", "qtd": 0, "corretora": "Sicoob", "objetivo": "Renda passiva",
         "valor": 15000, "atual": 15870, "rent": 5.80,
         "dataEntrada": "2025-01-15", "dataVenc": "2027-01-15",
         "indexador": "CDI", "liquidez": "No vencimento", "risco": "Baixo",
         "notas": "Isento de IR (agronegócio)"},
        {"nome": "Debênture Localiza 2030", "tipo": "Renda Fixa", "subtipo": "Debêntures",
         "ticker": "", "qtd": 0, "corretora": "BTG Pactual", "objetivo": "Longo prazo",
         "valor": 12000, "atual": 13620, "rent": 13.50,
         "dataEntrada": "2024-06-20", "dataVenc": "2030-06-20",
         "indexador": "IPCA+", "liquidez": "Mercado secundário", "risco": "Médio",
         "notas": "IPCA+8.4% — incentivada (isenta IR)"},

        # ─── AÇÕES (5 ativos com tickers reais) ─────────────────────
        {"nome": "Petrobras PN", "tipo": "Ações", "subtipo": "Ação PN (Preferencial)",
         "ticker": "PETR4", "qtd": 200, "corretora": "XP Investimentos", "objetivo": "Renda passiva",
         "valor": 8400, "atual": 9432, "rent": 12.29,
         "dataEntrada": "2024-04-10", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Alto",
         "notas": "DY histórico de 12-15%",
         "aportes": [
             {"tipo":"aporte","valor":4200,"qtd":100,"preco":42.00,"data":"2024-04-10","ts":1712707200000},
             {"tipo":"aporte","valor":4200,"qtd":100,"preco":42.00,"data":"2024-09-15","ts":1726358400000}
         ]},
        {"nome": "Vale ON", "tipo": "Ações", "subtipo": "Ação ON (Ordinária)",
         "ticker": "VALE3", "qtd": 100, "corretora": "Rico", "objetivo": "Longo prazo",
         "valor": 7500, "atual": 8587, "rent": 14.49,
         "dataEntrada": "2024-07-22", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Alto",
         "notas": "Maior mineradora brasileira",
         "aportes": [
             {"tipo":"aporte","valor":7500,"qtd":100,"preco":75.00,"data":"2024-07-22","ts":1721606400000}
         ]},
        {"nome": "Itaú Unibanco PN", "tipo": "Ações", "subtipo": "Ação PN (Preferencial)",
         "ticker": "ITUB4", "qtd": 150, "corretora": "Itaú", "objetivo": "Renda passiva",
         "valor": 5400, "atual": 6655, "rent": 23.24,
         "dataEntrada": "2023-12-05", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Médio",
         "notas": "Banco mais sólido do BR — DY consistente"},
        {"nome": "Banco do Brasil ON", "tipo": "Ações", "subtipo": "Ação ON (Ordinária)",
         "ticker": "BBAS3", "qtd": 80, "corretora": "Nuinvest", "objetivo": "Renda passiva",
         "valor": 2400, "atual": 2680, "rent": 11.67,
         "dataEntrada": "2025-01-20", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Médio",
         "notas": "Estatal — DY > 10%"},
        {"nome": "BOVA11 — ETF Ibovespa", "tipo": "Ações", "subtipo": "ETF Nacional",
         "ticker": "BOVA11", "qtd": 50, "corretora": "Clear", "objetivo": "Diversificação",
         "valor": 5500, "atual": 6125, "rent": 11.36,
         "dataEntrada": "2024-09-01", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Médio",
         "notas": "Replica o Ibovespa — diversificação automática"},

        # ─── FIIs (4 ativos pagadores de dividendos) ────────────────
        {"nome": "MXRF11 — Maxi Renda", "tipo": "FIIs", "subtipo": "FII de Papel",
         "ticker": "MXRF11", "qtd": 500, "corretora": "XP Investimentos", "objetivo": "Renda passiva",
         "valor": 4750, "atual": 4965, "rent": 4.53,
         "dataEntrada": "2024-05-15", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Médio",
         "notas": "DY histórico ~12% — distribui mensalmente",
         "aportes": [
             {"tipo":"aporte","valor":4750,"qtd":500,"preco":9.50,"data":"2024-05-15","ts":1715731200000}
         ]},
        {"nome": "KNCR11 — Kinea Crédito", "tipo": "FIIs", "subtipo": "FII de Papel",
         "ticker": "KNCR11", "qtd": 30, "corretora": "Itaú", "objetivo": "Renda passiva",
         "valor": 3000, "atual": 3186, "rent": 6.20,
         "dataEntrada": "2024-08-10", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Baixo",
         "notas": "FII high grade — IPCA+"},
        {"nome": "HGLG11 — CSHG Logística", "tipo": "FIIs", "subtipo": "FII de Tijolo",
         "ticker": "HGLG11", "qtd": 25, "corretora": "BTG Pactual", "objetivo": "Renda passiva",
         "valor": 4000, "atual": 4275, "rent": 6.88,
         "dataEntrada": "2024-03-20", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Médio",
         "notas": "Galpões logísticos — Vacância baixa"},
        {"nome": "BCFF11 — BTG Fundo de Fundos", "tipo": "FIIs", "subtipo": "FoF (Fundo de Fundos)",
         "ticker": "BCFF11", "qtd": 200, "corretora": "BTG Pactual", "objetivo": "Renda passiva",
         "valor": 1500, "atual": 1612, "rent": 7.47,
         "dataEntrada": "2025-02-01", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Médio",
         "notas": "Diversificação em vários FIIs"},

        # ─── CRIPTO (3 ativos com tickers brapi) ────────────────────
        {"nome": "Bitcoin", "tipo": "Cripto", "subtipo": "Bitcoin (BTC)",
         "ticker": "BTC-USD", "qtd": 0.05, "corretora": "Binance", "objetivo": "Especulação",
         "valor": 12000, "atual": 16500, "rent": 37.50,
         "dataEntrada": "2024-02-10", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Muito Alto",
         "notas": "DCA mensal — não mais que 5% da carteira",
         "aportes": [
             {"tipo":"aporte","valor":6000,"qtd":0.025,"preco":240000,"data":"2024-02-10","ts":1707523200000},
             {"tipo":"aporte","valor":6000,"qtd":0.025,"preco":240000,"data":"2024-08-20","ts":1724112000000}
         ]},
        {"nome": "Ethereum", "tipo": "Cripto", "subtipo": "Ethereum (ETH)",
         "ticker": "ETH-USD", "qtd": 1.5, "corretora": "Binance", "objetivo": "Longo prazo",
         "valor": 9000, "atual": 11250, "rent": 25.00,
         "dataEntrada": "2024-05-15", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Muito Alto",
         "notas": "Smart contracts — exposição ao DeFi"},
        {"nome": "USDT — Stablecoin", "tipo": "Cripto", "subtipo": "Stablecoin (USDT/USDC)",
         "ticker": "USDT-USD", "qtd": 1000, "corretora": "Mercado Bitcoin", "objetivo": "Curto prazo",
         "valor": 5000, "atual": 5050, "rent": 1.00,
         "dataEntrada": "2025-03-01", "dataVenc": "",
         "indexador": "USD", "liquidez": "Diária (D+0)", "risco": "Médio",
         "notas": "Hedge cambial via stablecoin"},

        # ─── INTERNACIONAL (BDRs, ETFs internacionais) ──────────────
        {"nome": "IVVB11 — ETF S&P 500", "tipo": "Internacional", "subtipo": "ETF Internacional",
         "ticker": "IVVB11", "qtd": 30, "corretora": "Clear", "objetivo": "Diversificação",
         "valor": 9000, "atual": 11340, "rent": 26.00,
         "dataEntrada": "2024-01-15", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Médio",
         "notas": "Exposição ao S&P 500 em reais"},
        {"nome": "AAPL34 — Apple BDR", "tipo": "Internacional", "subtipo": "BDR",
         "ticker": "AAPL34", "qtd": 40, "corretora": "Avenue", "objetivo": "Longo prazo",
         "valor": 4000, "atual": 5040, "rent": 26.00,
         "dataEntrada": "2024-06-01", "dataVenc": "",
         "indexador": "", "liquidez": "Diária (D+0)", "risco": "Médio",
         "notas": "Apple — uma das maiores empresas do mundo"},

        # ─── PREVIDÊNCIA ────────────────────────────────────────────
        {"nome": "PGBL XP Premium", "tipo": "Previdência", "subtipo": "PGBL",
         "ticker": "", "qtd": 0, "corretora": "XP Investimentos", "objetivo": "Aposentadoria",
         "valor": 24000, "atual": 26880, "rent": 12.00,
         "dataEntrada": "2023-01-15", "dataVenc": "",
         "indexador": "", "liquidez": "D+30", "risco": "Médio",
         "notas": "Dedutível IR — R$ 1.000/mês há 24 meses"},
        {"nome": "VGBL Bradesco Vida", "tipo": "Previdência", "subtipo": "VGBL",
         "ticker": "", "qtd": 0, "corretora": "Bradesco Seguros", "objetivo": "Aposentadoria",
         "valor": 18000, "atual": 19440, "rent": 8.00,
         "dataEntrada": "2024-03-01", "dataVenc": "",
         "indexador": "", "liquidez": "D+30", "risco": "Baixo",
         "notas": "Tributação regressiva — aporte mensal"},

        # ─── POUPANÇA ───────────────────────────────────────────────
        {"nome": "Poupança Caixa", "tipo": "Poupança", "subtipo": "Poupança",
         "ticker": "", "qtd": 0, "corretora": "Caixa Econômica", "objetivo": "Curto prazo",
         "valor": 8000, "atual": 8160, "rent": 2.00,
         "dataEntrada": "2025-01-01", "dataVenc": "",
         "indexador": "TR + 0.5% a.m.", "liquidez": "Diária (D+0)", "risco": "Baixo",
         "notas": "Reserva imediata — baixo rendimento"},

        # ─── CONSÓRCIOS (4 tipos diferentes — INTEGRADOS COM FIXAS) ──
        # Imóvel — apartamento, R$ 300k, 180 parcelas (15 anos)
        {"nome": "Apto Vila Madalena", "tipo": "Consórcio", "subtipo": "Consórcio de Imóvel",
         "ticker": "", "qtd": 0, "corretora": "", "administradora": "Embracon",
         "objetivo": "Imóvel próprio",
         "cartaCredito": 300000, "parcelaValor": 1850, "parcelasTotal": 180,
         "parcelasPagas": 38, "diaVenc": 10, "criarFixa": True,
         "valor": 70300, "atual": 70300, "rent": 0,
         "dataEntrada": "2023-01-10", "dataVenc": "2038-01-10",
         "indexador": "", "liquidez": "No vencimento", "risco": "Médio",
         "notas": "Aguardando contemplação para usar como entrada"},

        # Veículo — Honda HR-V, R$ 130k, 60 parcelas
        {"nome": "Honda HR-V 2027", "tipo": "Consórcio", "subtipo": "Consórcio de Veículo",
         "ticker": "", "qtd": 0, "corretora": "", "administradora": "Porto Consórcios",
         "objetivo": "Veículo",
         "cartaCredito": 130000, "parcelaValor": 1280, "parcelasTotal": 60,
         "parcelasPagas": 22, "diaVenc": 15, "criarFixa": True,
         "valor": 28160, "atual": 28160, "rent": 0,
         "dataEntrada": "2024-01-15", "dataVenc": "2029-01-15",
         "indexador": "", "liquidez": "No vencimento", "risco": "Médio",
         "notas": "Trocar o atual por um SUV familiar"},

        # Serviço — viagem família, R$ 25k, 24 parcelas
        {"nome": "Viagem Disney Família", "tipo": "Consórcio", "subtipo": "Consórcio de Serviço",
         "ticker": "", "qtd": 0, "corretora": "", "administradora": "CNP Consórcios",
         "objetivo": "Viagem",
         "cartaCredito": 25000, "parcelaValor": 1100, "parcelasTotal": 24,
         "parcelasPagas": 8, "diaVenc": 20, "criarFixa": True,
         "valor": 8800, "atual": 8800, "rent": 0,
         "dataEntrada": "2025-09-20", "dataVenc": "2027-09-20",
         "indexador": "", "liquidez": "No vencimento", "risco": "Baixo",
         "notas": "Viagem de 15 dias planejada para julho de 2027"},

        # Eletrodoméstico — móveis e eletros para nova casa, R$ 18k, 36 parcelas
        {"nome": "Móveis Cozinha Planejada", "tipo": "Consórcio", "subtipo": "Consórcio de Eletrodoméstico",
         "ticker": "", "qtd": 0, "corretora": "", "administradora": "Magazine Luiza",
         "objetivo": "Reforma",
         "cartaCredito": 18000, "parcelaValor": 580, "parcelasTotal": 36,
         "parcelasPagas": 14, "diaVenc": 5, "criarFixa": True,
         "valor": 8120, "atual": 8120, "rent": 0,
         "dataEntrada": "2025-02-05", "dataVenc": "2028-02-05",
         "indexador": "", "liquidez": "No vencimento", "risco": "Baixo",
         "notas": "Cozinha + lavanderia + sala de jantar"},
    ]

    # ── FIXAS — geradas automaticamente para os consórcios ──────────
    # As fixas seguem a estrutura do toggleFx + _sincronizarFixaConsorcio
    # Cada consórcio com criarFixa=true vira uma entry. Os indexes (consorcio_X)
    # batem com o índice do investimento na lista inv (começando em 0).
    fixas = []
    for idx, v in enumerate(inv):
        if v.get("tipo") == "Consórcio" and v.get("criarFixa"):
            cons_id = f"consorcio_{idx}"
            fixas.append({
                "desc":       f"Consórcio · {v['nome']}",
                "valor":      v["parcelaValor"],
                "cat":        "Investimentos",
                "metodo":     "Boleto",
                "cartao":     "",
                "venc":       str(v["diaVenc"]),
                "status":     "A pagar",
                "prioridade": "Alta",
                "obs":        f"{v.get('administradora','')} · {v['parcelasPagas']}/{v['parcelasTotal']} parcelas",
                "origem":     "consorcio",
                "consorcioId": cons_id,
            })

    # Adiciona algumas despesas fixas comuns pra deixar a vida realista
    fixas.extend([
        {"desc": "Aluguel apartamento",      "valor": 2200, "cat": "Moradia",     "metodo": "Pix",
         "cartao": "", "venc": "5",  "status": "Pago",    "prioridade": "Alta",  "obs": ""},
        {"desc": "Plano de Saúde Bradesco",   "valor":  580, "cat": "Saúde",       "metodo": "Débito automático",
         "cartao": "", "venc": "12", "status": "Pago",    "prioridade": "Alta",  "obs": "Titular + 1 dependente"},
        {"desc": "Internet Vivo Fibra",       "valor":  120, "cat": "Contas",      "metodo": "Débito automático",
         "cartao": "", "venc": "20", "status": "A pagar", "prioridade": "",      "obs": ""},
        {"desc": "Energia Elétrica",          "valor":  280, "cat": "Contas",      "metodo": "Boleto",
         "cartao": "", "venc": "15", "status": "A pagar", "prioridade": "",      "obs": ""},
        {"desc": "Netflix + Spotify + Prime", "valor":   95, "cat": "Assinaturas", "metodo": "Cartão crédito",
         "cartao": "", "venc": "8",  "status": "Pago",    "prioridade": "",      "obs": ""},
    ])

    # ── Cartões mínimos pra dashboard ficar bonito ──────────────────
    cartoes = [
        {"nome": "Nubank", "bandeira": "Mastercard", "banco": "Nubank",
         "limite": 8000, "fech": 15, "venc": 22, "cor": "#8B5CF6", "final": "4242", "debitoAuto": False},
        {"nome": "Itaú Personnalité", "bandeira": "Visa", "banco": "Itaú",
         "limite": 15000, "fech": 10, "venc": 17, "cor": "#FF6B00", "final": "1111", "debitoAuto": False},
    ]

    # ── Algumas transações pra dar vida ao dashboard ────────────────
    def tx(data, desc, valor, cat, metodo="Pix", cartao="", parcelas=1, parc_at=1):
        tipo = "Receita" if valor > 0 else "Gasto"
        d, m, y = data.split("/")
        meses = ["jan.", "fev.", "mar.", "abr.", "mai.", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."]
        return {
            "data": data, "hora": "00:00", "descricao": desc,
            "categoria": cat, "valor": valor, "metodo": metodo,
            "cartao": cartao, "parcelas": parcelas, "parcela_atual": parc_at,
            "tipo": tipo, "localizacao": "",
            "mes_ano": f"{meses[int(m)-1]}/{y}",
        }

    # IMPORTANTE: NÃO incluir transações de "Consórcio · X" aqui!
    # Os 4 consórcios já têm fixa correspondente (origem='consorcio'),
    # que aparece nos vencimentos e é contabilizada em calcularMes().
    # Adicionar TX duplicaria os valores no dashboard e em vencimentos.
    txs = [
        # Maio 2026 (mês corrente — coincide com user's currentDate)
        tx("01/05/2026", "Salário CLT",                  15000, "Salário", "Pix"),
        tx("05/05/2026", "Aluguel apartamento",          -2200, "Moradia", "Pix"),
        tx("08/05/2026", "Netflix + Spotify + Prime",      -95, "Assinaturas", "Cartão crédito", "Nubank"),
        tx("12/05/2026", "Plano de Saúde Bradesco",       -580, "Saúde", "Débito automático"),
        tx("15/05/2026", "Energia Elétrica CEMIG",        -280, "Contas", "Boleto"),
        tx("18/05/2026", "Aporte mensal Tesouro",        -2000, "Investimentos", "Pix"),
        tx("18/05/2026", "Aporte mensal PGBL XP",        -1000, "Investimentos", "Débito automático"),
        tx("20/05/2026", "Internet Vivo Fibra",           -120, "Contas", "Débito automático"),
        tx("22/05/2026", "Aporte BTC mensal (DCA)",       -500, "Investimentos", "Pix"),
        tx("22/05/2026", "Aporte VALE3 (10 cotas)",       -858, "Investimentos", "Pix"),
        tx("25/05/2026", "Mercado",                       -480, "Alimentação", "Cartão crédito", "Itaú Personnalité"),
        tx("28/05/2026", "Dividendos MXRF11",               55, "Dividendos", "Pix"),
        tx("28/05/2026", "Dividendos KNCR11",               42, "Dividendos", "Pix"),
        tx("28/05/2026", "Dividendos HGLG11",               58, "Dividendos", "Pix"),

        # Abril 2026
        tx("01/04/2026", "Salário CLT",                  15000, "Salário", "Pix"),
        tx("05/04/2026", "Aluguel apartamento",          -2200, "Moradia", "Pix"),
        tx("18/04/2026", "Aporte mensal Tesouro",        -2000, "Investimentos", "Pix"),
        tx("22/04/2026", "Aporte BTC mensal (DCA)",       -500, "Investimentos", "Pix"),
        tx("28/04/2026", "Dividendos MXRF11",               55, "Dividendos", "Pix"),

        # Março 2026
        tx("01/03/2026", "Salário CLT",                  15000, "Salário", "Pix"),
        tx("05/03/2026", "Aluguel apartamento",          -2200, "Moradia", "Pix"),
        tx("18/03/2026", "Aporte mensal Tesouro",        -2000, "Investimentos", "Pix"),
        tx("28/03/2026", "Dividendos MXRF11",               53, "Dividendos", "Pix"),
    ]

    # ── Categorias customizadas extras ──────────────────────────────
    cats = [
        {"nome": "Investimentos", "tipo": "gasto",   "cor": "#06B6D4", "emoji": "📈", "ativo": True},
        {"nome": "Dividendos",    "tipo": "receita", "cor": "#10B981", "emoji": "💰", "ativo": True},
    ]

    return {
        "txs":        txs,
        "fixas":      fixas,
        "dividas":    [],
        "metas":      [],
        "inv":        inv,
        "cartoes":    cartoes,
        "limites":    {"Investimentos": 9000, "Alimentação": 1000, "Contas": 600, "Moradia": 2300},
        "cats":       cats,
        "recorrencias": [],
        "familia_membros": [],
        "faturas_pagas":   {},
        "vcal_pagos":      {},
        "recorr_geradas":  {},
        "recorr_ultimo_mes": "",
        "_seed_version":   SEED_VERSION,
    }


def _write_local_fallback(user: dict, data: dict) -> None:
    """Persiste localmente em users.json + userdata/<id>.json (fallback se Supabase off)."""
    try:
        users_path = os.path.join(_BASE_DIR, "users.json")
        users = []
        if os.path.exists(users_path):
            try:
                with open(users_path, "r", encoding="utf-8") as f:
                    users = json.load(f)
            except Exception:
                users = []
        if not any(u.get("email") == user["email"] for u in users):
            users.append(user)
            with open(users_path, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Seed (local fallback users.json): {e}")
    try:
        ud_dir = os.path.join(_BASE_DIR, "userdata")
        os.makedirs(ud_dir, exist_ok=True)
        ud_path = os.path.join(ud_dir, f"{TEST_ID}.json")
        if not os.path.exists(ud_path):
            with open(ud_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Seed (local fallback userdata): {e}")


def _upsert_userdata(uid: str, mock_data: dict) -> bool:
    from datetime import datetime
    dt_iso = datetime.utcnow().isoformat() + "Z"
    payload = {"user_id": uid, "data": mock_data, "updated_at": dt_iso}
    h = {**_sb_headers(), "Prefer": "resolution=merge-duplicates"}
    r = httpx.post(f"{_SB_URL}/rest/v1/sf_userdata", headers=h, json=payload, timeout=15)
    if r.status_code in (200, 201):
        logger.info(f"✅ Seed invest: {len(mock_data['inv'])} ativos salvos para {uid}.")
        return True
    rp = httpx.patch(
        f"{_SB_URL}/rest/v1/sf_userdata?user_id=eq.{uid}",
        headers=_sb_headers(), json={"data": mock_data, "updated_at": dt_iso}, timeout=15
    )
    if rp.status_code in (200, 204):
        logger.info(f"✅ Seed invest (PATCH): atualizado para {uid}.")
        return True
    logger.warning(f"Seed invest: falha POST={r.status_code} PATCH={rp.status_code}: {rp.text[:200]}")
    return False


def _run_seed() -> None:
    pwd_hash = _sha256(TEST_PASSWORD)
    new_user = {
        "id":         TEST_ID,
        "name":       TEST_NAME,
        "email":      TEST_EMAIL,
        "password":   pwd_hash,
        "avatar":     "💎",
        "color":      "#06B6D4",
        "created_at": "2026-01-01T00:00:00Z",
    }
    mock_data = _build_mock_data()

    if not (_SB_URL and _SB_KEY):
        logger.info("Seed invest: Supabase não configurado — usando fallback local.")
        _write_local_fallback(new_user, mock_data)
        return

    try:
        # 1. Verificar se usuário já existe
        resp = httpx.get(
            f"{_SB_URL}/rest/v1/sf_users?email=eq.{TEST_EMAIL}&select=id",
            headers=_sb_headers(), timeout=10
        )
        uid = None
        if resp.status_code == 200 and resp.json():
            uid = resp.json()[0]["id"]
            # GUARD CRÍTICO: só prosseguir se o ID bater com TEST_ID, OU se o user
            # nunca teve dados (linha sf_userdata vazia). Sem isso, se um usuário
            # real registrar com investimento01@gmail.com, perderia os dados dele.
            if uid != TEST_ID:
                logger.warning(f"⚠️  Seed invest ABORTADO: email {TEST_EMAIL} pertence a "
                               f"user real (id={uid}, esperado={TEST_ID}). Não sobrescreve.")
                return
            logger.info(f"Seed invest: {TEST_EMAIL} já existe (id={uid}).")
        else:
            h = {**_sb_headers(), "Prefer": "resolution=merge-duplicates"}
            r2 = httpx.post(f"{_SB_URL}/rest/v1/sf_users", headers=h, json=new_user, timeout=10)
            if r2.status_code in (200, 201):
                uid = TEST_ID
                logger.info(f"✅ Seed invest: {TEST_EMAIL} criado ({uid}).")
            else:
                logger.warning(f"Seed invest: erro ao criar {r2.status_code}: {r2.text[:200]}")
                _write_local_fallback(new_user, mock_data)
                return

        # 2. Já tem dados NA VERSÃO ATUAL do seed? Pula.
        # Se a versão estiver desatualizada, sobrescreve APENAS se confirmar que
        # é o user de demonstração (ID == TEST_ID, já validado acima).
        resp2 = httpx.get(
            f"{_SB_URL}/rest/v1/sf_userdata?user_id=eq.{uid}&select=data",
            headers=_sb_headers(), timeout=10
        )
        if resp2.status_code == 200 and resp2.json():
            existing = resp2.json()[0].get("data", {}) or {}
            inv_count = len(existing.get("inv") or [])
            existing_ver = existing.get("_seed_version", 0)
            if inv_count >= 5 and existing_ver >= SEED_VERSION:
                logger.info(f"Seed invest: {TEST_EMAIL} já tem v{existing_ver} (>= {SEED_VERSION}), pulando.")
                _write_local_fallback(new_user, mock_data)
                return
            elif existing_ver < SEED_VERSION:
                # GUARD: só faz re-seed se o user é claramente o de demonstração.
                # Se houver dados sem _seed_version mas o ID bater com TEST_ID,
                # significa que é da v1 do seed (antes da version key existir) — OK sobrescrever.
                logger.info(f"Seed invest: {TEST_EMAIL} v{existing_ver} → v{SEED_VERSION} (re-seed forçado).")

        _upsert_userdata(uid, mock_data)
        _write_local_fallback(new_user, mock_data)
    except Exception as e:
        logger.error(f"❌ Seed invest: erro inesperado — {e}")
        try:
            _write_local_fallback(new_user, mock_data)
        except Exception:
            pass


def run_seed_background() -> None:
    """Executa em thread de background."""
    t = threading.Thread(target=_run_seed, daemon=True)
    t.start()
