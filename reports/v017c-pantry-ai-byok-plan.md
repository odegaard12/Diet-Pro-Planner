# v0.0.17c — Pantry MVP + AI BYOK policy

## Decisión

Diet Pro Planner no usará una clave central de IA.

Cada instancia es local y privada:

- Por defecto: Coach local con reglas, Strava, peso, BioCharge, histórico y despensa.
- IA externa: opcional.
- Cada usuario/deploy conecta su propia clave OpenAI/Gemini si quiere.
- No hay proxy central del autor.
- No hay consumo compartido.
- No hay responsabilidad del autor sobre instancias de otros.

## Modos

### Modo local

Funciona siempre:

- sin API externa;
- sin coste;
- sin enviar datos fuera;
- recomendaciones por reglas y despensa.

### Modo IA opcional

Futuro v0.0.18:

- provider: none / openai / gemini;
- cada instancia guarda su propia configuración local;
- límite diario;
- caché por día;
- fallback local si falla.

## Despensa

Smart Coach no debe recomendar ingredientes concretos si no sabe que están disponibles.

Debe elegir desde `data/pantry.json`:

- proteína disponible;
- verdura disponible;
- hidrato disponible;
- alimentos de riesgo o a evitar.

Si no hay despensa, recomienda por categorías:

- proteína magra;
- verdura;
- hidrato medido.

## Privacidad

No se commitea:

- `data/pantry.json`;
- secretos;
- claves API;
- DB privada.

Solo se commitea `data/pantry.example.json`.
