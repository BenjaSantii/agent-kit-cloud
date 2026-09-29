---
name: issue-delivery-orchestrator
description: "Orquestar de extremo a extremo una issue de Linear en modo Codex, Superset o Vanilla: adoptar el worktree, usar la rama de Linear, publicar spec/tickets, implementar, refactorizar, verificar la superficie afectada, crear la PR y converger blockers y Actions sin integrar otras ramas. Usar también para ajustes posteriores; cada reparación exige evidencia nueva proporcional al riesgo antes del handoff."
---

# Issue Delivery Orchestrator

Operar como plano de control conversacional. Usar el CLI privado como motor determinista; no ejecutar un segundo Grill interactivo mediante `codex exec`. Mantener toda decisión humana en la conversación actual.

Leer [workflow-contract.md](references/workflow-contract.md) antes de iniciar o reanudar una ejecución.

Si el usuario pide modificar o actualizar **este plugin** en vez de entregar una issue, leer
[plugin-maintenance.md](references/plugin-maintenance.md): editar siempre el repositorio fuente y
nunca el snapshot instalado en `plugins/cache/`.

Cuando se nombre otra skill incluida, invocarla con la sintaxis nativa del host: `$<skill>` en
Codex o `/issue-delivery-orchestrator-local:<skill>` en Claude Code. Resolver `<plugin-root>` como
el directorio instalado del plugin; en Claude Code corresponde a `${CLAUDE_PLUGIN_ROOT}`. Claude
Code nunca selecciona modo `codex`: usar `superset` cuando exista su señal válida y `vanilla` en
cualquier otro checkout preparado.

## Iniciar o reanudar

1. Resolver `<plugin-root>` como el directorio que contiene `.codex-plugin/plugin.json` o
   `.claude-plugin/plugin.json`. Ejecutar
   `python3 <plugin-root>/scripts/issue-delivery config` y bloquear si faltan
   `LINEAR_EXPECTED_EMAIL`, `GITHUB_EXPECTED_LOGIN` o no puede resolverse el repositorio objetivo
   desde la configuración o el worktree actual.
2. Exigir una issue existente de Linear por ID o URL. Para un run nuevo, permitir un modo explícito
   del usuario o detectarlo desde el worktree actual:

   - `codex`: iniciar el chat en la app de Codex con **Worktree** seleccionado y elegir la base
     solicitada, o la `defaultBase` del perfil. Codex crea el worktree antes de ejecutar el loop.
     Fijar el chat hasta el merge y cleanup final.
   - `superset`: crear en Superset el worktree sobre la rama entregada por Linear y abrir la sesión
     dentro de ese workspace.
   - `vanilla`: iniciar Codex CLI o Claude Code directamente en un checkout o worktree ya preparado
     por el usuario o su herramienta habitual. Ejecutar el setup local del repositorio antes del
     loop y seleccionar siempre `--mode vanilla`. En Claude Code, elegir este modo salvo que el
     checkout tenga una señal válida de Superset.

3. Antes de cambiar de directorio, ejecutar `git rev-parse --show-toplevel` en el workspace actual y
   conservar esa ruta absoluta. No iniciar modo `codex` desde Local, modo `superset` desde otro
   checkout ni modo `vanilla` fuera del checkout que se desea adoptar. No crear, solicitar ni
   delegar otro worktree mediante `create_thread`, subagentes, `git worktree add` o cualquier
   mecanismo equivalente. Si el worktree actual no es adoptable, bloquear en la misma sesión y
   pedir al usuario que abra manualmente otro con su setup local.
4. Ejecutar, agregando `--mode <codex|superset|vanilla>` sólo cuando el usuario indique uno:

   ```bash
   python3 <plugin-root>/scripts/issue-delivery <issue> --worktree <ruta> \
     [--mode <codex|superset|vanilla>] \
     [--base <branch>] [--new-run]
   ```

