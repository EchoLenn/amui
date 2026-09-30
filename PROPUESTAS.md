# Propuestas de Nuevas Funcionalidades — amui

Análisis de la versión actual de **amui** y propuestas priorizadas de nuevas funcionalidades diseñadas bajo principios de simplicidad, cero dependencias adicionales y alto impacto práctico.

**Estado v0.5.6:** las seis propuestas están implementadas. Este documento
conserva el diseño original; el comportamiento definitivo, configuración y
límites se describen en `README.md`, `docs/CONFIGURATION.md` y
`docs/AUDIT-v0.5.6.md`. Favoritos usa la operación real de Apple Music, no el
endpoint de calificación propuesto inicialmente; requiere el complemento incluido.

---

## 🚀 Funcionalidades Propuestas

### 1. Drill-down en el Buscador de Música (`b`)
* **Problema actual**: Al buscar un álbum o playlist en `b`, solo se puede reproducir completo o mandarlo a la cola a ciegas.
* **Propuesta**:
  - Al presionar `Enter` o `→` sobre un álbum o playlist, abrir la lista de canciones contenidas.
  - Seleccionar una canción individual para reproducirla o agregarla a la cola.
  - `←` o `Esc` para regresar al listado de resultados.
* **Implementación**: Consulta al endpoint `/v1/catalog/{storefront}/albums/{id}/tracks` (o `/v1/me/library/...`) de la API de Cider. Reutiliza el componente de lista navegable existente.

---

### 2. Gestión Interactiva de la Cola (`Q`)
* **Problema actual**: La vista de cola `Q` solo dibuja los próximos temas como texto estático.
* **Propuesta**:
  - Navegar con `↑` / `↓` entre las canciones en espera.
  - `Enter` para saltar inmediatamente a reproducir la pista seleccionada.
  - `d` o `Supr` para eliminar una canción de la cola.
  - `c` para limpiar la cola pendiente.
* **Implementación**: Manejo de índice activo en la vista `queue_panel` y despacho de acciones hacia la API de Cider / MPRIS.

---

### 3. Favoritos y "Añadir a Biblioteca" (`♥` / `H` / `A`)
* **Problema actual**: Si descubres una canción dentro de amui, debes abrir Cider o el móvil para guardarla.
* **Propuesta**:
  - Tecla `H` (Heart): Alternar "Favorito / Love" en Apple Music.
  - Tecla `A` (Add): Agregar la pista actual a la Biblioteca personal del usuario.
  - Indicador visual `♥` en el panel *Now Playing*.
* **Implementación**: Endpoint de calificación/biblioteca de Cider (`/v1/me/library`). 1 petición HTTP directa.

---

### 4. Notificaciones de Escritorio del Sistema (`notify-send`)
* **Problema actual**: El banner toast interno de 3 segundos solo es visible si la terminal está enfocada. En gestores tipo tiling (Hyprland, i3, Sway, bspwm) no hay aviso si amui corre en otro workspace.
* **Propuesta**:
  - Opción `desktop_notifications = true` en `config.toml`.
  - Envío de notificación nativa al cambiar de pista con título, artista, álbum y portada local descargada.
* **Implementación**: Llamada simple vía `subprocess.Popen(["notify-send", "-i", art_path, title, artist])`. Sin librerías externas.

---

### 5. Sleep Timer / Temporizador de Apagado (`Z`)
* **Problema actual**: Común escuchar música de noche o en sesiones de estudio sin querer que continúe reproduciéndose indefinidamente.
* **Propuesta**:
  - Tecla `Z`: selector rápido de duración (15 min, 30 min, 45 min, 60 min, o "al terminar la canción actual").
  - Muestra cuenta regresiva discreta en la barra de transporte (`⏳ 24:15`).
  - Al expirar, envía orden de pausa y restaura el estado.
* **Implementación**: Comparación contra `time.monotonic()` en el loop principal de la interfaz.

---

### 6. Control Remoto por CLI para Barras de Estado (Waybar / Polybar)
* **Problema actual**: Integrar amui en paneles y barras de estado requiere invocar y parsear múltiples comandos de `playerctl`.
* **Propuesta**:
  - `amui --status`: devuelve JSON en una sola línea (`{"title": "...", "artist": "...", "status": "Playing", "progress": 0.45}`).
  - Comandos remotos directos: `amui --next`, `amui --prev`, `amui --toggle`.
* **Implementación**: Reutilización de la lógica MPRIS/Cider existente en modo headless CLI sin inicializar curses.

---

## 🎯 Orden Recomendado de Implementación

1. **Drill-down en álbumes/playlists (`b`)**: convierte el buscador en una herramienta completa de navegación.
2. **Cola interactiva (`Q`)**: maximiza la utilidad del panel de cola existente.
3. **Favoritos / Biblioteca (`H` / `A`)**: conveniencia cotidiana directa.
4. **Notificaciones de escritorio**: integración nativa ligera y útil en Linux.
