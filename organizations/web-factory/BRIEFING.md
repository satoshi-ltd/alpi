# Qué pedirle al hotel

Guía para quien recoge el briefing en la reunión comercial. La fábrica produce un sitio completo a partir de una ficha breve; lo que decide la calidad del resultado no es la cantidad de texto, sino que estén presentes unos pocos datos operativos. Ocho ejecuciones medidas lo confirman: una ficha de 500 palabras con los datos correctos produce mejor sitio que un volcado de 4.600 palabras sin ellos.

**Ejemplo completo**: [`briefings/hotel-maestranza/brief.md`](briefings/hotel-maestranza/brief.md). Son 495 palabras y cubre todo lo imprescindible de esta guía; sirve de plantilla tal cual, cambiando los valores. Si dudas del formato de un dato, cópialo de ahí.

## Imprescindible

Sin esto el sitio se construye, pero sale con huecos que solo el hotel puede tapar.

| Dato | Por qué |
|---|---|
| **ID de hotel del motor Mirai** | Es el dato más importante del briefing. Hoy sin él el buscador de disponibilidad se monta sin hotel y no se puede reservar; mañana será además la llave con la que la fábrica pedirá al backend de Mirai las habitaciones, sus precios mínimos y las ofertas vigentes. Si el briefing no lo trae, la fábrica lo deja vacío y lo declara como hueco: nunca se inventa. |
| **Nombre, categoría (estrellas o llaves) y dirección completa** | La categoría se copia literal: «5 llaves» nunca se convierte en estrellas. La dirección, si viene desglosada (calle, localidad, código postal, provincia, país), alimenta los datos estructurados que leen Google y las redes. |
| **Teléfono, email de reservas y dominio** | Aparecen en cabecera, pie, contacto y datos estructurados. Un solo email para reservas: si hay dos, el sitio hereda la contradicción. |
| **Idiomas del sitio** | Cada idioma se produce completo o no se produce. |
| **Datos societarios**: razón social, identificador fiscal, domicilio social, email legal | Alimentan los cuatro documentos legales. Cada carácter se transcribe tal cual, así que un nombre mal escrito en el briefing se publica mal. |
| **Tipos de habitación** con nombre, ocupación máxima y cama | Cada tipo genera su ficha. Un tipo que falte en el briefing no existe en el sitio. |
| **Horarios de entrada y salida, y política de mascotas** | Son las tres preguntas que más se hacen antes de reservar. |

## Muy recomendable

Lo que convierte un sitio correcto en un sitio que vende.

| Dato | Efecto |
|---|---|
| **Tarifas «desde» por tipo de habitación, con divisa** | Es el dato de conversión más importante: sin él las fichas no muestran precio. Envíalas si las tienes a mano — y ten en cuenta que es un dato de transición (ver «Qué cambiará pronto»), así que no merece la pena perseguirlas si el hotel tarda en darlas. |
| **Ofertas activas**: nombre, beneficio y condición | Generan su propia página y su llamada a la acción. Una oferta que no llega en el briefing no se puede inventar. |
| **Descripción del hotel en la voz del hotel** (uno o dos párrafos) | Fija el tono de todo el sitio. |
| **Tono de tratamiento**: usted o tú | Se aplica a todos los textos. Sin indicación, la fábrica imita el tono de la descripción anterior. |
| **Servicios e instalaciones**, separando los que son espacios (azotea, biblioteca, piscina) de los que son servicios (traslado, aparcamiento) | Determina qué secciones se abren y cómo se componen. |
| **Restauración**: qué hay, para quién, y si el desayuno está incluido | |
| **Tres a cinco puntos de interés cercanos** con distancia o tiempo real | La página de ubicación se construye con ellos. |
| **Cómo llegar**: aeropuerto con distancia, transporte público, si el traslado es de pago | |
| **Políticas concretas**: cancelación, depósito con su importe, niños, fumadores, eventos | Si dices que hay depósito sin importe, el sitio dirá exactamente eso: nunca pondrá una cifra que no le hayas dado. |
| **Fotografías** con nombres descriptivos (`fachada.jpg`, `suite-deluxe-terraza.jpg`) | El nombre ayuda a colocar cada foto en su sitio. Incluye una imagen apaisada de al menos 1600 píxeles de ancho para la portada, y el logo **en SVG o WebP** (en PNG el optimizador lo salta y el sitio se queda sin marca), **con el contenido en blanco sobre transparente** — la cabecera y el pie son oscuros, así que una marca en tinta oscura no se ve y el sitio cae al logotipo tipográfico. Las fotos llegan por el repositorio del proyecto, nunca dentro del briefing. |

## Qué cambiará pronto

La fábrica va a dejar de depender del briefing para las tarifas y las ofertas: llamará a un servicio del backend de Mirai pasándole el ID de hotel, y recibirá las habitaciones con su precio mínimo y las ofertas disponibles en ese momento. Tres consecuencias para la conversación con el hotel:

- **El ID de hotel gana peso**: pasa de ser la llave del buscador a ser la llave de toda la información comercial. Es el único dato del briefing que conviene confirmar por escrito.
- **Las tarifas y ofertas del briefing son transitorias**: mientras el servicio no esté, se publican tal como las envíe el hotel; cuando esté, se refrescarán solas y dejarán de envejecer. No hace falta insistir al hotel para conseguirlas.
- **Los tipos de habitación seguirán viniendo del briefing** como fuente editorial —nombre, descripción, qué los diferencia—, y el servicio aportará el precio de cada uno. Conviene que los nombres del briefing coincidan con los del motor para que se emparejen sin ambigüedad.

## Opcional

- Fijar el estilo (`theme`: essential, signature o immersive) o la paleta con un color de marca en hexadecimal, si el hotel ya tiene identidad definida. Sin indicación, la fábrica elige según el material y lo justifica.
- Eventos: tipos, aforos, equipamiento.
- Programa de fidelización, si existe.
- Preguntas frecuentes ya redactadas.

## Cómo NO entregarlo

- **No mandes un volcado de la web actual.** Está medido: multiplica el coste por dos, el tiempo por dos, y produce un sitio peor. La narrativa la escribe la fábrica; lo que necesita de ti son los datos.
- **No mezcles varios establecimientos en un briefing.** Cada hotel es un proyecto: su ID de motor, su dirección, sus datos societarios y su sitio. Una cadena de cinco propiedades son cinco briefings.
- **No incluyas tarifas sin decir si son publicables**, ni cifras aproximadas «para rellenar»: cualquier número que entre se publica tal cual.
- **No adjuntes imágenes al documento.** Van al repositorio del proyecto.

## Qué hace la fábrica con lo que falta

Nada se inventa. Todo dato ausente se registra como hueco en el informe de admisión del proyecto, y las páginas legales marcan con `[TO CONFIRM]` exactamente lo que el hotel y su asesoría deben completar antes de publicar. Un sitio se puede construir con huecos y completarse después con una actualización de contenido; lo que no se puede es adivinar.