5. Confirmar `modeSource` y `developmentMode` en la respuesta. La detección usa, en orden:
   `SUPERSET_WORKSPACE_PATH` coincidente, raíces configuradas y componentes inequívocos de la ruta
   como `.codex` o `superset-worktrees`. Si no encuentra ninguna señal, elegir `vanilla` con
   `modeSource: vanilla-fallback`; si detecta señales contradictorias, pedir el modo al usuario. El
   modo determina el workspace y reviewer durante todo el run:

   - `codex` adopta el worktree del chat, acepta su `detached HEAD`, lo conecta a la rama de Linear
     y usa `issue-delivery-browser-review`.
   - `superset` adopta el worktree ya conectado a la rama de Linear y usa `issue-delivery-cua-review`. También
     acepta `SUPERSET_WORKSPACE_PATH`.
   - `vanilla` adopta el checkout/worktree indicado, permite partir desde `origin/<base>`,
     `detached HEAD` seguro o la rama de la issue, conecta la rama de Linear y usa
     `issue-delivery-cua-review`.

6. Publicar inmediatamente en el chat, para runs nuevos y reanudados, los valores exactos de
   `modeDecision` devueltos por el motor. Usar un mensaje autocontenido como:

   ```text
   Modo decidido: <mode> (fuente: <source>).
   Reviewer: <reviewer>.
   Worktree adoptado: <worktree>.
   ```

   No continuar al Grill ni presentar el modo sólo en logs o handoff final. Si `source` es
   `vanilla-fallback`, decir expresamente que se eligió Vanilla porque no hubo señales Codex o
   Superset. Si el motor bloquea la adopción del fallback por un checkout dirty, anunciar igualmente
   la decisión incluida en el error antes de pedir que se preserven o limpien los cambios.
7. Usar la branch base del perfil por defecto. En modo Codex, crear una rama inexistente desde el
   último `origin/<base>`; reutilizar la rama local o remota de la issue cuando exista.
8. No cambiar modo, worktree ni reviewer después de crear el run. Obedecer `currentPhase`,
   `developmentMode` y `reviewerMethod`; no recrear un run preservado.
   En modo Codex, no usar Handoff a Local: el estado ignorado bajo `.local-runtime` debe permanecer
   en el mismo worktree/chat.
9. Trabajar exclusivamente en el worktree retornado. Guardar prompts, snapshots, logs y evidencias
   bajo `.local-runtime/issue-delivery-orchestrator/<run-id>/`.
10. No guardar tokens, cookies ni secretos en el worktree. El CLI valida las identidades Linear y
    GitHub configuradas antes de mutar servicios.
11. Toda lectura y mutación de Linear debe pasar por el CLI autenticado con la API key personal.
    Antes del Grill y cada vez que se necesite contexto remoto actualizado, ejecutar:

    ```bash
    python3 <plugin-root>/scripts/issue-delivery <issue> read-linear-issue
    ```

    Usar su descripción y comentarios como fuente remota. No invocar `$linear`, `linear:linear`,
    `codex_apps.linear` ni ninguna app o conector MCP de Linear, ni siquiera para lectura. Si el
    comando falla, bloquear con su error; no recurrir al OAuth compartido como fallback.
12. Ejecutar también todas las escrituras mediante las acciones específicas del CLI. Respetar
    `LINEAR_COMMENTS_ENABLED`; cuando sea `false`, no crear comentarios en Linear en ninguna fase.

Los runs anteriores sin `mode` persistido conservan su worktree y reviewer históricos; exponer
`developmentMode=codex` sólo para `codex-browser` y `developmentMode=superset` para `cua-driver`,
sin migrar estado, ramas ni procesos. No inferir `vanilla` para estados legacy. Las sesiones que ya
están ejecutando el loop continúan sobre ese contrato.

Toda adopción exige el mismo repositorio y `.local-runtime` ignorado. Superset exige la rama exacta
de Linear o un prefijo truncado con el mismo ID. Codex admite el `detached HEAD` creado por la app.
Para todo run nuevo, el CLI descarta cambios trackeados y archivos no trackeados del worktree antes
de adoptar; preservar archivos ignorados como `.env`, dependencias y `.local-runtime`, y registrar
las rutas descartadas en `discardedInitialStatus`. No abandonar commits propios: bloquear si el
`HEAD` contiene commits que no estén preservados en la branch de la issue o la base remota. Nunca
limpiar al reanudar un run existente.

Excepción de seguridad: si `vanilla` fue elegido mediante `vanilla-fallback`, exigir un checkout
sin cambios trackeados ni archivos no ignorados y bloquear antes de limpiar si está dirty. Permitir
la limpieza normal sólo después de que el usuario preserve/limpie esos cambios o seleccione
explícitamente `modo vanilla`.

Si una fase se bloquea, registrar y detener procesos propios:

