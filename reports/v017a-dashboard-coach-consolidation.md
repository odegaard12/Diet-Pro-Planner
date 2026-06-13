# v0.0.17a — Dashboard Coach Consolidation

## Decisión

No añadir Smart Coach como tarjeta suelta.

La portada ya está cargada. La mejora correcta es consolidar bloques repetidos en un único bloque principal:

**Coach del día**

## Problemas actuales

La portada separa demasiada información relacionada:

- Inteligencia del día
- Score / base insuficiente
- Qué hacer ahora
- Sugerir comida
- proteína / energía / aceite / entreno
- peso oficial
- foto corporal
- composición corporal
- lecturas recientes

Esto provoca repetición visual y mensajes contradictorios:
- “Base insuficiente” junto a “Confianza exacta”
- “Sugerir comida” demasiado genérico
- BioCharge parcial con grasa/agua/músculo en `--`
- Smart Coach útil pero todavía sin integración visual

## Nuevo orden objetivo

1. Cabecera del día
   - fecha
   - peso oficial
   - BioCharge si existe
   - score si existe

2. Coach del día
   - estado del día
   - siguiente mejor comida
   - por qué
   - qué evitar
   - señales: ansiedad, deporte, BioCharge, peso

3. Resumen rápido
   - kcal
   - proteína
   - aceite
   - entreno

4. Comidas registradas

5. Actividad

6. Peso / composición compacto
   - en portada solo resumen
   - detalle largo a Peso 2.0

## Reglas

- No crear tarjetas sueltas nuevas.
- No duplicar recomendaciones.
- Absorber `Sugerir comida` y `Qué hacer ahora` en `Coach del día`.
- Si no hay base suficiente, Smart Coach debe seguir dando siguiente mejor comida.
- No crecer `static/app.js` sin control.
- Preferir módulos externos pequeños.
- No tocar DB en este PR.
