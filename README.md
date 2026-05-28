# Dieta Pro Planner

**Versión actual:** v0.0.2

Aplicación web local y privada para registrar peso, comidas por gramos, alimentos reutilizables, plantillas, deporte, planes e integraciones opcionales.

Pensada para ejecutarse en una Raspberry Pi con Docker y mantener los datos en local.

## Funciones

- Registro de peso oficial y de referencia.
- Comidas por alimentos guardados y gramos.
- Plantillas cargables en una comida para cambiar solo cantidades.
- Productos con marca, valores nutricionales y foto opcional de etiqueta.
- Entrenos manuales y base para sincronización Strava bajo demanda.
- SQLite local en `data/dieta.db`.

## Privacidad

No subas `data/`, bases de datos, `.env`, tokens ni backups. El `.gitignore` ya los excluye.

## Docker

```bash
docker compose up -d --build
```



## Releases

- `v0.0.1`: primera salida pública limpia.
- `v0.0.2`: regla visible, limpieza visual y preparación de releases.


## Strava local setup

Diet Pro Planner can connect to Strava without exposing the Raspberry Pi to the internet.

Recommended local OAuth flow:

1. Create a Strava API application.
2. Set the website to `http://localhost:8099`.
3. Set the authorization callback domain to `localhost`.
4. Store `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET` and `STRAVA_REDIRECT_URI` in the local `.env` file.
5. Open an SSH tunnel from your computer to the Raspberry Pi:

```bash
ssh -N -L 8099:127.0.0.1:8099 user@raspberry-ip
```

6. Open `http://localhost:8099`.
7. Go to Integrations -> Strava -> Connect Strava.

Tokens are stored locally under `data/` and are excluded from Git.

## Strava manual import

Version `v0.0.2` adds manual Strava import:

- choose start date
- choose end date
- search activities
- review activities before importing
- select activities to import
- avoid duplicates using the Strava activity id stored in workout notes

No automatic background sync is performed.
