"""
START FINANCE — Auth v1.0
Login multi-usuário com JWT.
Usuários configurados via variável de ambiente USERS_JSON ou padrão.
"""

import os, json, hashlib, hmac, base64, time, logging
from functools import wraps
from flask import request, jsonify

logger = logging.getLogger(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "start-finance-secret-2026")
TOKEN_EXP   = 60 * 60 * 24 * 7  # 7 dias

# ── Usuários ──────────────────────────────────────────────────────────
# Configure via env var USERS_JSON:
# '[{"id":"1","name":"Lucas","email":"lucas@pense.com","password":"senha123","avatar":"🧑‍💼"}]'
def get_users() -> list:
    raw = os.environ.get("USERS_JSON", "")
    if raw:
        try:
            return json.loads(raw)
        except Exception:
            pass
    # Usuário padrão de desenvolvimento
    return [
        {"id": "1", "name": "Lucas",  "email": "lucas@startfinance.com",  "password": "start123", "avatar": "🧑‍💼", "color": "#3B6FF0"},
        {"id": "2", "name": "Hellen", "email": "hellen@startfinance.com", "password": "start123", "avatar": "👩‍💼", "color": "#EC4899"},
    ]


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
    for u in get_users():
        if u["email"].lower() == email.lower() and u["password"] == password:
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
            dados = request.json or {}
            email    = (dados.get("email", "") or "").strip()
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
