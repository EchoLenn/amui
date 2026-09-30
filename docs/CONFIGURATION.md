# Configuración de amui 0.5.6

## Cola interactiva

`Q` amplía la cola: ↑↓ selecciona, PgUp/PgDn mueve cinco posiciones,
Home/End salta al inicio/final y Enter solicita reproducir esa posición existente.
Esc o Q vuelve al reproductor. No se añade la canción de nuevo. La selección
se reinicia cuando cambia la cola; antes del salto se valida de nuevo con Cider.
Requiere la API autenticada. La cola MPRIS sin API es solo informativa.
`d` o Supr solicita borrar la selección; `c` solicita vaciar únicamente las
pendientes. Enter confirma y Esc cancela. Cada eliminación vuelve a verificar
la canción y la cola; si cambian, se detiene. Nunca usa el borrado de cola completa.

## Favoritos, biblioteca y temporizador

`H` alterna el favorito real; `A` añade la canción actual a la biblioteca.
El estado se confirma consultando Apple Music y se asocia a la identidad de
esa canción. Un fallo no cambia el corazón ni anuncia un guardado exitoso.

Para `H`, ejecuta `amui --install-cider-plugin` y en Cider → Settings → Plugins
actualiza la lista y activa **amui Favorites Bridge**. El complemento usa el
bus de mensajes de PluginKit y el cliente Apple Music de Cider para POST/DELETE
de favoritos; la API de calificación antigua no es equivalente. No necesitas
reiniciar la reproducción. Para instalaciones distintas, el argumento opcional
es el directorio completo del complemento: `--install-cider-plugin /ruta/al/plugin`.
Si reemplaza archivos distintos, guarda la versión anterior en `.previous`.

`Z` abre el selector de 15/30/45/60 minutos, fin de canción o cancelar. Flechas
seleccionan; Enter aplica; Esc cierra sin cambiar el temporizador anterior.
La cuenta continúa durante una pausa, pero al vencer no inicia reproducción:
envía una pausa explícita solo si está reproduciendo. Se cancela al cambiar
de reproductor y al cerrar amui. Fin de canción necesita duración conocida;
un salto temprano lo cancela. El muestreo puede pausar al comienzo de la siguiente.

## Escritorio y control sin interfaz

`desktop_notifications = true` habilita `notify-send` al cambiar de canción en
reproducción, con título, artista, álbum y portada local si existe. Está
desactivado por defecto y es independiente del banner interno `notifications`.
Necesita `notify-send` y un servicio de notificaciones; sin ellos no hay avisos.
Puede duplicar los avisos propios de Cider.

`amui --status` imprime una sola línea JSON sin curses, hilos, historial ni
scrobbling. Incluye metadatos, estado, segundos, progreso y volumen.
`--next`, `--prev` y `--toggle` controlan la misma selección de reproductor;
aceptan `--player` exacto. Las cuatro opciones son mutuamente excluyentes.

## Temas y música desde la interfaz

`T` abre las fuentes: `1` carátula, `2` temas fijos, `3` personalizado y `4` Pywal.
En carátula elige extracción, complementarios (180°) o contrastantes (tríada y
contraste de acentos de al menos 7:1). Flechas navegan; Enter aplica y guarda.
Esc vuelve al menú anterior; desde el menú principal cancela todos los cambios
de vista previa. `t` conserva el ciclo rápido.

Personalizado muestra los temas del TOML y ofrece crear/editar `personal`.
El editor pide siete colores: Ctrl+U limpia, Enter acepta y avanza; el último
Enter guarda en `custom-theme.json`, junto al archivo TOML. Esc cancela la
edición sin sobrescribir el archivo. La representación en terminal usa 256
colores, pero se guardan los valores hexadecimales exactos.

La elección de tema, fuente y modo se guarda en un archivo hermano del TOML:
`config.toml` usa `config.appearance.json`. Prioridad: CLI → elección guardada →
TOML → predeterminados. Una edición manual del TOML invalida la elección guardada.
`--theme personal --theme-source custom` permite seleccionar el tema del editor.
`--list-themes` también lo incluye cuando existe.

