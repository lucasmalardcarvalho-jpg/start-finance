"""
START FINANCE — Bot v7.0
Bot Telegram completo: todas as funções do sistema web via API local.
"""

import os
import json
import logging
import tempfile
import time
from datetime import datetime

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, MessageHandler, CallbackQueryHandler,
    CommandHandler, filters, ContextTypes
)

from ai_extractor import AIExtractor
import web_server

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
extractor = AIExtractor()

MESES_PT = ['jan.','fev.','mar.','abr.','mai.','jun.',
            'jul.','ago.','set.','out.','nov.','dez.']

# ── Finance API Client ────────────────────────────────────────────────
class FinanceAPI:
    """Autentica e comunica com a API Flask local."""

    def __init__(self):
        self._token: str | None = None
        self._token_exp: float = 0.0

    def _base(self) -> str:
        port = os.environ.get("PORT", "8080")
        return f"http://localhost:{port}"

    def _ensure_token(self) -> bool:
        if self._token and time.time() < self._token_exp - 60:
            return True
        email    = os.environ.get("FINANCE_EMAIL", "")
        password = os.environ.get("FINANCE_PASSWORD", "")
        if not email or not password:
            logger.error("FINANCE_EMAIL ou FINANCE_PASSWORD não configurados!")
            return False
        try:
            r = httpx.post(f"{self._base()}/api/login",
                           json={"email": email, "password": password}, timeout=10)
            if r.status_code == 200:
                self._token     = r.json()["token"]
                self._token_exp = time.time() + 7 * 86400
                return True
            logger.error(f"Login API falhou: {r.status_code} {r.text[:200]}")
        except Exception as e:
            logger.error(f"Erro login API: {e}")
        return False

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    def get_data(self) -> dict | None:
        if not self._ensure_token():
            return None
        try:
            r = httpx.get(f"{self._base()}/api/userdata", headers=self._headers(), timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception as e:
            logger.error(f"Erro get_data: {e}")
        return None

    def save_data(self, data: dict) -> bool:
        if not self._ensure_token():
            return False
        try:
            r = httpx.post(f"{self._base()}/api/userdata",
                           headers=self._headers(), json=data, timeout=15)
            return r.status_code == 200 and r.json().get("ok", False)
        except Exception as e:
            logger.error(f"Erro save_data: {e}")
        return False


api = FinanceAPI()

# ── Helpers ───────────────────────────────────────────────────────────
def fmt_brl(v: float) -> str:
    return f"R$ {abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def hoje() -> str:
    return datetime.now().strftime("%d/%m/%Y")

def mes_ano_atual() -> str:
    now = datetime.now()
    return f"{MESES_PT[now.month - 1]}/{now.year}"

def mes_ano_de_data(data_str: str) -> str:
    """Converte 'DD/MM/YYYY' → 'abr./2026'."""
    try:
        partes = data_str.split("/")
        mes = int(partes[1])
        ano = partes[2]
        return f"{MESES_PT[mes - 1]}/{ano}"
    except Exception:
        return mes_ano_atual()

def make_id() -> str:
    return f"bot_{int(time.time() * 1000)}_{os.urandom(3).hex()}"

def parse_valor(s: str) -> float | None:
    s = s.replace("R$","").replace("r$","").replace(" ","").replace(",",".").strip()
    try:
        v = float(s)
        return abs(v) if v != 0 else None
    except Exception:
        return None

def parse_dia(s: str) -> int | None:
    try:
        d = int(s.strip())
        return d if 0 <= d <= 31 else None
    except Exception:
        return None

# ── Teclados ──────────────────────────────────────────────────────────
def menu_principal_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Resumo do Mês",    callback_data="menu_resumo")],
        [InlineKeyboardButton("💸 Transações",       callback_data="menu_tx"),
         InlineKeyboardButton("📌 Fixas",            callback_data="menu_fixas")],
        [InlineKeyboardButton("💳 Dívidas",          callback_data="menu_dividas"),
         InlineKeyboardButton("🎯 Metas",            callback_data="menu_metas")],
        [InlineKeyboardButton("📈 Investimentos",    callback_data="menu_inv"),
         InlineKeyboardButton("💳 Cartões",          callback_data="menu_cartoes")],
        [InlineKeyboardButton("🔄 Recorrências",     callback_data="menu_recorr"),
         InlineKeyboardButton("📅 Vencimentos",      callback_data="menu_vcal")],
    ])

def voltar_menu_kb(dest: str = "menu_principal") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data=dest)]])

def cancelar_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_flow")]])

# ── Comandos ──────────────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.effective_user.first_name
    msg = (
        f"💚 Olá, *{nome}*! Bem-vindo ao *Start Finance*!\n\n"
        "Sou seu assistente financeiro completo.\n\n"
        "📝 *Adicionar transação:* só falar!\n"
        "• \"Gastei R$45 no almoço\"\n"
        "• \"50 uber + 35 ifood\"\n"
        "• 🎤 Ou envie um áudio!\n\n"
        "Use o menu para gerenciar tudo:"
    )
    await update.message.reply_text(msg, parse_mode="Markdown",
                                    reply_markup=menu_principal_kb())

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📱 *Menu Principal*", parse_mode="Markdown",
                                    reply_markup=menu_principal_kb())

async def cmd_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _mostrar_resumo_msg(update.message, context)

async def cmd_ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🆘 *Como usar o Start Finance Bot:*\n\n"
        "*📝 Texto natural:*\n"
        "• \"Gastei R$50 no mercado\"\n"
        "• \"Paguei 120 de luz\"\n"
        "• \"Recebi R$3000 de salário\"\n"
        "• \"Peças do carro 600, 3x\"\n\n"
        "*🎤 Áudio:* grave e mande!\n\n"
        "*📊 Comandos:*\n"
        "/menu — Menu principal\n"
        "/resumo — Resumo do mês\n"
        "/ajuda — Esta mensagem\n\n"
        "Use /menu para fixas, dívidas, metas, investimentos e mais! 💚"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

