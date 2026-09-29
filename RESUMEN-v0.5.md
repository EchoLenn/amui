# amui v0.5.1 — implementación y reparación

Fecha: 29 de septiembre de 2026.

## Funciones entregadas

- T: carátula, temas fijos, tema personalizado y Pywal.
- Carátula: extracción de colores, complementarios y contrastantes.
- Tema personalizado: elección de temas TOML o editor de siete colores, con guardado de los hexadecimales originales.
- Pywal: lectura de colors.json y actualización cada dos segundos.
- Selección de apariencia persistente, con prioridad para cambios manuales de configuración y argumentos CLI.
- b: buscar canciones, álbumes y playlists en el catálogo y la biblioteca de Apple Music.
- Enter: buscar al editar, reproducir al navegar resultados; + añade al final, n añade a continuación.
- N: más resultados, conservando los anteriores y la selección.

## Correcciones respecto al resumen anterior

El borrado de legacy no era necesario: ambos respaldos fueron restaurados y coinciden con Git.
El tema personal ya no reemplaza otro tema personalizado elegido explícitamente.
La biblioteca consultada pertenece a Apple Music; no es un explorador de archivos locales.
Aurora está en el ejemplo TOML, no entre los ocho temas integrados.
La vista musical se cierra con Esc; b también cierra cuando se navegan resultados,
pero es texto normal al editar una consulta.
Las respuestas exitosas de la API confirman el envío de una orden; no se presentan
como prueba de reproducción efectiva de contenido bloqueado por región o suscripción.

## Verificación

55 pruebas aprobadas, incluyendo HTTP local, terminal PTY, errores,
persistencia, editor, modos de color y paginación acumulativa.
Consultas reales verificadas en Cider autenticado: catálogo México y biblioteca,
con canciones, álbumes, playlists y páginas siguientes.
La reproducción y las órdenes de cola se verificaron mediante servidor de prueba
y teclado PTY, sin reemplazar la cola personal del usuario.

El documento original externo de Antigravity se conserva sin editar.
Consulta README.md y docs/CONFIGURATION.md para instalación y uso.
