"""Páginas para clientes: ver servicios, reservar, consultar y cancelar."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from . import correo, db
from .disponibilidad import bloques_del_dia, es_horario_valido, horarios_disponibles

bp = Blueprint("publico", __name__)
PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")
HORAS_MINIMAS_CANCELAR = 2


def _negocio() -> dict:
    return current_app.config["NEGOCIO"]


def _ahora() -> datetime:
    return current_app.config["AHORA"]()


def _servicio(servicio_id: str) -> dict:
    servicio = _negocio()["servicios_por_id"].get(servicio_id)
    if not servicio:
        abort(404)
    return servicio


def _dias_abiertos() -> list[date]:
    hoy = _ahora().date()
    dias = (hoy + timedelta(days=i) for i in range(_negocio()["dias_anticipacion"] + 1))
    return [d for d in dias if bloques_del_dia(_negocio(), d)]


@bp.get("/")
def inicio():
    return render_template("inicio.html", servicios=_negocio()["servicios"])


@bp.get("/api/horarios")
def api_horarios():
    servicio = _servicio(request.args.get("servicio", ""))
    try:
        dia = date.fromisoformat(request.args.get("fecha", ""))
    except ValueError:
        return jsonify(error="Fecha inválida"), 400
    libres = horarios_disponibles(_negocio(), dia, servicio["duracion"], db.ocupados_del_dia(dia), _ahora())
    return jsonify(horarios=[h.strftime("%H:%M") for h in libres])


@bp.route("/reservar/<servicio_id>", methods=["GET", "POST"])
def reservar(servicio_id: str):
    servicio = _servicio(servicio_id)
    formulario = request.form.to_dict() if request.method == "POST" else {}
    if request.method == "POST":
        errores, datos = _validar(formulario, servicio)
        if not errores:
            try:
                codigo = db.crear_reserva(datos, _ahora())
            except ValueError as exc:
                errores.append(str(exc))
            else:
                _enviar_confirmacion(datos, servicio, codigo)
                session["ultima_reserva"] = {"codigo": codigo, "email": datos["email"]}
                return redirect(url_for("publico.confirmacion"))
        for e in errores:
            flash(e, "error")
    return render_template("reservar.html", servicio=servicio, dias=_dias_abiertos(), form=formulario)


def _validar(f: dict, servicio: dict) -> tuple[list[str], dict]:
    errores = []
    nombre = f.get("nombre", "").strip()
    email = f.get("email", "").strip().lower()
    telefono = re.sub(r"[^\d+]", "", f.get("telefono", ""))
    if len(nombre) < 3:
        errores.append("Ingresa tu nombre completo.")
    if not PATRON_EMAIL.match(email):
        errores.append("El correo no es válido.")
    if len(telefono) < 8:
        errores.append("Ingresa un teléfono válido.")
    try:
        personas = int(f.get("personas", "0"))
    except ValueError:
        personas = 0
    if not 1 <= personas <= servicio["max_personas"]:
        errores.append(f"La cantidad de personas debe estar entre 1 y {servicio['max_personas']}.")
    try:
        inicio = datetime.fromisoformat(f"{f.get('fecha', '')}T{f.get('hora', '')}")
    except ValueError:
        errores.append("Elige una fecha y un horario.")
        return errores, {}
    ocupados = db.ocupados_del_dia(inicio.date())
    if not es_horario_valido(_negocio(), inicio, servicio["duracion"], ocupados, _ahora()):
        errores.append("Ese horario ya no está disponible. Elige otro, por favor.")
    datos = {
        "servicio_id": servicio["id"], "inicio": inicio, "fin": inicio + timedelta(minutes=servicio["duracion"]),
        "nombre": nombre[:80], "email": email[:120], "telefono": telefono[:20], "personas": personas,
        "comentario": f.get("comentario", "").strip()[:500],
    }
    return errores, datos


def _enviar_confirmacion(datos: dict, servicio: dict, codigo: str) -> None:
    filtro_fecha = current_app.jinja_env.filters["fecha_larga"]
    reserva = {**datos, "codigo": codigo, "fecha_texto": filtro_fecha(datos["inicio"]),
               "hora_texto": datos["inicio"].strftime("%H:%M")}
    asunto, cuerpo = correo.confirmacion(_negocio(), reserva, servicio, url_for("publico.mi_reserva", _external=True))
    correo.enviar(datos["email"], asunto, cuerpo)


@bp.get("/confirmacion")
def confirmacion():
    ultima = session.get("ultima_reserva")
    reserva = db.buscar_reserva(ultima["codigo"], ultima["email"]) if ultima else None
    if not reserva:
        return redirect(url_for("publico.inicio"))
    return render_template("confirmacion.html", r=reserva, servicio=_servicio(reserva["servicio_id"]))


@bp.route("/mi-reserva", methods=["GET", "POST"])
def mi_reserva():
    reserva = None
    if request.method == "POST":
        reserva = db.buscar_reserva(request.form.get("codigo", ""), request.form.get("email", ""))
        if not reserva:
            flash("No encontramos una reserva con ese código y correo.", "error")
        elif request.form.get("accion") == "cancelar":
            inicio = datetime.fromisoformat(reserva["inicio"])
            if reserva["estado"] != "confirmada":
                flash("Esta reserva ya no se puede cancelar.", "error")
            elif inicio - _ahora() < timedelta(hours=HORAS_MINIMAS_CANCELAR):
                flash(f"Las reservas se pueden cancelar hasta {HORAS_MINIMAS_CANCELAR} horas antes. "
                      f"Comunícate al {_negocio().get('telefono', '')}.", "error")
            else:
                db.cambiar_estado(reserva["id"], "cancelada")
                flash("Tu reserva fue cancelada.", "ok")
                reserva = db.buscar_reserva(reserva["codigo"], reserva["email"])
    servicio = _servicio(reserva["servicio_id"]) if reserva else None
    return render_template("mi_reserva.html", r=reserva, servicio=servicio)
