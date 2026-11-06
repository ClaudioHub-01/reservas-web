"""Panel de administración del negocio: agenda, estados, indicadores y exportación."""
from __future__ import annotations

import csv
import hmac
import io
from datetime import date, datetime, timedelta

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, session, url_for

from . import db
from .disponibilidad import bloques_del_dia
from .seguridad import requiere_admin

bp = Blueprint("admin", __name__)
ESTADOS = {"confirmada": "Confirmada", "asistio": "Asistió", "no_asistio": "No asistió", "cancelada": "Cancelada"}


def _hoy() -> date:
    return current_app.config["AHORA"]().date()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if hmac.compare_digest(request.form.get("clave", ""), current_app.config["ADMIN_CLAVE"]):
            session.clear()
            session["admin"] = True
            siguiente = request.args.get("siguiente", "")
            return redirect(siguiente if siguiente.startswith("/admin") else url_for("admin.agenda"))
        flash("Clave incorrecta.", "error")
    return render_template("admin/login.html")


@bp.post("/salir")
def salir():
    session.pop("admin", None)
    return redirect(url_for("publico.inicio"))


def _indicadores(reservas, negocio: dict, desde: date, hasta: date) -> dict:
    servicios = negocio["servicios_por_id"]
    activas = [r for r in reservas if r["estado"] != "cancelada"]
    minutos_abiertos = sum(
        (b - a).total_seconds() / 60
        for d in (desde + timedelta(days=i) for i in range((hasta - desde).days + 1))
        for a, b in bloques_del_dia(negocio, d)
    )
    minutos_ocupados = sum(servicios[r["servicio_id"]]["duracion"] for r in activas if r["servicio_id"] in servicios)
    return {
        "reservas": len(activas),
        "personas": sum(r["personas"] for r in activas),
        "ingresos": sum(servicios.get(r["servicio_id"], {}).get("precio", 0) for r in activas),
        "ocupacion": round(100 * minutos_ocupados / minutos_abiertos) if minutos_abiertos else 0,
        "canceladas": len(reservas) - len(activas),
    }


@bp.get("/")
@requiere_admin
def agenda():
    negocio = current_app.config["NEGOCIO"]
    try:
        dia = date.fromisoformat(request.args.get("fecha", ""))
    except ValueError:
        dia = _hoy()
    lunes = dia - timedelta(days=dia.weekday())
    domingo = lunes + timedelta(days=6)
    semana = db.reservas_entre(lunes, domingo)
    del_dia = [r for r in semana if r["inicio"].startswith(dia.isoformat())]
    por_dia = {(lunes + timedelta(days=i)): 0 for i in range(7)}
    for r in semana:
        if r["estado"] != "cancelada":
            por_dia[date.fromisoformat(r["inicio"][:10])] += 1
    return render_template(
        "admin/agenda.html", dia=dia, reservas=del_dia, estados=ESTADOS, por_dia=por_dia,
        ind_dia=_indicadores(del_dia, negocio, dia, dia), ind_semana=_indicadores(semana, negocio, lunes, domingo),
        anterior=dia - timedelta(days=1), siguiente=dia + timedelta(days=1), hoy=_hoy(),
        servicios=negocio["servicios_por_id"], lunes=lunes, domingo=domingo,
    )


@bp.post("/reserva/<int:reserva_id>/estado")
@requiere_admin
def cambiar_estado(reserva_id: int):
    estado = request.form.get("estado")
    if estado in ESTADOS:
        db.cambiar_estado(reserva_id, estado)
        flash("Reserva actualizada.", "ok")
    return redirect(url_for("admin.agenda", fecha=request.form.get("fecha")))


@bp.get("/exportar.csv")
@requiere_admin
def exportar():
    try:
        desde = date.fromisoformat(request.args.get("desde", ""))
        hasta = date.fromisoformat(request.args.get("hasta", ""))
    except ValueError:
        desde, hasta = _hoy() - timedelta(days=30), _hoy() + timedelta(days=30)
    servicios = current_app.config["NEGOCIO"]["servicios_por_id"]
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=";")
    w.writerow(["Código", "Fecha", "Hora", "Servicio", "Personas", "Nombre", "Correo", "Teléfono", "Estado", "Precio"])
    for r in db.reservas_entre(desde, hasta):
        inicio = datetime.fromisoformat(r["inicio"])
        s = servicios.get(r["servicio_id"], {})
        w.writerow([r["codigo"], inicio.strftime("%d-%m-%Y"), inicio.strftime("%H:%M"), s.get("nombre", r["servicio_id"]),
                    r["personas"], r["nombre"], r["email"], r["telefono"], ESTADOS.get(r["estado"]), s.get("precio", 0)])
    nombre = f"reservas_{desde:%Y%m%d}_{hasta:%Y%m%d}.csv"
    return Response("﻿" + salida.getvalue(), mimetype="text/csv",  # BOM: Excel abre bien las tildes
                    headers={"Content-Disposition": f"attachment; filename={nombre}"})
