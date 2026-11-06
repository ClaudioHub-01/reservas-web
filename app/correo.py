"""
Correos de confirmación. Si no hay servidor SMTP configurado en .env,
el correo se muestra en la consola (modo demo) en lugar de enviarse.
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger("reservas.correo")


def enviar(destinatario: str, asunto: str, cuerpo: str) -> bool:
    host = os.getenv("SMTP_HOST")
    if not host:
        log.info("[MODO DEMO] Correo para %s\nAsunto: %s\n%s", destinatario, asunto, cuerpo)
        return False
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = os.getenv("SMTP_REMITENTE", os.getenv("SMTP_USUARIO", ""))
    msg["To"] = destinatario
    msg.set_content(cuerpo)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
            smtp.starttls()
            smtp.login(os.environ["SMTP_USUARIO"], os.environ["SMTP_CLAVE"])
            smtp.send_message(msg)
        return True
    except Exception:  # noqa: BLE001 - un fallo de correo no debe impedir la reserva
        log.exception("No se pudo enviar el correo a %s", destinatario)
        return False


def confirmacion(negocio: dict, reserva: dict, servicio: dict, enlace: str) -> tuple[str, str]:
    asunto = f"Reserva confirmada · {negocio['nombre']} · código {reserva['codigo']}"
    cuerpo = (
        f"Hola {reserva['nombre']},\n\n"
        f"Tu reserva está confirmada:\n\n"
        f"  Servicio: {servicio['nombre']}\n"
        f"  Fecha:    {reserva['fecha_texto']}\n"
        f"  Hora:     {reserva['hora_texto']}\n"
        f"  Personas: {reserva['personas']}\n"
        f"  Código:   {reserva['codigo']}\n\n"
        f"Para revisar o cancelar tu reserva ingresa a {enlace} con tu código y tu correo.\n\n"
        f"{negocio['nombre']} · {negocio.get('direccion', '')} · {negocio.get('telefono', '')}\n"
    )
    return asunto, cuerpo
