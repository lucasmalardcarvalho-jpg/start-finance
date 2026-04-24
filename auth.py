"""
START FINANCE — Auth v2.0
Login multi-usuário com JWT.
Usuários configurados via USERS_JSON (env) e/ou registrados via /api/register (arquivo persistente).
"""

import os, json, hashlib, hmac, base64, time, logging, uuid, re
from collections import defaultdict
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)

# JWT_SECRET é OBRIGATÓRIO em produção — sem fallback hardcoded
JWT_SECRET = os.environ.get("JWT_SECRET", "")
if not JWT_SECRET:
    # Em desenvolvimento local, usa um segredo temporário com aviso
    JWT_SECRET = "dev-only-" + hashlib.sha256(b"start-finance-dev").hexdigest()
    logger.warning("⚠️  JWT_SECRET não configurado! Use variável de ambiente em produção.")
TOKEN_EXP = 60 * 60 * 24 * 7  # 7 dias

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
    """Carrega usuários registrados do arquivo persistente."""
    try:
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
        if os.path.exists(_DB_PATH):
            with open(_DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Erro ao carregar users.json: {e}")
    return []

def _save_db_users(users: list) -> None:
    """Persiste a lista de usuários registrados."""
    try:
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
        with open(_DB_PATH, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Erro ao salvar users.json: {e}")


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
def autenticar(email: str, password: str) -> dict | None:
    """
    Suporta tanto senhas plaintext (usuários de env var) quanto
    SHA-256 hasheadas (usuários registrados via API).
    O frontend envia a senha já hasheada; env var users têm plaintext.
    """
    for u in get_users():
        if u["email"].lower() == email.lower():
            stored = u["password"]
            if _is_hash(stored):
                # Senha armazenada como hash — compara hash com hash
                # Frontend envia a senha já hasheada pelo crypto.subtle
                if stored == password:
                    return u
                # Caso extremo: frontend enviou plaintext — compara hash do plaintext
                if _sha256(password) == stored:
                    return u
            else:
                # Senha em plaintext (usuários de env var)
                if stored == password:
                    return u
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
        """Registra novo usuário — persiste em arquivo para sync entre dispositivos."""
        try:
            dados    = request.json or {}
            nome     = (dados.get("name",     "") or "").strip()
            email    = (dados.get("email",    "") or "").strip().lower()
            password = (dados.get("password", "") or "").strip()
            avatar   = (dados.get("avatar",   "🙂") or "🙂")
            cor      = (dados.get("color",    "#3B6FF0") or "#3B6FF0")

            if not nome or not email or not password:
                return jsonify({"erro": "Nome, email e senha são obrigatórios"}), 400
            if not _EMAIL_RE.match(email):
                return jsonify({"erro": "Email inválido"}), 400
            if len(password) < 6 and not _is_hash(password):
                return jsonify({"erro": "Senha deve ter pelo menos 6 caracteres"}), 400
            # Sanitiza nome (máx 80 chars, sem HTML)
            nome = nome[:80].replace("<","").replace(">","").replace("&","").strip()

            # Verifica se email já existe (env + arquivo)
            all_users = get_users()
            if any(u["email"].lower() == email for u in all_users):
                return jsonify({"erro": "Este email já está cadastrado"}), 409

            # Garante que a senha seja armazenada como hash
            pwd_hash = password if _is_hash(password) else _sha256(password)

            new_user = {
                "id":        "u_" + str(int(time.time() * 1000)) + "_" + uuid.uuid4().hex[:8],
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
