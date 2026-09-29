# Ideas.md — alcance y verificación

## Reparación v0.5.1 — auditoría del estado real

- Restaurados `legacy/amui.bash` y `legacy/amui-v0.2.py` desde Git, sin diferencias.
- Cuatro fuentes de color accesibles desde `T`, con tres modos de carátula.
- Selecciones persistentes; cambios manuales del TOML y flags CLI respetados.
- Corregido el arranque de temas personalizados: `personal` ya no sustituye un
  tema TOML elegido explícitamente. Se conservan hexadecimales originales al guardar.
- Pywal inválido no cambia la fuente seleccionada ni sustituye los colores válidos.
- Más resultados se agregan a la lista; no se pierde selección ni páginas anteriores.
- Respuestas tardías no reemplazan búsquedas nuevas; las órdenes de reproducción
  aceptadas no se descartan porque el usuario inicie otra búsqueda.
- 55 pruebas aprobadas: incluye persistencia/reinicio, precedencia TOML, exactitud
  del editor, paginación, errores y flujo PTY de búsqueda, selección y cola.
- Búsqueda real y paginación comprobadas con Cider autenticado: catálogo México y
  biblioteca, para canciones, álbumes y playlists. No se alteró la reproducción
  personal al verificar; las órdenes se comprobaron con HTTP local y PTY.

La guía actual está en `docs/CONFIGURATION.md`; las secciones siguientes son históricas.

## Actualización v0.4 — temas y colores

Alcance acordado de next-features.md: selector, cinco temas, paleta por portada,
caché, transiciones, recarga de temas y ayuda categorizada. Biblioteca, playlists,
favoritos, estadísticas, socket y hooks quedan para otra iteración.

- Selector `T`: vista previa, Enter aplica, Esc restaura tema y modo dinámico.
  `t` sigue recorriendo los temas. Prueba PTY verifica apertura y selección.
- Sakura, ocean, sunset, forest y mono disponibles junto a temas personalizados.
  `--list-themes` funciona sin TTY, con colores hexadecimales en salida redirigida.
- K-means determinista con hasta cinco centroides y doce iteraciones; lectura de
  píxeles con ImageMagick. Texto/acento con contraste mínimo 4.5:1 después de
  aproximar a 256 colores. Fondo oscuro por defecto y claro opcional.
- Caché de 256 paletas por hash del contenido; prueba con cambio de imagen en
  la misma ruta. El worker detecta modificaciones por fecha/tamaño.
- Transición de un segundo; pruebas del destino final y animaciones desactivadas.
- Revisión del TOML cada cinco segundos, sólo para definiciones de temas;
  un archivo inválido conserva el último conjunto válido.
- Ayuda por reproducción, navegación, letras y apariencia, con teclas resaltadas.
- La prueba Sixel pasa con fallback de Chafa a ImageMagick. Chafa instalado en
  este entorno no incluye lector PPM; la prueba usa ese formato.
- 42 pruebas aprobadas, incluyendo las anteriores y siete nuevas de temas.
- Instalación local verificada: versión 0.4.0, listado de temas y configuración válida.

Las secciones siguientes conservan la evidencia histórica de v0.3.

Objetivo: implementar los 13 elementos de Ideas.md, conservando reproducción,
portadas, letras y CAVA. Ideas.md se conserva como referencia del usuario.

## Requisitos

- [x] Cola UP NEXT de 3–5 canciones: MPRIS TrackList y API local Cider autenticada.
- [x] Shuffle `s` y repeat `e`, con estado real y manejo de no soportado.
- [x] Mini prompt de búsqueda de letras por título y artista.
- [x] Banner de cambio de canción durante 3 segundos, incluso en letras fullscreen.
- [x] TOML: tema, temas personalizados, teclas, backend CAVA, offset de letras.
- [x] Historial JSONL con fecha y metadata; `--history [N]`.
- [x] Portadas Kitty, iTerm2 / WezTerm y Sixel; fallback explícito.
- [x] `--mini`: barra de 1–2 líneas, controles y restauración de terminal.
- [x] Fade de metadata y transición gradual del progreso.
- [x] Last.fm y ListenBrainz: umbral 50% / 4 minutos, credenciales, errores y un envío por escucha/servicio.
- [x] Exportar con `S` a directorio elegido, LRC o texto, sin sobrescribir archivos.
- [x] Paleta dominante extraída de la portada.
- [x] Mouse: seek en progreso y scroll en letras.

