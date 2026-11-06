from datetime import date, datetime

import pytest

from app import create_app
from app.disponibilidad import horarios_disponibles, se_solapan

# Viernes 6 de noviembre de 2026, 10:00 (hora local del negocio)
AHORA = datetime(2026, 11, 6, 10, 0)
SABADO = date(2026, 11, 7)
LUNES = date(2026, 11, 9)


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "BASE_DATOS": str(tmp_path / "test.db"), "AHORA": lambda: AHORA,
                       "ADMIN_CLAVE": "clave-test"})


@pytest.fixture
def cliente(app):
    c = app.test_client()
    with c.session_transaction() as s:
        s["csrf"] = "token"
    return c


def _reservar(cliente, hora="12:00", servicio="tanda-20", **extra):
    datos = {"csrf": "token", "fecha": SABADO.isoformat(), "hora": hora, "nombre": "Ana Rojas",
             "email": "ana@ejemplo.example", "telefono": "+56 9 1234 5678", "personas": "2", **extra}
    return cliente.post(f"/reservar/{servicio}", data=datos)


# ---------- lógica de disponibilidad ----------
def test_solapamiento():
    a, b = datetime(2026, 1, 1, 10), datetime(2026, 1, 1, 11)
    assert se_solapan(a, b, datetime(2026, 1, 1, 10, 30), datetime(2026, 1, 1, 12))
    assert not se_solapan(a, b, b, datetime(2026, 1, 1, 12))  # termina justo cuando empieza otra


def test_respeta_horario_y_cierre(app):
    cfg = app.config["NEGOCIO"]
    libres = horarios_disponibles(cfg, SABADO, 60, [], AHORA)
    assert libres[0] == datetime(2026, 11, 7, 11, 0)
    assert datetime(2026, 11, 7, 13, 0) in libres       # termina 14:00 justo al cierre del tramo
    assert datetime(2026, 11, 7, 13, 15) not in libres  # terminaría después del cierre
    assert libres[-1] == datetime(2026, 11, 7, 21, 0)   # último inicio antes de cerrar a las 22:00


def test_dia_cerrado_y_fuera_de_rango(app):
    cfg = app.config["NEGOCIO"]
    assert horarios_disponibles(cfg, LUNES, 15, [], AHORA) == []
    assert horarios_disponibles(cfg, date(2027, 6, 1), 15, [], AHORA) == []


def test_anticipacion_minima(app):
    cfg = {**app.config["NEGOCIO"], "horarios": {"4": [["09:00", "13:00"]]}}
    libres = horarios_disponibles(cfg, AHORA.date(), 15, [], AHORA)
    assert libres[0] == datetime(2026, 11, 6, 11, 0)  # 60 minutos de aviso mínimo


def test_bloquea_horarios_ocupados(app):
    cfg = app.config["NEGOCIO"]
    ocupado = [(datetime(2026, 11, 7, 12, 0), datetime(2026, 11, 7, 12, 30))]
    libres = horarios_disponibles(cfg, SABADO, 30, ocupado, AHORA)
    assert datetime(2026, 11, 7, 11, 45) not in libres
    assert datetime(2026, 11, 7, 12, 15) not in libres
    assert datetime(2026, 11, 7, 12, 30) in libres


# ---------- flujo web ----------
def test_flujo_completo_de_reserva(cliente):
    r = _reservar(cliente)
    assert r.status_code == 302 and r.headers["Location"].endswith("/confirmacion")
    pagina = cliente.get("/confirmacion").get_data(as_text=True)
    assert "Reserva confirmada" in pagina
    horarios = cliente.get(f"/api/horarios?servicio=tanda-20&fecha={SABADO}").get_json()["horarios"]
    assert "12:00" not in horarios and "11:45" not in horarios


def test_no_permite_doble_reserva(cliente):
    _reservar(cliente)
    r = _reservar(cliente, hora="12:15")
    assert r.status_code == 200
    assert "ya no está disponible" in r.get_data(as_text=True)


def test_valida_datos(cliente):
    r = _reservar(cliente, nombre="A", email="no-es-correo", personas="50")
    texto = r.get_data(as_text=True)
    assert "nombre completo" in texto and "correo no es válido" in texto and "entre 1 y 8" in texto


def test_rechaza_post_sin_csrf(cliente):
    r = cliente.post("/reservar/tanda-20", data={"fecha": SABADO.isoformat(), "hora": "12:00"})
    assert r.status_code == 400


def test_consultar_y_cancelar(app, cliente):
    _reservar(cliente)
    with app.app_context():
        from app import db
        codigo = db.reservas_entre(SABADO, SABADO)[0]["codigo"]
    r = cliente.post("/mi-reserva", data={"csrf": "token", "codigo": codigo.lower(), "email": "ANA@ejemplo.example",
                                          "accion": "cancelar"})
    assert "fue cancelada" in r.get_data(as_text=True)
    horarios = cliente.get(f"/api/horarios?servicio=tanda-20&fecha={SABADO}").get_json()["horarios"]
    assert "12:00" in horarios  # el horario vuelve a quedar libre


def test_panel_requiere_clave(cliente):
    assert cliente.get("/admin/").status_code == 302
    r = cliente.post("/admin/login", data={"csrf": "token", "clave": "incorrecta"})
    assert "Clave incorrecta" in r.get_data(as_text=True)


def test_panel_y_exportacion(cliente):
    _reservar(cliente)
    with cliente.session_transaction() as s:
        s["admin"] = True
    agenda = cliente.get(f"/admin/?fecha={SABADO}").get_data(as_text=True)
    assert "Ana Rojas" in agenda
    csv = cliente.get(f"/admin/exportar.csv?desde={SABADO}&hasta={SABADO}")
    assert csv.mimetype == "text/csv" and "Ana Rojas" in csv.get_data(as_text=True)