```bash
python3 <plugin-root>/scripts/issue-delivery <issue> block --reason "<causa>"
```

Agregar `--decision` cuando se requiera una elección del usuario. Tras resolverla:

```bash
python3 <plugin-root>/scripts/issue-delivery <issue> resume
```

## Invariante de reparación y handoff

Aplicar esta regla en cualquier fase y también después de `completed_preserved`. Aplicarla a toda modificación correctiva posterior al inicio de Implement, sin importar si nace de un reporte del usuario, finding de Cua, review humano o automatizado, Action fallida, conflicto o descubrimiento del agente.

Considerar ciclo de reparación toda instrucción que pida ajustar, corregir o cambiar una implementación existente, o que reporte que algo no funciona, se ve mal o no cumple lo esperado. No tratarla como una edición aislada.

1. Reanudar el mismo run y worktree. Capturar el reporte exacto como escenario de aceptación de reparación.
2. Identificar las historias afectadas. Si el caso no estaba en el spec, crear una historia temporal `REPAIR-<n>` dentro del estado ignorado del run con precondición, pasos y resultado esperado; no ampliar el spec remoto por un bug compatible con su intención.
3. Invocar `issue-delivery-implement`, que debe delegar la validación automatizada enfocada a `test`, y dejar la branch en su estado final.
4. Declarar en el ledger del blocker la superficie afectada y la evidencia mínima necesaria: `STATIC`, `TEST`, `API_COMMAND`, `LOCAL_RUNTIME` o `UI`.
5. Levantar Local Runtime sólo cuando la integración o el estado ejecutándose sean parte del riesgo. Para `UI`, invocar el reviewer fijado por el modo: `issue-delivery-cua-review` en `superset` o `vanilla`, o `issue-delivery-browser-review` en `codex`.
6. No invocar CUA/browser para cambios exclusivamente backend, documentación, tests, build o lógica no observable en UI. Si una reparación puede invalidar una historia UI aceptada, repetir sólo esa historia con el reviewer fijado.
7. Si la verificación detecta un fallo, volver a `issue-delivery-implement` y repetir. Delegar la detección de ciclos y el límite de dos iteraciones fallidas a `pr-blocker-convergence`.
8. Considerar obsoleta sólo la evidencia cuya superficie pueda verse afectada por el último cambio. Actualizar capturas publicadas cuando corresponda.

Prohibir el handoff hasta disponer de evidencia posterior al último cambio para cada superficie afectada, con SHA verificado. Para UI, exigir PASS del reviewer del modo; para las demás, exigir el test, comando o análisis declarado en el ledger. Si la herramienta necesaria no está disponible, bloquear y explicar el impedimento; no degradar la cobertura.

## 1. Grill

1. Leer la issue, el repositorio y todos los `AGENTS.md` aplicables.
2. Invocar `issue-delivery-grill` en esta conversación. Si ya existe spec/tickets, tratarlos como base y reconciliar los mismos bloques e IDs.
3. Si existe Figma, inspeccionarlo mediante su MCP. Si no es accesible, bloquear antes de implementar, salvo que el usuario entregue explícitamente un PNG o PDF como fallback.
4. Etiquetar cada user story con una superficie verificable: `UI`, `API-assembled` o `command-test`.
5. Obtener aprobación explícita del spec y del desglose.
6. Invocar, en orden, `issue-delivery-spec-publisher` y `issue-delivery-ticket-publisher`.
7. Informar inmediatamente todo ticket HITL: ID, título, justificación, acción humana, dependencias y momento aproximado de pausa. No usar HITL para tareas difíciles que un agente sí puede resolver.
8. Guardar snapshots aprobados dentro del run y completar:

   ```bash
   python3 <plugin-root>/scripts/issue-delivery <issue> checkpoint --phase grill \
     --artifact spec=<ruta> --artifact tickets=<ruta>
   ```

## 2. Implement

Procesar tickets en su orden aprobado. Antes de cada uno, entregar a `issue-delivery-implement` el spec completo, el ticket, el SHA inicial y la validación declarada para que la delegue a `test`.

- Terminar primero los tickets AFK no bloqueados.
- Pausar justo antes de un HITL y pedir la acción mínima al usuario.
- Crear un commit descriptivo por ticket validado, sin push.
- Si ya está satisfecho, registrar `NO_OP` con evidencia y validación; no crear commits vacíos.
- Limitar a tres ciclos implementación-reparación por ticket. Bloquear si sigue rojo.
- Incluir commits preexistentes adoptados en la revisión del diff completo, sin reescribirlos.

