# Paridad con CI

Usar sólo cuando la skill llamadora pida explícitamente paridad con CI (antes del primer push de
una PR y antes de cada push de convergencia). El objetivo es que ningún reviewer ni Action
descubra algo que un comando local ya podía mostrar: specs desactualizados, lint, typecheck,
migraciones fuera de orden o snapshots de contrato stale.

## Fuente de verdad

La CI que importa es la de la branch target, no la del checkout local ni la de `main`. Leer los
workflows desde el remoto, sin cambiar de branch:

```bash
git fetch origin <target>
git ls-tree --name-only origin/<target> .github/workflows/
git show origin/<target>:.github/workflows/<workflow>.yml
```

Para cada workflow cuyo trigger o `paths` coincida con el delta, reproducir sus pasos de
validación con `base = git merge-base origin/<target> HEAD` y `head = HEAD`. Omitir pasos de
deploy, publicación o credenciales remotas y registrarlos como `No ejecutado`.

## TurboShop (target `test`)

Verificado contra `origin/test`. Si un workflow cambió, prevalece el workflow.

| Workflow | Cuándo | Comando local |
| --- | --- | --- |
| `validate-code` lint | Siempre | `node tools/scripts/select-direct-projects.js --base <base> --head HEAD --target lint --output-file <f>` y luego `pnpm nx run-many --target=lint --projects=<lista> -- --max-warnings=0`. Los warnings fallan. |
| `validate-typescript` | Siempre | `pnpm nx affected --target=typecheck --base=<base> --head=HEAD --parallel=1` |
| `validate-code` unit tests | Siempre | Mismo selector con `--target test`; `pnpm nx run-many --target=test --projects=<lista> --parallel=1 -- --runInBand` |
| `validate-code` DB tests | Proyectos con `test:db` en el delta | Selector con `--target test:db`; requiere Postgres del Local Runtime. Sin base de datos disponible, registrar `No ejecutado` con motivo. |
| `validate-migrations` | Hay migraciones nuevas o movidas | Leer `tools/scripts/validate-pr-migrations.js` en `origin/<target>` para sus variables. Ejecutarlo en un checkout desechable bajo el directorio del run con un merge temporal de `origin/<target>`; nunca integrar la target en la branch. |
| `shipment-mobile-compatibility` | Cambios en `apps/shipment-mobile-bff` o en contratos que expone | `pnpm nx run shipment-mobile-bff:contract-snapshot` y `pnpm nx run shipment-mobile-bff:compatibility-gate`. Si el snapshot cambia de forma intencional, commitearlo junto con el cambio. |
| `railway-config` | Cambios en `.railway/**` | `pnpm railway:check`. El `plan` y el `apply` requieren credenciales: `No ejecutado`. |
| `supplier-availability-contract` | Rutas de `paths` del workflow | Los comandos jest y typecheck del workflow. |

Además, chequear estos patrones que CI no siempre cubre y que ya bloquearon PRs:

- Config de Expo que referencia archivos (`googleServicesFile`, assets, plugins): el archivo debe
  existir o inyectarse en todos los builds soportados.
- Tests dentro de `src/app` de apps Expo Router: Metro los carga como rutas. Mantenerlos fuera o
  excluidos.
- Dependencias usadas por scripts o workflows (`tsx`, CLIs) deben declararse directamente; pnpm
  aislado no resuelve transitivas.
- Specs cuyas expectativas contradicen el último cambio: ejecutar siempre los specs de los archivos
  tocados después del último commit, no sólo antes.

## Recibo

Agregar al recibo habitual una tabla `Check | Comando | Resultado` con el código de salida y los
conteos (tests, warnings, proyectos). Esa tabla alimenta directamente el bloque de validación de la
PR. Toda omisión va a `No ejecutado` con su motivo; nunca marcar `PASS` un check que no corrió.
