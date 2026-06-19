# v0.0.17 — Smart Coach / Food Intelligence / Strava / Sensors

## Objetivo

Convertir Diet Pro Planner en un asistente diario más inteligente:

- no solo registrar comidas;
- interpretar peso, BioCharge, deporte y ansiedad;
- recomendar la siguiente mejor comida;
- evitar mensajes genéricos;
- mejorar días con Strava/pádel/carrera;
- analizar patrones históricos.

## Problemas actuales

### BioCharge / sensores

- El peso se inserta correctamente.
- BioCharge/Hybrid Charge no siempre se inserta porque el script no localiza bien la estructura real de métricas.
- `/api/body-snapshot/latest` sí expone `biocharge_current`, `biocharge_wakeup`, `biocharge`, `hybrid_charge`, etc., pero el backfill/inserción manual debe localizar el origen real.

### Food Intelligence

Mensajes actuales demasiado genéricos:

- “Cierra con 20-30 g de proteína”
- “Falta proteína útil”
- No diferencia bien:
  - día con deporte fuerte;
  - día sin deporte;
  - ansiedad/snack;
  - rebote de sal/hidratos;
  - déficit excesivo;
  - comida limpia pero incompleta.

### Strava

Strava importa entrenos, pero falta interpretación:

- pádel fuerte vs paseo suave;
- recuperación post-entreno;
- combustible antes de deporte;
- ajuste de recomendación por kcal reales;
- aviso de kcal sospechosamente altas.

### Histórico

Falta análisis semanal:

- qué días funcionaron;
- qué comidas evitaron ansiedad;
- relación sal/hidratos/peso;
- relación deporte/BioCharge/peso;
- patrones de casa abuelos, auditoría/trabajo, ansiedad, fiestas.

## Prioridad de implementación

1. Arreglar inserción y lectura de BioCharge/Hybrid Charge.
2. Crear módulo backend pequeño `dpp_smart_coach.py`, sin crecer `static/app.js`.
3. Añadir endpoint `/api/smart-coach/day?date=YYYY-MM-DD`.
4. Añadir lógica “siguiente mejor comida”.
5. Integrar señales de Strava:
   - no entreno;
   - entreno suave;
   - entreno fuerte;
   - pádel/carrera/fuerza.
6. Añadir análisis histórico semanal `/api/smart-coach/week`.
7. Añadir UI mínima en dashboard sin romper monolito.

## Reglas de calidad

- No meter DB privada en Git.
- No crecer `static/app.js` salvo ajuste mínimo.
- Preferir módulos backend pequeños.
- Mantener known-days regression.
- Mantener anti-monolith guard.
- No inventar datos de salud/sensores.
- Si BioCharge no existe para un día, decirlo claro.