Completar `implement` sólo con todos los tickets aceptados:

```bash
python3 <plugin-root>/scripts/issue-delivery <issue> checkpoint --phase implement
```

## 3. Refactor

Leer [refactor-review.md](references/refactor-review.md) completamente. Revisar el diff de
implementación contra los `AGENTS.md` aplicables y ejecutar cada gate de esa referencia.

- Allowlist: archivos cambiados por la implementación de este run y por commits preexistentes adoptados de la issue.
- Salir del allowlist sólo para corregir una violación concreta de `AGENTS.md`; registrar regla, archivo y razón.
- No hacer refactors especulativos.
- Invocar `test` después del último cambio de cada commit de refactor y consumir su recibo.
- Guardar el recibo de revisión bajo el directorio ignorado del run. No completar la fase con
  criterios `FAIL` o sin evidencia.

Completar la fase con:

```bash
python3 <plugin-root>/scripts/issue-delivery <issue> checkpoint --phase refactor \
  --artifact refactor-review=<ruta-del-recibo>
```

El orquestador puede ejecutar `git fetch` para consultar referencias remotas, pero nunca integra
ramas base u objetivo mediante `rebase`, `merge`, `cherry-pick` o `pull`. La PR se construye desde
la historia existente de la branch adoptada y se dirige a `pr_target_branch`.

## 4. Revisión manual

1. Inicializar un runtime persistente:

   ```bash
   python3 <plugin-root>/scripts/issue-delivery <issue> runtime-init
   ```

2. Levantar sólo las apps necesarias mediante `pnpm local-runtime` o `pnpm agent:*`, registrar sus PID y usar el runtime activo.
3. Ramificar exclusivamente por `developmentMode`:

   - `superset`: abrir el navegador dedicado mediante
     `python3 <plugin-root>/scripts/issue-delivery <issue> launch-browser --url <url-local>` e invocar `issue-delivery-cua-review`.
   - `vanilla`: abrir el navegador dedicado mediante el mismo comando e invocar
     `issue-delivery-cua-review` desde el checkout adoptado.
   - `codex`: no ejecutar `launch-browser`; exigir la app de Codex y Browser disponible,
     e invocar `issue-delivery-browser-review`. Permitir Playwright headless sólo para una story
     con brecha demostrada de `file-upload` o `hover`, sin cambiar reviewer ni modo.

4. Verificar las historias `UI` con el reviewer seleccionado y las demás mediante su superficie declarada.
5. Ningún reviewer edita código. Entregar findings a `issue-delivery-implement`, reparar y repetir sólo las historias invalidadas con el mismo método.
6. Permitir como máximo cinco ciclos revisión-reparación.
7. Leer
   [evidence-annotations.md](references/evidence-annotations.md). Conservar únicamente capturas
   originales del estado final aceptado y producir un manifiesto v2 con `provider` igual al método
   seleccionado. Exigir callouts honestos sobre lo nuevo o `annotationReason` para cambios globales.
8. Ejecutar
   `python3 <plugin-root>/scripts/issue-delivery <issue> prepare-evidence --manifest <ruta>`,
   inspeccionar la copia anotada y corregir bounds o captions antes del checkpoint. El motor
   preserva el original.

Leer [headless-assistance.md](references/headless-assistance.md). Mantener el reviewer del modo como
primera opción para toda story. Si no puede ejecutar `file-upload` o mantener/demostrar un `hover`
real, demostrar la brecha y activar Playwright headless sólo para esa story. Un resultado
incorrecto de la app es `FAIL`, no una brecha de capacidad. Bloquear cuando Playwright tampoco
pueda cubrirla. No degradar cobertura ni cambiar automáticamente de reviewer o modo.

Completar la fase con:

```bash
python3 <plugin-root>/scripts/issue-delivery <issue> checkpoint \
  --phase manual-revision --artifact ui-manifest=<ruta>
```

El checkpoint vuelve a preparar y validar las anotaciones.

## 5. PR

Leer [pr-quality.md](references/pr-quality.md) completamente antes de esta fase. Los tres pasos
siguientes son obligatorios y el motor los exige; no abrir la PR para "ver qué dice el bot".

