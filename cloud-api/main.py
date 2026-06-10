import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional


from fastapi import Cookie, Depends, FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr

from database import get_connection, init_db
from security import (
    create_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)


BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads" / "events"

SESSION_COOKIE_NAME = "watchtower_session"
SESSION_DAYS = 7

# For local development, keep False.
# On EC2 with HTTPS, change to True.
COOKIE_SECURE = False


app = FastAPI(title="Watchtower Cloud API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.1.148:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------
# Models
# --------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CreateSystemRequest(BaseModel):
    name: str
    location: Optional[str] = None
    api_base_url: Optional[str] = None


class CreateEventRequest(BaseModel):
    system_id: int
    event_type: str
    label: Optional[str] = None
    confidence: Optional[float] = None
    track_id: Optional[int] = None
    metadata: Optional[dict] = None


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_expiry_iso() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)).isoformat()


def row_to_dict(row):
    if row is None:
        return None

    return dict(row)


def get_current_user(
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token_hash = hash_session_token(session_token)

    conn = get_connection()

    row = conn.execute(
        """
        SELECT users.id, users.email, users.created_at, users.last_login_at
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.session_token_hash = ?
          AND sessions.revoked_at IS NULL
          AND sessions.expires_at > ?
        """,
        (token_hash, now_iso()),
    ).fetchone()

    conn.close()

    if row is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    return row_to_dict(row)


def ensure_user_owns_system(user_id: int, system_id: int):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM systems
        WHERE id = ?
          AND owner_user_id = ?
        """,
        (system_id, user_id),
    ).fetchone()

    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="System not found")

    return row_to_dict(row)


# --------------------------------------------------
# Auth routes
# --------------------------------------------------

@app.post("/api/auth/register")
def register(req: RegisterRequest, response: Response):
    email = req.email.lower().strip()
    password = req.password

    if len(password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters",
        )

    conn = get_connection()

    existing = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        (email,),
    ).fetchone()

    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")

    password_hash = hash_password(password)
    created_at = now_iso()

    cursor = conn.execute(
        """
        INSERT INTO users (email, password_hash, created_at)
        VALUES (?, ?, ?)
        """,
        (email, password_hash, created_at),
    )

    user_id = cursor.lastrowid

    # Create default system for this user.
    conn.execute(
        """
        INSERT INTO systems (
            owner_user_id,
            name,
            location,
            api_base_url,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            "Watchtower Pi 01",
            "Home Lab",
            "http://192.168.1.148:8000",
            "unknown",
            created_at,
        ),
    )

    token = create_session_token()
    token_hash = hash_session_token(token)

    conn.execute(
        """
        INSERT INTO sessions (
            user_id,
            session_token_hash,
            created_at,
            expires_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (user_id, token_hash, created_at, session_expiry_iso()),
    )

    conn.commit()
    conn.close()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_DAYS * 24 * 60 * 60,
        path="/",
    )

    return {
        "ok": True,
        "user": {
            "id": user_id,
            "email": email,
        },
    }


@app.post("/api/auth/login")
def login(req: LoginRequest, response: Response):
    email = req.email.lower().strip()
    password = req.password

    conn = get_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        """,
        (email,),
    ).fetchone()

    if user is None:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = row_to_dict(user)

    if not verify_password(password, user["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_session_token()
    token_hash = hash_session_token(token)
    created_at = now_iso()

    conn.execute(
        """
        INSERT INTO sessions (
            user_id,
            session_token_hash,
            created_at,
            expires_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (user["id"], token_hash, created_at, session_expiry_iso()),
    )

    conn.execute(
        """
        UPDATE users
        SET last_login_at = ?
        WHERE id = ?
        """,
        (created_at, user["id"]),
    )

    conn.commit()
    conn.close()

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=SESSION_DAYS * 24 * 60 * 60,
        path="/",
    )

    return {
        "ok": True,
        "user": {
            "id": user["id"],
            "email": user["email"],
        },
    }


@app.post("/api/auth/logout")
def logout(
    response: Response,
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
):
    if session_token:
        token_hash = hash_session_token(session_token)

        conn = get_connection()
        conn.execute(
            """
            UPDATE sessions
            SET revoked_at = ?
            WHERE session_token_hash = ?
            """,
            (now_iso(), token_hash),
        )
        conn.commit()
        conn.close()

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
    )

    return {"ok": True}


@app.get("/api/auth/me")
def me(user=Depends(get_current_user)):
    return {
        "ok": True,
        "user": user,
    }


# --------------------------------------------------
# Systems routes
# --------------------------------------------------

@app.get("/api/systems")
def list_systems(user=Depends(get_current_user)):
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM systems
        WHERE owner_user_id = ?
        ORDER BY id ASC
        """,
        (user["id"],),
    ).fetchall()

    conn.close()

    return {
        "ok": True,
        "systems": [row_to_dict(row) for row in rows],
    }


@app.post("/api/systems")
def create_system(req: CreateSystemRequest, user=Depends(get_current_user)):
    conn = get_connection()

    created_at = now_iso()

    cursor = conn.execute(
        """
        INSERT INTO systems (
            owner_user_id,
            name,
            location,
            api_base_url,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user["id"],
            req.name,
            req.location,
            req.api_base_url,
            "unknown",
            created_at,
        ),
    )

    conn.commit()

    system_id = cursor.lastrowid

    row = conn.execute(
        """
        SELECT *
        FROM systems
        WHERE id = ?
        """,
        (system_id,),
    ).fetchone()

    conn.close()

    return {
        "ok": True,
        "system": row_to_dict(row),
    }


@app.get("/api/systems/{system_id}")
def get_system(system_id: int, user=Depends(get_current_user)):
    system = ensure_user_owns_system(user["id"], system_id)

    return {
        "ok": True,
        "system": system,
    }


# --------------------------------------------------
# Events routes
# --------------------------------------------------

@app.get("/api/systems/{system_id}/events")
def list_events(system_id: int, user=Depends(get_current_user)):
    ensure_user_owns_system(user["id"], system_id)

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM events
        WHERE system_id = ?
        ORDER BY created_at DESC
        LIMIT 100
        """,
        (system_id,),
    ).fetchall()

    conn.close()

    events = []

    for row in rows:
        event = row_to_dict(row)
        event["has_image"] = bool(event.get("image_path"))
        events.append(event)

    return {
        "ok": True,
        "events": events,
    }


@app.post("/api/events")
def create_event(req: CreateEventRequest, user=Depends(get_current_user)):
    ensure_user_owns_system(user["id"], req.system_id)

    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO events (
            system_id,
            event_type,
            label,
            confidence,
            track_id,
            image_path,
            metadata_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            req.system_id,
            req.event_type,
            req.label,
            req.confidence,
            req.track_id,
            None,
            json.dumps(req.metadata or {}),
            now_iso(),
        ),
    )

    conn.commit()

    event_id = cursor.lastrowid

    row = conn.execute(
        """
        SELECT *
        FROM events
        WHERE id = ?
        """,
        (event_id,),
    ).fetchone()

    conn.close()

    return {
        "ok": True,
        "event": row_to_dict(row),
    }


@app.post("/api/events/with-image")
def create_event_with_image(
    system_id: int = Form(...),
    event_type: str = Form(...),
    label: Optional[str] = Form(None),
    confidence: Optional[float] = Form(None),
    track_id: Optional[int] = Form(None),
    metadata_json: Optional[str] = Form("{}"),
    image: UploadFile = File(...),
    user=Depends(get_current_user),
):
    ensure_user_owns_system(user["id"], system_id)

    if image.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="Only JPEG and PNG images are allowed")

    created_at = now_iso()

    conn = get_connection()

    cursor = conn.execute(
        """
        INSERT INTO events (
            system_id,
            event_type,
            label,
            confidence,
            track_id,
            image_path,
            metadata_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            system_id,
            event_type,
            label,
            confidence,
            track_id,
            None,
            metadata_json or "{}",
            created_at,
        ),
    )

    event_id = cursor.lastrowid

    extension = ".jpg" if image.content_type == "image/jpeg" else ".png"
    filename = f"event_{event_id}{extension}"
    relative_path = f"uploads/events/{filename}"
    absolute_path = BASE_DIR / relative_path

    with absolute_path.open("wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    conn.execute(
        """
        UPDATE events
        SET image_path = ?
        WHERE id = ?
        """,
        (relative_path, event_id),
    )

    conn.commit()

    row = conn.execute(
        """
        SELECT *
        FROM events
        WHERE id = ?
        """,
        (event_id,),
    ).fetchone()

    conn.close()

    return {
        "ok": True,
        "event": row_to_dict(row),
    }


@app.get("/api/events/{event_id}")
def get_event(event_id: int, user=Depends(get_current_user)):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT events.*
        FROM events
        JOIN systems ON systems.id = events.system_id
        WHERE events.id = ?
          AND systems.owner_user_id = ?
        """,
        (event_id, user["id"]),
    ).fetchone()

    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")

    event = row_to_dict(row)
    event["has_image"] = bool(event.get("image_path"))

    return {
        "ok": True,
        "event": event,
    }


