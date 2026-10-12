# Mantenimiento del plugin

Aplica sólo cuando el usuario pide modificar, corregir o actualizar **este plugin**. No aplica a la
entrega de issues de producto.

## Fuente canónica

El repositorio fuente es:

```text
~/agent-kit-cloud/plugins/issue-delivery-orchestrator-local
```

Codex y Claude Code instalan el plugin copiando un snapshot inmutable al caché:

- Claude Code: `~/.claude/plugins/cache/agent-kit-cloud/issue-delivery-orchestrator-local/<version>/`
- Codex: `~/.codex/plugins/cache/agent-kit-cloud/issue-delivery-orchestrator-local/<version>/`

Ambos hosts instalan desde el mismo marketplace `agent-kit-cloud`, cuya raíz es
`~/agent-kit-cloud`: Codex lee `.agents/plugins/marketplace.json` y Claude Code
`.claude-plugin/marketplace.json`.

Editar el caché no cambia la fuente y se pierde en la siguiente instalación.

## Regla

1. Resolver `<plugin-root>` y compararlo con la fuente canónica. Si `<plugin-root>` está bajo un
   directorio `plugins/cache/`, la sesión corre desde un snapshot instalado.
2. Aplicar **todas** las ediciones en la fuente canónica, nunca en el caché.
3. Si la fuente canónica no existe en esta máquina, bloquear y pedir su ruta al usuario en lugar de
   editar el snapshot.

## Publicar el cambio

Incrementar la versión en **ambos** manifiestos antes de reinstalar; el instalador reutiliza el
bundle cacheado cuando la versión no cambia.

- `.claude-plugin/plugin.json` → `version`
- `.codex-plugin/plugin.json` → `version` (conserva el sufijo de build `+codex.<timestamp>`)

Validar antes de reinstalar:

```bash
corepack pnpm test
```

Reinstalar en Claude Code. Usar `update`, no `install`: `install` corta con "already installed" y
deja el snapshot anterior en el caché.

```bash
claude plugin marketplace update agent-kit-cloud
claude plugin update issue-delivery-orchestrator-local@agent-kit-cloud
```

Reinstalar en Codex. `marketplace upgrade` sólo refresca snapshots de marketplaces **Git**; el
marketplace `agent-kit-cloud` es local, así que basta el bump de versión y volver a agregar el plugin.

```bash
codex plugin add issue-delivery-orchestrator-local@agent-kit-cloud
```

Los cambios sólo se cargan en una sesión o chat nueva. Para iterar sin reinstalar, Claude Code
puede cargar la fuente en vivo:

```bash
claude --plugin-dir ~/agent-kit-cloud/plugins/issue-delivery-orchestrator-local
```

Codex no expone un equivalente a `--plugin-dir`: cada cambio exige bump de versión y reinstalación.