1. **Paridad con CI.** Invocar `test` en modo paridad con CI sobre el delta completo contra
   `origin/<pr_target_branch>`. Reparar todo `branch-caused` con `issue-delivery-implement` antes de
   seguir. Nunca pushear una branch que ya se sabe roja en lint, typecheck, tests o chequeos de
   contrato/migraciones.
2. **Review previa a la PR.** Ejecutar `local-reviewer` sobre la branch y procesar sus findings con
   `pr-blocker-convergence` como ronda `00` local. Registrar el recibo contra el HEAD exacto:

   ```bash
   python3 <plugin-root>/scripts/issue-delivery <issue> record-pre-review --receipt <ruta>
   ```

   `ensure-pr` rechaza crear una PR nueva sin un recibo `PASS` o `SKIP_ONLY` del HEAD actual.
3. **PR y validación visible.** Crear el body dentro del run y ejecutar:

   ```bash
   python3 <plugin-root>/scripts/issue-delivery <issue> ensure-pr --body-file <ruta>
   python3 <plugin-root>/scripts/issue-delivery <issue> publish-validation --receipt <ruta>
   python3 <plugin-root>/scripts/issue-delivery <issue> publish-evidence --manifest <ruta>
   ```

   `publish-validation` reemplaza el bloque marcado de validación del body con el recibo del HEAD
   pusheado. Los checkpoints `pr-creation` y `review-convergence` bloquean si ese bloque no
   corresponde al HEAD actual.

Publicar cada PNG anotado en dos destinos distintos:

- Linear: copia privada para `## UI enhancements`.
- GitHub: copia en la evidence branch del perfil, fuera de la branch y diff de producto.

Publicar además el PNG original en ambos destinos y enlazarlo bajo la imagen anotada. Las
anotaciones son evidencia explicativa; nunca reemplazan la captura original auditable.

El comentario de la PR debe usar exclusivamente las rutas relativas devueltas por el motor. No
insertar URLs privadas de uploads de Linear: el proxy de imágenes de GitHub no puede renderizarlas.

Si un run antiguo ya publicó links rotos, repararlos sin repetir la validación funcional:

```bash
python3 <plugin-root>/scripts/issue-delivery <issue> repair-evidence-links
```

Este comando debe rehostear exactamente las PNG ya aceptadas y actualizar el comentario idempotente; no autoriza a sustituirlas por capturas distintas.

La PR debe ser normal, no draft, siempre hacia la branch target del perfil, sin asignar reviewers.
Reutilizar una PR abierta compatible. Una PR cerrada sin merge requiere decisión; una ya mergeada
exige issue/branch de seguimiento.

Completar la fase con `python3 <plugin-root>/scripts/issue-delivery <issue> checkpoint --phase pr-creation`.

## 6. Convergencia remota

Invocar `pr-blocker-convergence` como único contrato de clasificación, ledger, selección de herramientas y detección de ciclos. Ejecutar automáticamente hasta cuatro rondas:

```bash
python3 <plugin-root>/scripts/issue-delivery <issue> wait-review
```

Cada ronda usa los tiempos y autores automatizados declarados por el perfil. En el perfil TurboShop,
esperar diez minutos de quietud desde el último cambio relevante, con un máximo de veinte minutos
por ronda y polling cada quince segundos. Procesar sólo problemas concretos de los bots configurados
y sólo la sección `BLOCKERS` de los `blockerBots` (x100 en TurboShop); ignorar summaries, walkthroughs, sugerencias
opcionales y comentarios humanos durante el ciclo automático.

1. Entregar el snapshot completo a `pr-blocker-convergence`; esa skill agrega nuevos blockers, deduplica por causa raíz y decide `FIX`, `SKIP`, `NEEDS_USER_DECISION` o `STOP`.
2. Reparar automáticamente cada `FIX/MODEL` mediante `issue-delivery-implement`. Usar un commit por causa raíz, validar con las herramientas declaradas, repetir la paridad con CI sobre el delta completo y hacer un único push por ronda. Inmediatamente después del push, regenerar el recibo y ejecutar `publish-validation` antes de `wait-review`, para que cada corrida del reviewer vea la validación del SHA que revisa.
3. Si una solicitud exige negocio, arquitectura incompatible o cambiar un acuerdo vigente, registrar `NEEDS_USER_DECISION`, completar primero trabajo independiente seguro y pausar.
4. Si una cadena acumula dos iteraciones de reparación fallidas, registrar `STOP`, no intentar otro parche y avisar al usuario con la línea temporal y alternativas.
5. Si el usuario mantiene el spec, guardar `SKIP/PRIOR_DECISION`. Si acepta al reviewer, reconciliar primero spec y tickets en Linear y recién después editar.
6. Después de validar y pushear cada `FIX`, resolver su thread inline o reconocer su comentario
   general de un `blockerBots` con:

   ```bash
   python3 <plugin-root>/scripts/issue-delivery <issue> acknowledge-blocker --comment-id <id> --decision FIX
   ```