Pywal lee `pywal_file` cada dos segundos mientras está seleccionado. amui no
ejecuta `wal` ni modifica su archivo; conserva la última paleta válida ante un
error. Los textos se ajustan para mantener contraste legible.

`b` abre el navegador musical. Escribe una consulta y pulsa Enter para buscar.
Tab alterna catálogo/biblioteca de Apple Music; ←→ cambia canciones/álbumes/
playlists, incluso mientras escribes. La biblioteca sin consulta permite
recorrer los elementos de tu cuenta. ↑↓ selecciona; Enter abre álbumes/playlists
o pide reproducir una canción. `P` reproduce la colección completa,
`+` añadir al final y `n` añadir a continuación. `N` carga más resultados y
conserva los anteriores. `/` edita la consulta; Ctrl+U la limpia; Esc cierra.
Dentro de una colección, Esc o ← vuelve a los resultados conservando la
selección; → no cambia de tipo. `N` carga más canciones sin eliminar repeticiones
de la playlist y `r` reintenta si falla. `/` vuelve a editar la búsqueda original.
`b` también cierra al navegar resultados, pero se escribe como texto al editar.
Se muestra la respuesta de la API; un envío aceptado no garantiza que la cuenta
pueda reproducir contenido restringido por región o suscripción.

La búsqueda usa `/api/v1/amapi/run-v3` con la región de la cuenta; la selección
usa `/api/v1/playback/play-item`, `play-later` y `play-next`, según la
[documentación de Cider](https://github.com/ciderapp/docs/blob/main/docs/1.client/rpc.md).

## Preferencias

Archivo: `$XDG_CONFIG_HOME/amui/config.toml`, normalmente `~/.config/amui/config.toml`.
Crear: `amui --init-config`. Validar: `amui --check-config`. Seleccionar otro:
`amui --config /ruta/config.toml`.

| Campo | Predeterminado sin archivo | Uso |
| --- | --- | --- |
| theme | nocturne | Nombre integrado o definido en `[themes]` |
| theme_source | auto | cover, fixed, custom o pywal |
| palette_mode | extract | extract, complementary o contrast |
| pywal_file | ~/.cache/wal/colors.json | Ruta a colors.json de pywal |
| cava_input | pulse | pulse o pipewire |
| lyrics_offset | 0.0 | Segundos; positivo adelanta las letras |
| lyrics / cava / queue | true | Letras, CAVA y panel UP NEXT |
| history / notifications | true | Registro local y banner de 3 s |
| desktop_notifications | false | Avisos opcionales con notify-send |
| animations / mouse | true | Fade/progreso y click/rueda |
| dynamic_palette | false | El ejemplo instalado lo activa |
| cover_protocol | auto | auto, kitty, iterm, sixel, none |
| export_dir | ~/Music/amui-lyrics | Propuesta del prompt de exportación |

CLI `--theme`, `--theme-source`, `--palette-mode`, `--cava-input`, `--dynamic-palette`, `--no-lyrics` y `--no-cava`
tienen prioridad. Mini siempre evita arrancar CAVA y renderiza dos líneas;
los controles de teclado siguen disponibles. Para usar mini sin consultas de
letras: `amui --mini --no-lyrics`.

## Atajos

En `[keybinds]` cada valor es una tecla o una lista de teclas. La acción
reemplaza todas sus teclas anteriores. No se permiten colisiones; Esc y Enter
están reservados para cerrar/aceptar prompts.

Acciones:

```text
toggle next previous forward back up down mute restart
shuffle repeat quit help lyrics focus visualizer theme
theme_picker scroll_up scroll_down offset_back offset_forward retry open
search export queue music favorite library sleep
```

Los nombres especiales son `SPACE`, `LEFT`, `RIGHT`, `UP`, `DOWN`. El resto
son caracteres individuales, distinguiendo mayúsculas. La ayuda y la barra
de controles usan las teclas configuradas.

## API local de Cider

```toml
[cider]
url = "http://127.0.0.1:10767"
token_file = "~/.config/amui/cider.token"
```

`amui --connect-cider` pide el token sin mostrarlo, valida `/playback/active`
y sólo después lo guarda con permisos privados. `AMUI_CIDER_TOKEN` tiene
prioridad sobre el archivo. No se aceptan destinos remotos ni se siguen
redirecciones con autenticación.

Se consulta `/api/v1/playback/now-playing` y `/queue`. Para controles se usan
`/toggle-shuffle`, `/toggle-repeat` y `/seek`. Primero se intenta MPRIS donde
está soportado. Esta API está documentada por
[Cider](https://github.com/ciderapp/docs/blob/main/docs/1.client/rpc.md).
El acceso local observado devuelve 403 sin token; las pruebas usan además un
servidor HTTP local con el mismo contrato y un token de prueba.

## Scrobbling

Elige proveedores explícitamente:

```toml
[scrobble]
providers = ["listenbrainz", "lastfm"]
credentials_file = "~/.config/amui/scrobble.json"
```

El archivo JSON debe contener sólo los proveedores que uses:

```json
{
  "listenbrainz": {"token": "TU_TOKEN"},
  "lastfm": {
    "api_key": "TU_API_KEY",
    "secret": "TU_API_SECRET",
    "session_key": "TU_SESSION_KEY"
  }
}
```

Protege ese archivo con `chmod 600 ~/.config/amui/scrobble.json`. No lo copies
al repositorio. También se aceptan estas variables de entorno, con prioridad:

```text
AMUI_LISTENBRAINZ_TOKEN
AMUI_LASTFM_API_KEY
AMUI_LASTFM_SECRET
AMUI_LASTFM_SESSION_KEY
```

ListenBrainz ofrece el token en sus [ajustes](https://listenbrainz.org/settings/).
Last.fm necesita una API key/secret y una sesión obtenida mediante su
[autenticación oficial](https://www.last.fm/api/authentication). amui no pide
tu contraseña. Una API key sola no sustituye una sesión autorizada.

Los envíos respetan el umbral oficial de
[Last.fm](https://www.last.fm/api/scrobbling) y
[ListenBrainz](https://listenbrainz.readthedocs.io/en/latest/users/api/core.html).
La cola pendiente y el estado de éxito/error se prueban sin credenciales reales;
ninguna reproducción de prueba se envía a una cuenta. La activación real necesita
las credenciales del usuario y un proveedor habilitado en config.

El historial y la cola pendiente permanecen al desinstalar. Para dejar de enviar,
vuelve a `providers = []`; los pendientes se conservan, pero no se envían.

## Portadas y límites

- Kitty: `kitten icat` o `kitty +kitten icat`; se elimina sólo la imagen de amui.
- iTerm2 y WezTerm: protocolo OSC 1337 inline, sin dependencia adicional.
- foot/Sixel: `chafa --format=sixels`, o ImageMagick si Chafa no está presente.
- Forzar: `cover_protocol = "sixel"` / `"iterm"` / `"kitty"` / `"none"`.
- El origen habitual es una ruta local `file://` de MPRIS. Si Cider pierde esos
  metadatos, amui verifica la instancia y recupera su portada oficial HTTPS
  de `mzstatic.com`, sin seguir redirecciones y con límites de tamaño/tiempo.
  No descarga URLs arbitrarias. Si falta backend o portada, aparece el fallback.
- La paleta dominante requiere ImageMagick; si no existe, mantiene el tema.
- El mouse requiere soporte de eventos en la terminal; Shift+seleccionar suele
  permitir seleccionar texto del terminal sin que amui capture el click.

Documentación de los protocolos:
[iTerm2](https://iterm2.com/documentation-images.html),
[Chafa](https://hpjansson.org/chafa/),
[MPRIS TrackList](https://specifications.freedesktop.org/mpris/latest/Track_List_Interface.html).
