# Configuración de amui 0.3

## Preferencias

Archivo: `$XDG_CONFIG_HOME/amui/config.toml`, normalmente `~/.config/amui/config.toml`.
Crear: `amui --init-config`. Validar: `amui --check-config`. Seleccionar otro:
`amui --config /ruta/config.toml`.

| Campo | Predeterminado sin archivo | Uso |
| --- | --- | --- |
| theme | nocturne | Nombre integrado o definido en `[themes]` |
| cava_input | pulse | pulse o pipewire |
| lyrics_offset | 0.0 | Segundos; positivo adelanta las letras |
| lyrics / cava / queue | true | Letras, CAVA y panel UP NEXT |
| history / notifications | true | Registro local y banner de 3 s |
| animations / mouse | true | Fade/progreso y click/rueda |
| dynamic_palette | false | El ejemplo instalado lo activa |
| cover_protocol | auto | auto, kitty, iterm, sixel, none |
| export_dir | ~/Music/amui-lyrics | Propuesta del prompt de exportación |

CLI `--theme`, `--cava-input`, `--dynamic-palette`, `--no-lyrics` y `--no-cava`
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
scroll_up scroll_down offset_back offset_forward retry open
search export queue
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
- El origen sigue siendo una ruta local `file://` de MPRIS. URL remotas no se
  descargan. Si falta backend o portada, aparece el fallback.
- La paleta dominante requiere ImageMagick; si no existe, mantiene el tema.
- El mouse requiere soporte de eventos en la terminal; Shift+seleccionar suele
  permitir seleccionar texto del terminal sin que amui capture el click.

Documentación de los protocolos:
[iTerm2](https://iterm2.com/documentation-images.html),
[Chafa](https://hpjansson.org/chafa/),
[MPRIS TrackList](https://specifications.freedesktop.org/mpris/latest/Track_List_Interface.html).