# ── Resumo ────────────────────────────────────────────────────────────
def _build_resumo_text(data: dict) -> str:
    from collections import defaultdict
    txs = data.get("txs", [])
    mes = mes_ano_atual()
    entradas = sum(abs(t.get("valor", 0)) for t in txs
                   if t.get("tipo","").lower() in ("receita",) and t.get("mes_ano") == mes)
    saidas   = sum(abs(t.get("valor", 0)) for t in txs
                   if t.get("tipo","").lower() in ("gasto",)   and t.get("mes_ano") == mes)
    saldo    = entradas - saidas

    cats: dict = defaultdict(float)
    for t in txs:
        if t.get("tipo","").lower() == "gasto" and t.get("mes_ano") == mes:
            cats[t.get("categoria", "Outros")] += abs(t.get("valor", 0))

    total_fixas = sum(f.get("valor", 0) for f in data.get("fixas", []) if f.get("ativa", True))
    total_inv   = sum(i.get("valor", 0) for i in data.get("inv",   []))
    dividas_at  = [d for d in data.get("dividas", []) if not d.get("paga", False)]
    total_div   = sum(d.get("valor_total", d.get("valor", 0)) for d in dividas_at)
    n_tx        = sum(1 for t in txs if t.get("mes_ano") == mes)
    emoji_saldo = "💚" if saldo >= 0 else "🔴"

    txt = (
        f"📊 *Resumo — {mes}*\n\n"
        f"💰 Entradas: *{fmt_brl(entradas)}*\n"
        f"💸 Saídas:   *{fmt_brl(saidas)}*\n"
        f"{emoji_saldo} Saldo:    *{fmt_brl(saldo)}*\n"
    )
    if cats:
        txt += "\n📂 *Por categoria:*\n"
        for cat, val in sorted(cats.items(), key=lambda x: x[1], reverse=True)[:5]:
            txt += f"  • {cat}: {fmt_brl(val)}\n"
    if total_fixas > 0:
        txt += f"\n📌 Fixas: *{fmt_brl(total_fixas)}/mês*"
    if total_inv > 0:
        txt += f"\n📈 Investimentos: *{fmt_brl(total_inv)}*"
    if total_div > 0:
        txt += f"\n💳 Dívidas ativas: *{fmt_brl(total_div)}*"
    txt += f"\n\n📝 {n_tx} transações este mês"
    return txt

async def _mostrar_resumo_msg(msg, context):
    data = api.get_data()
    if data is None:
        await msg.reply_text("❌ Erro ao buscar dados. Tente novamente.")
        return
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📱 Menu", callback_data="menu_principal")]])
    await msg.reply_text(_build_resumo_text(data), parse_mode="Markdown", reply_markup=kb)

async def _mostrar_resumo_edit(query, context):
    data = api.get_data()
    if data is None:
        await query.edit_message_text("❌ Erro ao buscar dados.")
        return
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("📱 Menu", callback_data="menu_principal")]])
    await query.edit_message_text(_build_resumo_text(data), parse_mode="Markdown", reply_markup=kb)

# ── Seções do menu ────────────────────────────────────────────────────
async def _menu_tx(query, context):
    data = api.get_data()
    if data is None:
        await query.edit_message_text("❌ Erro ao buscar dados.")
        return
    mes = mes_ano_atual()
    txs_mes = sorted(
        [t for t in data.get("txs", []) if t.get("mes_ano") == mes],
        key=lambda t: (t.get("data", ""), t.get("hora", "")), reverse=True
    )
    txt = f"💸 *Transações — {mes}*\n\n"
    if not txs_mes:
        txt += "_Nenhuma transação este mês._\n"
    else:
        for t in txs_mes[:12]:
            emoji = "💸" if t.get("tipo","").lower() == "gasto" else "💰"
            txt += f"{emoji} {fmt_brl(t.get('valor',0))} — {t.get('categoria','Outros')} ({t.get('data','')})\n"
        if len(txs_mes) > 12:
            txt += f"_...e mais {len(txs_mes)-12} transações_\n"

    buttons = [
        [InlineKeyboardButton("➕ Como adicionar", callback_data="tx_info")],
        [InlineKeyboardButton("🗑️ Excluir última", callback_data="tx_del_last")],
        [InlineKeyboardButton("⬅️ Menu",           callback_data="menu_principal")],
    ]
    await query.edit_message_text(txt, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(buttons))

async def _menu_fixas(query, context):
    data = api.get_data()
    if data is None:
        await query.edit_message_text("❌ Erro ao buscar dados.")
        return
    fixas  = data.get("fixas", [])
    total  = sum(f.get("valor", 0) for f in fixas if f.get("ativa", True))
    txt    = f"📌 *Despesas Fixas*\n\nTotal mensal: *{fmt_brl(total)}*\n\n"
    if not fixas:
        txt += "_Nenhuma despesa fixa cadastrada._\n"
    else:
        for i, f in enumerate(fixas):
            status = "✅" if f.get("ativa", True) else "⏸️"
            dia    = f" | dia {f['dia_vencimento']}" if f.get("dia_vencimento") else ""
            txt   += f"{i+1}. {status} *{f.get('nome','?')}* — {fmt_brl(f.get('valor',0))}{dia}\n"

    buttons = [[InlineKeyboardButton("➕ Adicionar Fixa", callback_data="fixa_add")]]
    if fixas:
        buttons.append([InlineKeyboardButton("🗑️ Excluir", callback_data="fixa_del_sel")])
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="menu_principal")])
    await query.edit_message_text(txt, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(buttons))

async def _menu_dividas(query, context):
    data = api.get_data()
    if data is None:
        await query.edit_message_text("❌ Erro ao buscar dados.")
        return
    dividas = data.get("dividas", [])
    ativas  = [d for d in dividas if not d.get("paga", False)]
    total   = sum(d.get("valor_total", d.get("valor", 0)) for d in ativas)
    txt     = f"💳 *Dívidas*\n\nTotal: *{fmt_brl(total)}*\n\n"
    if not ativas:
        txt += "✅ _Nenhuma dívida ativa!_\n"
    else:
        for i, d in enumerate(ativas):
            pa = d.get("parcela_atual", 0)
            pt = d.get("total_parcelas", d.get("parcelas", 0))
            parc = f" ({pa}/{pt}x)" if pt and int(pt) > 0 else ""
            val_p = d.get("valor_parcela", d.get("valor", d.get("valor_total", 0)))
            txt += f"{i+1}. 💳 *{d.get('nome','?')}*{parc} — {fmt_brl(val_p)}/mês\n"

    buttons = [[InlineKeyboardButton("➕ Adicionar Dívida", callback_data="divida_add")]]
    if ativas:
        buttons.append([InlineKeyboardButton("✅ Marcar como paga",  callback_data="divida_pagar_sel")])
        buttons.append([InlineKeyboardButton("🗑️ Excluir",          callback_data="divida_del_sel")])
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="menu_principal")])
    await query.edit_message_text(txt, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(buttons))

