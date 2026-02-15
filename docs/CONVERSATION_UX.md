# Experiencia de conversación y riesgos de confusión del chatbot

Este documento recoge los puntos que pueden confundir al agente o romper la UX en conversaciones, y las mejoras aplicadas o recomendadas.

## Mejoras ya aplicadas

### 1. Banda efectiva siempre en la respuesta
- **Problema:** Si el usuario no especificaba banda (ej. "dame la imagen de M104"), el backend usaba SDSS (visible) por defecto pero el texto de la respuesta no lo decía. En el siguiente turno, si el usuario preguntaba "¿en qué banda está?", el LLM no tenía ese dato y podía contradecirse ("no puedo mostrar imágenes sin banda").
- **Solución:** En el orquestador se usa siempre una banda efectiva: si no viene en `options`, se usa `"visible"`. El caption y el resumen de análisis incluyen "en banda visible" (o la banda indicada), de modo que el historial de chat contiene la información y el LLM puede responder con coherencia.

### 2. Target vacío o placeholder
- **Problema:** Si el usuario decía solo "analiza la imagen" sin galaxia, el LLM podía devolver `name=null` y el backend asignaba target `"from conversation"`. El pipeline intentaba entonces resolver una galaxia con ese nombre y fallaba.
- **Solución:** En `AgentRunner` se comprueba, antes de llamar al orquestador, si el target es vacío o el placeholder `"from conversation"` y no hay `image_url`. En ese caso se devuelve un mensaje amigable pidiendo que indique galaxia (o coordenadas) y opcionalmente banda, sin ejecutar el pipeline.

### 3. BFF: último mensaje del usuario para `message`
- **Problema:** Si por algún motivo el frontend enviaba `messages` pero no `message`, el BFF rellenaba `message` con el último elemento de `messages`, que podía ser un mensaje del *assistant*, no del usuario.
- **Solución:** Se rellena `message` con el contenido del último mensaje de *rol user* en `messages`, no con el último mensaje en general.

### 4. Respuestas a lo no soportado (out of scope)
- El LLM decide si la petición es soportada (`can_fulfill`) y, si no, escribe un `decline_reason` en español explicando qué puede y qué no puede hacer el sistema, para evitar respuestas genéricas o contradictorias.

### 5. Análisis solo si lo piden en el mensaje actual
- **Problema:** Si el usuario decía "analiza la imagen" y luego "de m104", el sistema podía inferir análisis del turno anterior y ejecutar morfología cuando el usuario solo estaba indicando la galaxia.
- **Solución:** En el prompt se exige que `want_analysis` sea true **solo si el último mensaje del usuario** pide explícitamente análisis (analiza, medidas, morfología, etc.). No se infiere de mensajes anteriores: "de m104" → solo imagen.

### 6. Banda siempre en el texto de respuesta
- **Problema:** Aunque el backend usaba banda efectiva (visible por defecto), el LLM a veces no la incluía en el resumen; en el siguiente turno el usuario preguntaba "¿en qué banda?" y el agente se contradecía.
- **Solución:** En `generate_accompanying_summary` se antepone "Análisis de {galaxia} en banda {band}. " si el texto no lo incluye. En `generate_image_caption` si el LLM omite la banda se usa el texto por defecto ("Aquí tienes la imagen de X en banda Y.").

### 7. Preguntas de seguimiento sobre lo ya mostrado
- **Problema:** "¿En qué rango está la imagen que me diste?" se trataba como petición nueva y el agente respondía "no doy imágenes sin banda" en vez de responder desde el contexto.
- **Solución:** En el prompt se indica que si el usuario hace una pregunta sobre lo ya hecho (qué banda era, qué imagen se dio), `can_fulfill` debe ser false y `decline_reason` debe **responder desde la conversación** (leyendo el mensaje anterior del asistente donde ya se indicó la banda), sin lanzar una nueva petición de imagen.

---

## Riesgos y recomendaciones

### Historial muy largo
- **Riesgo:** Se envía todo el historial de la conversación al LLM. En chats muy largos puede haber límite de tokens o respuestas menos coherentes.
- **Recomendación:** Valorar truncar a las últimas N vueltas (ej. 10–20 mensajes) o a un máximo de tokens en el frontend o en el BFF antes de enviar a la Galaxy API.

### Errores de red o del backend
- **Estado actual:** Si la Galaxy API o el BFF fallan, el frontend muestra "Error: network error" o el texto del error. No hay reintentos ni mensaje específico del tipo "el servidor no está disponible".
- **Recomendación:** Diferenciar en el frontend errores de red (timeout, sin conexión) de errores 502/500 y mostrar mensajes claros; opcionalmente reintento con backoff.

### Orden de eventos en el stream
- El frontend actualiza el mensaje del asistente con: `status` → `summary` → `artifacts` (imageUrl) → `end`. Si llegara un `end` sin `summary` previo, el contenido final podría quedar con el último `status` en lugar del resumen. Hoy el orquestador siempre envía `summary` y luego `end` con el mismo `summary`, así que está cubierto.

### Peticiones estructuradas (target + task)
- Las peticiones que ya traen `target` y `task` no pasan por el LLM de intención ni por la lógica de out-of-scope. Si un cliente envía target vacío o inválido en modo estructurado, el guard de "from conversation" solo aplica cuando el target se ha resuelto desde NL (porque si viene estructurado, el target ya viene rellenado). Revisar si en el futuro hay clientes que envíen estructurado con target opcional.

### Idioma
- Los prompts del LLM y los mensajes fijos están en español. Si el usuario escribe en otro idioma, el modelo puede responder en ese idioma o en español según el prompt; no hay detección explícita de idioma.

---

## Resumen

| Área              | Estado / mejora |
|-------------------|-----------------|
| Banda en respuesta| ✅ Siempre indicada (visible por defecto) |
| Target vacío      | ✅ Guard + mensaje amigable |
| BFF message       | ✅ Último mensaje *user* |
| Out of scope      | ✅ decline_reason natural |
| Historial largo   | ⚠️ Sin truncar; valorar límite |
| Errores de red    | ⚠️ Mensaje genérico; mejorar si hace falta |
