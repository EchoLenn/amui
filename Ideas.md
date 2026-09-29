# Ideas — amui v0.3+

## Lo que ya tenemos ✅

- Playback controls (play/pause, next, prev, seek, volume, mute, restart)
- Portada via Kitty `icat` con fallback ASCII
- Letras sincronizadas (LRC) y plain text desde LRCLIB con caché
- Visualizador de espectro CAVA integrado
- 3 temas de color (nocturne, ember, ice)
- Layout adaptable (ancho/compacto/pantalla completa)
- Pantalla de ayuda, auto-detección de Cider/MPRIS

---

## Recomendaciones de Features 🚀

### Tier 1 — Alto impacto, complejidad moderada

| Feature | Descripción |
|---|---|
| **Cola / Queue** | Mostrar las próximas canciones (via `playerctl metadata` o D-Bus). Un panel `UP NEXT` que liste 3-5 tracks. |
| **Shuffle / Repeat** | Toggles `s` para shuffle y `e` para repeat. MPRIS expone `Shuffle` y `LoopStatus`. |
| **Búsqueda de letras manual** | Si LRCLIB falla, permitir que el usuario escriba título/artista manualmente con un mini-prompt. |
| **Notificaciones de canción** | Un toast/banner efímero tipo `♪ Now: Título — Artista` que aparece 3s al cambiar de track. Útil en modo pantalla completa de letras. |

### Tier 2 — Diferenciadores

| Feature | Descripción |
|---|---|
| **Temas personalizados / config** | Un `~/.config/amui/config.toml` para tema default, keybinds, backend de CAVA, offset de letras por defecto. |
| **Historial de reproducción** | Log local (`~/.cache/amui/history.jsonl`) con timestamp, título, artista, álbum. Comando `amui --history` para ver las últimas N canciones. |
| **Soporte Sixel / iTerm2** | Portadas en terminales no-Kitty (WezTerm, foot con Sixel). Detectar `TERM_PROGRAM` y usar `chafa` o protocolo Sixel como alternativa. |
| **Modo mini / barra** | Un `amui --mini` de 1-2 líneas tipo status bar: `▶ Título — Artista  03:22/05:10  ♪ 75%`. Ideal para tiling WMs. |

### Tier 3 — Polish

| Feature | Descripción |
|---|---|
| **Animaciones suaves** | Fade-in del texto al cambiar de canción, transición gradual de la barra de progreso. |
| **Scrobbling** | Integración con Last.fm / ListenBrainz. Enviar scrobble cuando position > 50% o > 4 min. |
| **Exportar letras** | Tecla `S` para guardar las letras de la canción actual como `.lrc` o `.txt` en un directorio elegido. |
| **Paleta dinámica** | Extraer colores dominantes de la portada (con `convert`/ImageMagick o un K-means simple en Python puro) y generar un tema que combine. |
| **Mouse support** | Click en la barra de progreso para seek, scroll en letras con rueda del mouse. curses soporta `mousemask`. |

---

## Top 3 para la v0.3

1. **Shuffle/Repeat** — Es trivial con MPRIS y los usuarios lo esperan.
2. **Config file** — Desacopla preferencias del CLI, escala mejor.
3. **Cola (Up Next)** — Es la feature que más diferencia un "player" de un "visualizador".
