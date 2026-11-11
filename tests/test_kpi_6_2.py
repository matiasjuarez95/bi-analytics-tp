import pandas as pd
import pytest

from src.kpi import calcular_kpis


def _datos():
    s = pd.DataFrame([
        dict(id_estudiante="ALU_0001", asignatura="Álgebra", matriculado=True, tiene_actividad=True,
             estado_provisorio="Promociona", nota_a_la_fecha=96, escala_nota_a_la_fecha=120,
             tiempo_uso_min=40, interacciones=10, eventos_trazabilidad=3,
             situacion_matricula="Matriculado con actividad"),
        dict(id_estudiante="ALU_0002", asignatura="Álgebra", matriculado=True, tiene_actividad=False,
             estado_provisorio="Sin notas", nota_a_la_fecha=None, escala_nota_a_la_fecha=120,
             tiempo_uso_min=None, interacciones=0, eventos_trazabilidad=0,
             situacion_matricula="Matriculado sin participación"),
        dict(id_estudiante="ALU_0003", asignatura="Álgebra", matriculado=False, tiene_actividad=True,
             estado_provisorio="Regular", nota_a_la_fecha=70, escala_nota_a_la_fecha=120,
             tiempo_uso_min=120, interacciones=100, eventos_trazabilidad=2,
             situacion_matricula="NO matriculado con actividad"),
    ])
    t = pd.DataFrame([
        dict(id_estudiante="ALU_0001", asignatura="Álgebra", fecha="2025-10-20 12:00:00",
             tipo_interaccion="Lectura de materiales"),
        dict(id_estudiante="ALU_0001", asignatura="Álgebra", fecha="2025-10-21 12:00:00",
             tipo_interaccion="Evaluaciones"),
        dict(id_estudiante="ALU_0003", asignatura="Álgebra", fecha="2025-10-21 13:00:00",
             tipo_interaccion="Acceso/navegación"),
    ])
    c = pd.DataFrame([
        dict(id_estudiante="ALU_0001", asignatura="Álgebra", instrumento="Parcial 1",
             nota_100=90, usa_en_nota_final=True),
        dict(id_estudiante="ALU_0001", asignatura="Álgebra", instrumento="Parcial 1",
             nota_100=30, usa_en_nota_final=False),
        dict(id_estudiante="ALU_0003", asignatura="Álgebra", instrumento="Parcial 1",
             nota_100=100, usa_en_nota_final=True),
    ])
    return s, t, c


def test_resumen_y_denominadores():
    k = calcular_kpis(*_datos())
    r = k["kpi_resumen_asignatura"].iloc[0]
    assert r["matriculados"] == 2
    assert r["activos"] == 1 and r["inactivos"] == 1
    assert r["cobertura_participacion_pct"] == 50
    assert r["promedio_nota_pct_solo_con_notas"] == 80
    assert r["tiempo_uso_promedio_min_por_matriculado"] == 20
    assert pd.isna(r["correlacion_tiempo_nota"])


def test_estado_y_alertas():
    k = calcular_kpis(*_datos())
    estados = k["kpi_estados_a_la_fecha"].set_index("estado_a_la_fecha")["cantidad"]
    assert estados["Promociona"] == 1 and estados["Sin notas"] == 1
    alertas = k["kpi_alertas_matricula"].set_index("alerta")["cantidad"]
    assert alertas["Matriculado sin participación"] == 1
    assert alertas["No matriculado con actividad"] == 1


def test_trazabilidad_y_notas_no_incluyen_no_matriculados():
    k = calcular_kpis(*_datos())
    assert k["kpi_interacciones_tipo"]["eventos"].sum() == 2
    assert k["kpi_actividad_diaria"]["eventos"].sum() == 2
    assert k["kpi_actividad_semanal"]["eventos"].sum() == 2
    assert k["kpi_notas_instrumento"].iloc[0]["cantidad_notas"] == 1
    assert k["kpi_notas_instrumento"].iloc[0]["promedio_nota_100"] == 90


def test_falla_clave_duplicada():
    s, t, c = _datos()
    with pytest.raises(ValueError, match="duplicados"):
        calcular_kpis(pd.concat([s, s.iloc[[0]]], ignore_index=True), t, c)


def test_falla_fecha_invalida():
    s, t, c = _datos()
    t.loc[0, "fecha"] = "invalida"
    with pytest.raises(ValueError, match="fechas inválidas"):
        calcular_kpis(s, t, c)
