"""Sistema de reservas web: punto de entrada de la aplicación Flask."""
from __future__ import annotations

import os
import tomllib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask

from . import db

RAIZ = Path(__file__).resolve().parents[1]


def cargar_env(ruta: Path) -> None:
    """Lee variables CLAVE=valor de un archivo .env (sin dependencias externas)."""
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, valor = linea.split("=", 1)
                os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def create_app(config: dict | None = None) -> Flask:
    cargar_env(RAIZ / ".env")
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "solo-para-desarrollo-cambiar"),
        ADMIN_CLAVE=os.getenv("ADMIN_CLAVE", "demo1234"),
        BASE_DATOS=os.getenv("BASE_DATOS", str(RAIZ / "instance" / "reservas.db")),
        ARCHIVO_NEGOCIO=os.getenv("ARCHIVO_NEGOCIO", str(RAIZ / "negocio.toml")),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)

    with open(app.config["ARCHIVO_NEGOCIO"], "rb") as f:
        negocio = tomllib.load(f)
    negocio["servicios_por_id"] = {s["id"]: s for s in negocio["servicios"]}
    app.config["NEGOCIO"] = negocio
    zona = ZoneInfo(negocio["zona_horaria"])
    # hora local del negocio sin zona (así se guarda en la base de datos)
    app.config.setdefault("AHORA", lambda: datetime.now(zona).replace(tzinfo=None, second=0, microsecond=0))

    Path(app.config["BASE_DATOS"]).parent.mkdir(parents=True, exist_ok=True)
    db.inicializar(app.config["BASE_DATOS"])
    app.teardown_appcontext(db.cerrar)

    @app.template_filter("clp")
    def formato_clp(valor: int) -> str:
        return "$" + f"{int(valor):,}".replace(",", ".")

    @app.template_filter("fecha_larga")
    def fecha_larga(valor) -> str:
        dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
        meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
                 "septiembre", "octubre", "noviembre", "diciembre"]
        if isinstance(valor, str):
            valor = datetime.fromisoformat(valor)
        return f"{dias[valor.weekday()]} {valor.day} de {meses[valor.month - 1]}"

    from .seguridad import token_csrf, verificar_csrf

    app.before_request(verificar_csrf)

    @app.context_processor
    def datos_globales():
        return {"negocio": negocio, "csrf": token_csrf}

    from .rutas_admin import bp as admin_bp
    from .rutas_publicas import bp as publicas_bp

    app.register_blueprint(publicas_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    return app
