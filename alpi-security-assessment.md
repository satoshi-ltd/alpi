# Seguridad de Alpi — pendientes antes de exponer una instancia online

Estado revisado contra el código el **7 de agosto de 2026**, después de
implementar endpoints `ws://` / `wss://`, soporte TLS en Desktop y Mobile,
configuración desde `alpi setup` y Desktop, protección básica contra abuso del
WebSocket, el overlay Docker/Caddy distribuido en v0.12.10 y emparejamiento de
un solo uso implementado y endurecido para v0.12.11. El transporte WSS
se ha verificado con una conexión y RPC autenticada reales mediante Tailscale
Funnel; sigue pendiente validar el dominio y firewall definitivos del cliente.

Este documento ya no conserva la auditoría histórica ni propuestas descartadas.
Es únicamente el trabajo de seguridad que sigue pendiente.

Una conexión controla **quién puede hablar con Alpi**, con qué rol y con qué
alcance de profiles. No es un sandbox de las herramientas del agente. Bloquear
`terminal`, `skill` o la red de forma general no forma parte de este plan: cada
profile debe conservar las herramientas que necesita para hacer su trabajo.

---

## P0 — Antes de abrir el dominio al cliente

### 1. Desplegar y comprobar la topología WSS

El soporte está implementado, pero la seguridad final depende del despliegue.

- Crear el DNS de `your.domain.com` apuntando a la máquina correcta.
- Permitir entrada pública únicamente a `80/tcp` y `443/tcp`. El puerto 80 se
  usa para la emisión/renovación del certificado; el tráfico de cliente entra
  por 443.
- Mantener `49200` fuera de Internet. Puede publicarse en loopback, en una IP
  privada o en la IP de Tailscale, pero no en `0.0.0.0` del host público.
- Arrancar el overlay `docker-compose.wss.yml` con `ALPI_DOMAIN` configurado.
  El overlay elimina las publicaciones heredadas de `49200` y `7423`; verificar
  el resultado con `docker compose ... config` antes de desplegar.
- Configurar `host.endpoints` con `wss://your.domain.com` como primera ruta y,
  solo si hace falta, una ruta directa privada como segunda opción.
- Probar desde una red externa con Desktop y Mobile. Un certificado caducado,
  autofirmado o emitido para otro hostname debe fallar.
- Revocar un dispositivo con streams abiertos desde Desktop y Mobile, y
  confirmar que la UI corta la actividad y muestra el estado revocado de forma
  comprensible sin afectar a los demás dispositivos de la conexión.
- Observar los contadores WebSocket con tráfico real, alertar ante capacidad o
  rechazos anormales y decidir si el borde público necesita también un límite
  por IP. Ese límite debe vivir donde se conserve la IP real, no dentro de Alpi
  detrás de Caddy.
- Confirmar desde el host y desde AWS que `49200` no es alcanzable
  públicamente. No basta con comprobar el bind dentro del contenedor.

Configuración objetivo:

```yaml
host:
  tcp_port: 49200
  endpoints:
    - url: wss://your.domain.com
      label: Secure Internet
    - url: ws://100.64.10.2:49200
      label: Direct
```

Puerta de salida: el cliente funciona por WSS desde Internet, el certificado
se valida, la revocación corta sesiones reales, los límites no afectan al uso
normal y una conexión directa a `IP_PUBLICA:49200` falla.

---

## P1 — Credenciales y revocación

### 2. Definir rotación y respuesta a incidentes

Falta una operación explícita para rotar la credencial de un dispositivo sin
recrear toda la conexión.

Pendiente:

- acción “Rotate credential” por dispositivo;
- invalidación atómica del token anterior;
- procedimiento documentado para pérdida de móvil/portátil;
- procedimiento para rotación masiva si se sospecha exposición del almacén de
  conexiones.

Hashear los tokens en disco puede añadirse después como defensa en profundidad,
pero no sustituye el intercambio de un solo uso, la rotación ni la revocación
de sockets.

---

## P1 — Roles y alcance de cada cliente

### 3. Crear una matriz de conexiones antes de incorporar clientes

No hay un rol universalmente correcto. Crear una conexión como `member` o
`admin`, y dejar el scope abierto o limitado, depende de lo que ese cliente
deba hacer.

Antes del despliegue hay que registrar para cada conexión:

