"""
START FINANCE — Auth v2.0
Login multi-usuário com JWT.
Usuários configurados via USERS_JSON (env) e/ou registrados via /api/register (arquivo persistente).
"""

import os, json, hashlib, hmac, base64, time, logging, uuid, re, threading, secrets, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict
from functools import wraps
from flask import request, jsonify
import httpx

logger = logging.getLogger(__name__)

# ── Supabase (opcional) — persistent storage ──────────────────────────
_SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
_SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def _sb_headers() -> dict:
    return {
        "apikey":        _SUPABASE_KEY,
        "Authorization": f"Bearer {_SUPABASE_KEY}",
        "Content-Type":  "application/json",
    }

# JWT_SECRET é OBRIGATÓRIO em produção — sem fallback hardcoded
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    # Em desenvolvimento local, usa um segredo temporário com aviso
    JWT_SECRET = "dev-only-" + hashlib.sha256(b"start-finance-dev").hexdigest()
    logger.warning("⚠️  JWT_SECRET não configurado! Use variável de ambiente em produção.")
TOKEN_EXP = 60 * 60 * 24 * 7  # 7 dias

# ── SMTP para recuperação de senha (opcional) ─────────────────────────
_SMTP_HOST = os.environ.get("SMTP_HOST", "")
_SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
_SMTP_USER = os.environ.get("SMTP_USER", "")
_SMTP_PASS = os.environ.get("SMTP_PASS", "")
_SMTP_FROM = os.environ.get("SMTP_FROM", "") or _SMTP_USER
_APP_URL   = os.environ.get("APP_URL", "")

_RESET_TOKENS: dict = {}  # token -> {email, expires}
_RESET_EXP = 60 * 60  # 1 hora

def _enviar_email_reset(to_email: str, reset_url: str) -> bool:
    if not (_SMTP_HOST and _SMTP_USER and _SMTP_PASS):
        return False
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Redefinir sua senha — PenseFinances'
        msg['From']    = _SMTP_FROM
        msg['To']      = to_email
        texto = f"Clique no link para redefinir sua senha:\n{reset_url}\n\nVálido por 1 hora. Se não foi você, ignore."
        html  = f"""<div style="font-family:sans-serif;max-width:480px;margin:auto;padding:32px">
          <h2 style="color:#3B6FF0">PenseFinances</h2>
          <p>Recebemos uma solicitação para redefinir a senha da conta <b>{to_email}</b>.</p>
          <a href="{reset_url}" style="display:inline-block;background:#3B6FF0;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:700;margin:16px 0">Redefinir senha</a>
          <p style="color:#888;font-size:12px">Link válido por 1 hora. Se não foi você, ignore este email.</p>
        </div>"""
        msg.attach(MIMEText(texto, 'plain'))
        msg.attach(MIMEText(html,  'html'))
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as s:
            s.ehlo(); s.starttls(); s.login(_SMTP_USER, _SMTP_PASS)
            s.sendmail(_SMTP_FROM, to_email, msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Email reset falhou: {e}")
        return False

# ── Rate Limiting simples para login (sem dependência externa) ────────
_login_attempts: dict = defaultdict(list)  # ip -> [timestamps]
_LOGIN_MAX     = 10    # tentativas
_LOGIN_WINDOW  = 300   # segundos (5 min)

def _check_rate_limit(ip: str) -> bool:
    """Retorna True se dentro do limite, False se bloqueado."""
    now = time.time()
    attempts = [t for t in _login_attempts[ip] if now - t < _LOGIN_WINDOW]
    _login_attempts[ip] = attempts
    if len(attempts) >= _LOGIN_MAX:
        return False
    _login_attempts[ip].append(now)
    return True

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

# ── Banco de usuários registrados (arquivo persistente) ───────────────
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'users.json')