## Verificación prevista

Pruebas unitarias y de integración offline con contratos de servicios; pruebas
de terminal PTY para navegación, prompts, resize y cierre; render real en Kitty;
instalación en prefijo temporal antes de actualizar el ejecutable del usuario.
Credenciales externas no se inventan ni se escriben en el repositorio.

## Evidencia inicial

- Cider escucha en localhost:10767 y `/api/v1/playback/queue` devuelve 403
  `UNAUTHORIZED_APP_TOKEN` sin credencial.
- La sesión Chromium publica `HasTrackList=false` y no admite shuffle/loop.
- Python 3.14, busctl, ImageMagick, Kitty, CAVA y playerctl están instalados.
- Chafa no está instalado; iTerm2 puede implementarse sin dependencia y Sixel
  tendrá soporte opcional mediante Chafa, probado con su contrato de salida.

## Auditoría de entrega — v0.3.0

Se inspeccionaron las implementaciones, no sólo la lista de pruebas. `make check`
pasa 35 pruebas: las 9 anteriores y 26 de funciones/servicios/terminal.

| Requisito | Evidencia |
| --- | --- |
| Cola | `Extras.poll` consulta MPRIS TrackList, excluye pista actual e historial; test de variantes D-Bus y servidor HTTP local autenticado. UI real en Kitty muestra cinco filas. |
| Shuffle/repeat | `Player.act` usa estado MPRIS o endpoints Cider; pruebas de ciclo y rutas HTTP. PTY verifica despacho de `s` y `e`. |
| Búsqueda manual | Prompts título/artista, generación para descartar respuestas viejas, conservación del override. Pruebas de worker y flujo PTY. |
| Banner | Cambio de identidad en `UI.run` inicia `toast` de 3 s; se dibuja después de la vista normal/fullscreen. Test de expiración y captura Kitty con banner visible. |
| Config/temas | `load_config` valida tipos, colores, conflictos de teclas, backend y offset; tema aurora de ejemplo. Prueba de instalación ejecuta init/check-config y verifica no sobrescritura. |
| Historial | `Activity` registra al reproducir, `History` escribe JSONL y lee últimos N tolerando líneas corruptas. CLI probado sin TTY. |
| Portadas | Kitty conservado; test de detección y bytes OSC 1337 con tamaño; ImageMagick real genera una imagen SIXEL. No hay WezTerm/foot/iTerm2 instalados para inspección visual nativa de esos protocolos. |
| Mini | PTY de exactamente 2 filas muestra metadata y sale por SIGTERM restaurando modo canónico. Test de canvas verifica sólo filas 0/1. |
| Animaciones | Test verifica colores intermedios del fade y convergencia del progreso sin overshoot. Render en Kitty. |
| Scrobbling | Umbrales, pausas, seek, pistas cortas, un envío, firma Last.fm, payload ListenBrainz, opt-in y persistencia al cerrar probados offline. Envío a cuentas reales no activado sin credenciales. |
| Exportación | Test LRC round-trip, TXT, carpeta elegida, sanitización, colisiones, snapshot de pista; prueba PTY produce un archivo real. |
| Paleta | ImageMagick real extrae una paleta de una portada de prueba; se verifica cambio del acento. |
| Mouse | Click al final de la barra produce seek a duración; rueda desplaza letras. Eventos curses habilitados y reset al cerrar en PTY. |

## Instalación y activación

- Instalación verificada primero en un prefijo temporal, después en `~/.local`.
- Ejecutable instalado reporta `0.3.0`; script y módulo coinciden con el repo.
- Configuración creada en `~/.config/amui/config.toml` y validada.
- v0.2 respaldada byte por byte en `legacy/amui-v0.2.py`; Bash original conservado.
- `Ideas.md` se conserva. Guía de activación en `docs/CONFIGURATION.md`.
- La integración autenticada queda lista: el usuario aporta su token con
  `amui --connect-cider`. Scrobbling requiere credenciales y providers explícitos.
  No se declara que esas cuentas estén conectadas ni se enviaron escuchas de prueba.

La entrega implementa todas las propuestas. Las credenciales del usuario y la
disponibilidad de servicios siguen siendo requisitos de uso, no datos simulados
en la aplicación. Las pruebas de servicios usan fixtures aislados del reproductor
y de las cuentas del usuario.
