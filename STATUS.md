# Estado del proyecto — amui

Última actualización: 29 de septiembre de 2026.

## Qué es

`amui` es una interfaz musical para terminal construida sobre Cider, MPRIS y
Python estándar. Cider se encarga de la reproducción de Apple Music; amui pone
al frente los metadatos, controles, portada, letras y visualizador.

Repositorio remoto: <https://github.com/EchoLenn/amui> (privado).

## Implementado

- Detección automática de sesiones `chromium.instance*` de Cider mediante
  MPRIS, con opción `--player` para seleccionar una sesión concreta.
- Metadatos, controles de reproducción, seek, volumen, mute, reinicio y barra
  de progreso con duración cacheada por canción.
- Diseño adaptable de terminal: vista completa, compacta, modo mini de dos
  líneas, panel de ayuda, avisos de cambio de canción y animaciones suaves.
- Portadas en Kitty, iTerm2/WezTerm y Sixel cuando el terminal lo permite,
  además de paleta dinámica basada en la portada.
- Visualizador CAVA, letras de LRCLIB con caché, letras sincronizadas, búsqueda
  manual, ajuste de desfase y exportación LRC/TXT sin sobrescribir archivos.
- Cola "Up next", shuffle y repeat a través de MPRIS TrackList o de la API
  local autenticada de Cider cuando esa sesión no expone dichos controles.
- Configuración TOML, temas y atajos personalizables; historial local;
  scrobbling opcional para Last.fm y ListenBrainz.
- Soporte de mouse: seek desde la barra de progreso y desplazamiento de letras.

## Estructura

```text
bin/amui                    ejecutable principal
lib/amui/features.py        configuración e integraciones
share/amui/                 configuración de ejemplo
docs/                       guía de configuración
tests/                      pruebas unitarias, HTTP y terminal PTY
legacy/                     versiones anteriores conservadas
README.md                   instalación, uso y controles
IMPLEMENTATION.md           alcance y verificación detallada
```

## Uso rápido

En Arch Linux:

```bash
sudo pacman -S python playerctl kitty cava
make check
make install
amui --init-config
amui
```

Cider se instala por separado y debe estar ejecutándose con MPRIS disponible.
Las opciones y atajos completos están en [README.md](README.md) y
[docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Estado de calidad

La suite tiene 35 pruebas. La última ejecución aprobó 34; una prueba de
generación Sixel falló porque no pudo producir la portada Sixel en este entorno.
No afecta las rutas de Kitty ni iTerm2/WezTerm, pero queda como pendiente antes
de considerar Sixel verificado en todos los equipos.

## Publicación

El repositorio privado contiene el proyecto completo en la rama `main` y el
script `bin/amui` conserva su permiso de ejecución. No se publicaron tokens,
configuración personal ni cachés de reproducción.
