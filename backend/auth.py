"""Create account / log in / log out for Campus Customs (Problem 4).

Passwords
    Stored only as salted PBKDF2-HMAC-SHA256 hashes, never as plain text.
    - Seed users use the original 3-part format  pbkdf2_sha256$<salt>$<hex>  (120,000 iterations).
    - New accounts use a 4-part format           pbkdf2_sha256$<iterations>$<salt>$<hex>
      with 600,000 iterations (OWASP recommendation) and a random 16-byte salt.
    Hashes are compared in constant time.

Sessions
    After login the browser gets an HttpOnly cookie holding  <user_id>.<expiry>.<HMAC signature>.
    JavaScript (and therefore injected scripts) can't read it, and it can't be forged
    without SESSION_SECRET from .env.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "campus_customs.db"
load_dotenv(ROOT / ".env")

ALGORITHM = "pbkdf2_sha256"
LEGACY_ITERATIONS = 120_000  # iterations used by the seed database hashes
ITERATIONS = 600_000  # new accounts
MIN_PASSWORD, MAX_PASSWORD = 8, 128  # max length stops very long inputs from slowing the hasher

COOKIE_NAME = "cc_session"
SESSION_SECONDS = 7 * 24 * 3600

MAX_FAILED_LOGINS = 5  # per email within the window below
FAILED_WINDOW_SECONDS = 15 * 60

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_secret = os.getenv("SESSION_SECRET")
if not _secret:
    # Still works, but sessions reset whenever the server restarts.
    print("WARNING: SESSION_SECRET not set in .env; using a temporary random secret.")
    _secret = secrets.token_urlsafe(48)
SESSION_SECRET = _secret.encode()

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------- Password hashing ----------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"{ALGORITHM}${ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    parts = stored.split("$")
    if len(parts) == 3:  # seed format: algorithm$salt$digest
        algorithm, salt, digest = parts
        iterations = LEGACY_ITERATIONS
    elif len(parts) == 4:  # new format: algorithm$iterations$salt$digest
        algorithm, iter_text, salt, digest = parts
        iterations = int(iter_text)
    else:
        return False
    if algorithm != ALGORITHM:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return hmac.compare_digest(candidate, digest)


# A real hash to check against when the email doesn't exist, so a wrong email
# takes as long as a wrong password and response timing doesn't reveal who has an account.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


# ---------- Signed session cookie ----------

def _sign(data: str) -> str:
    sig = hmac.new(SESSION_SECRET, data.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode().rstrip("=")


def make_session_token(user_id: int) -> str:
    data = f"{user_id}.{int(time.time()) + SESSION_SECONDS}"
    return f"{data}.{_sign(data)}"


def read_session_token(token: str | None) -> int | None:
    if not token:
        return None
    try:
        user_id, expires, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(f"{user_id}.{expires}")):
            return None
        if int(expires) < time.time():
            return None
        return int(user_id)
    except ValueError:
        return None


def set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        make_session_token(user_id),
        max_age=SESSION_SECONDS,
        httponly=True,  # not readable from JavaScript
        samesite="lax",  # not sent on cross-site POSTs
        secure=False,  # local http dev; set True when served over https
        path="/",
    )


# ---------- Database ----------

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class PublicUser(BaseModel):
    """What the API returns about a user. Never includes the password hash."""

    id: int
    first_name: str
    last_name: str
    email: str


def to_public(row: sqlite3.Row) -> PublicUser:
    first, last = row["first_name"], row["last_name"]
    if not first:  # older rows may only have the combined name
        first, _, last = (row["name"] or "").partition(" ")
    return PublicUser(id=row["id"], first_name=first or "", last_name=last or "", email=row["email"])


def get_user(user_id: int) -> PublicUser | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, first_name, last_name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    return to_public(row) if row else None


def current_user(request: Request) -> PublicUser | None:
    user_id = read_session_token(request.cookies.get(COOKIE_NAME))
    return get_user(user_id) if user_id else None


# ---------- Failed-login throttle ----------

_failed: dict[str, deque[float]] = defaultdict(deque)


def _recent_failures(email: str) -> deque[float]:
    attempts = _failed[email]
    while attempts and attempts[0] < time.time() - FAILED_WINDOW_SECONDS:
        attempts.popleft()
    return attempts


# ---------- Request models ----------

class SignupRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


# ---------- Routes ----------

@router.post("/signup", response_model=PublicUser, status_code=201)
def signup(body: SignupRequest, response: Response):
    first, last = body.first_name.strip(), body.last_name.strip()
    email = normalize_email(body.email)

    if not first or not last:
        raise HTTPException(400, "Please enter your first and last name.")
    if len(first) > 50 or len(last) > 50:
        raise HTTPException(400, "Names must be 50 characters or fewer.")
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(400, "Please enter a valid email address.")
    if not MIN_PASSWORD <= len(body.password) <= MAX_PASSWORD:
        raise HTTPException(400, f"Password must be {MIN_PASSWORD}–{MAX_PASSWORD} characters.")
    if body.password != body.confirm_password:
        raise HTTPException(400, "Passwords do not match.")
    if body.password.lower() == email:
        raise HTTPException(400, "Password can't be the same as your email.")

    password_hash = hash_password(body.password)
    with connect() as conn:
        if conn.execute("SELECT 1 FROM users WHERE lower(email) = ?", (email,)).fetchone():
            raise HTTPException(409, "An account with that email already exists. Try logging in.")
        cur = conn.execute(
            "INSERT INTO users (name, email, password_hash, first_name, last_name) VALUES (?, ?, ?, ?, ?)",
            (f"{first} {last}", email, password_hash, first, last),
        )
        user_id = cur.lastrowid

    set_session_cookie(response, user_id)
    return PublicUser(id=user_id, first_name=first, last_name=last, email=email)


@router.post("/login", response_model=PublicUser)
def login(body: LoginRequest, response: Response):
    email = normalize_email(body.email)
    failures = _recent_failures(email)
    if len(failures) >= MAX_FAILED_LOGINS:
        raise HTTPException(429, "Too many failed attempts. Please wait 15 minutes and try again.")

    with connect() as conn:
        row = conn.execute(
            "SELECT id, name, first_name, last_name, email, password_hash FROM users WHERE lower(email) = ?",
            (email,),
        ).fetchone()

    password = body.password[:MAX_PASSWORD + 1]
    valid = verify_password(password, row["password_hash"] if row else _DUMMY_HASH) and row is not None
    if not valid:
        failures.append(time.time())
        # Same message whether the email or the password was wrong.
        raise HTTPException(401, "Incorrect email or password.")

    failures.clear()
    set_session_cookie(response, row["id"])
    return to_public(row)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=PublicUser)
def me(request: Request):
    user = current_user(request)
    if user is None:
        raise HTTPException(401, "Not logged in.")
    return user