@app.get("/api/events/{event_id}/image")
def get_event_image(event_id: int, user=Depends(get_current_user)):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT events.image_path
        FROM events
        JOIN systems ON systems.id = events.system_id
        WHERE events.id = ?
          AND systems.owner_user_id = ?
        """,
        (event_id, user["id"]),
    ).fetchone()

    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")

    image_path = row["image_path"]

    if not image_path:
        raise HTTPException(status_code=404, detail="Event has no image")

    absolute_path = BASE_DIR / image_path

    if not absolute_path.exists():
        raise HTTPException(status_code=404, detail="Image file missing")

    return FileResponse(absolute_path)


@app.post("/api/events/{event_id}/reviewed")
def mark_event_reviewed(event_id: int, user=Depends(get_current_user)):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT events.id
        FROM events
        JOIN systems ON systems.id = events.system_id
        WHERE events.id = ?
          AND systems.owner_user_id = ?
        """,
        (event_id, user["id"]),
    ).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Event not found")

    conn.execute(
        """
        UPDATE events
        SET reviewed = 1
        WHERE id = ?
        """,
        (event_id,),
    )

    conn.commit()
    conn.close()

    return {"ok": True}


@app.post("/api/dev/events/with-image")
def dev_create_event_with_image(
    system_id: int = Form(...),
    event_type: str = Form(...),
    label: Optional[str] = Form(None),
    confidence: Optional[float] = Form(None),
    track_id: Optional[int] = Form(None),
    metadata_json: Optional[str] = Form("{}"),
    image: UploadFile = File(...),
):
    """
    Temporary local development endpoint.

    This lets the Pi upload events without login/device security.
    Later replace with /api/device/events/with-image.
    """

    if image.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(
            status_code=400,
            detail="Only JPEG and PNG images are allowed",
        )

    created_at = now_iso()

    conn = get_connection()

    system = conn.execute(
        """
        SELECT *
        FROM systems
        WHERE id = ?
        """,
        (system_id,),
    ).fetchone()

    if system is None:
        conn.close()
        raise HTTPException(status_code=404, detail="System not found")

    cursor = conn.execute(
        """
        INSERT INTO events (
            system_id,
            event_type,
            label,
            confidence,
            track_id,
            image_path,
            metadata_json,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            system_id,
            event_type,
            label,
            confidence,
            track_id,
            None,
            metadata_json or "{}",
            created_at,
        ),
    )

    event_id = cursor.lastrowid

    extension = ".jpg" if image.content_type == "image/jpeg" else ".png"
    filename = f"event_{event_id}{extension}"
    relative_path = f"uploads/events/{filename}"
    absolute_path = BASE_DIR / relative_path

    with absolute_path.open("wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    conn.execute(
        """
        UPDATE events
        SET image_path = ?
        WHERE id = ?
        """,
        (relative_path, event_id),
    )

    conn.commit()

    row = conn.execute(
        """
        SELECT *
        FROM events
        WHERE id = ?
        """,
        (event_id,),
    ).fetchone()

    conn.close()

    return {
        "ok": True,
        "event": row_to_dict(row),
    }