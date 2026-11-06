"""Acceso a datos con SQLite (incluido en Python, sin instalar nada)."""
from __future__ import annotations

import secrets
import sqlite3
from datetime import date, datetime, timedelta

from flask import current_app, g

ESQUEMA = """
CREATE TABLE IF NOT EXISTS reservas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT    NOT NULL UNIQUE,
    servicio_id TEXT    NOT NULL,
    inicio      TEXT    NOT NULL,          -- ISO 8601, hora local del negocio
    fin         TEXT    NOT NULL,
    nombre      TEXT    NOT NULL,
    email       TEXT    NOT NULL,
    telefono    TEXT    NOT NULL,
    personas    INTEGER NOT NULL,
    comentario  TEXT    NOT NULL DEFAULT '',
    estado      TEXT    NOT NULL DEFAULT 'confirmada',  -- confirmada | cancelada | asistio | no_asistio
    creada      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reservas_inicio ON reservas (inicio);
"""
ESTADOS_ACTIVOS = ("confirmada", "asistio", "no_asistio")


def conexion() -> sqlite3.Connection:
    if "db" not in g:
        # autocommit: las transacciones se controlan explícitamente con BEGIN/COMMIT
        g.db = sqlite3.connect(current_app.config["BASE_DATOS"], isolation_level=None)
        g.db.row_factory = sqlite3.Row
    return g.db


def cerrar(_=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def inicializar(ruta: str) -> None:
    with sqlite3.connect(ruta) as db:
        db.executescript(ESQUEMA)


def ocupados_del_dia(dia: date) -> list[tuple[datetime, datetime]]:
    desde, hasta = dia.isoformat(), (dia + timedelta(days=1)).isoformat()
    filas = conexion().execute(
        f"SELECT inicio, fin FROM reservas WHERE inicio >= ? AND inicio < ? "
        f"AND estado IN ({','.join('?' * len(ESTADOS_ACTIVOS))})",
        (desde, hasta, *ESTADOS_ACTIVOS),
    ).fetchall()
    return [(datetime.fromisoformat(f["inicio"]), datetime.fromisoformat(f["fin"])) for f in filas]


def crear_reserva(datos: dict, ahora: datetime) -> str:
    """Inserta la reserva en una transacción exclusiva para evitar dobles reservas simultáneas."""
    db = conexion()
    codigo = secrets.token_hex(3).upper()  # ej. "A3F9C1"
    db.execute("BEGIN IMMEDIATE")
    try:
        choque = db.execute(
            f"SELECT 1 FROM reservas WHERE inicio < ? AND fin > ? "
            f"AND estado IN ({','.join('?' * len(ESTADOS_ACTIVOS))}) LIMIT 1",
            (datos["fin"].isoformat(), datos["inicio"].isoformat(), *ESTADOS_ACTIVOS),
        ).fetchone()
        if choque:
            raise ValueError("Ese horario acaba de ser reservado por otra persona. Elige otro, por favor.")
        db.execute(
            "INSERT INTO reservas (codigo, servicio_id, inicio, fin, nombre, email, telefono, personas, comentario, creada) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (codigo, datos["servicio_id"], datos["inicio"].isoformat(), datos["fin"].isoformat(),
             datos["nombre"], datos["email"], datos["telefono"], datos["personas"], datos["comentario"],
             ahora.isoformat(timespec="seconds")),
        )
        db.execute("COMMIT")
    except Exception:
        db.execute("ROLLBACK")
        raise
    return codigo


def buscar_reserva(codigo: str, email: str) -> sqlite3.Row | None:
    return conexion().execute(
        "SELECT * FROM reservas WHERE codigo = ? AND lower(email) = lower(?)", (codigo.upper().strip(), email.strip())
    ).fetchone()


def reservas_entre(desde: date, hasta: date) -> list[sqlite3.Row]:
    return conexion().execute(
        "SELECT * FROM reservas WHERE inicio >= ? AND inicio < ? ORDER BY inicio",
        (desde.isoformat(), (hasta + timedelta(days=1)).isoformat()),
    ).fetchall()


def cambiar_estado(reserva_id: int, estado: str) -> None:
    conexion().execute("UPDATE reservas SET estado = ? WHERE id = ?", (estado, reserva_id))
