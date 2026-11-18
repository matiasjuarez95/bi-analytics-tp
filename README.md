# Business Intelligence & Analytics — Trabajo Práctico

Repositorio privado para el trabajo práctico grupal de **Business Intelligence & Analytics**.

## Integrantes y ramas

| Integrante | Rama |
| --- | --- |
| Matías | `matias` |
| Tatiana | `tatiana` |
| Agostina | `agostina` |
| Lara | `lara` |
| Trabajo integrado | `main` |

**Regla principal:** cada integrante desarrolla y hace `push` en su rama personal. Los cambios llegan a `main` únicamente a través de **Pull Requests (PR)** revisados por otra persona. No hacer `push` directamente a `main`.

## 1. Configuración inicial (una sola vez)

Clonar el repositorio y entrar a la carpeta:

```bash
git clone https://github.com/matiasjuarez95/bi-analytics-tp.git
cd bi-analytics-tp
```

Cambiar a la rama personal (reemplazar `matias` por `tatiana`, `agostina` o `lara`):

```bash
git fetch origin
git switch --track origin/matias
```

Si ya existe una rama local con ese nombre, usar solamente `git switch matias`. Cada persona ejecuta estos pasos en su propia computadora.

## 2. Antes de empezar a trabajar: actualizar la rama personal

Primero asegurarse de estar en la rama propia y de no tener cambios locales sin guardar:

```bash
git switch matias
git status
git fetch origin
git pull --ff-only origin matias
git merge origin/main
```

- `git fetch origin` trae las referencias actualizadas del remoto.
- `git pull --ff-only origin matias` actualiza la rama personal con sus propios cambios remotos, sin crear un merge inesperado.
- `git merge origin/main` incorpora a la rama personal los avances que ya se integraron en `main`.
- Si el merge genera conflictos, resolverlos antes de continuar. Si el merge produjo un commit, subirlo después con `git push origin matias`.

**Importante:** `git pull` a secas en la rama personal **no garantiza** incorporar los últimos cambios de `main`; normalmente actualiza desde la rama personal remota.

## 3. Desarrollar y hacer commits

Trabajar en los archivos asignados y guardar avances en commits locales, preferiblemente pequeños y con mensajes claros:

```bash
git status
git add <ruta-del-archivo>
git commit -m "Agrega consultas SQL del análisis"
```

Reemplazar `<ruta-del-archivo>` por el nombre o ruta real del archivo. Se puede usar `git add .` si se revisaron previamente todos los cambios con `git status`.

No subir contraseñas, tokens, credenciales, archivos `.env`, datos personales ni archivos grandes sin coordinación.

## 4. Antes de publicar: volver a sincronizar con main

Con el trabajo ya guardado en commits (y el árbol de trabajo limpio):

```bash
git fetch origin
git pull --ff-only origin matias
git merge origin/main
```

Si aparecen conflictos, resolverlos, probar que el proyecto siga funcionando y completar el merge. Si no hay cambios nuevos en `main`, no habrá nada adicional que integrar.

**Por qué hacemos commit antes:** es más seguro sincronizar cuando no hay cambios locales sin guardar. Si aún no se quiere hacer commit, usar `git stash` con cuidado, pero para el trabajo cotidiano recomendamos commits pequeños.

## 5. Subir los avances a la rama personal

```bash
git push -u origin matias
```

La opción `-u` configura el seguimiento remoto; luego suele alcanzar con `git push`. **Nunca** ejecutar `git push origin main` para publicar un cambio individual.

## 6. Abrir un Pull Request a main

1. Entrar a [Pull Requests](https://github.com/matiasjuarez95/bi-analytics-tp/pulls).
2. Elegir **New pull request**.
3. Configurar **base: `main`** y **compare: tu rama personal** (por ejemplo, `matias`).
4. Describir qué se hizo, qué archivos se modificaron y cómo se verificó.
5. Solicitar revisión a otra integrante.
6. Corregir lo necesario en la misma rama y hacer otro `push`; el PR se actualiza automáticamente.
7. Cuando esté revisado y sin conflictos pendientes, hacer **Merge pull request** a `main`.

Como las ramas personales son permanentes, **no borrar la rama personal al completar el PR**. Para el próximo trabajo, repetir desde el paso 2.

> Si `main` avanzó mientras el PR estaba abierto, sincronizar nuevamente la rama personal con `origin/main`, resolver los posibles conflictos y hacer `push` antes de fusionar.

## Conflictos de merge: qué hacer

Un conflicto significa que Git no pudo combinar automáticamente cambios realizados en zonas incompatibles de un archivo.

1. Ejecutar `git status` para ver los archivos en conflicto.
2. Abrir esos archivos en VS Code, comparar ambas versiones y decidir qué contenido conservar.
3. Revisar el resultado y eliminar los marcadores `<<<<<<<`, `=======` y `>>>>>>>` si aparecen.
4. Marcar los archivos como resueltos con `git add <archivo>`.
5. Finalizar el merge con `git commit` (si Git no lo completó automáticamente).
6. Probar el proyecto y hacer `git push origin matias`.

Si todavía no se resolvió nada y se necesita cancelar la integración, usar `git merge --abort`. No usar `git push --force` ni `git reset --hard` sin coordinarlo.

## Acuerdos de trabajo

- **`main` debe mantenerse estable:** integrar únicamente cambios revisados.
- Trabajar en **ramas personales**, no directamente en `main`.
- Hacer commits chicos, descriptivos y frecuentes.
- Antes de comenzar **y antes de abrir cada PR**, sincronizar con `main`.
- Revisar y probar los cambios antes de fusionarlos.
- Avisar al equipo antes de modificar archivos compartidos, especialmente notebooks `.ipynb`, archivos Power BI `.pbix` y datasets que pueden ser difíciles de fusionar.
- Si varias personas necesitan modificar el mismo archivo, coordinar para minimizar conflictos.

### Resumen rápido del flujo habitual (ejemplo: Matías)

```bash
git switch matias
git status
git fetch origin
git pull --ff-only origin matias
git merge origin/main

# Trabajar y guardar los cambios:
git add <ruta-del-archivo>
git commit -m "Describe el cambio"

# Actualizar nuevamente antes del PR:
git fetch origin
git pull --ff-only origin matias
git merge origin/main

# Publicar en tu propia rama:
git push -u origin matias
```

Por último, abrir un **PR de `matias` hacia `main`**, solicitar revisión y fusionarlo cuando esté aprobado.

## Estructura inicial del proyecto

| Ruta | Propósito |
| --- | --- |
| `data/raw/` | Fuentes `.xlsx` originales (Drive, no modificadas) |
| `data/interim/` | Resultados temporales de las transformaciones |
| `data/processed/` | Tablas limpias y modeladas para los dashboards |
| `src/etl/` | Código de integración, limpieza y validación |
| `dashboards/` | Aplicación y vistas interactivas |
| `notebooks/` | Análisis exploratorio de los datos |
| `tests/` | Pruebas de reglas de negocio e integridad |
| `docs/` | Consigna, inventario y decisiones técnicas |
| `reports/` | Informe de avance y entrega final |

**Datos:** el proyecto utiliza directamente **26 archivos Excel** de la [carpeta compartida de Drive](https://drive.google.com/drive/folders/1uOrWfHv7u-Sr4mhMpFOuWJr7FNXec7lA). Por ahora no se suben los binarios al repositorio: ver [instrucciones para descargarlos](data/raw/README.md) y [fuentes y decisiones](docs/fuentes_y_decisiones.md). No hace falta convertirlos a CSV.
