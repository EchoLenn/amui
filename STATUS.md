# Estado del proyecto — amui v0.5.6

Actualizado: 30 de septiembre de 2026.

Frontend universal de Apple Music para terminal. Cider reproduce; amui aporta
MPRIS, controles, portadas, CAVA, letras, temas y navegación musical. Sigue
usando Python estándar y un ejecutable para todas las terminales compatibles.

## Entrega actual

Las seis propuestas de `PROPUESTAS.md` están implementadas:

1. Entrar en álbumes/playlists, paginar y elegir canciones (`b`).
2. Navegar y saltar en cola; eliminar selección o vaciar pendientes con
   confirmación y protección de historial/canción actual (`Q`).
3. Favorito real confirmado (`H`) y añadir a biblioteca (`A`).
4. Avisos de escritorio opcionales, desactivados por defecto.
5. Temporizador de pausa de 15/30/45/60 minutos o fin de canción (`Z`).
6. Estado JSON y controles sin interfaz (`--status/--next/--prev/--toggle`).

Para favoritos, instalar el complemento incluido con
`amui --install-cider-plugin` y activarlo en Cider → Settings → Plugins.
La activación es necesaria; reiniciar Cider no basta. Los demás controles
siguen usando MPRIS o la API local autenticada según corresponda.

## Estabilidad y auditoría

Se conservan las reparaciones de volumen, shuffle, portadas y Unicode; el
lanzador opcional `amui-kitty` cambia la fuente solo para su ventana.
La v0.5.5 recupera metadatos MPRIS vacíos desde la instancia verificada de Cider.
El usuario informó que el fallo de playlist ya no reaparece en la última versión;
no se considera reproducido un nuevo fallo completo de reproducción.

La auditoría de v0.5.6 cancela controles de otra sesión, limita reintentos de
portadas fallidas y evita recalcular fades terminados. No inventa una canción
con los flags residuales que Cider conserva cuando no hay pista cargada.
La revisión de requisitos, pruebas y límites está en
[docs/AUDIT-v0.5.6.md](docs/AUDIT-v0.5.6.md).
Las 129 pruebas pasan; también se verificó una instalación completa en prefijo temporal.

## Estructura

```text
bin/amui                    interfaz y controles
bin/amui-kitty              lanzador opcional, configuración aislada
lib/amui/features.py        configuración e integraciones
lib/amui/services.py        temporizador y notificaciones ligeras
share/amui/                 ejemplo, lanzador y complemento Cider
docs/                       configuración y auditoría
tests/                      unitarias, HTTP, JavaScript y teclado PTY
legacy/                     versiones anteriores conservadas
```

## Instalación y publicación

`make check` verifica; `make install` actualiza la instalación local sin tocar
preferencias, tokens, cachés ni configuración global de Kitty. Si ya existe
configuración, no vuelvas a crearla: las nuevas opciones tienen predeterminados.
Repositorio privado: [EchoLenn/amui](https://github.com/EchoLenn/amui).
No se incluyen secretos ni datos personales de reproducción en el repositorio.