async def _menu_metas(query, context):
    data = api.get_data()
    if data is None:
        await query.edit_message_text("❌ Erro ao buscar dados.")
        return
    metas = data.get("metas", [])
    txt   = "🎯 *Metas Financeiras*\n\n"
    if not metas:
        txt += "_Nenhuma meta cadastrada._\n"
    else:
        for i, m in enumerate(metas):
            alvo  = float(m.get("valor_alvo", m.get("alvo", 0)) or 0)
            atual = float(m.get("valor_atual", m.get("atual", 0)) or 0)
            pct   = (atual / alvo * 100) if alvo > 0 else 0
            blocos = int(pct / 10)
            bar   = "█" * blocos + "░" * (10 - blocos)
            txt  += f"{i+1}. 🎯 *{m.get('nome','?')}*\n   `{bar}` {pct:.0f}%\n   {fmt_brl(atual)} / {fmt_brl(alvo)}\n\n"

    buttons = [[InlineKeyboardButton("➕ Adicionar Meta", callback_data="meta_add")]]
    if metas:
        buttons.append([InlineKeyboardButton("💰 Atualizar progresso", callback_data="meta_prog_sel")])
        buttons.append([InlineKeyboardButton("🗑️ Excluir",            callback_data="meta_del_sel")])
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="menu_principal")])
    await query.edit_message_text(txt, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(buttons))

async def _menu_inv(query, context):
    data = api.get_data()
    if data is None:
        await query.edit_message_text("❌ Erro ao buscar dados.")
        return
    inv   = data.get("inv", [])
    total = sum(i.get("valor", 0) for i in inv)
    txt   = f"📈 *Investimentos*\n\nTotal: *{fmt_brl(total)}*\n\n"
    if not inv:
        txt += "_Nenhum investimento cadastrado._\n"
    else:
        for i, item in enumerate(inv):
            rend     = item.get("rendimento", item.get("rendimento_anual", 0))
            rend_str = f" | {rend}% aa" if rend else ""
            tipo_str = f" [{item.get('tipo','')}]" if item.get("tipo") else ""
            txt += f"{i+1}. 📈 *{item.get('nome','?')}*{tipo_str} — {fmt_brl(item.get('valor',0))}{rend_str}\n"

    buttons = [[InlineKeyboardButton("➕ Adicionar Investimento", callback_data="inv_add")]]
    if inv:
        buttons.append([InlineKeyboardButton("🗑️ Excluir", callback_data="inv_del_sel")])
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="menu_principal")])
    await query.edit_message_text(txt, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(buttons))

async def _menu_cartoes(query, context):
    data = api.get_data()
    if data is None:
        await query.edit_message_text("❌ Erro ao buscar dados.")
        return
    cartoes = data.get("cartoes", [])
    txt     = "💳 *Cartões de Crédito*\n\n"
    if not cartoes:
        txt += "_Nenhum cartão cadastrado._\n"
    else:
        for i, c in enumerate(cartoes):
            fech = c.get("fechamento", c.get("dia_fechamento", "?"))
            venc = c.get("vencimento",  c.get("dia_vencimento", "?"))
            txt += (f"{i+1}. 💳 *{c.get('nome','?')}* | "
                    f"Lim: {fmt_brl(c.get('limite',0))} | "
                    f"Fecha d.{fech} | Vence d.{venc}\n")

    buttons = [[InlineKeyboardButton("➕ Adicionar Cartão", callback_data="cartao_add")]]
    if cartoes:
        buttons.append([InlineKeyboardButton("🗑️ Excluir", callback_data="cartao_del_sel")])
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="menu_principal")])
    await query.edit_message_text(txt, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(buttons))

async def _menu_recorr(query, context):
    data = api.get_data()
    if data is None:
        await query.edit_message_text("❌ Erro ao buscar dados.")
        return
    recorr = data.get("recorrencias", [])
    txt    = "🔄 *Regras de Recorrência*\n\n"
    if not recorr:
        txt += "_Nenhuma regra cadastrada._\n"
    else:
        for i, r in enumerate(recorr):
            freq = r.get("frequencia", r.get("tipo", "mensal"))
            txt += f"{i+1}. 🔄 *{r.get('nome','?')}* — {fmt_brl(r.get('valor',0))} ({freq})\n"

    buttons = [[InlineKeyboardButton("➕ Adicionar Regra", callback_data="recorr_add")]]
    if recorr:
        buttons.append([InlineKeyboardButton("🗑️ Excluir", callback_data="recorr_del_sel")])
    buttons.append([InlineKeyboardButton("⬅️ Menu", callback_data="menu_principal")])
    await query.edit_message_text(txt, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(buttons))

async def _menu_vcal(query, context):
    data = api.get_data()
    if data is None:
        await query.edit_message_text("❌ Erro ao buscar dados.")
        return
    now       = datetime.now()
    dia_hoje  = now.day
    items: list[tuple[int, str]] = []

    for f in data.get("fixas", []):
        if not f.get("ativa", True):
            continue
        dia = f.get("dia_vencimento")
        if dia:
            try:
                diff = int(dia) - dia_hoje
                if diff < 0:
                    diff += 30
                items.append((diff, f"📌 *{f['nome']}* — {fmt_brl(f.get('valor',0))} (dia {dia})"))
            except Exception:
                pass

    for c in data.get("cartoes", []):
        dia = c.get("vencimento", c.get("dia_vencimento"))
        if dia:
            try:
                diff = int(dia) - dia_hoje
                if diff < 0:
                    diff += 30
                items.append((diff, f"💳 *{c['nome']}* — fatura (dia {dia})"))
            except Exception:
                pass

    vcal = data.get("vcal", {})
    if isinstance(vcal, dict):
        mes_key = f"{now.year}-{now.month:02d}"
        for item_v in vcal.get(mes_key, []):
            dia = item_v.get("dia")
            if dia:
                try:
                    diff = int(dia) - dia_hoje
                    if diff < 0:
                        continue
                    nome = item_v.get("nome", "Vencimento")
                    valor = item_v.get("valor", 0)
                    items.append((diff, f"📅 *{nome}* — {fmt_brl(valor)} (dia {dia})"))
                except Exception:
                    pass

    items.sort(key=lambda x: x[0])
    txt = f"📅 *Próximos Vencimentos*\nHoje é dia {dia_hoje}\n\n"
    if not items:
        txt += "_Nenhum vencimento próximo._\n"
    else:
        for diff, desc in items[:10]:
            if diff == 0:
                urgencia = "🔴 HOJE —"
            elif diff <= 3:
                urgencia = f"⚠️ em {diff}d —"
            elif diff <= 7:
                urgencia = f"🟡 em {diff}d —"
            else:
                urgencia = f"🟢 em {diff}d —"
            txt += f"{urgencia} {desc}\n"

    await query.edit_message_text(txt, parse_mode="Markdown",
                                  reply_markup=voltar_menu_kb())

# ── Seleção de item para excluir ──────────────────────────────────────
_CHAVES = {
    "fixa":   "fixas",
    "divida": "dividas",
    "meta":   "metas",
    "inv":    "inv",
    "cartao": "cartoes",
    "recorr": "recorrencias",
}
_BACK = {
    "fixa":   "menu_fixas",
    "divida": "menu_dividas",
    "meta":   "menu_metas",
    "inv":    "menu_inv",
    "cartao": "menu_cartoes",
    "recorr": "menu_recorr",
}

