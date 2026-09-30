# amui — a little louder, a little closer

Apple Music en tu terminal: **Cider reproduce; amui pone la portada, letras,
CAVA, controles y navegación musical al frente.**

Versión actual: [v0.5.6](https://github.com/EchoLenn/amui/releases/tag/v0.5.6).
Un ejecutable universal, Python estándar y diseño adaptable; no hay versiones
separadas por terminal. La entrega pasó **129 pruebas automatizadas**.

## Qué incluye

- Reproducción, seek, volumen, mute, reinicio, shuffle y repeat mediante MPRIS
  o la API local autenticada de Cider.
- Portadas Kitty, iTerm2/WezTerm y Sixel, con alternativa sin imágenes.
- CAVA integrado; letras LRCLIB sincronizadas o de texto, caché, búsqueda,
  desfase y exportación sin sobrescribir archivos.
- Carátula con extracción, complementarios o contraste; ocho temas fijos,
  editor personalizado y Pywal con recarga de colores.
- Catálogo y biblioteca Apple Music: búsqueda, álbumes/playlists, canciones,
  paginación, reproducción y agregado a la cola desde `b`.
- Cola navegable: salto a una canción existente, borrado y limpieza de pendientes
  con confirmación. No borra historial ni la canción actual.
- Favoritos reales y biblioteca, temporizador, notificaciones opcionales,
  modo mini, mouse, historial y scrobbling opt-in.
- Estado JSON y controles sin interfaz para barras y atajos del escritorio.

## Instalar

Necesitas **Python 3.11+, Cider y playerctl**, con Apple Music iniciado en Cider
y MPRIS disponible en tu sesión de escritorio. En Arch Linux:

```bash
sudo pacman -S python playerctl kitty cava
# Opcionales: paletas, Sixel y notificaciones
sudo pacman -S imagemagick chafa libnotify
```

Desde la carpeta del proyecto:

```bash
make check
make install
amui --init-config  # solo la primera vez; no sobrescribe un archivo existente
amui
```

La instalación usa `~/.local`; añade `~/.local/bin` a tu `PATH` si hace falta.
Para actualizar, basta `make install`: conserva tus preferencias, tokens y cachés.
Para probar sin instalar: `./bin/amui`. Para desinstalar: `make uninstall`;
el proyecto y los datos personales se conservan.

`amui-kitty` abre una ventana dedicada con **JetBrains Mono** (instálala por
separado). Solo cambia la fuente de esa ventana; nunca modifica `kitty.conf`.
`amui` usa la fuente de la terminal actual. Para ver todos los paneles cómodamente,
usa unas 140 × 40 celdas; ventanas menores usan el layout compacto.

## Conectar Cider

Para búsqueda, gestión de cola y biblioteca, habilita la API local de Cider:

1. Cider → Settings → Connectivity → API tokens: crea un token para amui.
2. Ejecuta `amui --connect-cider` y pégalo en el prompt oculto.
3. Vuelve a abrir amui. El token queda fuera del repo con permisos `0600`.

La dirección predeterminada es `http://127.0.0.1:10767`.
También acepta `AMUI_CIDER_TOKEN`. Sin API, los controles MPRIS disponibles
siguen funcionando; la cola obtenida solo por MPRIS es informativa.

Para **favoritos (`H`)**, instala y activa una vez el puente incluido:

```bash
amui --install-cider-plugin
```

En **Cider → Settings → Plugins**, actualiza la lista y activa
**amui Favorites Bridge**. Reiniciar Cider por sí solo no lo activa.
El complemento usa el cliente Apple Music de Cider; no requiere Node para
funcionar. Añadir a biblioteca (`A`) no necesita el complemento.

## Controles

| Tecla | Acción |
| --- | --- |
| Espacio | Reproducir / pausar |
| `n` / `p` | Siguiente / anterior |
| ← / → o `h` / `l` | Seek −5 / +5 segundos |
| ↑ / ↓ o `k` / `j` | Volumen +5 / −5 puntos |
| `m` / `r` | Mute-restaurar / reiniciar pista |
| `s` / `e` | Shuffle / repeat |
| `b` | Buscar y elegir música |
| `Q` | Cola navegable |
| `H` / `A` | Alternar favorito / añadir a biblioteca |
| `Z` | Temporizador de pausa |
| `T` / `t` | Fuentes y editor de temas / ciclo rápido |
| `L` / `f` | Mostrar letras / letras a pantalla completa |
| `v` | Mostrar u ocultar CAVA |
| `/` / `R` | Buscar letras / reconsultar ignorando caché |
| `[` / `]` | Desplazar letras |
| `,` / `.` | Desfase de letras −0.5 / +0.5 segundos |
| `S` | Exportar LRC o TXT |
| `o` | Abrir Cider cuando no hay reproductor |
| `?` / Esc / `q` | Ayuda / cerrar panel o prompt / salir |

Dentro de **`b`**: Tab cambia catálogo/biblioteca; ←→ cambia tipo; Enter busca
al escribir, abre álbumes/playlists al navegar y reproduce canciones.
`+` agrega al final, `n` a continuación, `N` carga más y `P` reproduce la colección.
Esc o ← vuelve desde una colección; `/` edita la búsqueda y `r` reintenta una
consulta fallida. Ctrl+U limpia el texto; las teclas escritas no controlan audio.

Dentro de **`Q`**: ↑↓, PgUp/PgDn y Home/End seleccionan; Enter salta.
`d`/Supr o `c` solicitan borrar selección o vaciar pendientes: **Enter confirma,
Esc cancela**. Si cambia la cola o pista, amui cancela la operación.

`Z` ofrece 15/30/45/60 minutos, fin de canción y cancelar. Cerrar amui o cambiar
de reproductor cancela el temporizador. Fin de canción puede pausar al inicio
de la siguiente por el intervalo de muestreo; un salto manual temprano lo cancela.

## Configuración y CLI

Preferencias en `~/.config/amui/config.toml` (respeta `XDG_CONFIG_HOME`).
Ejemplo completo: [config.example.toml](share/amui/config.example.toml).
`amui --check-config` valida tipos, temas y atajos duplicados.

```bash
amui --mini --no-lyrics
amui --no-cava
amui --theme ice
amui --theme-source cover --palette-mode complementary
amui --cava-input pipewire
amui --player chromium.instance4938
amui --history 30
amui --status
amui --next  # también --prev y --toggle
```

`--status` imprime una línea JSON con metadatos, estado, segundos, progreso
0–1 y volumen 0–1, sin abrir curses ni arrancar hilos, historial o scrobbling.
Sin reproductor devuelve `Stopped` y metadatos vacíos.

Las notificaciones nativas están desactivadas por defecto:
`desktop_notifications = true` requiere `notify-send` y un servicio de avisos.
Last.fm y ListenBrainz también requieren activación y credenciales explícitas.
CAVA captura la salida del sistema, incluidas otras aplicaciones; su backend
`pulse` funciona con `pipewire-pulse`, o puedes elegir `pipewire`.

## Documentación y desarrollo

- [Estado, arquitectura, historial y continuidad del proyecto](docs/PROJECT.md).
- [Configuración, temas, credenciales e integraciones](docs/CONFIGURATION.md).
- [Auditoría v0.5.6: pruebas y límites de verificación](docs/AUDIT-v0.5.6.md).

Ejecuta `make check` antes de cambiar comportamiento. Node es opcional para
probar el complemento JavaScript; no es dependencia de uso. Las pruebas no
alteran la cola ni biblioteca personales. Los documentos históricos y propuestas
ya implementadas se consolidaron; los originales siguen recuperables desde Git.
