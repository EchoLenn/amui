# amui — a little louder, a little closer

Una sala de escucha en tu terminal: Cider reproduce Apple Music; **amui** pone
la portada, los controles, el espectro de audio y las letras al frente.

## Lo nuevo en 0.5.1

- **Fuentes de color y temas interactivos (`T`)**:
  1. **Carátula**: modos de extracción K-means, colores complementarios y alto contraste.
  2. **Temas fijos**: selección con vista previa de los ocho temas integrados.
  3. **Tema personalizado**: temas del TOML (incluido aurora en el ejemplo) y editor de siete colores `#RRGGBB`, guardados sin perder sus valores en `custom-theme.json`.
  4. **Pywal**: lectura automática y recarga en caliente al detectar cambios en `~/.cache/wal/colors.json`.
- **Elegir y buscar música desde amui (`b`)**:
  - Búsqueda en el catálogo de Apple Music o en tu Biblioteca (`Tab` alterna la fuente).
  - Filtro por tipo: Canciones, Álbumes o Playlists (`←` / `→`).
  - Escribe y pulsa Enter para buscar; después usa ↑↓ y Enter para reproducir.
    `+` añade a la cola, `n` añade a continuación y `N` agrega más resultados sin borrar los anteriores.
  - `/` vuelve a editar la consulta, Ctrl+U la limpia y Esc cierra el navegador.
    La biblioteca es la de tu cuenta de Apple Music, no una carpeta de archivos locales.

Las selecciones de apariencia se guardan junto al TOML en `config.appearance.json`.
Editar manualmente el TOML invalida esa selección guardada; los argumentos CLI
tienen prioridad. Esc desde el menú principal de temas cancela la vista previa.
Pywal conserva los últimos colores válidos si su archivo desaparece o contiene errores.
Los colores en pantalla siguen aproximándose a 256 colores; el archivo personalizado
conserva los hexadecimales originales. Los respaldos `legacy/` permanecen intactos.

## Lo nuevo en 0.4

- `T` abre el selector de temas: flechas para vista previa, Enter para aplicar,
  Esc para recuperar el tema y el modo dinámico anteriores. `t` conserva el ciclo rápido.
- Cinco temas nuevos: sakura, ocean, sunset, forest y mono.
- `amui --list-themes` muestra temas integrados y personalizados con sus siete
  colores; al redirigir la salida muestra valores hexadecimales.
- Paletas de portada con K-means (hasta cinco colores), fondo adaptado y contraste
  mínimo de 4.5:1 para texto y acentos. Se conserva el modo oscuro; `palette_light = true`
  permite fondos claros cuando predominan colores claros en la portada.
- Caché por contenido de imagen en `$XDG_CACHE_HOME/amui/palettes.json`, con un
  máximo de 256 entradas. Una portada modificada en la misma ruta se vuelve a procesar.
- Transiciones de paleta de un segundo; `animations = false` aplica el cambio de inmediato.
  Los colores se aproximan a la paleta de 256 colores del terminal.
- Recarga de las definiciones `[themes]` cada cinco segundos. Los errores de TOML
  conservan la última configuración válida y se muestran en pantalla. El tema
  elegido se mantiene si todavía existe; las otras preferencias requieren reiniciar.
- Ayuda agrupada en reproducción, navegación, letras y apariencia.
- Sixel intenta ImageMagick si Chafa no puede decodificar la imagen.

## Lo nuevo en 0.3

Se implementan las 13 propuestas de `Ideas.md`:

- **UP NEXT** con hasta cinco canciones, desde MPRIS TrackList o la API local
  de Cider. `Q` abre la cola a pantalla completa.
- **Shuffle / repeat** con `s` y `e`, mostrando el estado del reproductor.
- **Búsqueda manual de letras** con `/`: título, artista y Enter.
- **Banner de canción** durante tres segundos, también en la vista de letras.
- **Preferencias TOML**, temas personalizados y teclas configurables.
- **Historial** local y `amui --history 20`.
- **Portadas Kitty, iTerm2/WezTerm y Sixel**; detección o selección explícita.
- **Modo mini** de dos líneas: `amui --mini`.
- **Fade de metadata** y progreso con transición gradual.
- **Scrobbling opcional** a Last.fm y ListenBrainz, con cola de reintentos.
- **Exportación de letras** con `S` a un directorio elegido.
- **Paleta de la portada** con ImageMagick.
- **Mouse**: click en progreso para seek, rueda sobre las letras para desplazarlas.

### Se conserva de la 0.2

- Interfaz oscura con paneles, portada grande y tres paletas: **nocturne**,
  **ember** e **ice**.
- **CAVA real**, integrado a 30 cuadros por segundo, con barras turquesa,
  lavanda y rosa. Captura la salida del sistema, incluidas otras apps.
- **Letras de LRCLIB**: seguimiento por tiempo cuando existen letras LRC;
  texto desplazable cuando sólo hay letras sin sincronizar. Caché local de 30 días.
