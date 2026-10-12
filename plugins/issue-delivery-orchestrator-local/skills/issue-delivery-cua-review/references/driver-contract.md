# Contrato de Cua Driver

## Selección de entorno

Usar un escritorio Linux en Docker por defecto. Usar el escritorio real sólo cuando el usuario
lo indique. Si falta Docker, Cua o una capacidad exclusiva del host, devolver `BLOCKED`; no cambiar
de entorno automáticamente. El modo del orchestrator y `provider=cua-driver` se conservan.

## Docker

Comprobar `docker info`, `cua --version` y `cua runtime doctor`. Usar la CLI `cua` para crear
el escritorio que contiene Cua Driver. Un `cua-driver` ejecutado en el Mac controla el Mac,
aunque Docker esté encendido; todas las observaciones y acciones deben apuntar al sandbox.

Asignar un nombre único al run, por ejemplo `ido-<run-id>`, y una raíz absoluta ignorada:

```bash
export CUA_HOME="<worktree>/.local-runtime/issue-delivery-orchestrator/<run-id>/cua"
cua --embedded --state-dir "$CUA_HOME/sandboxes" sandbox create \
  ghcr.io/trycua/linux:24.04-slim --on local --kind container --runtime runc \
  --name <sandbox-name> --cpu 2 --memory 4GB --wait desktop
cua --embedded --state-dir "$CUA_HOME/sandboxes" do switch <sandbox-name>
```

Conservar `CUA_HOME` y `--state-dir` en cada llamada, también desde otra shell. Esto separa
el target seleccionado, sesiones y estado de otros runs. Antes de reanudar, consultar
`sandbox info`, confirmar propiedad y recuperar sólo ese sandbox. No reutilizar uno ajeno.

Registrar nombre, ID de contenedor, imagen, raíz de estado, perfil del navegador dentro del
contenedor y relación entre URL del host y URL del sandbox en `validation/ui/cua-environment.json`.
No copiar `env_token` ni secretos al recibo. Los PID y window IDs del guest pertenecen al guest;
nunca pasarlos a `register-process` ni a comandos que terminen procesos del host.

Mantener las apps y bases del producto en el Local Runtime activo. En Docker Desktop, sustituir
el hostname local por `host.docker.internal`, conservando puerto, path, query y fragmento. Verificar
también los backends, redirecciones y WebSockets que el navegador necesita. Si una URL embebida
apunta al localhost del guest, resolver su conectividad con la configuración existente o un
proxy del run; no modificar código de producto sólo para la revisión. En otros motores Docker,
comprobar una ruta equivalente al host. Una URL no alcanzable es `BLOCKED`, no `FAIL` del producto.

Abrir Chromium en el guest con un perfil exclusivo, por ejemplo `/tmp/ido-browser-profile`:

```bash
cua --embedded --state-dir "$CUA_HOME/sandboxes" do launch chromium \
  --user-data-dir=/tmp/ido-browser-profile --no-first-run --no-default-browser-check <guest-url>
cua --embedded --state-dir "$CUA_HOME/sandboxes" do screenshot --save <absolute-host-png>
cua --embedded --state-dir "$CUA_HOME/sandboxes" do click <x> <y>
cua --embedded --state-dir "$CUA_HOME/sandboxes" do type "<text>"
```

Inspeccionar `cua do --help` y la ayuda de la acción si su forma es incierta. También se pueden
usar las herramientas MCP de Cua enlazadas al mismo sandbox. Preferir acciones por elemento
cuando el árbol las exponga; para visión, tomar las coordenadas de la última captura exacta.
Capturar y verificar después de cada acción. Un envío exitoso no prueba que la UI cambió.

El foreground y scope `desktop` del guest no toman la pantalla del usuario y pueden usarse
dentro del sandbox propio. No abrir el viewer del host salvo que el usuario lo solicite.
Los PNG de `--save` se escriben en el host; usar rutas absolutas bajo `validation/ui/`.
Copiar sólo fixtures necesarios al guest para uploads. No montar perfiles personales, todo
el home del usuario ni el socket Docker dentro del guest.

Conservar el sandbox durante los ciclos de reparación. Al terminar o bloquear, ejecutar
`sandbox rm <sandbox-name> --force` con la misma raíz de estado y registrar el resultado en
el recibo del entorno. No asumir que `stop-processes` limpia contenedores. No borrar capturas.

## Host explícito

Aplicar esta sección sólo cuando el usuario seleccione el escritorio real. Exigir Accessibility
y Screen Recording en macOS bajo la identidad de `CuaDriver.app`. No ejecutar instaladores,
`permissions grant`, `check_permissions` ni cambios de telemetry desde el reviewer.

Usar `launch-browser` del motor para abrir el navegador y perfil exclusivos del run. Registrar
su PID con el motor. Obtener `window_id` mediante `list_windows`; renovarlo al cambiar de ventana.
Mantener una sesión única derivada del run ID en cada llamada que la acepte.

```bash
cua-driver call list_windows '{"pid": <pid>}'
cua-driver call get_window_state \
  '{"pid": <pid>, "window_id": <window-id>, "session": "<run-session>"}' \
  --screenshot-out-file <absolute-host-png>
```

Preferir `element_token`. Para `element_index`, incluir el `snapshot_id` correspondiente.
Las coordenadas nativas provienen del PNG de esa misma ventana; las del navegador usan
el viewport de su propia captura. Renovar el estado antes de reutilizar elementos.

Usar `delivery_mode=background`. No activar foreground ni scope `desktop` del host sin una
indicación del usuario que permita tomar el foco. Una acción que necesita foco y no está
autorizada bloquea esa story. No controlar ventanas personales ni sesiones ajenas al run.

## Datos y evidencia

Usar cuentas y datos locales sembrados. Verificar el SHA y runtime activos antes de capturar.
Guardar screenshots originales y recibos bajo el run y mantener `provider=cua-driver`.