async def _sel_deletar(query, tipo: str):
    data_obj = api.get_data()
    if data_obj is None:
        await query.edit_message_text("❌ Erro ao buscar dados.")
        return
    items = data_obj.get(_CHAVES.get(tipo, tipo), [])
    if not items:
        await query.edit_message_text("❌ Nenhum item para excluir.",
                                      reply_markup=voltar_menu_kb(_BACK.get(tipo, "menu_principal")))
        return
    buttons = []
    for i, item in enumerate(items):
        nome = item.get("nome", f"Item {i+1}")
        buttons.append([InlineKeyboardButton(f"🗑️ {nome}", callback_data=f"del_{tipo}_{i}")])
    buttons.append([InlineKeyboardButton("⬅️ Voltar", callback_data=_BACK.get(tipo, "menu_principal"))])
    await query.edit_message_text("🗑️ *Qual item deseja excluir?*", parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(buttons))

async def _exec_deletar(query, tipo: str, idx: int):
    data_obj = api.get_data()
    if data_obj is None:
        await query.edit_message_text("❌ Erro ao buscar dados.")
        return
    key   = _CHAVES.get(tipo, tipo)
    items = data_obj.get(key, [])
    if idx >= len(items):
        await query.edit_message_text("❌ Item não encontrado.")
        return
    nome = items[idx].get("nome", "Item")
    items.pop(idx)
    data_obj[key] = items
    ok = api.save_data(data_obj)
    back = _BACK.get(tipo, "menu_principal")
    if ok:
        await query.edit_message_text(f"✅ *{nome}* excluído com sucesso!",
                                      parse_mode="Markdown",
                                      reply_markup=voltar_menu_kb(back))
    else:
        await query.edit_message_text("❌ Erro ao salvar. Tente novamente.",
                                      reply_markup=voltar_menu_kb(back))

# ── Fluxos de adição ──────────────────────────────────────────────────
PROMPTS = {
    "fixa_nome":       "📌 *Nova Despesa Fixa*\n\nQual o nome?\n\n_Ex: Aluguel, Netflix, Academia_",
    "fixa_valor":      "💰 Qual o valor mensal? (em R$)\n\n_Ex: 1500 ou 29.90_",
    "fixa_dia":        "📅 Qual o dia do vencimento? (1-31)\n\n_Digite 0 para não definir_",
    "divida_nome":     "💳 *Nova Dívida*\n\nQual o nome?\n\n_Ex: Empréstimo Banco, Cartão Visa_",
    "divida_valor":    "💰 Qual o valor total da dívida? (em R$)\n\n_Ex: 5000_",
    "divida_parcelas": "🔢 Em quantas parcelas?\n\n_Digite 0 para dívida sem parcelas fixas_",
    "meta_nome":       "🎯 *Nova Meta*\n\nQual o nome?\n\n_Ex: Reserva emergência, Viagem_",
    "meta_alvo":       "💰 Qual o valor alvo? (em R$)\n\n_Ex: 10000_",
    "meta_atual":      "💰 Quanto você já tem guardado? (em R$)\n\n_Digite 0 se ainda não tem nada_",
    "meta_prog_valor": "💰 Qual o novo valor atual da meta? (em R$)\n\n_Ex: 2500_",
    "inv_nome":        "📈 *Novo Investimento*\n\nQual o nome?\n\n_Ex: CDB Nubank, Tesouro SELIC_",
    "inv_valor":       "💰 Qual o valor investido? (em R$)\n\n_Ex: 5000_",
    "cartao_nome":     "💳 *Novo Cartão*\n\nQual o nome?\n\n_Ex: Nubank, Itaú Visa_",
    "cartao_limite":   "💰 Qual o limite? (em R$)\n\n_Ex: 5000_",
    "cartao_fech":     "📅 Qual o dia de fechamento? (1-31)",
    "cartao_venc":     "📅 Qual o dia de vencimento? (1-31)",
    "recorr_nome":     "🔄 *Nova Recorrência*\n\nQual o nome?\n\n_Ex: Renda Aluguel, Mesada_",
    "recorr_valor":    "💰 Qual o valor? (em R$)\n\n_Ex: 500_",
}

async def _set_state(target, context, state: str, edit: bool = False):
    context.user_data["state"] = state
    txt = PROMPTS.get(state, state)
    if edit:
        await target.edit_message_text(txt, parse_mode="Markdown", reply_markup=cancelar_kb())
    else:
        await target.reply_text(txt, parse_mode="Markdown", reply_markup=cancelar_kb())

# ── Finalizar fluxos ──────────────────────────────────────────────────
async def _save_item(target, context, key: str, item: dict, back: str, msg_ok: str, edit: bool = False):
    data_obj = api.get_data()
    if data_obj is None:
        text = "❌ Erro ao acessar dados."
        if edit:
            await target.edit_message_text(text)
        else:
            await target.reply_text(text)
        context.user_data.clear()
        return
    lst = data_obj.get(key, [])
    lst.append(item)
    data_obj[key] = lst
    ok = api.save_data(data_obj)
    context.user_data.clear()
    kb = voltar_menu_kb(back)
    if ok:
        if edit:
            await target.edit_message_text(msg_ok, parse_mode="Markdown", reply_markup=kb)
        else:
            await target.reply_text(msg_ok, parse_mode="Markdown", reply_markup=kb)
    else:
        text = "❌ Erro ao salvar. Tente novamente."
        if edit:
            await target.edit_message_text(text, reply_markup=kb)
        else:
            await target.reply_text(text, reply_markup=kb)