7. Cuando todo feedback automatizado todavía pendiente tenga decisión `SKIP` —sin `FIX`, `NEEDS_USER_DECISION` ni `STOP` restantes— crear dentro del run:

   ```json
   {
     "skips": [
       {
         "commentId": 123,
         "title": "Título breve",
         "reason": "Motivo público, concreto y autocontenido."
       }
     ]
   }
   ```

   Publicar una explicación visible antes de cerrar o reconocer esos blockers:

   ```bash
   python3 <plugin-root>/scripts/issue-delivery <issue> publish-skip-summary --input <ruta-json>
   ```

   El comando consulta ambas superficies en vivo y exige que el archivo cubra exactamente todos los
   blockers automatizados pendientes. Crea o actualiza idempotentemente un único comentario general
   de la PR bajo la identidad GitHub configurada. No incluir datos privados del ledger.
8. Sólo después de publicar el resumen, resolver los threads inline con `SKIP` y reconocer cada
   comentario general de un `blockerBots`:

   ```bash
   python3 <plugin-root>/scripts/issue-delivery <issue> acknowledge-blocker --comment-id <id> --decision SKIP
   ```

   `acknowledge-blocker` añade idempotentemente `+1` bajo la identidad configurada, registra el
   recibo y rechaza un `SKIP` sin resumen público.
9. Monitorear Actions. Reparar sólo fallos causados o agravados por la branch.
10. Aplicar la invariante de reparación según la superficie declarada. Usar CUA/browser sólo para comportamiento UI afectado; registrar `ninguna` cuando no se requiera herramienta especial.

Terminar como `completed_with_base_failures` cuando sólo queden fallos demostrablemente heredados. Terminar antes si el gate queda limpio. Después de la cuarta ronda, no pedir extensiones ni seguir reparando automáticamente: informar el estado completo, incluidos blockers nuevos de esa ronda. Un `STOP` o `NEEDS_USER_DECISION` bloquea el checkpoint hasta decisión explícita.

Antes de aceptar la ronda final, ejecutar un refetch determinista de ambas superficies de
review:

```bash
python3 <plugin-root>/scripts/issue-delivery <issue> review-gate
python3 <plugin-root>/scripts/issue-delivery <issue> checkpoint --phase review-convergence
```

`review-gate` consulta en vivo los `reviewThreads` inline mediante GraphQL y los comentarios
generales de la PR. Debe bloquear mientras exista un thread automatizado sin resolver o un
comentario general accionable de un `blockerBots` sin `+1` de la identidad GitHub configurada; los comentarios humanos
no participan del gate automático. El checkpoint de `review-convergence` vuelve a ejecutar el
mismo gate y no puede omitirse aunque el snapshot de una ronda esté incompleto o desactualizado.
También rechaza todo `SKIP` reconocido que no figure en un resumen público. Procesar todo
resultado pendiente con `pr-blocker-convergence` antes de reintentar. El informe final debe
indicar ronda, SHA, cantidades por disposición, blockers nuevos versus repetidos, checks, gate,
herramientas planificadas y herramientas realmente usadas.

El CLI detiene procesos propios y conserva worktree, rama, runtimes y estado.

## Review humano posterior y cleanup

Ignorar review humano salvo petición explícita. Para atenderlo, reanudar el mismo run en `review-convergence`, procesar únicamente feedback autorizado y aplicar íntegramente la invariante de reparación y handoff, además de los gates de spec, validación y evidencia.

Después del merge y sólo por petición explícita:

```bash
python3 <plugin-root>/scripts/issue-delivery <issue> cleanup
```

Eliminar recursos de todos los runtimes y el perfil del navegador. Preservar worktree y branch local. Rechazar cleanup antes del merge salvo `--force` explícito del usuario.
