"""
Seed de perfil de demonstração — Start Finance
Cria o usuário teste01@gmail.com com dados mockados em TODAS as abas.
Roda automaticamente no startup do servidor (idempotente).
"""
import os, json, hashlib, time, logging, threading
import httpx

logger = logging.getLogger(__name__)

_SB_URL = os.environ.get("SUPABASE_URL", "")
_SB_KEY = os.environ.get("SUPABASE_KEY", "")

TEST_EMAIL    = "teste01@gmail.com"
TEST_PASSWORD = "1234567"
TEST_NAME     = "Lucas Teste"
TEST_ID       = "u_demo_teste01"

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
    """Retorna o payload completo de dados financeiros mockados."""

    # ── Cartões ──────────────────────────────────────────────────────
    cartoes = [
        {"nome": "Nubank",         "bandeira": "Mastercard", "banco": "Nubank",
         "limite": 5000, "fech": 15, "venc": 22, "cor": "#8B5CF6", "final": "4242", "debitoAuto": False},
        {"nome": "Inter Platinum", "bandeira": "Mastercard", "banco": "Inter",
         "limite": 8000, "fech": 10, "venc": 17, "cor": "#FF6B00", "final": "1234", "debitoAuto": False},
    ]

    # ── Despesas Fixas ───────────────────────────────────────────────
    fixas = [
        {"desc": "Aluguel apartamento",       "valor": 2200, "cat": "Moradia",     "venc": "5",  "status": "Pago",     "obs": "Transferência bancária"},
        {"desc": "Condomínio",                "valor":  350, "cat": "Moradia",     "venc": "10", "status": "Pago",     "obs": ""},
        {"desc": "Internet Vivo Fibra 300Mb", "valor":  120, "cat": "Contas",      "venc": "20", "status": "A pagar",  "obs": ""},
        {"desc": "Energia Elétrica CEMIG",    "valor":  185, "cat": "Contas",      "venc": "15", "status": "A pagar",  "obs": ""},
        {"desc": "Netflix + Spotify",         "valor":   75, "cat": "Assinaturas", "venc": "28", "status": "Pago",     "obs": "Débito automático"},
        {"desc": "Academia SmartFit",         "valor":   89, "cat": "Saúde",       "venc": "1",  "status": "Pago",     "obs": "Plano Black"},
        {"desc": "Seguro Auto Bradesco",      "valor":  210, "cat": "Veículo",     "venc": "8",  "status": "A pagar",  "obs": "Vistoria em dezembro"},
        {"desc": "Plano de Saúde Amil",       "valor":  480, "cat": "Saúde",       "venc": "12", "status": "Pago",     "obs": "Titular + 1 dependente"},
    ]

    # ── Dívidas ──────────────────────────────────────────────────────
    dividas = [
        {"nome": "Financiamento Honda Civic", "credor": "Banco Bradesco",
         "total": 28800, "parcelas": 48, "mensal": 680, "pagas": 12,
         "venc": "10", "tabela": "Price", "taxa": 1.49, "indexador": "Pré-fixado"},
        {"nome": "Curso Full Stack Alura",    "credor": "Alura",
         "total": 1800, "parcelas": 6, "mensal": 300, "pagas": 3,
         "venc": "20", "tabela": "", "taxa": 0, "indexador": ""},
        {"nome": "Empréstimo reformas",       "credor": "Banco Santander",
         "total": 12000, "parcelas": 24, "mensal": 570, "pagas": 4,
         "venc": "5", "tabela": "SAC", "taxa": 2.20, "indexador": "IPCA"},
    ]

    # ── Metas ────────────────────────────────────────────────────────
    metas = [
        {"id": "mt_001", "tipo": "economia",  "nome": "Viagem Europa",
         "emoji": "✈️",  "total": 15000, "orcamento": 0,    "atual": 3200, "mensal": 800,  "inicio": "", "desc": "Meta para viagem de 15 dias em 2027"},
        {"id": "mt_002", "tipo": "economia",  "nome": "Fundo de Emergência",
         "emoji": "🛡️", "total": 18000, "orcamento": 0,    "atual": 8500, "mensal": 1000, "inicio": "", "desc": "6 meses de despesas cobertas"},
        {"id": "mt_003", "tipo": "economia",  "nome": "MacBook Pro M4",
         "emoji": "💻",  "total": 12000, "orcamento": 0,    "atual": 4800, "mensal": 600,  "inicio": "", "desc": "Para trabalho e projetos pessoais"},
        {"id": "mt_004", "tipo": "orcamento", "nome": "Reforma da Cozinha",
         "emoji": "🏗️", "total": 8000,  "orcamento": 8000, "atual": 0,    "mensal": 0,    "inicio": "2026-06-01", "desc": "Reforma completa — armários e bancada"},
        {"id": "mt_005", "tipo": "economia",  "nome": "Novo Carro 2028",
         "emoji": "🚗",  "total": 45000, "orcamento": 0,    "atual": 5400, "mensal": 1500, "inicio": "", "desc": "Trocar o Civic por zero km"},
    ]

    # ── Investimentos ────────────────────────────────────────────────
    inv = [
        {"nome": "Tesouro Selic 2029",     "tipo": "Renda Fixa",     "subtipo": "Título público",
         "ticker": "TESOURO", "corretora": "XP Investimentos", "objetivo": "Reserva de emergência",
         "valor": 8000, "atual": 8430, "rent": 5.38,
         "dataEntrada": "2025-01-15", "dataVenc": "2029-03-01",
         "indexador": "Selic", "liquidez": "Diária", "risco": "Baixo", "notas": "Resgate em 2029"},
        {"nome": "CDB Nubank 120% CDI",    "tipo": "Renda Fixa",     "subtipo": "CDB",
         "ticker": "", "corretora": "Nubank", "objetivo": "Reserva / liquidez",
         "valor": 5000, "atual": 5180, "rent": 3.60,
         "dataEntrada": "2025-06-01", "dataVenc": "2026-12-01",
         "indexador": "CDI", "liquidez": "D+1", "risco": "Baixo", "notas": ""},
        {"nome": "Petrobras PETR4",        "tipo": "Renda Variável", "subtipo": "Ação",
         "ticker": "PETR4", "corretora": "XP Investimentos", "objetivo": "Longo prazo / dividendos",
         "valor": 2500, "atual": 2750, "rent": 10.0,
         "dataEntrada": "2025-03-20", "dataVenc": "",
         "indexador": "", "liquidez": "D+2", "risco": "Alto", "notas": "DY acima de 12% ao ano"},
        {"nome": "HGLG11 — FII Logística", "tipo": "Renda Variável", "subtipo": "FII",
         "ticker": "HGLG11", "corretora": "XP Investimentos", "objetivo": "Renda mensal",
         "valor": 3000, "atual": 3120, "rent": 4.0,
         "dataEntrada": "2025-05-10", "dataVenc": "",
         "indexador": "", "liquidez": "D+2", "risco": "Médio", "notas": "Distribuição mensal de proventos"},
        {"nome": "Bitcoin (BTC)",          "tipo": "Criptomoeda",    "subtipo": "Crypto",
         "ticker": "BTC", "corretora": "Binance", "objetivo": "Especulativo / longo prazo",
         "valor": 1000, "atual": 1380, "rent": 38.0,
         "dataEntrada": "2025-10-01", "dataVenc": "",
         "indexador": "", "liquidez": "Imediata", "risco": "Muito alto", "notas": "Não mais que 5% da carteira"},
        {"nome": "LCI Itaú 96% CDI",       "tipo": "Renda Fixa",     "subtipo": "LCI",
         "ticker": "", "corretora": "Itaú", "objetivo": "Isenção IR / liquidez média",
         "valor": 4500, "atual": 4590, "rent": 2.0,
         "dataEntrada": "2025-09-01", "dataVenc": "2027-03-01",
         "indexador": "CDI", "liquidez": "No vencimento", "risco": "Baixo", "notas": "Isento de IR"},
    ]

    # ── Recorrências ─────────────────────────────────────────────────
    recorrencias = [
        {"id": 1001, "nome": "Salário Empresa",          "tipo": "Receita", "categoria": "Salário",      "valor": 8500, "dia": 5,  "metodo": "Pix",                "ativo": True},
        {"id": 1002, "nome": "Freelance Mensal",         "tipo": "Receita", "categoria": "Freelance",    "valor": 2000, "dia": 15, "metodo": "Pix",                "ativo": True},
        {"id": 1003, "nome": "Academia SmartFit",        "tipo": "Gasto",   "categoria": "Saúde",        "valor":   89, "dia": 1,  "metodo": "Débito automático",  "ativo": True},
        {"id": 1004, "nome": "Netflix + Spotify + Prime","tipo": "Gasto",   "categoria": "Assinaturas",  "valor":   85, "dia": 5,  "metodo": "Cartão crédito",     "ativo": True},
        {"id": 1005, "nome": "Contribuição previdência", "tipo": "Gasto",   "categoria": "Investimento", "valor":  500, "dia": 10, "metodo": "Débito automático",  "ativo": True},
        {"id": 1006, "nome": "Aluguel",                  "tipo": "Gasto",   "categoria": "Moradia",      "valor": 2200, "dia": 5,  "metodo": "Pix",                "ativo": True},
    ]

    # ── Categorias customizadas ──────────────────────────────────────
    cats = [
        {"nome": "Pets",          "tipo": "gasto",   "cor": "#84CC16", "emoji": "🐾", "ativo": True},
        {"nome": "Cursos Online", "tipo": "gasto",   "cor": "#F59E0B", "emoji": "📖", "ativo": True},
        {"nome": "Renda Extra",   "tipo": "receita", "cor": "#10B981", "emoji": "💡", "ativo": True},
    ]

    # ── Limites de orçamento ─────────────────────────────────────────
    limites = {
        "Alimentação": 1500,
        "Transporte":   500,
        "Lazer":        600,
        "Saúde":        400,
        "Vestuário":    300,
        "Contas":       700,
        "Assinaturas":  150,
        "Educação":     400,
        "Moradia":     2700,
    }

    # ── Transações ───────────────────────────────────────────────────
    # mes_ano usa o formato do frontend: MESES_PT[mês] + "/" + ano
    # MESES_PT = ["jan.","fev.","mar.","abr.","mai.","jun.","jul.","ago.","set.","out.","nov.","dez."]
    def tx(data, desc, valor, cat, metodo="Pix", cartao="", tipo=None, parcelas=1, parc_at=1, local=""):
        if tipo is None:
            tipo = "Receita" if valor > 0 else "Gasto"
        d, m, y = data.split("/")
        meses = ["jan.", "fev.", "mar.", "abr.", "mai.", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."]
        mes_ano = f"{meses[int(m)-1]}/{y}"
        return {
            "data": data, "hora": "00:00", "descricao": desc,
            "categoria": cat, "valor": valor, "metodo": metodo,
            "cartao": cartao, "parcelas": parcelas, "parcela_atual": parc_at,
            "tipo": tipo, "local": local, "mes_ano": mes_ano
        }

    txs_raw = [
        # ── Janeiro 2026 ─────────────────────────────────────────────
        tx("02/01/2026","Supermercado Pão de Açúcar",-312,"Alimentação","Cartão crédito","Inter Platinum"),
        tx("05/01/2026","Salário Empresa",8500,"Salário","Pix"),
        tx("05/01/2026","Aluguel apartamento",-2200,"Moradia","Pix"),
        tx("06/01/2026","Festa de Reveillon gastos",-420,"Lazer","Cartão crédito","Nubank"),
        tx("08/01/2026","Seguro Auto Bradesco",-210,"Veículo","Boleto"),
        tx("10/01/2026","Condomínio",-350,"Moradia","Boleto"),
        tx("10/01/2026","Parcela financiamento Honda",-680,"Veículo","Boleto"),
        tx("10/01/2026","Parcela curso Alura 1/6",-300,"Educação","Boleto", parcelas=6, parc_at=1),
        tx("12/01/2026","Plano de Saúde Amil",-480,"Saúde","Débito automático"),
        tx("14/01/2026","IPVA 2026 (Parcela 1 de 5)",-620,"Impostos","Boleto", parcelas=5, parc_at=1),
        tx("15/01/2026","Energia Elétrica CEMIG",-198,"Contas","Boleto"),
        tx("16/01/2026","iFood — Almoço no trabalho",-62.40,"Alimentação","Cartão crédito","Nubank"),
        tx("17/01/2026","Gasolina Posto Shell",-185,"Transporte","Cartão débito","Inter Platinum"),
        tx("18/01/2026","Farmácia vitaminas e suplementos",-125,"Saúde","Cartão crédito","Nubank"),
        tx("19/01/2026","Netflix + Spotify",-75,"Assinaturas","Cartão crédito","Nubank"),
        tx("19/01/2026","Freelance projeto web"  ,3000,"Freelance","Pix"),
        tx("20/01/2026","Internet Vivo Fibra",-120,"Contas","Débito automático"),
        tx("22/01/2026","Smartphone Samsung S25 (Parcela 1 de 12)",-350,"Tecnologia","Cartão crédito","Nubank", parcelas=12, parc_at=1),
        tx("24/01/2026","Almoço restaurante japonês",-95,"Alimentação","Cartão crédito","Nubank"),
        tx("26/01/2026","Uber corrida aeroporto",-35.80,"Transporte","Cartão crédito","Nubank"),
        tx("28/01/2026","Academia SmartFit",-89,"Saúde","Débito automático"),
        tx("30/01/2026","Depósito meta — Fundo Emergência",800,"Investimento","Pix"),

        # ── Fevereiro 2026 ───────────────────────────────────────────
        tx("01/02/2026","Academia SmartFit",-89,"Saúde","Débito automático"),
        tx("04/02/2026","Supermercado Extra",-265,"Alimentação","Cartão crédito","Inter Platinum"),
        tx("05/02/2026","Salário Empresa",8500,"Salário","Pix"),
        tx("05/02/2026","Aluguel apartamento",-2200,"Moradia","Pix"),
        tx("08/02/2026","Seguro Auto Bradesco",-210,"Veículo","Boleto"),
        tx("10/02/2026","Condomínio",-350,"Moradia","Boleto"),
        tx("10/02/2026","Parcela financiamento Honda",-680,"Veículo","Boleto"),
        tx("10/02/2026","Parcela curso Alura 2/6",-300,"Educação","Boleto", parcelas=6, parc_at=2),
        tx("10/02/2026","IPVA 2026 (Parcela 2 de 5)",-620,"Impostos","Boleto", parcelas=5, parc_at=2),
        tx("12/02/2026","Plano de Saúde Amil",-480,"Saúde","Débito automático"),
        tx("14/02/2026","Jantar Dia dos Namorados — restaurante",-285,"Alimentação","Cartão crédito","Nubank"),
        tx("14/02/2026","Flores e presente Dia dos Namorados",-150,"Presentes","Cartão crédito","Nubank"),
        tx("15/02/2026","Energia Elétrica CEMIG",-156,"Contas","Boleto"),
        tx("17/02/2026","Gasolina Posto Ipiranga",-172,"Transporte","Cartão débito","Inter Platinum"),
        tx("18/02/2026","iFood pedido noturno",-68.90,"Alimentação","Cartão crédito","Nubank"),
        tx("19/02/2026","Netflix + Spotify",-75,"Assinaturas","Cartão crédito","Nubank"),
        tx("20/02/2026","Internet Vivo Fibra",-120,"Contas","Débito automático"),
        tx("20/02/2026","Freelance design identidade visual",2500,"Freelance","Pix"),
        tx("22/02/2026","Smartphone Samsung S25 (Parcela 2 de 12)",-350,"Tecnologia","Cartão crédito","Nubank", parcelas=12, parc_at=2),
        tx("22/02/2026","Tênis Nike Air Max (Parcela 1 de 2)",-380,"Vestuário","Cartão crédito","Nubank", parcelas=2, parc_at=1),
        tx("24/02/2026","Carnaval — viagem + hospedagem",-650,"Lazer","Pix"),
        tx("26/02/2026","Whey Protein + creatina",-198,"Saúde","Cartão crédito","Nubank"),
        tx("28/02/2026","Livros técnicos — Clean Code e DDD",-124,"Educação","Cartão crédito","Nubank"),

        # ── Março 2026 ───────────────────────────────────────────────
        tx("01/03/2026","Academia SmartFit",-89,"Saúde","Débito automático"),
        tx("03/03/2026","Supermercado Pão de Açúcar",-287.40,"Alimentação","Cartão crédito","Inter Platinum"),
        tx("05/03/2026","Salário Empresa",8500,"Salário","Pix"),
        tx("05/03/2026","Aluguel apartamento",-2200,"Moradia","Pix"),
        tx("08/03/2026","Seguro Auto Bradesco",-210,"Veículo","Boleto"),
        tx("10/03/2026","Condomínio",-350,"Moradia","Boleto"),
        tx("10/03/2026","Parcela financiamento Honda",-680,"Veículo","Boleto"),
        tx("10/03/2026","Parcela curso Alura 3/6",-300,"Educação","Boleto", parcelas=6, parc_at=3),
        tx("10/03/2026","IPVA 2026 (Parcela 3 de 5)",-620,"Impostos","Boleto", parcelas=5, parc_at=3),
        tx("10/03/2026","Parcela empréstimo Santander",-570,"Moradia","Boleto"),
        tx("12/03/2026","Plano de Saúde Amil",-480,"Saúde","Débito automático"),
        tx("12/03/2026","Camisa polo Hugo Boss",-149,"Vestuário","Cartão crédito","Nubank"),
        tx("14/03/2026","Almoço restaurante brasileiro",-89.50,"Alimentação","Cartão crédito","Nubank"),
        tx("15/03/2026","Energia Elétrica CEMIG",-162,"Contas","Boleto"),
        tx("15/03/2026","Freelance site institucional",1500,"Freelance","Pix"),
        tx("16/03/2026","Uber viagem shopping",-42.10,"Transporte","Cartão crédito","Nubank"),
        tx("18/03/2026","Gasolina Posto Shell",-165,"Transporte","Cartão débito","Inter Platinum"),
        tx("19/03/2026","Netflix + Spotify",-75,"Assinaturas","Cartão crédito","Nubank"),
        tx("20/03/2026","Internet Vivo Fibra",-120,"Contas","Débito automático"),
        tx("20/03/2026","Farmácia drogaria",-67.30,"Saúde","Cartão débito","Inter Platinum"),
        tx("21/03/2026","Tênis Nike Air Max (Parcela 2 de 2)",-380,"Vestuário","Cartão crédito","Nubank", parcelas=2, parc_at=2),
        tx("22/03/2026","Show Coldplay — ingresso",-320,"Lazer","Pix"),
        tx("22/03/2026","Smartphone Samsung S25 (Parcela 3 de 12)",-350,"Tecnologia","Cartão crédito","Nubank", parcelas=12, parc_at=3),
        tx("24/03/2026","iFood pedido família",-78.90,"Alimentação","Cartão crédito","Nubank"),
        tx("25/03/2026","Curso JavaScript (Parcela 1 de 3)",-189,"Educação","Cartão crédito","Nubank", parcelas=3, parc_at=1),
        tx("28/03/2026","Aporte — Tesouro Selic",1000,"Investimento","Pix"),
        tx("30/03/2026","Café + Açaí — saída com amigos",-38.50,"Alimentação","Pix"),

        # ── Abril 2026 ───────────────────────────────────────────────
        tx("01/04/2026","Academia SmartFit",-89,"Saúde","Débito automático"),
        tx("02/04/2026","iFood almoço no trabalho",-58.90,"Alimentação","Cartão crédito","Nubank"),
        tx("03/04/2026","Supermercado Extra",-245.60,"Alimentação","Cartão crédito","Inter Platinum"),
        tx("05/04/2026","Salário Empresa",8500,"Salário","Pix"),
        tx("05/04/2026","Aluguel apartamento",-2200,"Moradia","Pix"),
        tx("07/04/2026","Uber corrida trabalho",-28.50,"Transporte","Cartão crédito","Nubank"),
        tx("08/04/2026","Seguro Auto Bradesco",-210,"Veículo","Boleto"),
        tx("09/04/2026","Farmácia Droga Raia",-89.90,"Saúde","Cartão débito","Inter Platinum"),
        tx("10/04/2026","Condomínio",-350,"Moradia","Boleto"),
        tx("10/04/2026","Parcela financiamento Honda",-680,"Veículo","Boleto"),
        tx("10/04/2026","IPVA 2026 (Parcela 4 de 5)",-620,"Impostos","Boleto", parcelas=5, parc_at=4),
        tx("10/04/2026","Parcela curso Alura 4/6",-300,"Educação","Boleto", parcelas=6, parc_at=4),
        tx("10/04/2026","Parcela empréstimo Santander",-570,"Moradia","Boleto"),
        tx("12/04/2026","Plano de Saúde Amil",-480,"Saúde","Débito automático"),
        tx("13/04/2026","Pizza Hut — jantar sexta",-124.80,"Alimentação","Cartão crédito","Nubank"),
        tx("14/04/2026","Livro Clean Architecture",-68,"Educação","Cartão crédito","Nubank"),
        tx("15/04/2026","Freelance consultoria UX",2000,"Freelance","Pix"),
        tx("15/04/2026","Energia Elétrica CEMIG",-185,"Contas","Boleto"),
        tx("17/04/2026","Gasolina Posto Ipiranga",-178,"Transporte","Cartão débito","Inter Platinum"),
        tx("18/04/2026","Shopping roupas novas (Parcela 1 de 3)",-389,"Vestuário","Cartão crédito","Nubank", parcelas=3, parc_at=1),
        tx("19/04/2026","Netflix + Spotify",-75,"Assinaturas","Cartão crédito","Nubank"),
        tx("20/04/2026","Internet Vivo Fibra",-120,"Contas","Débito automático"),
        tx("21/04/2026","Happy hour amigos",-98.40,"Lazer","Pix"),
        tx("22/04/2026","Cinema + pipoca — casal",-72,"Lazer","Cartão crédito","Nubank"),
        tx("22/04/2026","Smartphone Samsung S25 (Parcela 4 de 12)",-350,"Tecnologia","Cartão crédito","Nubank", parcelas=12, parc_at=4),
        tx("23/04/2026","Aporte meta — Viagem Europa",800,"Investimento","Pix"),
        tx("24/04/2026","Supermercado compras semana",-198.30,"Alimentação","Cartão crédito","Inter Platinum"),
    ]

    # Adiciona idx incremental
    txs = [{**t, "idx": i} for i, t in enumerate(txs_raw)]

    # ── Faturas pagas ────────────────────────────────────────────────
    faturas_pagas = {
        "Nubank_jan./2026":         True,
        "Nubank_fev./2026":         True,
        "Nubank_mar./2026":         True,
        "Inter Platinum_jan./2026": True,
        "Inter Platinum_fev./2026": True,
    }

    # ── Família ──────────────────────────────────────────────────────
    familia = [
        {"id": TEST_ID, "nome": TEST_NAME, "avatar": "🧑", "cor": "#3B6FF0"},
    ]

    return {
        "txs":           txs,
        "fixas":         fixas,
        "dividas":       dividas,
        "metas":         metas,
        "inv":           inv,
        "cartoes":       cartoes,
        "limites":       limites,
        "cats":          cats,
        "recorrencias":  recorrencias,
        "familia":       familia,
        "faturas_pagas": faturas_pagas,
        "vcal_pagos":    {},
    }


def _write_local_fallback(user: dict, data: dict) -> None:
    """Escreve nos arquivos locais — funciona mesmo sem Supabase."""
    # data/users.json
    try:
        users_path = os.path.join(_BASE_DIR, "data", "users.json")
        os.makedirs(os.path.dirname(users_path), exist_ok=True)
        users = []
        if os.path.exists(users_path):
            with open(users_path, "r", encoding="utf-8") as f:
                users = json.load(f)
        if not any(u["email"] == user["email"] for u in users):
            users.append(user)
            with open(users_path, "w", encoding="utf-8") as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Seed (local fallback users.json): {e}")

    # userdata/{user_id}.json
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
    """Insere ou substitui os dados financeiros — funciona mesmo se a linha já existir."""
    from datetime import datetime
    dt_iso = datetime.utcnow().isoformat() + "Z"
    payload = {"user_id": uid, "data": mock_data, "updated_at": dt_iso}
    h = {**_sb_headers(), "Prefer": "resolution=merge-duplicates"}
    r = httpx.post(f"{_SB_URL}/rest/v1/sf_userdata", headers=h, json=payload, timeout=15)
    if r.status_code in (200, 201):
        logger.info(f"✅ Seed: {len(mock_data['txs'])} txs salvas para user_id={uid}.")
        return True
    # Se POST falhou, tenta PATCH (linha pode existir com PK conflict sem merge)
    rp = httpx.patch(
        f"{_SB_URL}/rest/v1/sf_userdata?user_id=eq.{uid}",
        headers=_sb_headers(), json={"data": mock_data, "updated_at": dt_iso}, timeout=15
    )
    if rp.status_code in (200, 204):
        logger.info(f"✅ Seed (PATCH): dados mockados atualizados para user_id={uid}.")
        return True
    logger.warning(f"Seed: falha ao salvar dados POST={r.status_code} PATCH={rp.status_code}: {rp.text[:200]}")
    return False


def _run_seed() -> None:
    pwd_hash = _sha256(TEST_PASSWORD)
    new_user = {
        "id":         TEST_ID,
        "name":       TEST_NAME,
        "email":      TEST_EMAIL,
        "password":   pwd_hash,
        "avatar":     "🧪",
        "color":      "#10B981",
        "created_at": "2026-01-01T00:00:00Z",
    }
    mock_data = _build_mock_data()

    if not (_SB_URL and _SB_KEY):
        logger.info("Seed: Supabase não configurado — usando fallback local.")
        _write_local_fallback(new_user, mock_data)
        return

    try:
        # 1. Verificar se usuário já existe em Supabase
        resp = httpx.get(
            f"{_SB_URL}/rest/v1/sf_users?email=eq.{TEST_EMAIL}&select=id",
            headers=_sb_headers(), timeout=10
        )
        uid = None
        if resp.status_code == 200 and resp.json():
            uid = resp.json()[0]["id"]
            # GUARD CRÍTICO: só prosseguir se o ID bater com TEST_ID. Se um usuário
            # real registrou com este email, perderia os dados dele se sobrescrevêssemos.
            if uid != TEST_ID:
                logger.warning(f"⚠️  Seed ABORTADO: email {TEST_EMAIL} pertence a "
                               f"user real (id={uid}, esperado={TEST_ID}). Não sobrescreve.")
                return
            logger.info(f"Seed: usuário {TEST_EMAIL} já existe em Supabase (id={uid}).")
        else:
            # Cria o usuário
            h = {**_sb_headers(), "Prefer": "resolution=merge-duplicates"}
            r2 = httpx.post(f"{_SB_URL}/rest/v1/sf_users", headers=h, json=new_user, timeout=10)
            if r2.status_code in (200, 201):
                uid = TEST_ID
                logger.info(f"✅ Seed: usuário {TEST_EMAIL} criado ({uid}).")
            else:
                logger.warning(f"Seed: erro ao criar usuário {r2.status_code}: {r2.text[:200]}")
                _write_local_fallback(new_user, mock_data)
                return

        # 2. Verificar se os dados financeiros têm conteúdo real (não apenas linha vazia)
        resp2 = httpx.get(
            f"{_SB_URL}/rest/v1/sf_userdata?user_id=eq.{uid}&select=data",
            headers=_sb_headers(), timeout=10
        )
        has_real_data = False
        if resp2.status_code == 200 and resp2.json():
            existing_data = resp2.json()[0].get("data", {}) or {}
            txs_count = len(existing_data.get("txs") or [])
            has_real_data = txs_count > 5  # mais de 5 txs = dados reais, não vazio
            if has_real_data:
                logger.info(f"Seed: {TEST_EMAIL} já tem {txs_count} transações, pulando.")
                _write_local_fallback(new_user, mock_data)
                return

        # 3. Salvar dados mockados (insert ou overwrite)
        _upsert_userdata(uid, mock_data)
        _write_local_fallback(new_user, mock_data)

    except Exception as e:
        logger.error(f"❌ Seed: erro inesperado — {e}")
        try:
            _write_local_fallback(new_user, mock_data)
        except Exception:
            pass


def run_seed_background() -> None:
    """Executa o seed em thread de background para não atrasar o startup."""
    t = threading.Thread(target=_run_seed, daemon=True)
    t.start()