- Letras a pantalla completa, ajuste de sincronización y ayuda integrada.
- Layout adaptable: paneles lado a lado desde 112 columnas; vista compacta
  en ventanas pequeñas. Para ver todo cómodamente, usa unas **140 × 40 celdas**.
- Conserva autodetección `chromium.instance*`, metadata MPRIS, caché de duración,
  seek, volumen, mute, restart y controles de reproducción.

La interfaz usa Python 3.11+ y `curses`, con bibliotecas estándar. MPRIS, letras y CAVA
trabajan en segundo plano.
La búsqueda requiere la API local de Cider conectada: `amui --connect-cider`.

## Requisitos e instalación

En Arch Linux:

```bash
sudo pacman -S python playerctl kitty cava
```

Necesitas Cider instalado por separado, con Apple Music iniciado y MPRIS
disponible en tu sesión de escritorio. Cider puede quedarse minimizado.
Para la portada en Kitty se usa `kitten icat` o `kitty +kitten icat`.
WezTerm/iTerm2 usan el protocolo de imágenes iTerm; foot usa Sixel mediante
Chafa o ImageMagick. Sin un backend disponible aparece una ilustración.
`busctl` (systemd) se usa para MPRIS TrackList. Opcionales en Arch:

```bash
sudo pacman -S imagemagick chafa
```

ImageMagick permite tanto paleta automática como Sixel; no hace falta Chafa
si ya tienes ImageMagick con soporte SIXEL.

Desde esta carpeta:

```bash
make check
make install
amui --init-config
amui
```

`make install` actualiza `~/.local/bin/amui`; ese directorio debe estar en tu
`PATH`. Para probar sin instalar: `./bin/amui`.

```bash
amui --theme ember
amui --theme ice
amui --no-lyrics        # sin consultas de letras por Internet
amui --no-cava          # sin proceso de captura de audio
amui --cava-input pipewire
amui --player chromium.instance4938
amui --mini
amui --history 30
amui --dynamic-palette
```

El backend de CAVA predeterminado es `pulse`, también compatible con
PipeWire mediante `pipewire-pulse`. Si usas PipeWire sin esa compatibilidad,
prueba `--cava-input pipewire`. amui crea una configuración temporal propia;
no modifica tu configuración personal de CAVA.

## Controles

| Tecla | Acción |
| --- | --- |
| `Espacio` | Reproducir / pausar |
| `n` / `p` | Pista siguiente / anterior |
| `→` / `←` o `l` / `h` | Adelantar / retroceder 5 segundos |
| `↑` / `↓` o `k` / `j` | Subir / bajar volumen 5 puntos |
| `m` | Silenciar / restaurar volumen |
| `r` | Reiniciar pista |
| `s` | Alternar shuffle |
| `e` | Alternar repeat: off, cola, pista (el orden de Cider puede diferir) |
| `Q` | Cola a pantalla completa |
| `/` | Buscar letras por título y artista |
| `S` | Exportar letras a un directorio elegido |
| `L` (mayúscula) | Mostrar / ocultar panel de letras |
| `f` | Letras a pantalla completa; también sirve en ventanas angostas |
| `v` | Mostrar / ocultar visualizador |
| `b` | Buscar / elegir música (Apple Music y biblioteca) |
| `T` | Selector de temas y fuentes de color (carátula, fijos, personal, pywal) |
| `t` | Cambiar paleta |
| `[` / `]` | Desplazar letras; en LRC vuelve al seguimiento después de 5 s |
| `,` / `.` | Ajustar sincronización −0.5 / +0.5 segundos |
| `R` (mayúscula) | Volver a consultar letras, ignorando la caché |
| `o` | Abrir Cider si no hay reproductor y existe el comando `cider` |
| `?` / `Esc` | Mostrar ayuda / cerrar ayuda |
| `q` | Salir |

`L` y `v` controlan la visibilidad. Para desactivar consultas o captura desde
el arranque, usa `--no-lyrics` o `--no-cava`.

Los prompts aceptan `Enter`, `Esc`, retroceso y `Ctrl+U` para limpiar. Las
teclas escritas dentro del prompt no controlan el reproductor.

## Configuración y temas

`amui --init-config` crea `~/.config/amui/config.toml` sin sobrescribir un
archivo existente. Respeta `XDG_CONFIG_HOME`. El ejemplo completo está en
`share/amui/config.example.toml`; `amui --check-config` valida tipos, colores,
atajos duplicados y opciones. Puedes usar `--config /ruta/config.toml`.

La prioridad es CLI → config → valores predeterminados. Por ejemplo:

```toml
theme = "aurora"
cava_input = "pipewire"
lyrics_offset = -0.5
dynamic_palette = true
animations = true
mouse = true
cover_protocol = "auto"
export_dir = "~/Music/amui-lyrics"

[keybinds]
shuffle = "z"
forward = ["RIGHT", "l"]
```

El ejemplo instalado define el tema `aurora`. Puedes añadir `[themes.nombre]`
con siete colores: `background`, `foreground`, `muted`, `border`, `accent`,
`secondary` y `tertiary`. Acepta índices 0–255 o `"#RRGGBB"`, convertidos a la
paleta de 256 colores. `t` elige un tema manual y desactiva la paleta automática
durante esa sesión. `animations=false` elimina fade y suavizado.

