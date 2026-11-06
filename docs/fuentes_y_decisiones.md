# Fuentes, alcance y decisiones pendientes

## Consigna oficial

[Trabajo Final Integrador de BI&A](https://docs.google.com/document/d/11AAnctgYEXbOcAUvmsXw2j_GH00fOjt80c4mry4-yAg/edit)

[Drive de archivos fuente](https://drive.google.com/drive/folders/1uOrWfHv7u-Sr4mhMpFOuWJr7FNXec7lA)

El material incluye **28 archivos Excel**: 3 matrículas, 3 reportes de participación, 3 de trazabilidad y 19 exportaciones de calificaciones. Las hojas y columnas todavía deben perfilarse antes de definir un modelo y KPI definitivos. Se conserva la procedencia por materia y archivo original.

| Materia | Matrícula | Participación | Trazabilidad | Calificaciones |
| --- | ---: | ---: | ---: | ---: |
| Álgebra | 1 | 1 | 1 | 3 |
| Probabilidad y Estadística | 1 | 1 | 1 | 9 |
| Algoritmos y Estructuras de Datos | 1 | 1 | 1 | 5 |
| **Total** | **3** | **3** | **3** | **17** |

**Nota de control:** el inventario de archivos de Drive revela 17, no 19, archivos de calificaciones; el total correcto es **26 Excel** (3 + 3 + 3 + 17). Esta tabla es la referencia verificada y no deben suponerse archivos faltantes.

## Reglas académicas de la consigna

- **Álgebra:** suma de puntos (P1 25, P2 25, cinco autoevaluaciones de 10 y recuperatorio 20; máximo 120). Libre <60, regular 60–84, promociona >=85.
- **Probabilidad y Estadística:** promedio de instrumentos (cada uno sobre 100). Libre <60, regular 60–84, promociona >=85.
- **Algoritmos y Estructuras de Datos:** promedio de autoevaluaciones (sobre 100). Libre <60, regular 60–89, promociona >=90.

**No inferir todavía** que un instrumento faltante vale cero ni cómo interviene el recuperatorio: requiere verificar el dataset y acordar criterio documentado.

## Decisiones técnicas previas al modelado

1. Identificar encabezados, hojas, granularidad, columnas de usuario y formatos.
2. Confirmar qué campos permiten cruzar matrícula, participación, trazabilidad y notas.
3. Definir el tratamiento de usuarios sin matrícula y matriculados sin actividad.
4. Definir sesión, actividad, cobertura y período de análisis de manera consistente.
5. Validar si las calificaciones son reintentos, distintas evaluaciones o recuperatorios.
6. Diseñar tablas de hechos y dimensiones que eviten duplicar métricas en cruces muchos-a-muchos.
7. Verificar anonimización y sensibilidad antes de subir CSV al repositorio, aunque sea privado.

## Entregables

Regularización: mínimo tres dashboards funcionales e informe de avance con KPI. TFI completo: siete vistas interactivas, informe técnico y defensa de resultados.
