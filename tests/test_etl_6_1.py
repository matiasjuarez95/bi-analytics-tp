# -*- coding: utf-8 -*-
"""
Pruebas del ETL 6.1. Usan datos sintéticos mínimos (no necesitan los Excel).
Ejecutar desde la raíz del repo:  python -m pytest tests/ -v
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.etl import procesar_datos as etl  # noqa: E402

ALG, PROB, ALGO = "Álgebra", "Probabilidad y Estadística", "Algoritmos y Estructuras de Datos"


# ----------------------------------------------------------------------------- helpers
def mov(id_, estado, fecha, nro):
    return dict(id_estudiante=id_, estado_insc=estado, fecha_inscripcion=pd.Timestamp(fecha),
                nro_transaccion=nro, nombre_completo=f"NOMBRE {id_}", asignatura=ALG)


def nota(id_, asig, instrumento, puntos, maximo, recuperatorio=False):
    return dict(id_estudiante=id_, asignatura=asig, instrumento=instrumento, puntos=puntos, maximo=maximo,
                nota_100=round(puntos / maximo * 100, 2), es_recuperatorio=recuperatorio)


def universo(*pares):
    return pd.DataFrame(pares, columns=["id_estudiante", "asignatura"])


def fila(df, id_, asig):
    return df[(df["id_estudiante"] == id_) & (df["asignatura"] == asig)].iloc[0]


# ----------------------------------------------------------------------------- matrícula
def test_baja_posterior_a_la_inscripcion_deja_al_alumno_dado_de_baja():
    df = pd.DataFrame([mov("ALU_0001", "Aceptada", "2025-08-01 10:00", 100),
                       mov("ALU_0001", "Baja", "2025-08-05 10:00", 120)])
    vig, movs = etl.resolver_matricula(df)
    assert len(vig) == 1
    assert vig.iloc[0]["estado_insc"] == "Baja" and not vig.iloc[0]["matriculado"]
    assert len(movs) == 2                      # la auditoría conserva todos los movimientos


def test_reinscripcion_posterior_a_una_baja_deja_al_alumno_matriculado():
    df = pd.DataFrame([mov("ALU_0002", "Baja", "2025-08-01 10:00", 100),
                       mov("ALU_0002", "Aceptada", "2025-08-02 10:00", 130)])
    vig, _ = etl.resolver_matricula(df)
    assert vig.iloc[0]["matriculado"]


def test_el_orden_de_las_filas_en_el_archivo_no_altera_el_estado_vigente():
    a = [mov("ALU_0003", "Aceptada", "2025-08-01 10:00", 100), mov("ALU_0003", "Baja", "2025-08-05 10:00", 120)]
    v1, _ = etl.resolver_matricula(pd.DataFrame(a))
    v2, _ = etl.resolver_matricula(pd.DataFrame(a[::-1]))
    assert v1.iloc[0]["estado_insc"] == v2.iloc[0]["estado_insc"] == "Baja"


def test_empate_de_fecha_se_desempata_por_nro_de_transaccion_y_se_marca_ambiguo():
    df = pd.DataFrame([mov("ALU_0004", "Baja", "2025-08-01 10:00", 100),
                       mov("ALU_0004", "Aceptada", "2025-08-01 10:00", 101)])
    vig, _ = etl.resolver_matricula(df)
    assert vig.iloc[0]["estado_insc"] == "Aceptada"       # mayor nro. de transacción
    assert vig.iloc[0]["caso_ambiguo"]


def test_varias_bajas_seguidas_siguen_siendo_baja():
    df = pd.DataFrame([mov("ALU_0005", "Baja", f"2025-08-0{i} 10:00", 100 + i) for i in (1, 2, 3)])
    vig, _ = etl.resolver_matricula(df)
    assert len(vig) == 1 and not vig.iloc[0]["matriculado"] and vig.iloc[0]["n_movimientos"] == 3


# ----------------------------------------------------------------------------- umbrales
@pytest.mark.parametrize("asig,valor,esperado", [
    (ALG, 85, "Promociona"), (ALG, 84.99, "Regular"), (ALG, 60, "Regular"), (ALG, 59.99, "Libre"),
    (PROB, 85, "Promociona"), (PROB, 84.99, "Regular"), (PROB, 60, "Regular"), (PROB, 59.99, "Libre"),
    (ALGO, 90, "Promociona"), (ALGO, 89.99, "Regular"), (ALGO, 60, "Regular"), (ALGO, 59.99, "Libre"),
])
def test_umbrales_de_las_tres_materias(asig, valor, esperado):
    assert etl.condicion(valor, asig) == esperado


def test_condicion_de_un_valor_nulo_no_es_libre():
    assert etl.condicion(np.nan, ALG) is None


# ----------------------------------------------------------------------------- Álgebra
def _alg(puntos_por_alumno):
    filas = []
    for id_, lista in puntos_por_alumno.items():
        for i, (p, m) in enumerate(lista):
            filas.append(nota(id_, ALG, f"inst{i}", p, m))
    return pd.DataFrame(filas)


def test_algebra_la_proyeccion_no_es_nota_definitiva():
    # saca 45/45 en lo que hay (3 de 8 instrumentos): proyecta 120 pero NO está promocionado
    cal = _alg({"ALU_0010": [(10, 10), (10, 10), (25, 25)]})
    n = etl.calcular_notas_finales(cal, universo(("ALU_0010", ALG)))
    f = fila(n, "ALU_0010", ALG)
    assert f["puntos_acumulados"] == 45 and f["puntos_maximos_observados"] == 45
    assert f["proyeccion_120_rendidos"] == 120 and f["proyeccion_120_observados"] == 120
    assert f["estado_definitivo"] == "Pendiente"
    assert f["estado_provisorio"] == "Pendiente"          # tampoco el provisorio sale de la proyección
    assert f["completitud_datos"] == pytest.approx(3 / 8)


def test_algebra_promociona_si_los_puntos_acumulados_ya_alcanzan_85():
    cal = _alg({"ALU_0011": [(25, 25), (25, 25), (10, 10), (10, 10), (10, 10), (10, 10), (10, 10)]})
    f = fila(etl.calcular_notas_finales(cal, universo(("ALU_0011", ALG))), "ALU_0011", ALG)
    assert f["puntos_acumulados"] == 100                  # 25+25+5*10
    assert f["estado_definitivo"] == "Promociona"         # los puntos no pueden bajar


def test_algebra_regular_y_libre_solo_son_definitivos_con_cursada_cerrada_y_datos_completos():
    cal = _alg({"ALU_0012": [(20, 25), (20, 25)] + [(5, 10)] * 5 + [(0, 20)]})   # 8 instrumentos, 65 pts
    u = universo(("ALU_0012", ALG))
    abierta = fila(etl.calcular_notas_finales(cal, u, cursada_cerrada=False), "ALU_0012", ALG)
    cerrada = fila(etl.calcular_notas_finales(cal, u, cursada_cerrada=True), "ALU_0012", ALG)
    assert abierta["puntos_acumulados"] == 65
    assert abierta["estado_definitivo"] == "Pendiente"
    assert cerrada["estado_definitivo"] == "Regular"       # 85 > 65 >= 60 con datos completos


# ----------------------------------------------------------------------------- sin notas
def test_alumno_sin_notas_no_es_libre_en_ninguna_materia():
    cal = pd.DataFrame([nota("ALU_0020", PROB, "PARCIAL 1", 80, 100), nota("ALU_0021", ALGO, "Auto 1", 90, 100),
                        nota("ALU_0022", ALG, "AUTOEVALUACION1", 8, 10)])
    u = universo(("ALU_0099", ALG), ("ALU_0099", PROB), ("ALU_0099", ALGO))
    n = etl.calcular_notas_finales(cal, u, cursada_cerrada=True)
    assert (n["estado_provisorio"] == "Sin notas").all()
    assert (n["estado_definitivo"] == "Sin notas").all()
    assert n["promedio_con_faltantes"].isna().all() or n["promedio_con_faltantes"].dropna().empty


# ----------------------------------------------------------------------------- promedios
def test_promedio_observado_y_con_faltantes_son_distintos_y_explicitos():
    cal = pd.DataFrame([nota("ALU_0030", PROB, "PARCIAL 1", 100, 100), nota("ALU_0030", PROB, "Actividad 1", 100, 100),
                        nota("ALU_0031", PROB, "PARCIAL 1", 50, 100), nota("ALU_0031", PROB, "Actividad 1", 50, 100),
                        nota("ALU_0031", PROB, "Actividad 2", 50, 100), nota("ALU_0031", PROB, "Actividad 3", 50, 100)])
    n = etl.calcular_notas_finales(cal, universo(("ALU_0030", PROB), ("ALU_0031", PROB)))
    a = fila(n, "ALU_0030", PROB)
    assert a["promedio_observados"] == 100
    assert a["promedio_con_faltantes"] == 50               # 200 / 4 instrumentos presentes en los datos
    assert not a["denominador_confirmado"]                 # el total oficial NO está confirmado
    assert a["estado_definitivo"] == "Pendiente"           # no se promociona por un supuesto


def test_estado_provisorio_de_probabilidad_usa_solo_lo_rendido():
    cal = pd.DataFrame([nota("ALU_0032", PROB, "PARCIAL 1", 90, 100), nota("ALU_0033", PROB, "PARCIAL 1", 10, 100)])
    n = etl.calcular_notas_finales(cal, universo(("ALU_0032", PROB), ("ALU_0033", PROB)))
    assert fila(n, "ALU_0032", PROB)["estado_provisorio"] == "Promociona"
    assert fila(n, "ALU_0033", PROB)["estado_provisorio"] == "Libre"


# ----------------------------------------------------------------------------- recuperatorios
def _prob_con_recuperatorio():
    return pd.DataFrame([
        nota("ALU_0040", PROB, "Evaluación Semanal Nº1", 0, 100),
        nota("ALU_0040", PROB, "Recuperatorio: Evaluación Semanal Nº1", 83.33, 100, True),
        nota("ALU_0041", PROB, "Evaluación Semanal Nº1", 90, 100),
        nota("ALU_0041", PROB, "Recuperatorio: Evaluación Semanal Nº1", 40, 100, True),
        nota("ALU_0042", PROB, "Evaluación Semanal Nº1", 70, 100),
        nota("ALU_0040", PROB, "Evaluación Semanal Nº2", 100, 100),
    ])


def test_recuperatorio_reemplaza_a_la_evaluacion_original():
    c = etl.aplicar_recuperatorios(_prob_con_recuperatorio(), "reemplaza")
    usadas = c[c["usa_en_nota_final"] & (c["id_estudiante"] == "ALU_0040")]
    assert sorted(usadas["nota_100"]) == [83.33, 100.0]    # recuperatorio + Semanal Nº2, sin el 0
    u41 = c[c["usa_en_nota_final"] & (c["id_estudiante"] == "ALU_0041")]
    assert list(u41["nota_100"]) == [40.0]                 # reemplaza incluso si empeora (supuesto documentado)
    assert (c["instrumento_base"][c["es_recuperatorio"]] == "Evaluación Semanal Nº1").all()
    # se elige la fila completa: el instrumento y el puntaje siempre pertenecen al mismo registro
    assert (u41["instrumento"] == "Recuperatorio: Evaluación Semanal Nº1").all()


def test_recuperatorio_mayor_nota_conserva_la_mejor_fila_completa():
    c = etl.aplicar_recuperatorios(_prob_con_recuperatorio(), "mayor_nota")
    u41 = c[c["usa_en_nota_final"] & (c["id_estudiante"] == "ALU_0041")]
    assert list(u41["nota_100"]) == [90.0] and not u41["es_recuperatorio"].iloc[0]


def test_recuperatorio_aparte_cuenta_como_instrumento_propio():
    c = etl.aplicar_recuperatorios(_prob_con_recuperatorio(), "aparte")
    assert c["usa_en_nota_final"].all()
    assert c["instrumento_base"].nunique() == 3


def test_recuperatorio_cuenta_una_sola_vez_en_el_total_de_instrumentos():
    c = etl.aplicar_recuperatorios(_prob_con_recuperatorio(), "reemplaza")
    n = etl.calcular_notas_finales(c, universo(("ALU_0040", PROB)))
    assert fila(n, "ALU_0040", PROB)["instrumentos_en_datos"] == 2   # Semanal Nº1 y Nº2


def test_recuperatorio_sin_original_en_los_datos_se_registra():
    etl.reiniciar_registro()
    cal = pd.DataFrame([nota("ALU_0043", PROB, "Recuperatorio: Parcial X", 70, 100, True),
                        nota("ALU_0043", PROB, "PARCIAL 1", 80, 100)])
    etl.aplicar_recuperatorios(cal, "reemplaza")
    assert any("sin evaluación original" in e["problema"] for e in etl.LOG)


# ----------------------------------------------------------------------------- duplicados
def test_eventos_identicos_de_trazabilidad_se_marcan_y_no_se_borran():
    base = dict(fecha=pd.Timestamp("2025-09-01 10:00:00"), ip="10.0.0.1", id_estudiante="ALU_0050",
                perfil="Alumnos", seccion="Inicio", accion="Acceder", descripcion="Acceso a 'Inicio'")
    df = pd.DataFrame([base, base, {**base, "fecha": pd.Timestamp("2025-09-01 10:00:01")}])
    r = etl.marcar_duplicados_trazabilidad(df)
    assert len(r) == 3                                      # no se eliminó ninguno
    assert list(r["duplicado_potencial"]) == [False, True, False]


def test_notas_repetidas_del_mismo_alumno_se_reportan(tmp_path):
    import openpyxl
    etl.reiniciar_registro()
    wb = openpyxl.Workbook()
    ws = wb.active
    for fila_ in [["Fecha de exportación: x"], ["Nombre del aula: x"], ["Calificación: PARCIAL 1"], ["Responsable: x"],
                  ["nota"], [], ["Usuario", "Apellido", "Nombre", "Nota", "Observaciones", "Detalle"],
                  ["ALU_0060", "A", "B", "40.00/100.00", "no aprobada", None],
                  ["ALU_0060", "A", "B", "70.00/100.00", "aprobada", None],
                  ["ALU_0061", "C", "D", "90.00/100.00", "aprobada", None]]:
        ws.append(fila_)
    archivo = tmp_path / "calificaciones_alumnos_1.xlsx"
    wb.save(archivo)
    df = etl.leer_calificaciones(str(archivo), PROB)
    assert df["id_estudiante"].is_unique
    assert any("más de una nota" in e["problema"] and e["registros_afectados"] == 2 for e in etl.LOG)
    assert any(len(d) for d in etl.DESCARTADOS)             # la fila no usada queda auditada


# ----------------------------------------------------------------------------- personal
def test_personal_se_separa_sin_perder_alumnos_validos():
    etl.reiniciar_registro()
    df = pd.DataFrame({"id_estudiante": ["ALU_0070", "DOC_01", "STAFF_03", "ALU_0071", "ALU_0072"],
                       "perfil": ["Alumnos", "Tutores", "Coordinadores", "Alumnos", "Tutores"]})
    alumnos, personal = etl.separar_alumnos_personal(df, "trazabilidad", ALG)
    assert sorted(alumnos["id_estudiante"]) == ["ALU_0070", "ALU_0071"]
    assert len(personal) == 3
    assert "Inconsistencia perfil/ID (revisar)" in set(personal["motivo_exclusion"])   # tutor con ID ALU_


# ----------------------------------------------------------------------------- matrícula vs actividad
def test_situacion_matricula_cubre_los_cuatro_casos():
    m = pd.Series([True, True, False, False])
    a = pd.Series([True, False, True, False])
    assert list(etl.clasificar_situacion_matricula(m, a)) == [
        "Matriculado con actividad", "Matriculado sin participación",
        "NO matriculado con actividad", "No matriculado sin actividad"]


def test_modelo_situacion_una_fila_por_alumno_y_asignatura_sin_multiplicar():
    u = universo(("ALU_0080", ALG), ("ALU_0080", PROB), ("ALU_0081", PROB))
    mat = pd.DataFrame([dict(id_estudiante="ALU_0080", asignatura=ALG, nombre_completo="X", estado_insc="Aceptada",
                             matriculado=True, fecha_inscripcion=pd.Timestamp("2025-08-01"))])
    par = pd.DataFrame([dict(id_estudiante="ALU_0081", asignatura=PROB, perfil="Alumnos", interacciones=5)])
    ev = pd.DataFrame([dict(id_estudiante="ALU_0081", asignatura=PROB, eventos_trazabilidad=5)])
    cal = pd.DataFrame([nota("ALU_0081", PROB, "PARCIAL 1", 70, 100)])
    notas = etl.calcular_notas_finales(cal, u)
    sit = etl.construir_situacion(u, mat, par, ev, notas)
    assert len(sit) == 3 and not sit.duplicated(["id_estudiante", "asignatura"]).any()
    assert fila(sit, "ALU_0080", ALG)["situacion_matricula"] == "Matriculado sin participación"
    assert fila(sit, "ALU_0081", PROB)["situacion_matricula"] == "NO matriculado con actividad"


# ----------------------------------------------------------------------------- detección de archivos
def _crear(base, rutas):
    for r in rutas:
        p = Path(base) / r
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")


ARCHIVOS_OK = [f"{c}/reporte_{t}_1.xlsx" for c in ("algebra", "probabilidad", "algoritmos")
               for t in ("trazabilidad", "participacion")] + \
              [f"{c}/calificaciones_alumnos_1.xlsx" for c in ("algebra", "probabilidad", "algoritmos")] + \
              ["matriculados/Álgebra.xlsx", "matriculados/Probabilidad y Estadística.xlsx",
               "matriculados/Algoritmos y Estructuras de Datos.xlsx"]


def test_deteccion_de_archivos_funciona_con_tildes_y_nombres_cortos(tmp_path):
    _crear(tmp_path, ARCHIVOS_OK)
    r = etl.encontrar_archivos(str(tmp_path))
    assert set(r) == set(etl.ASIGNATURAS)
    assert r[ALG]["matricula"].endswith("Álgebra.xlsx")


def test_falta_un_reporte_da_error_claro(tmp_path):
    _crear(tmp_path, [a for a in ARCHIVOS_OK if "algebra/reporte_trazabilidad" not in a])
    with pytest.raises(etl.DatosError, match="trazabilidad"):
        etl.encontrar_archivos(str(tmp_path))


def test_dos_reportes_candidatos_dan_error_en_lugar_de_elegir_uno(tmp_path):
    _crear(tmp_path, ARCHIVOS_OK + ["algebra/reporte_trazabilidad_2.xlsx"])
    with pytest.raises(etl.DatosError, match="exactamente 1"):
        etl.encontrar_archivos(str(tmp_path))


def test_falta_la_carpeta_de_una_materia(tmp_path):
    _crear(tmp_path, [a for a in ARCHIVOS_OK if not a.startswith("algoritmos/")])
    with pytest.raises(etl.DatosError, match="carpeta"):
        etl.encontrar_archivos(str(tmp_path))


# ----------------------------------------------------------------------------- validaciones
def test_validacion_detecta_claves_duplicadas_en_situacion():
    u = universo(("ALU_0090", PROB))
    cal = pd.DataFrame([nota("ALU_0090", PROB, "PARCIAL 1", 70, 100)])
    notas = etl.calcular_notas_finales(cal, u)
    mat = pd.DataFrame(columns=["id_estudiante", "asignatura"])
    sit_mala = pd.concat([etl.construir_situacion(
        u, pd.DataFrame(columns=["id_estudiante", "asignatura", "nombre_completo", "estado_insc", "matriculado",
                                 "fecha_inscripcion"]),
        pd.DataFrame([dict(id_estudiante="ALU_0090", asignatura=PROB, perfil="Alumnos", interacciones=1)]),
        pd.DataFrame([dict(id_estudiante="ALU_0090", asignatura=PROB, eventos_trazabilidad=1)]), notas)] * 2,
        ignore_index=True)
    v = etl.validar_modelo(sit_mala, notas, cal, mat, u, pd.DataFrame(columns=["id_estudiante", "asignatura"]))
    assert not v.loc[v["chequeo"].str.startswith("situacion_estudiante única"), "ok"].iloc[0]