Los nombres especiales de teclas son `SPACE`, `LEFT`, `RIGHT`, `UP` y `DOWN`.
Las acciones configurables están enumeradas en `docs/CONFIGURATION.md`.

## Conectar la cola, shuffle y repeat a Cider

Algunas sesiones Chromium, incluida la usada durante el desarrollo, no exponen
`TrackList`, `Shuffle` ni `LoopStatus` por MPRIS. En esos casos se usa la API
local de Cider, que debe estar habilitada en sus ajustes de conectividad.

1. En Cider → Settings → Connectivity → API tokens, crea un token para amui.
2. Ejecuta `amui --connect-cider` y pégalo en el prompt oculto.
3. Reinicia amui. El token se guarda fuera del repo, con permisos `0600`.

También acepta `AMUI_CIDER_TOKEN`. La dirección predeterminada es
`http://127.0.0.1:10767`; se puede cambiar en `[cider].url` a otra dirección
local. La configuración personal de Cider no se modifica.

La cola excluye historial y pista actual. Si el backend no puede identificar
la posición actual (por ejemplo, IDs duplicados sin índice), muestra un aviso.
Si faltan credenciales, la interfaz indica cómo conectarlas, no inventa pistas.
Con API disponible también se usan sus tiempos por canción, porque algunos
Chromium publican un reloj acumulado que no corresponde a la pista actual.

## Historial y scrobbling

El historial se registra cuando una pista empieza a reproducirse y se guarda
en `~/.cache/amui/history.jsonl` (o `XDG_CACHE_HOME/amui`). Incluye timestamp UTC,
título, artista y álbum. `history=false` lo desactiva. `--history [N]` funciona
sin abrir una terminal interactiva ni conectar Cider.

El scrobbling está **desactivado por defecto**. Para activarlo, configura
`[scrobble].providers = ["listenbrainz"]`, `["lastfm"]` o ambos, y proporciona
las credenciales como se explica en [la guía](docs/CONFIGURATION.md#scrobbling).
Nunca se incluyen credenciales en el código o el historial.

Cuenta tiempo efectivamente escuchado: las pausas y saltos de seek no cuentan.
Envía una vez al escuchar la mitad de la pista o cuatro minutos, lo que ocurra
primero; excluye pistas de 30 s o menos. Si no hay duración, espera cuatro
minutos. Guarda pendientes sin tokens en `scrobbles.json` y reintenta cada
60 segundos. El estado aparece al pie de la interfaz. Evita activar otro
scrobbler para la misma reproducción si no quieres duplicados entre clientes.

## Exportar letras

`S` propone `export_dir` y permite escribir otra carpeta. Guarda `.lrc` cuando
hay tiempos utilizables, o `.txt` para letras de texto. Si el archivo existe,
añade un número; no sobrescribe tu archivo. La exportación conserva la canción
que estaba seleccionada al abrir el prompt, aunque cambie durante la escritura.
Las búsquedas manuales se mantienen para esa canción; `R` reintenta la última.

## Letras y portadas

Las letras vienen de [LRCLIB](https://lrclib.net/docs); se envían título,
artista, álbum y duración cuando está disponible. No se envían credenciales
de Apple Music. No todas las canciones tienen letras o marcas de tiempo.
Los errores de red se muestran en el panel; `R` vuelve a intentarlo.

La caché está en `$XDG_CACHE_HOME/amui/lyrics` o `~/.cache/amui/lyrics`.
La portada usa la ruta local `file://` publicada por MPRIS, incluidos espacios
codificados. Se actualiza si llega tarde o cambia de ruta. Las portadas con
URL remota no se descargan en esta versión.

## Desarrollo

```text
bin/amui              Interfaz y servicios; Python estándar
lib/amui/features.py   Config, cola/API, historial, scrobbling y portadas
share/amui/           Configuración de ejemplo instalada
tests/                Pruebas unitarias, HTTP local y terminal PTY
docs/                 Configuración y detalles de integración
Makefile              check / install / uninstall
```

```bash
make check
./bin/amui --no-lyrics --no-cava
```

La autodetección prioriza un `chromium.instance*` en reproducción; si ninguno
reproduce, usa el primero. `--player` permite fijar una sesión exacta cuando
otros reproductores Chromium compiten con Cider.

La duración se conserva por canción y descarta valores inválidos como
`INT64_MAX`. Si Cider nunca publica una duración válida, se muestra `--:--`.
Los tiempos y controles dependen de lo que Cider publique y acepte vía MPRIS.
Si la duración MPRIS no coincide con la de LRCLIB, se presentan letras de texto
con un aviso en vez de seguir un reloj que no corresponde a esa versión.
El visualizador se oculta si no hay suficiente altura; usa `f` para ver letras
en una ventana angosta.

Para quitar el ejecutable instalado: `make uninstall`. El proyecto y su caché
se conservan. CAVA se integra mediante su
[salida raw ASCII](https://github.com/karlstav/cava/blob/master/example_files/config).