# ── Callback principal ────────────────────────────────────────────────
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    d = query.data

    # ── Navegação ──────────────────────────────────────────────────
    if d == "menu_principal":
        await query.edit_message_text("📱 *Menu Principal*", parse_mode="Markdown",
                                      reply_markup=menu_principal_kb())
        return
    if d == "menu_resumo":
        await _mostrar_resumo_edit(query, context); return
    if d == "menu_tx":
        await _menu_tx(query, context); return
    if d == "menu_fixas":
        await _menu_fixas(query, context); return
    if d == "menu_dividas":
        await _menu_dividas(query, context); return
    if d == "menu_metas":
        await _menu_metas(query, context); return
    if d == "menu_inv":
        await _menu_inv(query, context); return
    if d == "menu_cartoes":
        await _menu_cartoes(query, context); return
    if d == "menu_recorr":
        await _menu_recorr(query, context); return
    if d == "menu_vcal":
        await _menu_vcal(query, context); return

    # ── Cancelar fluxo ─────────────────────────────────────────────
    if d == "cancelar_flow":
        context.user_data.clear()
        await query.edit_message_text(
            "❌ Operação cancelada.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 Menu", callback_data="menu_principal")]]))
        return

    # ── Transações ─────────────────────────────────────────────────
    if d == "tx_info":
        await query.edit_message_text(
            "💸 *Adicionar transação*\n\n"
            "Basta digitar normalmente:\n\n"
            "• \"Gastei 50 no mercado\"\n"
            "• \"Recebi 3000 de salário\"\n"
            "• \"120 conta de luz\"\n\n"
            "Ou envie um 🎤 áudio!",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="menu_tx")]]))
        return

    if d == "tx_del_last":
        data_obj = api.get_data()
        if not data_obj:
            await query.edit_message_text("❌ Erro ao buscar dados."); return
        mes     = mes_ano_atual()
        txs_mes = [(i, t) for i, t in enumerate(data_obj.get("txs", []))
                   if t.get("mes_ano") == mes]
        if not txs_mes:
            await query.edit_message_text("❌ Nenhuma transação este mês.",
                                          reply_markup=voltar_menu_kb("menu_tx")); return
        idx, tx = txs_mes[-1]
        context.user_data["del_tx_idx"] = idx
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Confirmar", callback_data="tx_del_confirm"),
            InlineKeyboardButton("❌ Cancelar",  callback_data="menu_tx"),
        ]])
        await query.edit_message_text(
            f"⚠️ *Excluir esta transação?*\n\n"
            f"{'💸' if tx.get('tipo','').lower()=='gasto' else '💰'} "
            f"{fmt_brl(tx.get('valor',0))} — {tx.get('categoria','?')} ({tx.get('data','')})",
            parse_mode="Markdown", reply_markup=kb)
        return

    if d == "tx_del_confirm":
        idx      = context.user_data.pop("del_tx_idx", None)
        data_obj = api.get_data()
        if idx is not None and data_obj:
            txs = data_obj.get("txs", [])
            if idx < len(txs):
                txs.pop(idx)
                data_obj["txs"] = txs
                if api.save_data(data_obj):
                    await query.edit_message_text(
                        "✅ Transação excluída!",
                        reply_markup=voltar_menu_kb("menu_tx"))
                    return
        await query.edit_message_text("❌ Erro ao excluir.", reply_markup=voltar_menu_kb("menu_tx"))
        return

    # ── Confirmar transação via AI ──────────────────────────────────
    if d == "confirmar":
        dados    = context.user_data.pop("pendente", None)
        if not dados:
            await query.edit_message_text("❌ Dados expirados. Envie novamente."); return
        data_obj = api.get_data()
        if data_obj is None:
            await query.edit_message_text("❌ Erro ao acessar dados."); return
        dados["id"]      = make_id()
        dados["mes_ano"] = dados.get("mes_ano") or mes_ano_de_data(dados.get("data",""))
        dados["metodo"]  = dados.get("metodo", dados.get("metodo_pagamento",""))
        txs = data_obj.get("txs", [])
        txs.append(dados)
        data_obj["txs"] = txs
        if api.save_data(data_obj):
            tipo_emoji = "💸" if dados.get("tipo","").lower() == "gasto" else "💰"
            cat        = dados.get("categoria","Outros")
            sub        = dados.get("subcategoria","")
            cat_str    = cat + (f" · {sub}" if sub else "")
            valor      = abs(float(dados.get("valor", 0)))
            msg_ok     = f"✅ *Registrado!*\n\n{tipo_emoji} *{fmt_brl(valor)}* em {cat_str}"
            if dados.get("localizacao"):
                msg_ok += f"\n📍 {dados['localizacao']}"
            if dados.get("metodo_pagamento"):
                msg_ok += f"\n💳 {dados['metodo_pagamento']}"
            pt = dados.get("total_parcelas", 0)
            if pt and int(pt) > 1:
                msg_ok += f"\n🔢 Parcelado em *{pt}x*"
            dica = _gerar_dica(dados)
            if dica:
                msg_ok += f"\n\n💡 _{dica}_"
            await query.edit_message_text(
                msg_ok, parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 Menu", callback_data="menu_principal")]]))
        else:
            await query.edit_message_text("❌ Erro ao salvar. Tente novamente!")
        return

    if d == "cancelar":
        context.user_data.pop("pendente", None)
        await query.edit_message_text(
            "❌ Cancelado.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 Menu", callback_data="menu_principal")]]))
        return

    # ── Fixas ──────────────────────────────────────────────────────
    if d == "fixa_add":
        context.user_data.update({"flow": "fixa", "flow_data": {}})
        await _set_state(query, context, "fixa_nome", edit=True); return
    if d == "fixa_del_sel":
        await _sel_deletar(query, "fixa"); return

    # ── Dívidas ────────────────────────────────────────────────────
    if d == "divida_add":
        context.user_data.update({"flow": "divida", "flow_data": {}})
        await _set_state(query, context, "divida_nome", edit=True); return
    if d == "divida_del_sel":
        await _sel_deletar(query, "divida"); return
    if d == "divida_pagar_sel":
        data_obj = api.get_data()
        if not data_obj:
            await query.edit_message_text("❌ Erro."); return
        ativas = [(i, dv) for i, dv in enumerate(data_obj.get("dividas", []))
                  if not dv.get("paga", False)]
        if not ativas:
            await query.edit_message_text("✅ Nenhuma dívida ativa!",
                                          reply_markup=voltar_menu_kb("menu_dividas")); return
        buttons = [[InlineKeyboardButton(f"✅ {dv.get('nome','?')}", callback_data=f"divida_pagar_{i}")]
                   for i, dv in ativas]
        buttons.append([InlineKeyboardButton("⬅️ Voltar", callback_data="menu_dividas")])
        await query.edit_message_text("✅ *Qual dívida foi paga?*", parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(buttons)); return

    # ── Metas ──────────────────────────────────────────────────────
    if d == "meta_add":
        context.user_data.update({"flow": "meta", "flow_data": {}})
        await _set_state(query, context, "meta_nome", edit=True); return
    if d == "meta_del_sel":
        await _sel_deletar(query, "meta"); return
    if d == "meta_prog_sel":
        data_obj = api.get_data()
        if not data_obj:
            await query.edit_message_text("❌ Erro."); return
        metas = data_obj.get("metas", [])
        if not metas:
            await query.edit_message_text("❌ Nenhuma meta cadastrada.",
                                          reply_markup=voltar_menu_kb("menu_metas")); return
        buttons = [[InlineKeyboardButton(f"🎯 {m.get('nome','?')}", callback_data=f"meta_prog_{i}")]
                   for i, m in enumerate(metas)]
        buttons.append([InlineKeyboardButton("⬅️ Voltar", callback_data="menu_metas")])
        await query.edit_message_text("🎯 *Qual meta atualizar?*", parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(buttons)); return

    # ── Investimentos ──────────────────────────────────────────────
    if d == "inv_add":
        context.user_data.update({"flow": "inv", "flow_data": {}})
        await _set_state(query, context, "inv_nome", edit=True); return
    if d == "inv_del_sel":
        await _sel_deletar(query, "inv"); return

    # ── Cartões ────────────────────────────────────────────────────
    if d == "cartao_add":
        context.user_data.update({"flow": "cartao", "flow_data": {}})
        await _set_state(query, context, "cartao_nome", edit=True); return
    if d == "cartao_del_sel":
        await _sel_deletar(query, "cartao"); return

    # ── Recorrências ───────────────────────────────────────────────
    if d == "recorr_add":
        context.user_data.update({"flow": "recorr", "flow_data": {}})
        await _set_state(query, context, "recorr_nome", edit=True); return
    if d == "recorr_del_sel":
        await _sel_deletar(query, "recorr"); return

    # ── Dinâmicos: del_tipo_idx ────────────────────────────────────
    if d.startswith("del_"):
        parts = d.split("_", 2)
        if len(parts) == 3:
            await _exec_deletar(query, parts[1], int(parts[2]))
        return

    if d.startswith("divida_pagar_"):
        idx      = int(d.split("_")[-1])
        data_obj = api.get_data()
        if data_obj:
            dividas = data_obj.get("dividas", [])
            if idx < len(dividas):
                dividas[idx]["paga"]            = True
                dividas[idx]["data_pagamento"]  = hoje()
                data_obj["dividas"] = dividas
                if api.save_data(data_obj):
                    nome = dividas[idx].get("nome", "Dívida")
                    await query.edit_message_text(
                        f"✅ *{nome}* marcada como paga!",
                        parse_mode="Markdown",
                        reply_markup=voltar_menu_kb("menu_dividas"))
                    return
        await query.edit_message_text("❌ Erro ao atualizar.")
        return

    if d.startswith("meta_prog_"):
        idx = int(d.split("_")[-1])
        context.user_data["flow"]          = "meta_prog"
        context.user_data["meta_prog_idx"] = idx
        await _set_state(query, context, "meta_prog_valor", edit=True)
        return

    if d.startswith("inv_tipo_"):
        tipos = {1: "Renda Fixa", 2: "Renda Variável", 3: "FII", 4: "Criptomoedas", 5: "Outro"}
        num   = int(d.split("_")[-1])
        context.user_data["flow_data"]["tipo"] = tipos.get(num, "Outro")
        await _salvar_inv(query, context, edit=True)
        return

    if d.startswith("recorr_freq_"):
        freqs = {1: "mensal", 2: "semanal", 3: "quinzenal", 4: "anual"}
        num   = int(d.split("_")[-1])
        context.user_data["flow_data"]["frequencia"] = freqs.get(num, "mensal")
        await _salvar_recorr(query, context, edit=True)
        return

