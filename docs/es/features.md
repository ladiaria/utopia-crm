# Utopia - CRM

## Propósito y principales funcionalidades

CRM y ERP para el diario *la diaria*.

*la diaria* (ladiaria.uy) es un diario por suscripción de la Cooperativa la diaria que se edita de lunes a sábado en Montevideo y se distribuye a todo el Uruguay.

Este Sistema trata de modelar todos los procesos que se realizan para la venta de las suscripciones del diario y la entrega del mismo en cada casa de cada suscriptor.

Además contiene funcionalidades extra para realizar lo mismo con otro producto de la Cooperativa la diaria, una revista mensual llamada *Lento* (lento.uy) así como también interoperar con el sitio web del diario para poder realizar tareas de sincronización de datos de suscriptores y la gestión de facturación y activación de cuentas para las suscripciones realizadas de forma on-line desde el sitio web.

A continuación se enumeran las principales funcionalidades del Sistema:

### 1. Alta masiva de contactos

 A partir de planillas en formato CSV con los datos personales de posibles clientes, el Sistema permite una importación masiva haciendo un control de duplicados basándose en los campos de teléfono.

### 2. Supervisión de venta

 Los usuarios supervisores pueden asignar clientes de forma masiva a los usuarios vendedores para que los mismos se encarguen del proceso de venta de la suscripción.

### 3. Consola de promoción y venta

 En la consola de venta, los usuarios vendedores pueden ver los posibles clientes que tienen para contactar, agrupados por tipo de promoción y acceder a una ventana con botones de *click-to-call* y *Anterior, Siguiente* para llamarlos y registrar si los mismos aceptan recibir una promoción o acceden directamente a ser suscriptores.

### 4. Gestión de promociones

 El Sistema posibilita a que un potencial cliente pueda recibir el producto por un lapso de 3 días y luego el vendedor asignado pueda consultarlo en la consola de promoción y venta para ofrecerle la suscripción y pasar a ser un cliente.

### 5. Facturación

 Interfaces de usuario para la facturación masiva de clientes en base a cada forma de pago que los mismos puedan tener asignada, empresa de pagos, efectivo, débito bancario o tarjeta de crédito. El Sistema genera facturas que también son descargables de forma concatenada en formato PDF para su posterior impresión.

### 6. Distribución

 En base a los clientes suscriptos, el Sistema indica a los operadores de distribución cuántos ejemplares del diario se necesita imprimir para satisfacer la demanda, genera etiquetas para cada uno de ellos y hojas de ruta para la distribución en las diferentes particiones geográficas del territorio, llamadas rutas.

### 7. Mapa de rutas y suscriptores

 El sistema tiene la capacidad de asociar cada cliente con una dirección georeferenciada, esto posibilita que también con una interfaz del sistema, se pueda obtener en pantalla un mapa donde se ven las rutas (particiones geográficas del territorio) con sus clientes asociados.

### 8. Gestión de Reclamos

 Soporte para la gestión de reclamos de los clientes, registro de reclamos de diversos tipos: no llegó el diario, llegó mojado, etc.

### 9. Gestión de cobranza

 El Sistema brinda listados de facturas por cliente y permite generar "Gestiones" (incidencias de casos de facturación) y asignárselas a algún gestor (usuario del Sistema) para que analice el caso.

### 10. Gestión de morosidad

 Reportes de deuda y gráficas según años, planes de suscripción y actividad de los clientes.

### 11. Reportes

 El Sistema puede exportar a CSV una amplia cantidad de consultas que a lo largo del tiempo los usuarios han demandado. A su vez también puede guardar un histórico de valores de estas tablas para poder a futuro por ejemplo graficar la evolución de los indicadores.

## Sitio Administrativo

## Sitio de suscripciones

* TODO: Listar cada modelo.