def _load_db_users() -> list:
    """Carrega usuários registrados: tenta Supabase primeiro, cai em arquivo."""
    if _SUPABASE_URL and _SUPABASE_KEY:
        try:
            url = f"{_SUPABASE_URL}/rest/v1/sf_users?select=*"
            resp = httpx.get(url, headers=_sb_headers(), timeout=5)
            if resp.status_code == 200:
                rows = resp.json()
                # Normaliza campo created_at -> createdAt para compatibilidade interna
                users = []
                for r in rows:
                    u = dict(r)
                    if "created_at" in u and "createdAt" not in u:
                        u["createdAt"] = u.pop("created_at")
                    users.append(u)
                return users
            else:
                logger.warning(f"Supabase _load_db_users HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Supabase _load_db_users falhou, usando arquivo: {e}")

    # Fallback: arquivo local
    try:
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
        if os.path.exists(_DB_PATH):
            with open(_DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Erro ao carregar users.json: {e}")
    return []

def _save_db_users(users: list) -> None:
    """Persiste usuários em arquivo (síncrono) e, em background, no Supabase."""
    # 1. Salva no arquivo local (rápido, síncrono)
    try:
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
        with open(_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Erro ao salvar users.json: {e}")

    # 2. Upsert no Supabase em background (não bloqueia o request)
    if _SUPABASE_URL and _SUPABASE_KEY:
        def _upsert():
            try:
                url = f"{_SUPABASE_URL}/rest/v1/sf_users"
                headers = {**_sb_headers(), "Prefer": "resolution=merge-duplicates"}
                # Mapeia createdAt -> created_at para o schema Supabase
                rows = []
                for u in users:
                    row = dict(u)
                    if "createdAt" in row:
                        row["created_at"] = row.pop("createdAt")
                    rows.append(row)
                resp = httpx.post(url, headers=headers, json=rows, timeout=10)
                if resp.status_code not in (200, 201):
                    logger.warning(f"Supabase _save_db_users HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                logger.warning(f"Supabase _save_db_users falhou: {e}")
        _upsert()


# ── Usuários ──────────────────────────────────────────────────────────
def get_users() -> list:
    """Retorna todos os usuários: env var (prioridade) + arquivo persistente."""
    env_users = []
    raw = os.environ.get("USERS_JSON", "")
    if raw:
        try:
            env_users = json.loads(raw)
        except Exception:
            pass

    # Usuários registrados via API (arquivo persistente)
    db_users = _load_db_users()

    # Mescla: env_users têm prioridade por email
    env_emails = {u["email"].lower() for u in env_users}
    merged = list(env_users)
    for u in db_users:
        if u["email"].lower() not in env_emails:
            merged.append(u)

    return merged


# ── Hashing de senha ──────────────────────────────────────────────────
def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def _is_hash(s: str) -> bool:
    """Verifica se a string é um SHA-256 hex (64 chars)."""
    return isinstance(s, str) and len(s) == 64 and all(c in '0123456789abcdef' for c in s.lower())


# ── JWT simples (sem dependência externa) ─────────────────────────────
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

def _b64d(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + '=' * (pad % 4))

def gerar_token(user: dict) -> str:
    header  = _b64(json.dumps({"alg":"HS256","typ":"JWT"}).encode())
    payload = _b64(json.dumps({
        "sub":   user["id"],
        "name":  user["name"],
        "email": user["email"],
        "avatar":user.get("avatar","🙂"),
        "color": user.get("color","#3B6FF0"),
        "iat":   int(time.time()),
        "exp":   int(time.time()) + TOKEN_EXP,
    }).encode())
    sig = _b64(hmac.new(
        JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256
    ).digest())
    return f"{header}.{payload}.{sig}"

def verificar_token(token: str) -> dict | None:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header, payload, sig = parts
        expected = _b64(hmac.new(
            JWT_SECRET.encode(), f"{header}.{payload}".encode(), hashlib.sha256
        ).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_b64d(payload))
        if data.get("exp", 0) < time.time():
            return None
        return data
    except Exception:
        return None


# ── Autenticação ──────────────────────────────────────────────────────
def _check_password(stored: str, received: str) -> bool:
    """Verifica senha: suporta hash-vs-hash e plaintext-vs-hash."""
    if _is_hash(stored):
        return stored == received or _sha256(received) == stored
    else:
        return stored == received or (_is_hash(received) and _sha256(stored) == received)

def autenticar(email: str, password: str) -> dict | None:
    """
    Verifica senha com prioridade para db_users (permite reset sobrescrever env var).
    Suporta senhas plaintext (env var) e SHA-256 hasheadas (API).
    """
    email = email.lower()
    # db_users têm prioridade — assim o reset de senha sempre funciona
    for u in _load_db_users():
        if u["email"].lower() == email and _check_password(u["password"], password):
            return u
    # Fallback: env var users (apenas se não existe entrada em db_users)
    db_emails = {u["email"].lower() for u in _load_db_users()}
    raw = os.environ.get("USERS_JSON", "")
    if raw:
        try:
            for u in json.loads(raw):
                if u["email"].lower() == email and u["email"].lower() not in db_emails:
                    if _check_password(u["password"], password):
                        return u
        except Exception:
            pass
    return None


# ── Decorator para rotas protegidas ───────────────────────────────────
def requer_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        if not token:
            token = request.args.get("token")
        if not token:
            return jsonify({"erro": "Token não fornecido", "auth": False}), 401
        payload = verificar_token(token)
        if not payload:
            return jsonify({"erro": "Token inválido ou expirado", "auth": False}), 401
        request.user = payload
        return f(*args, **kwargs)
    return decorated


# ── Endpoints de auth (adicionar ao web_server) ───────────────────────
def registrar_rotas_auth(app, sheets_factory=None):

    @app.route("/api/login", methods=["POST"])
    def login():
        try:
            # Rate limiting por IP
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
            if not _check_rate_limit(ip):
                return jsonify({"erro": "Muitas tentativas. Aguarde 5 minutos."}), 429

            dados = request.json or {}
            email    = (dados.get("email", "") or "").strip().lower()
            password = (dados.get("password", "") or "").strip()
            if not email or not password:
                return jsonify({"erro": "Email e senha obrigatórios"}), 400
            user = autenticar(email, password)
            if not user:
                return jsonify({"erro": "Email ou senha incorretos"}), 401
            token = gerar_token(user)
            return jsonify({
                "token": token,
                "user": {
                    "id":     user["id"],
                    "name":   user["name"],
                    "email":  user["email"],
                    "avatar": user.get("avatar", "🙂"),
                    "color":  user.get("color", "#3B6FF0"),
                }
            })
        except Exception as e:
            logger.error(f"❌ Login: {e}")
            return jsonify({"erro": str(e)}), 500

    @app.route("/api/register", methods=["POST"])
    def register():
        """Registra novo usuário — persiste em arquivo para sync entre dispositivos.
        Aceita client_id para re-registro silencioso quando o servidor perdeu os dados."""
        try:
            dados     = request.json or {}
            nome      = (dados.get("name",      "") or "").strip()
            email     = (dados.get("email",     "") or "").strip().lower()
            password  = (dados.get("password",  "") or "").strip()
            avatar    = (dados.get("avatar",    "🙂") or "🙂")
            cor       = (dados.get("color",     "#3B6FF0") or "#3B6FF0")
            client_id = (dados.get("client_id", "") or "").strip()

            if not nome or not email or not password:
                return jsonify({"erro": "Nome, email e senha são obrigatórios"}), 400
            if not _EMAIL_RE.match(email):
                return jsonify({"erro": "Email inválido"}), 400
            if len(password) < 6 and not _is_hash(password):
                return jsonify({"erro": "Senha deve ter pelo menos 6 caracteres"}), 400
            nome = nome[:80].replace("<","").replace(">","").replace("&","").strip()

            # Verifica se email já existe
            all_users = get_users()
            existing = next((u for u in all_users if u["email"].lower() == email), None)
            if existing:
                # Email já cadastrado — verifica se a senha bate antes de emitir token
                incoming_hash = password if _is_hash(password) else _sha256(password)
                stored_hash   = existing.get("password", "")
                if not stored_hash or incoming_hash != stored_hash:
                    return jsonify({"erro": "Email já cadastrado. Use a tela de login."}), 409
                # Senha correta — re-registro silencioso (ex: novo dispositivo)
                token = gerar_token(existing)
                logger.info(f"↩️ Re-registro silencioso (senha ok): {email}")
                return jsonify({
                    "token": token,
                    "user": {
                        "id":     existing["id"],
                        "name":   existing["name"],
                        "email":  existing["email"],
                        "avatar": existing.get("avatar","🙂"),
                        "color":  existing.get("color","#3B6FF0"),
                    }
                }), 200

            # Garante que a senha seja armazenada como hash
            pwd_hash = password if _is_hash(password) else _sha256(password)

            # Usa client_id do frontend para preservar keys de dados locais
            user_id = client_id if (client_id and len(client_id) > 4) else \
                      "u_" + str(int(time.time() * 1000)) + "_" + uuid.uuid4().hex[:8]

            new_user = {
                "id":        user_id,
                "name":      nome,
                "email":     email,
                "password":  pwd_hash,
                "avatar":    avatar,
                "color":     cor,
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            # Persiste no arquivo
            db_users = _load_db_users()
            db_users.append(new_user)
            _save_db_users(db_users)

            token = gerar_token(new_user)
            logger.info(f"✅ Novo usuário registrado: {email}")
            return jsonify({
                "token": token,
                "user": {
                    "id":     new_user["id"],
                    "name":   new_user["name"],
                    "email":  new_user["email"],
                    "avatar": new_user["avatar"],
                    "color":  new_user["color"],
                }
            }), 201
        except Exception as e:
            logger.error(f"❌ Register: {e}")
            return jsonify({"erro": str(e)}), 500

    @app.route("/api/me")
    def me():
        token = request.headers.get("Authorization","").replace("Bearer ","")
        payload = verificar_token(token)
        if not payload:
            return jsonify({"auth": False}), 401
        return jsonify({"auth": True, "user": payload})

    @app.route("/api/users")
    def list_users():
        """Lista usuários sem senhas (para admin)."""
        token = request.headers.get("Authorization","").replace("Bearer ","")
        if not verificar_token(token):
            return jsonify({"erro": "Não autorizado"}), 401
        users = [{"id":u["id"],"name":u["name"],"email":u["email"],"avatar":u.get("avatar"),"color":u.get("color")} for u in get_users()]
        return jsonify({"users": users})

    @app.route("/api/forgot-password", methods=["POST"])
    def forgot_password():
        dados = request.json or {}
        email = (dados.get("email", "") or "").strip().lower()
        if not email:
            return jsonify({"erro": "Email obrigatório"}), 400
        users = get_users()
        user  = next((u for u in users if u["email"].lower() == email), None)
        if not user:
            return jsonify({"erro": "Não existe uma conta cadastrada com este email"}), 404
        token    = secrets.token_urlsafe(32)
        _RESET_TOKENS[token] = {"email": email, "expires": time.time() + _RESET_EXP}
        base_url  = _APP_URL or request.host_url.rstrip('/')
        reset_url = f"{base_url}/?reset={token}"
        sent = _enviar_email_reset(email, reset_url)
        if not sent:
            logger.warning(f"Reset solicitado: {email} | SMTP não configurado | URL: {reset_url}")
        else:
            logger.info(f"Reset solicitado: {email} | email enviado")
        return jsonify({"ok": True}), 200

    @app.route("/api/reset-password", methods=["POST"])
    def reset_password():
        dados    = request.json or {}
        token    = (dados.get("token", "") or "").strip()
        password = (dados.get("password", "") or "").strip()
        if not token or not password:
            return jsonify({"erro": "Token e senha obrigatórios"}), 400
        if len(password) < 6 and not _is_hash(password):
            return jsonify({"erro": "Senha deve ter pelo menos 6 caracteres"}), 400
        td = _RESET_TOKENS.get(token)
        if not td or td["expires"] < time.time():
            return jsonify({"erro": "Link inválido ou expirado"}), 400
        email    = td["email"]
        pwd_hash = password if _is_hash(password) else _sha256(password)
        db_users = _load_db_users()
        updated  = False
        for u in db_users:
            if u["email"].lower() == email:
                u["password"] = pwd_hash
                updated = True
                break
        if not updated:
            # Usuário existe apenas no env var — adiciona ao db para sobrescrever
            all_users = get_users()
            original  = next((u for u in all_users if u["email"].lower() == email), None)
            if original:
                db_users.append({**original, "password": pwd_hash})
                updated = True
        if updated:
            _save_db_users(db_users)
        del _RESET_TOKENS[token]
        logger.info(f"Senha redefinida: {email}")
        return jsonify({"ok": True}), 200
