# Auditoría de entrega — v0.5.6

Fecha: 30 de septiembre de 2026. Alcance: completar las seis propuestas,
verificar comportamiento y evitar código o dependencias innecesarias.

**Resultado:** 129 pruebas aprobadas con `python3 -m unittest discover -s tests -q`.
Instalación en prefijo temporal verificada: ejecutable, módulos, lanzador,
configuración de ejemplo y complemento. Se comprobó la instalación del puente
desde ese prefijo sin tocar Cider real.

## Requisitos y pruebas

| Propuesta | Implementación | Evidencia automatizada |
| --- | --- | --- |
| Álbumes/playlists | `MusicBrowser`, navegación y páginas conservadas | `test_collections.py`, `test_music_sources.py`, teclado PTY |
| Cola interactiva | Índices absolutos; confirmación; eliminar pendientes en orden descendente | `test_queue_navigation.py`, `test_library_queue_controls.py`, PTY |
| Favorito/biblioteca | Estado guardado confirmado; POST/DELETE real mediante PluginKit; no calificación | `test_library_queue_controls.py`, `test_favorite_bridge.py`, instalación |
| Avisos nativos | Opt-in; argumentos seguros; deduplicación y limpieza del proceso | `test_services.py` |
| Temporizador | Reloj monotónico; pausa explícita una vez; cambio de sesión y fin de pista | `test_services.py`, PTY |
| CLI | JSON Unicode de una línea; controles sin UI ni hilos | `test_cli.py` |

La suite también verifica tamaños de terminal, acentos compuestos/descompuestos,
temas, fallos HTTP, respuestas tardías y recuperación tras reiniciar amui.
`test_audit_regressions.py` protege las correcciones de sesión, portada y fade.

## Código añadido y necesidad

- `services.py`: dos servicios pequeños impulsados por el bucle existente;
  no añade hilos ni dependencias Python.
- Complemento Cider: puente acotado para favoritos reales. La API HTTP instalada
  no proporciona el POST/DELETE necesario; `set-rating` no es un sustituto.
  Solo actúa sobre una solicitud explícita válida y revalida la pista al ejecutarla.
- Snapshots, identidades y validaciones de cola: necesarios para no borrar ni
  controlar una canción diferente cuando cambia el estado entre teclas y peticiones.
- Confirmaciones de biblioteca: evitan corazones optimistas y falsos éxitos.
- El muestreo de `Player` se comparte entre TUI y CLI; se retiró un import sin uso.
  Se mantienen las protecciones de autenticación, secretos, URLs y cachés existentes.
- No se añadieron servidores, gestores de paquetes ni otra arquitectura musical.
  Node se utiliza únicamente para probar JavaScript; no es requisito de ejecución.

## Correcciones demostradas

- Controles en espera de otro reproductor se cancelan antes de usar MPRIS o API.
- Un fallo de portada no ejecuta el dibujador cada cuadro: espera diez segundos
  antes de reintentar, pero acepta una portada nueva inmediatamente.
- Un fade terminado mantiene sus colores sin recalcularlos en cada cuadro.
- Metadatos MPRIS temporalmente vacíos no cancelan el temporizador de fin de pista
  solo porque su identidad sintetizada no está vacía.
- Cider conectado sin canción no se confunde con otra canción durante el cambio;
  no se reconstruye una pista a partir de favoritos/shuffle residuales.

## Verificación real y límites

Consultas reales de catálogo/biblioteca y del estado guardado de Apple Music
confirmaron el formato de datos. Se inspeccionó el código instalado de Cider
para verificar índices cero-based, el bus de mensajes y la carga de complementos.
La instalación y el estado se comprueban sin modificar la cola ni favoritos reales.

Las mutaciones de cola/biblioteca/favoritos y el vencimiento del temporizador
se prueban con servicios simulados y JavaScript ejecutado en Node; no se afirma
haber alterado la biblioteca personal para verificarlas. Para usar `H` hay que
activar una vez el complemento en Cider. Los avisos nativos necesitan un daemon
de notificaciones; fin de canción está limitado por el intervalo de muestreo.

El usuario indicó que el fallo previo de playlist dejó de reproducirse en la
última versión y autorizó continuar con esta entrega. Si vuelve a ocurrir, se
investigará con su estado y error concretos, sin atribuirlo automáticamente al layout.
