# amui — estado y continuidad del proyecto

Actualizado: 30 de septiembre de 2026. Versión publicada: **v0.5.6**.
Repositorio: [EchoLenn/amui](https://github.com/EchoLenn/amui).

Este documento consolida estado, implementación, resúmenes y propuestas
anteriores. Instalación y controles están en [README](../README.md);
los ajustes detallados, en [CONFIGURATION](CONFIGURATION.md).

## Alcance

Un frontend de Apple Music para terminal sobre Cider, MPRIS y Python estándar.
Cider sigue siendo el motor musical: amui no implementa reproducción, login
de Apple Music ni almacenamiento de audio. Mantiene un ejecutable para Linux
de escritorio; no ofrece soporte nativo de macOS o Windows.

La base incluye detección `chromium.instance*`, controles de reproducción,
seek, volumen/mute, reinicio, duración cacheada, portada y layout adaptable.
Se añadieron CAVA, letras LRCLIB sincronizadas o de texto, búsqueda manual,
desfase, exportación, banner de canción, modo mini y soporte de mouse.
El historial es local; Last.fm y ListenBrainz son opt-in y requieren credenciales.

Temas: ocho integrados; fuentes carátula, fijos, personalizado y Pywal.
Carátula ofrece extracción, complementarios y contraste. El editor conserva
siete hexadecimales originales; en pantalla se aproximan a 256 colores.
Pywal se lee sin ejecutarlo ni cambiar su configuración.

Las seis propuestas más recientes están implementadas:

1. **Colecciones:** entrar en álbumes/playlists de catálogo o biblioteca,
   conservar páginas y selección, elegir canciones y volver a resultados.
2. **Cola:** navegar y saltar a una posición existente; eliminar selección o
   vaciar solo pendientes con confirmación y verificación de cambios.
3. **Biblioteca/favoritos:** `A` añade; `H` alterna el favorito real. La etiqueta FAVORITO
   representa estado guardado confirmado, no una calificación ni estado optimista.
4. **Notificaciones:** `notify-send` opcional, deduplicado y sin bloquear el dibujo.
5. **Temporizador:** pausa única en 15/30/45/60 minutos o fin de canción;
   cancelación, cuenta regresiva y protección frente a otra sesión.
6. **CLI:** JSON de estado y siguiente/anterior/play-pause sin abrir la TUI.

## Arquitectura y archivos

```text
bin/amui                    entrada CLI, Player, letras, CAVA, portada y UI
bin/amui-kitty              lanzador opcional con fuente aislada
lib/amui/features.py        TOML, Cider API, buscador, cola, temas, historial/scrobbling
lib/amui/services.py        temporizador y notificaciones impulsados por la UI
share/amui/config.example.toml
share/amui/amui.desktop.in  entrada para el menú del escritorio
share/amui/cider-plugin/    puente mínimo de favoritos de PluginKit
tests/                      pruebas unitarias, HTTP, teclado PTY y JavaScript
legacy/                     Bash original y v0.2 conservados
docs/                       esta guía, configuración y auditoría
```

MPRIS es la base de detección y metadatos. La API local autenticada de Cider
complementa funciones que Chromium no expone y sus tiempos por canción.
Si MPRIS queda vacío, se verifica que el PID pertenece a Cider antes de
recuperar datos y portada oficial. No se sustituyen metadatos válidos de otro
Chromium ni se inventa una canción a partir de flags residuales.

Las búsquedas trabajan en segundo plano con generaciones para ignorar
respuestas tardías. Las órdenes aceptadas no se descartan por una búsqueda
nueva. La cola usa snapshots e índices absolutos cero-based comprobados en
Cider; al vaciar pendientes elimina de atrás hacia adelante, nunca toda la cola.

El puente de favoritos existe porque la API instalada no permite esa escritura
real mediante su endpoint de calificación. Usa PluginKit y el cliente Apple Music
de Cider; valida solicitudes, serializa y revalida la canción antes de POST/DELETE.
Debe instalarse y **activarse** una vez en Plugins; reiniciar no sustituye activarlo.

## Datos y preferencias

- TOML y token en `$XDG_CONFIG_HOME/amui`, normalmente `~/.config/amui`.
  Token privado `0600`; las credenciales nunca se guardan en el repositorio.
- Apariencia en `config.appearance.json`, junto al TOML. Prioridad:
  CLI → elección guardada → TOML → predeterminados. Editar TOML invalida la elección.
- Editor en `custom-theme.json`; `personal` no reemplaza otro tema explícito.
  `aurora` pertenece al ejemplo TOML, no a los ocho temas integrados.
- Cachés, historial JSONL y pendientes de scrobbling en `$XDG_CACHE_HOME/amui`.
  Letras reutilizables durante 30 días; paletas por contenido, máximo 256 entradas.
- Exportaciones LRC/TXT eligen nombres nuevos si hay colisiones; conservan la
  canción seleccionada al abrir el prompt aunque cambie la reproducción.
- Scrobbling cuenta escucha efectiva, sin pausas/seek; umbral mitad de pista
  o cuatro minutos, excluye pistas de 30 s o menos y reintenta pendientes.

## Privacidad e integraciones

No hay embeds de terceros en la documentación ni medios empaquetados en el
repositorio. Esto no significa que la aplicación funcione sin conexiones:

| Integración | Datos y destino | Cuándo |
| --- | --- | --- |
| LRCLIB | Título, artista, álbum y duración para encontrar letras; caché local | Letras activadas, predeterminado; `--no-lyrics` las desactiva |
| Cider / Apple Music | Token enviado solo a la API localhost; consultas de catálogo/biblioteca y acciones a través de Cider | Configuración de API y funciones musicales |
| Portadas | Ruta local MPRIS o descarga HTTPS de hosts `mzstatic.com`, sin URL arbitraria ni redirecciones | Cuando hay portada disponible; caché local |
| Last.fm / ListenBrainz | Metadatos de escucha y credenciales al proveedor elegido | Solo con proveedor habilitado y credenciales |
| CAVA | Audio de la salida del sistema, también de otras apps | Visualizador habilitado; no se almacena ni envía audio desde amui |
| Notificaciones | Título, artista, álbum y posible portada al servicio del escritorio | Solo con `desktop_notifications = true` |
| Historial / exportación | Metadatos locales, letras en caché y LRC/TXT exportados | Historial predeterminado; exportación manual |

Las consultas externas también exponen la conexión al proveedor (por ejemplo,
la dirección IP). No hay telemetría propia añadida por amui; Cider y los servicios
externos tienen sus propias políticas. Pywal solo se lee localmente.
`cover_protocol = "none"` evita dibujar imágenes; no es un control de privacidad
que garantice que no se recuperen metadatos o portada. Desinstalar conserva datos.

No publiques tokens, historial, cachés ni exportaciones. `.gitignore` excluye
archivos de credenciales y datos personales habituales, pero no sustituye revisar
lo que se añade a Git. Una credencial publicada debe revocarse, no solo borrarse.

## Revisión de accesibilidad y publicación

Revisión posterior a v0.5.6, 30 de septiembre de 2026:

- **139 pruebas aprobadas** con `make check`, incluidas diez regresiones nuevas
  de contraste y teclado, pruebas de terminal PTY y del puente JavaScript.
- Contraste de los ocho temas, temas personalizados/dinámicos y fases de fade:
  objetivo 4.5:1 para texto y 3:1 para bordes con los RGB de la paleta xterm.
  Los valores guardados no cambian; se corrige únicamente su representación.
  En ocho colores se usa blanco sobre negro. No se atenúa texto con `A_DIM`.
- Ayuda modal, selección por teclado, preguntas de confirmación y cancelación
  visibles en paneles compactos; campos de color nombrados y formato explícito.
  Los estados de favorito no dependen solo de un corazón.
- Título, artista y álbum proporcionan la identificación textual independiente
  de la portada. No equivalen a una descripción visual de la obra de arte.
  No hay imágenes Markdown que necesiten `alt`; futuras capturas deben tener
  alternativas descriptivas y derechos de uso.
- Revisión de archivos y escaneo por patrones del historial Git alcanzable,
  incluyendo `origin/main` y etiquetas: 93 blobs comprobados antes de esta
  actualización, sin coincidencias de credenciales conocidas ni rutas privadas.
  No es una garantía exhaustiva de ausencia de secretos o de procedencia legal.
- Código y documentación originales bajo [MIT](../LICENSE). Dependencias y
  servicios externos conservan sus condiciones; avisos en [NOTICE](../NOTICE).
  No se empaquetan música, letras, portadas, fuentes ni bibliotecas de terceros.

Las comprobaciones de paleta y teclado son automatizadas; la interpretación
real depende del emulador, su paleta configurable y su fuente. No se ha validado
con lectores de pantalla ni se declara cumplimiento WCAG. La alternativa CLI
de estado es texto estable, pero no reemplaza la navegación de la TUI.
Objetivos de contraste: [W3C](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

### Prueba manual con lector de pantalla

**Estado: pendiente; no hay una prueba de voz o braille aprobada.** La revisión
local del 30 de septiembre de 2026 encontró Arch Linux, KDE/Wayland, Kitty
0.49.1, Konsole 26.08.1, AT-SPI2 2.60.7 y espeak-ng 1.52.0. Orca y
Speech Dispatcher no están instalados; disponer de un sintetizador no equivale
a disponer de un lector funcional. La fuente efectiva de la ventana no se midió.
No se instalaron paquetes ni se activaron aplicaciones para esta revisión.

[Orca necesita aplicaciones que expongan AT-SPI](https://gnome.pages.gitlab.gnome.org/orca/help/introduction.html).
El [mantenedor de Kitty documentó la ausencia de integración con lectores](https://github.com/kovidgoyal/kitty/discussions/9202);
el soporte de imágenes o teclado de Kitty no prueba accesibilidad por voz.
Elegir una terminal que el lector pueda leer, comprobar primero texto normal
y registrar la combinación exacta; Konsole instalado tampoco demuestra que
su funcionamiento con Orca haya sido probado aquí.

Realizar la evaluación en una sesión de prueba con el lector configurado,
preferiblemente con una persona que lo use habitualmente. Registrar commit y
`amui --version`, distribución/kernel, escritorio, Wayland/X11, terminal y
versión, fuente **real** y versión/tamaño, paleta, lector y versión, idioma/voz
o dispositivo braille, layout/modificador del lector y tamaño en celdas.
`fc-match monospace` por sí solo no identifica una fuente sobrescrita por la
ventana. Los resultados deben describir lo oído o leído, no solo lo dibujado.

Desde el repositorio, usar `tests/ui_fixture.py`: sus reproductor, búsqueda,
letras y cola son simulados. Crear un directorio temporal:

```bash
task_dir=$(mktemp -d)
```

Guardar allí `manual.toml` con los ajustes siguientes; así la prueba no necesita
una cuenta ni modifica reproducción real:

```toml
theme = "mono"
theme_source = "fixed"
animations = false
cava = false
cover_protocol = "none"
mouse = false
history = false
desktop_notifications = false
[scrobble]
providers = []
```

```bash
XDG_CONFIG_HOME="$task_dir/config" XDG_CACHE_HOME="$task_dir/cache" \
  python3 tests/ui_fixture.py --config "$task_dir/manual.toml" --no-cava
```

| Paso manual | Qué comprobar y registrar |
| --- | --- |
| Texto normal antes de amui | El lector reconoce la terminal y lee una línea con «canción, sesión, música». Si falla, bloquear la combinación antes de evaluar la TUI. |
| Metadatos sin portada | Localizar título, artista, álbum, estado y tiempos por voz/braille; no depender de imagen, color ni ayuda visual. |
| Lectura y selección | Distinguir revisión del texto de selección de amui. En `b`, buscar, mover ↑↓ y comprobar que se identifica el resultado seleccionado y su acción. |
| Ayuda y formularios | Abrir `?`, salir con Esc; abrir `T` → personalizado, identificar nombre de campo y `#RRGGBB`, editar con Ctrl+U y cancelar. Registrar etiquetas ausentes, tecla interceptada o lectura desactualizada. |
| Cola y confirmaciones | Abrir `Q`, mover selección, solicitar `d`/`c` y cancelar con Esc. Leer canción/alcance, Enter/Esc y cambio de contexto; realizar confirmaciones únicamente en la simulación. |
| Solo teclado y cambios | Completar lo anterior sin mouse; volver al reproductor, cambiar entre paneles y redimensionar. Comprobar foco/selección recuperables y que los redibujados no interrumpen constantemente la voz. |
| Movimiento y paleta | Comparar los ajustes sin movimiento con la paleta/fuente habitual y ventana compacta. No tratar lectura por voz como prueba de contraste ni viceversa. |

La [revisión plana de Orca](https://gnome.pages.gitlab.gnome.org/orca/help/howto_flat_review.html)
lee contenido visible y puede quedar desactualizada tras un redibujado;
refrescarla no demuestra que amui anuncie automáticamente selección o cambios.
Registrar por paso **aprobado, fallo o bloqueado**, teclas exactas, respuesta
literal y ayuda requerida, sin tokens ni datos de cuentas. Si no hay acceso
al texto, foco o selección, dejarlo como fallo/bloqueo y reportar la combinación;
no sustituirlo por una prueba PTY o por `--status`. Esa CLI sigue siendo una
alternativa textual parcial. La aceptación real requiere completar esta matriz
con salida de un lector funcional y evaluación humana, pendiente actualmente.

### Derechos y condiciones

La [LFDA mexicana](https://www.diputados.gob.mx/LeyesBiblio/pdf/LFDA.pdf)
protege, entre otras categorías, obras musicales, fotografías y programas de
cómputo (art. 13 y 101–102). La licencia de amui no concede derechos sobre obras
obtenidas de otros servicios. Los [términos de Apple para México](https://www.apple.com/legal/internet-services/itunes/mx/terms.html)
restringen acceso mediante software de terceros y extracción automatizada;
la compatibilidad contractual de esta integración no se ha establecido.
Esta revisión no es asesoría ni autorización legal. Se necesita revisión
específica de derechos y condiciones antes de redistribuir contenido de terceros,
usar el proyecto comercialmente con dichos servicios u ofrecerlo como servicio.

## Historial resumido

- **Bash/v0.2:** base funcional, portada Kitty, letras, CAVA y diseño adaptable.
- **v0.3:** trece mejoras de cola, configuración, letras, historial, protocolos,
  mini, animaciones, scrobbling, exportación, paleta y mouse; 35 pruebas entonces.
- **v0.4:** selector y cinco temas nuevos, K-means, contraste, caché, transiciones,
  recarga de temas y ayuda; 42 pruebas entonces.
- **v0.5.1:** reparación de apariencia y buscador; legacy restaurado, hexadecimales
  conservados, persistencia, paginación y precedencia corregidas; 55 pruebas entonces.
- **v0.5.2:** volumen real, shuffle estable, cursor/portada y Unicode; lanzador
  Kitty opcional con JetBrains Mono sin cambios globales; 59 pruebas entonces.
- **v0.5.3:** navegación en álbumes/playlists; 65 pruebas entonces.
- **v0.5.4:** selección y salto en cola sin duplicar canciones.
- **v0.5.5:** recuperación de metadatos MPRIS vacíos tras saltar, incluso al reabrir.
- **v0.5.6:** las seis propuestas completas y auditoría; **129 pruebas aprobadas**,
  instalación temporal/local y publicación verificadas. El fallo previo de
  playlist no volvió a reproducirse durante la validación de esa entrega.

## Límites y cómo seguir

La evidencia completa está en [la auditoría](AUDIT-v0.5.6.md). Las escrituras
de cuenta/cola y el temporizador se probaron con servicios simulados, no cambiando
la biblioteca personal. Consultas reales confirmaron contratos de catálogo,
biblioteca y estado guardado. Node ejecuta las pruebas del puente cuando está disponible.

Los avisos necesitan daemon; letras dependen de LRCLIB y versión/duración de la
pista; CAVA captura audio del sistema. Fin de canción está limitado por el muestreo
y puede pausar al empezar la siguiente. Las portadas requieren soporte del terminal;
la inspección visual nativa no se realizó en todos los backends. Un envío aceptado
por Cider no garantiza reproducción de contenido restringido por región/suscripción.

Antes de iterar: leer esta guía, revisar `git status`, mantener preferencias y
legacy, añadir una regresión para cada fallo y ejecutar `make check`. Verificar
instalación en prefijo temporal antes de actualizar la local. No ampliar
dependencias ni cambiar arquitectura sin una necesidad concreta; no hay nuevas
funcionalidades pendientes acordadas dentro de las seis propuestas completadas.

Como ideas futuras, todavía no implementadas ni comprometidas para una versión:
estadísticas de escucha, socket de control y hooks. Se conservan como posibilidades,
no como funciones actuales ni requisitos de esta entrega.

La limpieza documental y los ajustes de accesibilidad posteriores a v0.5.6
no cambian esa etiqueta; están disponibles en `main`, sin una nueva release.
Los cinco documentos raíz redundantes se retiraron de `main`; sus versiones
originales siguen en Git y en la etiqueta v0.5.6, sin perder el historial.
