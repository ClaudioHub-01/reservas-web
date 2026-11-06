"""Protección CSRF mínima para formularios y control de acceso al panel."""
from __future__ import annotations

import hmac
import secrets
from functools import wraps

from flask import abort, redirect, request, session, url_for


def token_csrf() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def verificar_csrf() -> None:
    """Se ejecuta antes de cada POST: el formulario debe traer el token de la sesión."""
    if request.method == "POST":
        enviado = request.form.get("csrf", "")
        if not enviado or not hmac.compare_digest(enviado, session.get("csrf", "")):
            abort(400, "La sesión expiró. Vuelve a cargar la página e inténtalo de nuevo.")


def requiere_admin(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin.login", siguiente=request.path))
        return vista(*args, **kwargs)

    return envoltura
