# Inasistencias de vendedores - t1132

## Objetivo

Crear una herramienta que pueda contabilizar las inasistencias de los vendedores para llevar luego a utilizar contabilidad y estadísticas sobre ellos. Para ello debemos crear un modelo que permita registrar los días con inasistencias para cada vendedor.

## Pasos previos

Debemos primero agregar algunos campos nuevos a los vendedores:

- Turno (Matutino, Vespertino)
- Trabaja en call center (booleano)

Actualmente solo tienen un campo de "Es Interno" que anteriormente se utilizaba para definir si el vendedor trabajaba en el call center o era un distribuidor que podía vender por fuera, pero ahora se utiliza para cualquier vendedor e indicar si está activo. Necesitamos ser más específicos y poner cuáles exactamente trabajan en el call center, y sobre ellos se llevará un contro de asistencia o inasistencia.

## Desarrollo del modelo

El modelo ser un super modelo que permita registrar la fecha, y debería contar con relaciones hacia los vendedores que trabajan en el call center. Las relaciones con los vendedores en el call center deberían contar con lo siguiente:

- Vendedor
- Estado (Asistencia, Inasistencia)
- Motivo de inasistencia (modelo detallado más abajo)
- Inicio del turno
- Fin del turno

## Modelo de motivos de inasistencia

El modelo de motivos de inasistencia debe contener los siguientes campos:

- Nombre
- Descripción
- Justificado o injustificado (selección)
- Activo (booleano)

El método `__str__` del modelo debe retornar el nombre del motivo y si es justificado o injustificado entre paréntesis para recordar al usuario qué tipo de inasistencia es.

Más adelante las inasistencias justificadas se utilizarán para que el objetivo de días computables del vendedor sea menor, ya que se justifica su falta y se toma como que debía trabajar menos días que una persona que no tiene inasistencia justificada.

## Vista de inasistencias

La vista de inasistencias debe permitir registrar las inasistencias de los vendedores que trabajan en el call center. Esta debe ser creada con permisos para los Managers, Admins y superusers. En el menú de la izquierda deberá ir sobre "Campaign Management".

La vista debe contar con un selector de fecha. Al seleccionar la fecha, se debe mostrar una lista de vendedores que trabajan en el call center y sus estados de asistencia o inasistencia para esa fecha. Si ya hay datos se deben mostrar los datos ya guardados. Solo se deben guardar los datos que hayan cambiado y si se selecciona algo en el vendedor, porque el operador de esta vista puede entrar a ella en varios momentos del día. Se debe poder consultar asistencias e inasistencias de días anteriores también, pero no se recomienda de días futuros. Solo deberíamos permitir editar a los Admins o superusuarios.

Pensar si para marcar asistencia o inasistencia se necesita un selector o booleanos, posiblemente sea un selector. Para el motivo de inasistencia es un selector con los motivos disponibles del modelo creado anteriormente. Mostrar un mensaje de error si no se selecciona un motivo de inasistencia cuando se marca como inasistencia y mostrar un mensaje de error y no permitir guardar si no existen motivos de inasistencia creados en la base de datos. Debemos tener en cuenta que posiblemente en algún momento se borren motivos de inasistencia y hay que alertar para migrar motivos a algún otro que corresponda antes de hacer el borrado.

En la lista de los vendedores también deben estar los campos inicio de jornada y fin de jornada que estén ya predefinidos según el turno que tenga asignado el vendedor. Si es un vendedor que no tiene turno asignado, se debe mostrar un mensaje de error junto a esa línea y no permitir guardar. Los horarios que se mostrarán por ahora serán fijos: Si el vendedor es matutino, el inicio del turno es a las 9:00 y el fin a las 17:00. Si el vendedor es vespertino, el inicio del turno es a las 17:00 y el fin a las 21:00. Se debe permitir al operador de la vista cambiar estos horarios manualmente ya que es simplemente una sugerencia y el vendedor puede haber venido a otra hora. Acepto sugerencias de cómo poder controlar los horarios de estos turnos de un modo que no sea por código (por base de datos, un modelo?), pero por ahora en la empresa son los que se van a utilizar.

Solo se debe guardar la línea de vendedor y su inasistencia en caso de haber elegido el estado de asistencia o inasistencia. Por defecto este campo seleccionable debe venir vacío. En el caso de seleccionar una inasistencia se debe seleccionar el motivo de inasistencia. Para ambos casos el turno también es requerido para esa línea. No permitir guardar si el turno no está seleccionado o si el motivo de inasistencia no está seleccionado en caso de ser una inasistencia. En caso de ser una asistencia no se requiere motivo de inasistencia, ignorar este campo o te permito decidir si queremos que ese select esté desactivado y/o vacío o ambos. En el caso de que no haya seleccionado ningún estado de asistencia o inasistencia, no se deben mostrar los motivos de inasistencia tampoco.