# ── Handler de texto ──────────────────────────────────────────────────
async def handle_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    if texto.startswith("/"):
        return
    state = context.user_data.get("state", "")
    if state:
        await _process_flow(update.message, context, texto)
    else:
        await _extrair_tx(update, context, texto)

async def _extrair_tx(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str):
    await update.message.reply_text("🧠 Analisando sua mensagem...")
    try:
        dados = await extractor.extrair(texto, update.message.date)
        if dados:
            if isinstance(dados, list):
                for d in dados:
                    await _pedir_confirmacao(update, context, d)
            else:
                await _pedir_confirmacao(update, context, dados)
        else:
            await update.message.reply_text(
                "🤔 Não identifiquei uma transação financeira.\n\n"
                "Tente: *\"Gastei R$50 no mercado\"*\n\n"
                "Use /menu para gerenciar fixas, dívidas, metas e mais!",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 Menu", callback_data="menu_principal")]]))
    except Exception as e:
        logger.error(f"Erro extrair: {e}")
        await update.message.reply_text("❌ Erro ao processar. Tente novamente!")

# ── State machine ─────────────────────────────────────────────────────
async def _process_flow(msg, context: ContextTypes.DEFAULT_TYPE, texto: str):
    state = context.user_data.get("state", "")
    fd    = context.user_data.setdefault("flow_data", {})

    # ── Fixas ──────────────────────────────────────────────────────
    if state == "fixa_nome":
        fd["nome"] = texto.strip()[:80]
        await _set_state(msg, context, "fixa_valor"); return

    if state == "fixa_valor":
        v = parse_valor(texto)
        if v is None:
            await msg.reply_text("❌ Valor inválido. Ex: *150* ou *29.90*", parse_mode="Markdown"); return
        fd["valor"] = v
        await _set_state(msg, context, "fixa_dia"); return

    if state == "fixa_dia":
        dia = parse_dia(texto)
        if dia is None:
            await msg.reply_text("❌ Dia inválido. Ex: *5* ou *0* para não definir"); return
        fd["dia_vencimento"] = dia if dia > 0 else None
        await _salvar_fixa(msg, context); return

    # ── Dívidas ────────────────────────────────────────────────────
    if state == "divida_nome":
        fd["nome"] = texto.strip()[:80]
        await _set_state(msg, context, "divida_valor"); return

    if state == "divida_valor":
        v = parse_valor(texto)
        if v is None:
            await msg.reply_text("❌ Valor inválido. Ex: *5000*", parse_mode="Markdown"); return
        fd["valor_total"] = v
        await _set_state(msg, context, "divida_parcelas"); return

    if state == "divida_parcelas":
        try:
            parcelas = max(0, int(texto.strip()))
        except Exception:
            await msg.reply_text("❌ Número inválido. Ex: *12* ou *0*", parse_mode="Markdown"); return
        fd["total_parcelas"] = parcelas
        fd["parcelas"]       = parcelas
        fd["valor_parcela"]  = round(fd["valor_total"] / parcelas, 2) if parcelas > 0 else fd["valor_total"]
        await _salvar_divida(msg, context); return

    # ── Metas ──────────────────────────────────────────────────────
    if state == "meta_nome":
        fd["nome"] = texto.strip()[:80]
        await _set_state(msg, context, "meta_alvo"); return

    if state == "meta_alvo":
        v = parse_valor(texto)
        if v is None:
            await msg.reply_text("❌ Valor inválido. Ex: *10000*", parse_mode="Markdown"); return
        fd["valor_alvo"] = v
        fd["alvo"]       = v
        await _set_state(msg, context, "meta_atual"); return

    if state == "meta_atual":
        v = parse_valor(texto) if texto.strip() != "0" else 0.0
        if v is None:
            await msg.reply_text("❌ Valor inválido. Ex: *1500* ou *0*", parse_mode="Markdown"); return
        fd["valor_atual"] = v
        fd["atual"]       = v
        await _salvar_meta(msg, context); return

    # ── Meta progresso ─────────────────────────────────────────────
    if state == "meta_prog_valor":
        v = parse_valor(texto) if texto.strip() != "0" else 0.0
        if v is None:
            await msg.reply_text("❌ Valor inválido. Ex: *2500*", parse_mode="Markdown"); return
        idx      = context.user_data.get("meta_prog_idx", 0)
        data_obj = api.get_data()
        if data_obj:
            metas = data_obj.get("metas", [])
            if idx < len(metas):
                metas[idx]["valor_atual"] = v
                metas[idx]["atual"]       = v
                data_obj["metas"] = metas
                if api.save_data(data_obj):
                    nome = metas[idx].get("nome","Meta")
                    alvo = float(metas[idx].get("valor_alvo", metas[idx].get("alvo", 0)) or 0)
                    pct  = (v / alvo * 100) if alvo > 0 else 0
                    context.user_data.clear()
                    await msg.reply_text(
                        f"✅ *{nome}* atualizada!\n{fmt_brl(v)} / {fmt_brl(alvo)} ({pct:.0f}%)",
                        parse_mode="Markdown",
                        reply_markup=voltar_menu_kb("menu_metas"))
                    return
        await msg.reply_text("❌ Erro ao atualizar meta.")
        context.user_data.clear(); return

    # ── Investimentos ──────────────────────────────────────────────
    if state == "inv_nome":
        fd["nome"] = texto.strip()[:80]
        await _set_state(msg, context, "inv_valor"); return

    if state == "inv_valor":
        v = parse_valor(texto)
        if v is None:
            await msg.reply_text("❌ Valor inválido. Ex: *5000*", parse_mode="Markdown"); return
        fd["valor"] = v
        context.user_data["state"] = "inv_tipo_sel"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("1️⃣ Renda Fixa",     callback_data="inv_tipo_1"),
             InlineKeyboardButton("2️⃣ Renda Variável",  callback_data="inv_tipo_2")],
            [InlineKeyboardButton("3️⃣ FII",            callback_data="inv_tipo_3"),
             InlineKeyboardButton("4️⃣ Criptomoedas",    callback_data="inv_tipo_4")],
            [InlineKeyboardButton("5️⃣ Outro",          callback_data="inv_tipo_5")],
            [InlineKeyboardButton("❌ Cancelar",        callback_data="cancelar_flow")],
        ])
        await msg.reply_text("📈 Qual o tipo de investimento?", reply_markup=kb); return

    # ── Cartões ────────────────────────────────────────────────────
    if state == "cartao_nome":
        fd["nome"] = texto.strip()[:80]
        await _set_state(msg, context, "cartao_limite"); return

    if state == "cartao_limite":
        v = parse_valor(texto)
        if v is None:
            await msg.reply_text("❌ Valor inválido. Ex: *5000*", parse_mode="Markdown"); return
        fd["limite"] = v
        await _set_state(msg, context, "cartao_fech"); return

    if state == "cartao_fech":
        dia = parse_dia(texto)
        if not dia or dia < 1:
            await msg.reply_text("❌ Dia inválido (1-31)."); return
        fd["fechamento"] = dia
        fd["dia_fechamento"] = dia
        await _set_state(msg, context, "cartao_venc"); return

    if state == "cartao_venc":
        dia = parse_dia(texto)
        if not dia or dia < 1:
            await msg.reply_text("❌ Dia inválido (1-31)."); return
        fd["vencimento"]     = dia
        fd["dia_vencimento"] = dia
        await _salvar_cartao(msg, context); return

    # ── Recorrências ───────────────────────────────────────────────
    if state == "recorr_nome":
        fd["nome"] = texto.strip()[:80]
        await _set_state(msg, context, "recorr_valor"); return

    if state == "recorr_valor":
        v = parse_valor(texto)
        if v is None:
            await msg.reply_text("❌ Valor inválido. Ex: *500*", parse_mode="Markdown"); return
        fd["valor"] = v
        context.user_data["state"] = "recorr_freq_sel"
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("1️⃣ Mensal",    callback_data="recorr_freq_1"),
             InlineKeyboardButton("2️⃣ Semanal",   callback_data="recorr_freq_2")],
            [InlineKeyboardButton("3️⃣ Quinzenal", callback_data="recorr_freq_3"),
             InlineKeyboardButton("4️⃣ Anual",     callback_data="recorr_freq_4")],
            [InlineKeyboardButton("❌ Cancelar",   callback_data="cancelar_flow")],
        ])
        await msg.reply_text("🔄 Qual a frequência?", reply_markup=kb); return

    # Estado desconhecido → fallback para AI
    await _extrair_tx_from_msg(msg, context, texto)

