---
name: whoop-auth
category: health
description: Obtén token de WHOOP via OAuth y guárdalo en ~/.alf/secrets/whoop.json
tools:
  - terminal
requires_env:
  - WHOOP_CLIENT_ID
  - WHOOP_CLIENT_SECRET
---

# Instrucciones

1. Asegúrate de tener `WHOOP_CLIENT_ID` y `WHOOP_CLIENT_SECRET` en tu environment.
2. Ejecuta `python3 whoop_auth.py` (o el script en el mismo directorio).
3. Abre la URL que aparece, autoriza la app, y cierra la ventana del navegador.
4. Verifica que `~/.alf/secrets/whoop.json` se ha creado con `access_token` y `refresh_token`.
