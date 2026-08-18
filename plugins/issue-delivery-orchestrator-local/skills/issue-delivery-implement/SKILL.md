---
name: issue-delivery-implement
description: "Implementar o reparar un ticket aprobado con alcance YAGNI, obediencia a AGENTS.md, seguimiento exacto del spec, validaciones enfocadas del repositorio y un commit local por ticket o causa raíz. Usar también ante ajustes dentro de Issue Delivery Orchestrator; exigir evidencia posterior proporcional a la superficie afectada antes del handoff."
---

# Implement

Implementar una unidad de trabajo a la vez. Exigir como entrada el spec vigente, ticket o finding, SHA inicial y criterios de aceptación. Leer todos los `AGENTS.md` aplicables antes de editar.

Leer [validation.md](references/validation.md) antes de calcular o ejecutar validaciones.

## Delimitar

1. Inspeccionar código, tests y patrones existentes.
2. Verificar si el comportamiento ya está satisfecho. En ese caso devolver `NO_OP` con evidencia y validación; no crear commit vacío.
3. Identificar la solución mínima compatible con el spec. No añadir abstracciones, compatibilidad ni defensas especulativas.
4. Si el pedido contradice spec, ticket o una decisión aprobada, no editar. Devolver `NEEDS_USER_DECISION` con las fuentes en conflicto.
5. Mantener cualquier log, prompt o memoria bajo el directorio del run en `.local-runtime`.

## Implementar

- Respetar la arquitectura y política de auditoría del backend dueño.
- Mantener interfaces pequeñas y cambios localizados.
- Inspeccionar cobertura existente antes de añadir tests; extender un seam estable para comportamiento o riesgo distinto.
- No editar migraciones comprometidas; generarlas con el script del proyecto dueño.
- Mantener llamadas externas fuera de transacciones.
- No alterar archivos ajenos al ticket, salvo que sean indispensables para la causa raíz.
- No pushear.

## Validar

1. Calcular el delta del ticket desde su SHA inicial, incluyendo archivos creados, modificados, renombrados y eliminados.
2. Ejecutar todos los comandos declarados en `## Validation`.
3. Usar el mecanismo existente del repositorio para calcular proyectos o paquetes afectados por ese
   delta y sus dependientes. En un workspace Nx, aplicar el procedimiento de `validation.md`.
4. Ejecutar typecheck sólo para proyectos afectados que lo expongan.
5. Ejecutar unit tests sólo para proyectos afectados que los expongan.
6. No ejecutar lint, E2E ni validación de todo el repo salvo comando focalizado explícito del ticket.
7. Reparar y repetir hasta tres ciclos. Si sigue rojo, devolver `BLOCKED` con logs reales.
8. No reparar fallos demostrablemente presentes en el SHA integrado de la branch target del perfil;
   reportarlos como base failures.

## Reparaciones posteriores a Implement

Cuando el input sea un ajuste, corrección o reporte de algo que no funciona, cualquiera sea su origen:

1. Convertir el reporte en un escenario de aceptación reproducible y listar las historias afectadas.
2. Implementar y ejecutar la validación enfocada habitual.
3. Entregar el SHA candidato, escenario, superficies afectadas y evidencia mínima propuesta al skill padre.
4. Para lógica determinista usar tests/comandos enfocados. Levantar Local Runtime sólo cuando la integración lo exija. Invocar `issue-delivery-cua-review` en modo `superset` o `vanilla`, o `issue-delivery-browser-review` en modo `codex`, únicamente si cambió o puede haber regresado comportamiento visual/interactivo.
5. Si la verificación falla, usar el finding como nueva entrada. Para blockers remotos, `pr-blocker-convergence` debe emitir `STOP` después de dos iteraciones fallidas de la misma cadena causal.
6. Invalidar sólo el PASS o recibo de una superficie que una edición posterior pueda afectar.

No ejecutar revisión UI por defecto para backend, documentación, tests o build. Si el cambio puede afectar una historia UI, crear `REPAIR-<n>` y verificar esa historia con el reviewer real; si la herramienta necesaria no está disponible, devolver `BLOCKED`.

## Entregar

Antes del commit, devolver:

- Archivos del delta.
- Proyectos o paquetes afectados.
- Comandos ejecutados y resultados.
- Tests no ejecutados y razón.
- Historias UI invalidadas por el cambio.
- Estado de verificación por superficie: `REQUIRED`, `PASS` o `BLOCKED`, incluyendo herramienta y razón.

Crear un commit descriptivo sólo cuando todo lo atribuible al ticket esté verde. Para una reparación de review, usar un commit por causa raíz; agrupar únicamente findings inseparables.

Durante Refactor, limitar cambios al allowlist entregado. Salir de él sólo para una violación concreta de `AGENTS.md` y registrar regla, path y razón.