async def _extrair_tx_from_msg(msg, context, texto: str):
    await msg.reply_text("🧠 Analisando...")
    try:
        dados = await extractor.extrair(texto, datetime.now())
        if dados:
            if isinstance(dados, list):
                for d in dados:
                    await _pedir_confirmacao_msg(msg, context, d)
            else:
                await _pedir_confirmacao_msg(msg, context, dados)
        else:
            await msg.reply_text(
                "🤔 Não identifiquei uma transação. Use /menu para gerenciar suas finanças.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📱 Menu", callback_data="menu_principal")]]))
    except Exception as e:
        logger.error(f"Erro: {e}")
        await msg.reply_text("❌ Erro. Tente novamente!")

# ── Salvadores ────────────────────────────────────────────────────────
async def _salvar_fixa(msg, context):
    fd   = context.user_data.get("flow_data", {})
    item = {
        "id":              make_id(),
        "nome":            fd.get("nome", ""),
        "valor":           fd.get("valor", 0),
        "dia_vencimento":  fd.get("dia_vencimento"),
        "categoria":       "Contas",
        "ativa":           True,
    }
    await _save_item(msg, context, "fixas", item, "menu_fixas",
                     f"✅ *{item['nome']}* adicionada!\n{fmt_brl(item['valor'])}/mês")

async def _salvar_divida(msg, context):
    fd   = context.user_data.get("flow_data", {})
    item = {
        "id":              make_id(),
        "nome":            fd.get("nome", ""),
        "valor_total":     fd.get("valor_total", 0),
        "valor":           fd.get("valor_total", 0),
        "total_parcelas":  fd.get("total_parcelas", 0),
        "parcelas":        fd.get("parcelas", 0),
        "parcela_atual":   1,
        "valor_parcela":   fd.get("valor_parcela", fd.get("valor_total", 0)),
        "paga":            False,
        "data_inicio":     hoje(),
    }
    pt   = item["total_parcelas"]
    parc = f" em {pt}x" if pt > 0 else ""
    await _save_item(msg, context, "dividas", item, "menu_dividas",
                     f"✅ *{item['nome']}* adicionada!\n{fmt_brl(item['valor_total'])}{parc}")

