"""
Carga reservas FICTICIAS para la demo: semana pasada, esta semana y la próxima,
para que el panel de administración muestre datos desde el primer momento.

Uso:
    python scripts/datos_demo.py            # agrega reservas de ejemplo
    python scripts/datos_demo.py --limpiar  # borra todo antes de cargar
"""
from __future__ import annotations

import random
import sqlite3
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app  # noqa: E402
from app.disponibilidad import horarios_disponibles  # noqa: E402

NOMBRES = ["Ana Rojas", "Pedro Soto", "Camila Díaz", "Luis Muñoz", "Javiera Pérez", "Matías Vera",
           "Fernanda Silva", "Diego González", "Valentina Morales", "Tomás Fuentes", "Catalina Reyes",
           "Benjamín Araya", "Francisca Tapia", "Joaquín Castillo", "Constanza Herrera"]
COMENTARIOS = ["", "", "", "Cumpleaños de mi hijo", "Somos principiantes", "Grupo de la oficina", ""]


def main() -> None:
    random.seed(11)
    app = create_app()
    negocio = app.config["NEGOCIO"]
    ahora = app.config["AHORA"]()
    ruta = app.config["BASE_DATOS"]
    with sqlite3.connect(ruta) as db:
        if "--limpiar" in sys.argv:
            db.execute("DELETE FROM reservas")
        creadas = 0
        for delta in range(-7, 15):
            dia = ahora.date() + timedelta(days=delta)
            ocupados = []
            objetivo = random.randint(4, 9) if dia.weekday() >= 4 else random.randint(1, 5)
            for _ in range(objetivo):
                servicio = random.choices(negocio["servicios"], weights=[5, 4, 1])[0]
                # para días pasados se simula "desde el inicio del día" para poder generar historial
                referencia = ahora if delta >= 0 else ahora - timedelta(days=30)
                cfg = {**negocio, "dias_anticipacion": 60}
                libres = horarios_disponibles(cfg, dia, servicio["duracion"], ocupados, referencia)
                if not libres:
                    break
                inicio = random.choice(libres)
                fin = inicio + timedelta(minutes=servicio["duracion"])
                ocupados.append((inicio, fin))
                nombre = random.choice(NOMBRES)
                usuario = nombre.lower().split()[0].replace("á", "a").replace("í", "i").replace("é", "e")
                if delta < 0:
                    estado = random.choices(["asistio", "no_asistio", "cancelada"], weights=[85, 7, 8])[0]
                else:
                    estado = random.choices(["confirmada", "cancelada"], weights=[92, 8])[0]
                db.execute(
                    "INSERT INTO reservas (codigo, servicio_id, inicio, fin, nombre, email, telefono, personas, "
                    "comentario, estado, creada) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"{random.randrange(16**6):06X}", servicio["id"], inicio.isoformat(), fin.isoformat(), nombre,
                     f"{usuario}{random.randint(1, 99)}@ejemplo.example", f"+569{random.randint(10000000, 99999999)}",
                     random.randint(1, servicio["max_personas"]), random.choice(COMENTARIOS), estado,
                     (inicio - timedelta(days=random.randint(1, 6))).isoformat()),
                )
                creadas += 1
    print(f"{creadas} reservas de ejemplo cargadas en {ruta}")


if __name__ == "__main__":
    main()
