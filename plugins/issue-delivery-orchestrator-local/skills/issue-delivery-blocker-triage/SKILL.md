---
name: issue-delivery-blocker-triage
description: "Compatibilidad para analizar blockers de code review en Issue Delivery Orchestrator. Usar cuando un flujo existente invoque esta skill; delegar la clasificación, ledger, herramientas, ciclos y convergencia al contrato canónico pr-blocker-convergence."
---

# Blocker Triage Compatibility

Invocar `pr-blocker-convergence` y obedecer su contrato completo.

Si el caller solicita sólo análisis, ejecutar únicamente preparación, deduplicación, clasificación y actualización del ledger; no editar código ni mutar GitHub. En la fase `review-convergence` del orquestador, permitir el loop autónomo completo de hasta cuatro rondas.

No mantener una taxonomía, ledger ni límite paralelo en esta skill.
