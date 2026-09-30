# amui — estado y continuidad del proyecto

Actualizado: 30 de septiembre de 2026. Versión publicada: **v0.5.6**.
Repositorio: [EchoLenn/amui](https://github.com/EchoLenn/amui).

Este documento consolida estado, implementación, resúmenes y propuestas
anteriores. Instalación y controles están en [README](../README.md);
los ajustes detallados, en [CONFIGURATION](CONFIGURATION.md).

## Qué construimos

Un frontend de Apple Music para terminal sobre Cider, MPRIS y Python estándar.
Cider sigue siendo el motor musical: amui no implementa reproducción, login
de Apple Music ni almacenamiento de audio. Mantiene un ejecutable universal.

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
3. **Biblioteca/favoritos:** `A` añade; `H` alterna el favorito real. El corazón
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
- **v0.5.3:** navegación en álbumes/playlists; confirmada por el usuario; 65 pruebas entonces.
- **v0.5.4:** selección y salto en cola sin duplicar canciones.
- **v0.5.5:** recuperación de metadatos MPRIS vacíos tras saltar, incluso al reabrir.
- **v0.5.6:** las seis propuestas completas y auditoría; **129 pruebas aprobadas**,
  instalación temporal/local y publicación verificadas. El usuario indicó que
  el fallo previo de playlist dejó de reproducirse y autorizó el lanzamiento.

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

La limpieza documental posterior a v0.5.6 no cambia el código ni esa etiqueta.
Los cinco documentos raíz redundantes se retiraron de `main`; sus versiones
originales siguen en Git y en la etiqueta v0.5.6, sin perder el historial.