async def _salvar_meta(msg, context):
    fd   = context.user_data.get("flow_data", {})
    alvo = fd.get("valor_alvo", 0)
    at   = fd.get("valor_atual", 0)
    pct  = (at / alvo * 100) if alvo > 0 else 0
    item = {
        "id":          make_id(),
        "nome":        fd.get("nome", ""),
        "valor_alvo":  alvo,
        "alvo":        alvo,
        "valor_atual": at,
        "atual":       at,
        "categoria":   "Geral",
    }
    await _save_item(msg, context, "metas", item, "menu_metas",
                     f"✅ Meta *{item['nome']}* criada!\n{fmt_brl(at)} / {fmt_brl(alvo)} ({pct:.0f}%)")

async def _salvar_inv(target, context, edit: bool = False):
    fd   = context.user_data.get("flow_data", {})
    item = {
        "id":          make_id(),
        "nome":        fd.get("nome", ""),
        "valor":       fd.get("valor", 0),
        "tipo":        fd.get("tipo", "Outro"),
        "data_inicio": hoje(),
    }
    await _save_item(target, context, "inv", item, "menu_inv",
                     f"✅ *{item['nome']}* adicionado!\n{fmt_brl(item['valor'])} — {item['tipo']}",
                     edit=edit)

async def _salvar_cartao(msg, context):
    fd   = context.user_data.get("flow_data", {})
    item = {
        "id":              make_id(),
        "nome":            fd.get("nome", ""),
        "limite":          fd.get("limite", 0),
        "fechamento":      fd.get("fechamento", 1),
        "dia_fechamento":  fd.get("dia_fechamento", 1),
        "vencimento":      fd.get("vencimento", 10),
        "dia_vencimento":  fd.get("dia_vencimento", 10),
        "cor":             "#3B6FF0",
    }
    await _save_item(msg, context, "cartoes", item, "menu_cartoes",
                     f"✅ Cartão *{item['nome']}* adicionado!\n"
                     f"Lim: {fmt_brl(item['limite'])} | Fecha d.{item['fechamento']} | Vence d.{item['vencimento']}")

async def _salvar_recorr(target, context, edit: bool = False):
    fd   = context.user_data.get("flow_data", {})
    item = {
        "id":         make_id(),
        "nome":       fd.get("nome", ""),
        "valor":      fd.get("valor", 0),
        "frequencia": fd.get("frequencia", "mensal"),
        "tipo":       fd.get("frequencia", "mensal"),
        "categoria":  "Receita",
    }
    await _save_item(target, context, "recorrencias", item, "menu_recorr",
                     f"✅ *{item['nome']}* adicionada!\n{fmt_brl(item['valor'])} — {item['frequencia']}",
                     edit=edit)

# ── Confirmação de transação ──────────────────────────────────────────
async def _pedir_confirmacao(update: Update, context: ContextTypes.DEFAULT_TYPE, dados: dict):
    await _pedir_confirmacao_msg(update.message, context, dados)

async def _pedir_confirmacao_msg(msg, context, dados: dict):
    tipo_emoji = "💸" if dados.get("tipo","").lower() == "gasto" else "💰"
    cat        = dados.get("categoria", "Outros")
    sub        = dados.get("subcategoria", "")
    cat_str    = cat + (f" · {sub}" if sub else "")
    valor      = abs(float(dados.get("valor", 0)))

    txt = f"📋 *Confirma este registro?*\n\n{tipo_emoji} *{fmt_brl(valor)}* em {cat_str}"
    if dados.get("localizacao"):
        txt += f"\n📍 {dados['localizacao']}"
    if dados.get("metodo_pagamento"):
        txt += f"\n💳 {dados['metodo_pagamento']}"
    pt = dados.get("total_parcelas", 0)
    if pt and int(pt) > 1:
        txt += f"\n🔢 Parcelado em *{pt}x*"
    txt += f"\n📅 {dados.get('data',hoje())} às {dados.get('hora','00:00')}"

    context.user_data["pendente"] = dados
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Confirmar", callback_data="confirmar"),
        InlineKeyboardButton("❌ Cancelar",  callback_data="cancelar"),
    ]])
    await msg.reply_text(txt, parse_mode="Markdown", reply_markup=kb)

# ── Handler de áudio ──────────────────────────────────────────────────
async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎤 Recebi seu áudio! Transcrevendo...")
    try:
        voice = update.message.voice or update.message.audio
        file  = await context.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        await update.message.reply_text("🧠 Entendendo o conteúdo...")
        transcricao = await extractor.transcrever_audio(tmp_path)
        os.unlink(tmp_path)

        if not transcricao:
            await update.message.reply_text("❌ Não entendi o áudio. Tente como texto!")
            return

        dados = await extractor.extrair(transcricao, update.message.date)
        if dados:
            if isinstance(dados, list):
                for d in dados:
                    await _pedir_confirmacao(update, context, d)
            else:
                await _pedir_confirmacao(update, context, dados)
        else:
            await update.message.reply_text(
                f"🎤 Entendi: _{transcricao}_\n\nMas não encontrei transação financeira.",
                parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Erro áudio: {e}")
        await update.message.reply_text("❌ Erro no áudio. Tente como texto!")

# ── Dica inteligente ──────────────────────────────────────────────────
def _gerar_dica(dados: dict) -> str:
    cat   = dados.get("categoria", "")
    valor = abs(float(dados.get("valor", 0)))
    if cat == "Alimentação" and valor > 80:
        return "Almoços caros acumulam rápido! Que tal cozinhar em casa 2x por semana?"
    if cat == "Transporte" and valor > 50:
        return "Compare Uber com transporte público para trajetos frequentes!"
    if cat == "Veículo":
        return "Gastos com veículo podem pesar! Acompanhe no dashboard. 🚘"
    if cat == "Investimento":
        return "Ótima decisão investir! Continue construindo seu patrimônio. 📈"
    if cat == "Beleza" and valor > 150:
        return "Autocuidado é essencial! Só fique de olho na frequência. 💅"
    return ""

# ── MAIN ─────────────────────────────────────────────────────────────
def main():
    port = int(os.environ.get("PORT", "8080"))
    web_server.start(port=port)

    logger.info("🚀 Start Finance Bot v7.0 iniciando...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("menu",   cmd_menu))
    app.add_handler(CommandHandler("resumo", cmd_resumo))
    app.add_handler(CommandHandler("ajuda",  cmd_ajuda))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_texto))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO,   handle_audio))
    app.add_handler(CallbackQueryHandler(handle_callback))

    logger.info("✅ Bot v7.0 rodando!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