| conexión | cliente/dispositivo | rol | profiles | motivo del admin |
|---|---|---|---|---|
| propietario | Desktop/Mobile personal | según necesidad | según necesidad | funciones de gestión utilizadas |
| cliente final | app del cliente | normalmente member | instancia/profiles acordados | n/a |
| integración | servicio interno | según contrato | profiles que consume | solo si llama verbos administrativos |

Reglas:

- `admin` se concede porque el cliente necesita verbos administrativos, no
  porque el agente use `terminal`.
- `profile_scope` limita qué profiles puede seleccionar una conexión member;
  no determina las tools disponibles dentro de esos profiles.
- varios dispositivos de una conexión comparten rol y scope, pero cada uno
  debe tener su propio token.
- si dos dispositivos necesitan permisos diferentes, deben estar en
  conexiones diferentes.

Pendiente de producto: mostrar en Desktop/Mobile, antes de escanear, un resumen
claro de rol, scope y capacidades administrativas que recibirá el dispositivo.

---

## P2 — Auditoría y operación

### 4. Registrar acciones administrativas sin registrar secretos

Los fallos de autenticación ya evitan escribir el token completo y registran
el método. Falta un audit log estructurado de operaciones exitosas sensibles.

Pendiente para cada mutación administrativa:

- timestamp;
- `connection_id` y `device_id`;
- método;
- profile afectado, cuando exista;
- resultado correcto/error;
- nunca `auth_token`, contenido de chat, claves, payload completo ni enlace de
  emparejamiento.

El log debe tener rotación y retención definida. “Eliminar los tokens de los
logs” no es una migración pendiente porque no deberían escribirse; el trabajo
real es añadir auditoría útil con una lista explícita de campos permitidos.

### 5. Mejorar el diagnóstico de exposición en Docker

Dentro de Docker el daemon escucha en `0.0.0.0`, que es normal para que Caddy
pueda alcanzarlo. Desde el contenedor no puede saber si Docker publicó ese
puerto en loopback, Tailscale o todas las interfaces del host.

`alpi doctor` ya explica que no puede deducir la publicación del host desde el
bind interno. El overlay WSS también elimina los puertos directos del compose
base. Sigue pendiente:

- incorporar la comprobación del compose efectivo al aprovisionamiento;
- comprobar security groups/firewall desde fuera de la máquina;
- monitorizar disponibilidad y fecha de expiración del certificado WSS.

### 6. Revisar recuperación y copias de seguridad

Una copia de `~/.alpi/host/connections.yaml` contiene credenciales activas.

Pendiente:

- confirmar que backups, snapshots y soporte técnico no exportan ese fichero
  fuera del entorno autorizado;
- cifrar backups que incluyan `~/.alpi`;
- documentar restauración: restaurar conexiones antiguas también restaura
  tokens antiguos;
- decidir si una restauración obliga a rotar credenciales.

---

## P3 — Solo antes de aceptar peers ALP no plenamente confiables

### 7. Definir el límite de confianza de `link.ask` y workgroups

ALP autentica criptográficamente al peer, pero autenticar identidad no vuelve
confiable el texto que envía. Un peer con permiso para provocar un turno puede
introducir instrucciones en el contexto del agente.

Pendiente si A y B dejan de ser dos daemons bajo el mismo control:

- conceder `link.ask` únicamente a peers que deban iniciar turnos;
- separar contenido del peer de las instrucciones internas del profile;
- etiquetar explícitamente contenido externo como no confiable;
- decidir por peer/profile qué herramientas necesita ese flujo;
- añadir evaluaciones de prompt injection para mensajes ALP y workgroups.

Esto tampoco se resuelve bloqueando `terminal` globalmente: se resuelve
definiendo qué peers pueden provocar turnos y qué profile deliberadamente
atiende ese tráfico.

---

## Orden recomendado

1. Desplegar DNS + Caddy y validar WSS, revocación, límites y exposición desde
   clientes y redes reales.
2. Crear la matriz real de conexiones, roles y scopes del cliente.
3. Añadir rotación por dispositivo.
4. Añadir audit log estructurado.
5. Revisar backups.
6. Abrir el trabajo ALP únicamente si aparecen peers menos confiables.

La salida segura a producción no exige quitar herramientas a profiles que las
necesitan. Exige que el único canal público sea WSS, que el puerto interno no se
publique, que cada cliente tenga una credencial revocable con el rol/scope
correctos y que el servicio resista abuso básico y deje una auditoría útil.
