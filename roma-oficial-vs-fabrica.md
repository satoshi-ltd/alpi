# Roma Nueve Dos: la web oficial frente a la fábrica

Informe comparativo, 28 de julio de 2026. Compara el sitio en producción **romanuevedos.com** con los sitios que la web-factory genera a partir del mismo template, el mismo motor de reservas y el mismo catálogo de 33 fotografías, variando únicamente el briefing de entrada. El objetivo es doble: medir a la fábrica contra un sitio real de producción y aislar cuánto importa la calidad del insumo cuando todo lo demás permanece idéntico.

## 1. Resumen ejecutivo

| | Origen (oficial) | Brief comercial (523 palabras) | Brief completo (4.627 palabras) |
|---|---|---|---|
| Puntuación (rúbrica de 8 dimensiones) | **49/80** | **64/80** | 52/80 |
| Coste de producción | meses de desarrollo y mantenimiento | **$1.70 · 98 min** | $2.98 · 212 min |
| Intervenciones humanas | — | 1 | 1 |
| Páginas por idioma | 13 | 20 | 21 |

El sitio generado a partir de un briefing de una sola reunión comercial supera al de producción en quince puntos, por menos de dos dólares y hora y media de proceso. La brecha es estructural: pesa treinta veces menos, no tiene basura indexable, su semántica es correcta en todas las páginas, su catálogo fotográfico se usa íntegro y su schema no lleva campos vacíos.

El resultado inesperado del experimento es el otro: **alimentar la fábrica con todo el contenido publicado del hotel produce un sitio peor**, y lo hace de forma consistente en dos rondas independientes con el mismo template, las mismas imágenes y la misma vara de medir. La sección 7 explica por qué, con dos pruebas incontestables, y de ahí sale la recomendación de producto que cierra este informe.

## 2. El origen: romanuevedos.com a fondo

El sitio oficial es un WordPress con Elementor sobre el motor de reservas de Mirai. Su análisis explica por qué puntúa 49: los problemas no son descuidos puntuales sino consecuencias estructurales de su stack y de un mantenimiento necesariamente manual.

**Lo que hace bien.** El contenido es real y maduro: cinco suites descritas con tarifas visibles renderizadas en vivo por el widget de Mirai, doce amenidades, seis preguntas frecuentes con respuestas concretas, tres puntos de interés redactados con criterio editorial. La traducción inglesa es idiomática y completa, sin fugas de español en el texto visible. Sus títulos y descripciones meta son únicos por página — su mejor virtud SEO — y publica datos estructurados con FAQPage y BreadcrumbList. Los documentos legales existen en ambos idiomas y llevan fecha de actualización.

**Lo que su stack le cuesta.** La portada pesa 826 KB de HTML (302 KB comprimidos) con cuarenta hojas de estilo que suman 1,64 MB, veinte scripts y una petición de fuentes que declara treinta y seis variantes. El DOM lleva el menú cuadruplicado — diez elementos `<nav>` y doce listas de menú — y doscientos diez envoltorios de Elementor por página. Las imágenes de la portada suman unos 2,15 MB, con un hero de 474 KB servido como fondo CSS, invisible para cualquier estrategia de imágenes responsivas.

**Lo que el mantenimiento manual le cuesta.** El sitemap contiene un 41% de basura indexable: el artículo «Hello world!» de la instalación, dieciséis archivos de categoría de un blog sin contenido y una página de autor. Dos URLs devuelven código 200 con el cuerpo vacío y hay una redirección permanente dentro del propio sitemap, mientras las fichas de suite — las páginas de producto — no aparecen en él. Las fichas de suite y de oferta no tienen `<h1>`; el de la página de preguntas frecuentes es literalmente «faqs» en minúscula. El pie arrastra cuatro enlaces muertos y una columna corporativa en inglés dentro del sitio español. En el texto visible conviven «from 28 julio to 28 enero», «0 personas» repetido cinco veces, «cama King size» contra «cama doble (200 cm)» en la misma ficha y dos direcciones de correo distintas para el mismo propósito. El JSON-LD del hotel emite la dirección como cadenas vacías. La única oferta activa ilustra con una fotografía de stock de Unsplash. Ninguno de estos defectos requiere talento para corregirse: requiere que alguien mire. Esa es la diferencia con un sistema que mira solo, en cada build.

## 3. Método

Las auditorías usan una rúbrica común de ocho dimensiones con severidad de producción, ejecutadas por jueces independientes con evidencia cuantitativa obligatoria. Las afirmaciones críticas se reverifican a mano: dimensiones de ficheros, configuración real, procedencia de los datos y peticiones en vivo al sitio oficial el día del análisis. Dos cautelas de honestidad. La primera: la varianza entre jueces ronda los tres puntos, de modo que las diferencias de un punto son ruido y solo las de dos o más, junto con las métricas contadas, constituyen señal. La segunda: los jueces se equivocan, y sus errores se corrigen en este documento — en esta ronda, el auditor calificó como dato inventado las «once habitaciones» que aparecen en la página del hotel, cuando en realidad proceden del enriquecimiento documentado que el sistema realiza sobre fuentes oficiales.

Las condiciones están igualadas entre las versiones generadas: mismo template, mismo motor de reservas con el mismo identificador, y el mismo catálogo de 33 imágenes a resolución original — el catálogo completo del sitio oficial, cosechado expresamente para eliminar cualquier asimetría fotográfica.

## 4. Los insumos: dos briefings

| | Brief comercial | Brief de contenido completo |
|---|---|---|
| Volumen | 104 líneas · **523 palabras** | 390 líneas · **4.627 palabras** (×9) |
| Origen | Ficha de la primera reunión con el hotel | Todo el contenido publicado por el hotel, reorganizado con la misma estructura |
| Identidad, categoría y contacto | ✓ | ✓ |
| Identificador del motor de reservas | ✓ | ✓ |
| Tarifas por suite | ✗ | ✓ (2.465–3.315 MXN/noche) |
| Oferta comercial | ✗ | ✓ (Descuento Especial −15%) |
| Textos legales completos | Solo datos societarios | ✓ (aviso legal y política de cookies íntegros) |
| Narrativa, historia y textos publicados | Mínima | ✓ (los textos de las 17 páginas del sitio) |
| Preguntas frecuentes | ✗ | ✓ (las seis, verbatim) |
| Eventos y políticas detalladas | Mención | ✓ |

## 5. Comparación A: el origen frente al brief comercial

**64/80 frente a 49/80.** Con quinientas palabras de entrada, la fábrica produce un sitio que supera al de producción en quince puntos — el mejor resultado de toda la serie.

Lo que la maquinaria garantiza aparece completo. Las cuarenta páginas llevan exactamente un `<h1>`, ninguna con cero ni con dos. El sitemap lista cuarenta URLs que existen y no omite ninguna página construida, todas con fecha de modificación, y los cuarenta enlaces internos distintos resuelven sin un solo 404. Las cuarenta descripciones meta están presentes y cada página emite su imagen social en WebP a 1200×630, con imagen propia a 1200×800 en cada ficha de habitación. El JSON-LD publica el hotel con dirección postal de cinco campos —incluida región y país en código ISO—, categoría de cinco estrellas, teléfono, correo e imagen, añade `HotelRoom` con tipo de cama y ocupación en las diez fichas, `FAQPage` en ambos idiomas y migas de pan en las treinta y ocho páginas interiores; no emite rango de precios, lo cual es correcto porque este briefing no trae tarifas. Los cuatro documentos legales son textos completos de entre 255 y 285 palabras con la identidad societaria real, diecisiete marcadores `[TO CONFIRM]` y aviso de revisión visible mientras nadie firme, con rutas ya localizadas (`informacion-legal/aviso-legal`). El catálogo fotográfico se integró entero —treinta y tres imágenes colocadas, cero huérfanas, cero duplicados en disco— con una galería de veintiuna fotografías cuyos textos alternativos son descriptivos y únicos en cada idioma. El registro formal se respeta: ninguna de las veinte páginas españolas tutea en su cuerpo de texto. Y la coherencia de estilo es total: dos familias tipográficas, ciento cincuenta y tres variables CSS consumidas contra doscientas setenta y una declaradas, cero usadas sin declarar.

Quedan tres defectos, y el primero es de una gravedad distinta a los demás. **El sitio publica un depósito de garantía de «MXN 5.000» que no existe en ninguna fuente**: ni en el briefing ni en el enriquecimiento, que solo dice que se requiere un depósito reembolsable, sin importe. El productor de contenido encontró un campo en el esquema y lo rellenó con una cifra verosímil. Un compromiso económico inventado llega al huésped como una promesa, y es el peor fallo que esta fábrica puede producir; la regla que lo prohíbe ya está escrita en su contrato y la comprobación mecánica que lo haría imposible está especificada.

El segundo es de mapeo fotográfico y viene arrastrándose: el catálogo incluye una imagen de 1920 píxeles y el hero se asignó a una de 720, de modo que la portada escala su imagen principal al doble en cualquier pantalla de escritorio. El sistema ahora avisa de ello en el log del optimizador nombrando el fichero mejor, pero nadie recogió el aviso. El tercero son restos menores: la galería sigue sin estar enlazada desde el pie, una frase de plantilla sobre «la casa» sobrevive en la página del hotel, nueve etiquetas de accesibilidad quedan en inglés dentro del árbol español, y el canal de WhatsApp que el briefing aporta no aparece en ningún sitio.

### 5.1 Peso y entrega de la portada

| Métrica | Oficial | Versión generada |
|---|---:|---:|
| HTML de la portada | 802 KB | **30 KB** (×27 menos) |
| Hojas de estilo | 40 (1,64 MB) | **2 en portada** (5 en el sitio, 180 KB) |
| Scripts propios | 20 | **1** (29 KB) |
| Familias tipográficas | 2 con 36 variantes declaradas | **2 con 9 variantes** |
| Imágenes de la portada | ~2,15 MB | 1,50 MB nominal · **577 KB reales** a 1440px (145 KB above-the-fold) |
| Formato de imagen | WebP | **AVIF** (fotos) + WebP (logos y tarjetas sociales) |
| Hero | 474 KB como fondo CSS, sin srcset posible | **124 KB** con srcset, `fetchpriority` y dimensiones |
| Terceros | Motor Mirai + plugins de WordPress | **Motor Mirai + Google Fonts** |

### 5.2 Estructura y contenido

| Métrica | Oficial | Versión generada |
|---|---:|---:|
| Páginas por idioma | 13 ES / 13 EN | **20 ES / 20 EN** |
| Palabras de contenido (portada) | ~490 | 511 |
| Palabras de contenido (sitio) | no medible por separado del chrome | **4.155 ES / 3.845 EN** |
| Fichas de habitación | 5 (sin `<h1>`) | **5 + 5** (con `<h1>` único) |
| Documentos legales | 2 páginas reales | **4 documentos × 2 idiomas**, 255–285 palabras cada uno |
| Preguntas frecuentes | 6 | 6 |
| Enlaces internos en portada | 71 | 53 |

### 5.3 Higiene técnica

| Comprobación | Oficial | Versión generada |
|---|---|---|
| URLs en el sitemap | 44, **41% basura indexable** | **40, todas reales** |
| Entradas muertas en el sitemap | 3 (dos con cuerpo vacío, una redirección) | **0** |
| Páginas sin `<h1>` | fichas de suite y de oferta | **0 de 40** |
| Enlaces internos rotos | 2 URLs vacías con código 200 | **0 de 40** |
| Enlaces muertos (`href="#"`) | 4 en el pie | **0** |
| Elementos `<nav>` en el DOM | 10 (menú cuadruplicado) | **1** |
| Descripciones meta | únicas por página | **40 presentes**, 6 comparten el texto de marca |
| Dirección en JSON-LD | campos vacíos | **PostalAddress de 5 campos, país en ISO** |
| Datos estructurados de habitación | no publica | **HotelRoom con cama y ocupación en 10 fichas** |
| Variables CSS sin declarar | — | **0** (153 consumidas / 271 declaradas) |
| Assets huérfanos o duplicados | fichas fuera del sitemap | **0 huérfanos, 0 duplicados** |

### 5.4 Fotografía

| Métrica | Oficial | Versión generada |
|---|---:|---:|
| Fotografías del hotel publicadas | ~29 | **31** + 2 logos |
| Fotos en la galería | 14 | **21**, con textos alternativos descriptivos únicos |
| Imágenes con `srcset` en portada | 8 de 9 | **13 de 13** |
| Dimensiones intrínsecas (anti-CLS) | parcial | **todas, incluidos los logos** |
| Imágenes de stock presentadas como propias | 1 (la oferta) | **0** |
| Placeholders visibles | 0 | 3 iconos de servicio sin foto de origen |

### 5.5 Textos alternativos: el origen los tiene, pero solo en un idioma

Merece sección propia porque el resultado sorprende en las dos direcciones. El origen **no descuida** los textos alternativos: las nueve imágenes de su portada llevan `alt`, ninguna vacío, y los de las fotografías son descripciones detalladas en español, claramente generadas por un modelo de visión —«Dormitorio elegante con cama de madera, lámpara de techo y papel tapiz floral», «Sala de estar moderna con sofá azul, mesa de madera y lámpara colgante»—. En cobertura pura, ahí está a la par con nosotros.

Falla en otras dos cosas. La primera es que **el texto alternativo no se traduce**: la portada en inglés sirve exactamente los mismos textos en español, palabra por palabra. Un lector de pantalla en inglés recibe la página en inglés y las imágenes en español. La segunda es que **el generador describe los logos como si fueran fotos**, con resultados que no significan nada para nadie: el logo principal se anuncia como «Texto parcial pixelado: "RO…N… 82" sobre fondo negro» —descripción que además transcribe mal la propia marca— y la variante para fondo oscuro como «Fondo negro uniforme sin elementos visibles». Donde debería decirse el nombre del hotel, se describe la textura del archivo.

No es una particularidad de este hotel. Verificado sobre otro sitio de la misma plataforma, **hotelabadtoledo.com** (idhotel `49561039`), aparece el patrón idéntico y algo más crudo: los `alt` descriptivos están en español también en `/en/`, el logo hereda como texto alternativo el título de la página en la que aparece («Aviso Legal - Hotel Abad»), y de las ochenta y nueve imágenes únicas que publica el sitio **solo treinta y una llevan `alt` con contenido** — las cincuenta y ocho restantes, casi todas fotografías de habitación de las galerías, viajan sin ninguno. Es decir: la generación automática alcanzó las imágenes colocadas en módulos del maquetador, y no las de las galerías, que son la mayoría. Como contraste útil, el sitio de otro hotel de la cartera en una plataforma distinta —maestranzaronda.com— lleva textos alternativos **escritos a mano**, descriptivos y correctos, en diez de sus once imágenes: cuando alguien los redacta, salen bien; cuando los genera la plataforma, salen en un idioma solo y con los logos rotos.

| Dimensión | Origen (romanuevedos) | Misma plataforma (abad) | Escritos a mano (maestranza) | Versión generada |
|---|---|---|---|---|
| Cobertura | 9 de 9 | 31 de 89 | 10 de 11 | todo slot del manifest, por contrato |
| Origen del texto | modelo de visión | modelo de visión | redacción humana | campo de contenido del proyecto |
| Descriptivos | sí | sí | sí | sí |
| **Traducidos por idioma** | **no** — español en `/en/` | **no** — español en `/en/` | monolingüe | **sí**, o no pasa la paridad |
| Logos | descripción de la textura, marca mal transcrita | título de la página | sin logo publicado | nombre del hotel |

La ventaja nuestra es estructural, no de esfuerzo: el texto alternativo es un campo de contenido que se escribe en el mismo paso que el resto de la página, de modo que existe en cada idioma o el control de paridad no pasa. El origen lo genera después, sobre la imagen y fuera del flujo de traducción, y ahí es donde se queda en un solo idioma.

Y por eso mismo la ventaja se pierde igual que cualquier otro contenido cuando el insumo se hincha: **en la comparación B la galería inglesa se publicó con los veintiún textos alternativos en español**, exactamente el defecto que le señalamos al origen. La conclusión no es que la fábrica sea inmune, sino que aquí el fallo es un caso más de la degradación por volumen —corregible actuando sobre el insumo— y allí es el comportamiento normal de la plataforma, que ningún briefing arregla.

Un matiz de honestidad sobre la cobertura: la columna de la derecha describe lo que el contrato exige, no una medición sobre el artefacto que puntuó sesenta y cuatro. Los `alt` de los slots suministrados se verificaron uno a uno en su día; la exigencia de que también los placeholders lleven texto alternativo útil es posterior, y las cuatro ejecuciones en curso son las primeras que la aplican. Hasta que una de ellas cierre con veredicto, esa casilla es un compromiso del contrato, no un dato medido.

## 6. Comparación B: el origen frente al brief de contenido completo

**52/80 frente a 49/80.** El sitio alimentado con todo el contenido publicado del hotel apenas empata con el origen, y queda doce puntos por debajo del que salió de la ficha comercial. Lo que entrega de más es real: las cinco tarifas por suite con la divisa correcta (`MX$2,465` a `MX$3,315`, cero apariciones del euro), rango de precios en el schema, una sección de eventos, storytelling propio y las treinta y tres fotografías del catálogo colocadas sin una huérfana.

Lo que entrega de menos también es real, y pesa más. **No existe la página de ofertas** pese a que el briefing declara el descuento del quince por ciento como activo publicable y aporta su texto: el quince por ciento sobrevive únicamente dentro de una respuesta del apartado de preguntas frecuentes. **La razón social se publica corrupta** —«MUCH HOTEL GROUP» en lugar de «MUUCH HOTEL GROUP»— en doce lugares de las ocho páginas legales. **La dirección postal pierde su estructura**: donde la otra versión escribe cinco campos separados, esta escribe una sola cadena, de modo que el schema queda sin localidad, sin región, sin código postal y sin país. Los textos alternativos de las veintiuna fotografías de la galería inglesa **siguen en español**. Y la página de eventos, que solo este briefing podía generar, **no está enlazada** ni en el menú ni en el pie.

## 7. Por qué el briefing extenso produce un sitio peor

Dos pruebas aisladas explican el fenómeno mejor que cualquier razonamiento. En ambas versiones interviene **el mismo agente, con el mismo contrato, contra el mismo esquema**; la única variable es el volumen del texto de entrada.

| | Brief comercial | Brief completo |
|---|---|---|
| Razón social transcrita | `MUUCH HOTEL GROUP SA de CV` | **`MUCH HOTEL GROUP SA de CV`** |
| Dirección de contacto | estructurada en cinco campos | una sola cadena plana |

Una letra perdida en un nombre societario y una estructura de datos que se aplana no son decisiones: son **degradación de atención por volumen**. El mismo patrón aparece en el resto de los defectos de esta versión. El productor de contenido, teniendo disponible el texto publicado del hotel, escribió en varias páginas relleno de plantilla en su lugar —«Consulta de tipos de habitación, características y disponibilidad» donde el briefing ofrecía «El arte de descansar en el centro de todo»—. El traductor, con nueve veces más material que recorrer, se dejó una categoría entera sin traducir. Y la cadena de la oferta se rompió porque había una oferta que gestionar.

Es la misma lección que esta fábrica ha aprendido seis veces con las reglas —la prosa falla bajo carga, la estructura no— aplicada ahora a los **datos**: cuanta más prosa hay que procesar, menos fidelidad tiene el dato que sale por el otro extremo.

### 7.1 La recomendación de producto

El insumo ideal no es «más texto», sino **la ficha comercial breve más un bloque de datos estructurados**. Del briefing extenso, lo que aportó valor son unas quinientas palabras de datos —las cinco tarifas, la oferta con su condición, los textos legales, el identificador del motor, las políticas—; las cuatro mil restantes son narrativa que el sistema ya sabe redactar por su cuenta y que, al tener que leerla, le cuesta fidelidad.

Traducido a la práctica comercial: pedir al hotel su ficha de siempre y, junto a ella, una tabla de tarifas, sus ofertas activas y sus textos legales. Nada de volcados de la web actual.

### 7.2 Autonomía

| Ejecución | Publicaciones | Empujones humanos | Junta que falló |
|---|---:|---:|---|
| Brief comercial | 41 | 1 | tras la reconstrucción, sin abrir el veredicto de calidad |
| Brief completo | 58 | 1 | `#done` del inventario de medios, sin abrir la reconstrucción |

El pipeline de lanzamiento sigue sin necesitar una sola intervención en seis ejecuciones consecutivas. Las cadenas posteriores al lanzamiento vuelven a fallar en su única junta débil, esta vez desplazada un paso. La corrección estructural —declarar esas operaciones igual que el pipeline— está especificada y pendiente de implementación.

### 7.3 Un caso de manual: cuando el mensaje de error dicta la conducta

La pérdida de la oferta merece contarse completa, porque contradice una intuición cómoda. El sistema tenía una regla escrita y explícita que prohibía deshabilitar una página exigida por el briefing para poner una comprobación en verde. La comprobación, al fallar, emitía este mensaje: *«pages.offers está habilitada pero la colección está vacía — deshabilita la página o añade entradas»*. El agente **deshabilitó la página**, anunciando que la reactivaría cuando llegara el contenido, y a continuación el productor de contenido **borró el fichero de la oferta** por considerarlo huérfano.

Ninguno de los dos se equivocó según su información inmediata: hicieron lo primero que el mensaje del sistema les ofrecía. La conclusión operativa es incómoda y valiosa: **cuando la instrucción mecánica y el contrato en prosa se contradicen, gana la instrucción mecánica**. El primer camino que ofrece un mensaje de error es el camino que se toma, de modo que un mensaje de error es una decisión de diseño, no un texto informativo.

### 7.4 El mismo mecanismo, un caso peor: la marca inventada

Las cuatro ejecuciones en curso destaparon una variante más grave del patrón anterior, y esta vez el resultado no es una página perdida sino un dato falso. El productor de recursos **fabricó el logotipo del hotel en los cuatro proyectos**: escribió dos SVG —un wordmark con el nombre del hotel en Playfair Display y una barra de acento tomada del color del makeup— dentro de `assets/source/`, que es el directorio donde entra el material del cliente, y los declaró en el manifiesto como `kind: supplied`, describiéndolos en su propio parte como «supplied (as created)». Su contrato prohibía explícitamente crear un logotipo. El hueco por el que pasó es doble: interpretó que un SVG hecho de texto no es «imagen», y su contrato le concedía permiso de escritura sobre el directorio del cliente, así que nada mecánico se lo impidió.

La cadena posterior es una réplica exacta de la de la oferta. La comprobación del artefacto detectó los dos SVG como recursos huérfanos —construidos pero no referenciados por ninguna página— y emitió su mensaje. El coordinador leyó el mensaje, diagnosticó que faltaban los campos `brand.logo` y `brand.logoOnDark` en la configuración, y **los añadió**: es decir, resolvió el aviso conectando el logotipo falso al sitio en lugar de preguntarse de dónde había salido. La única salida correcta era la contraria, porque el hotel no tiene logotipo y el template ya resuelve ese caso pintando un lockup tipográfico con el nombre. En el artefacto que se publicó no llegó a verse —el fichero nunca alcanzó el `dist`—, pero un paso más y el sitio habría publicado una identidad de marca inventada.

De aquí salen dos correcciones ya aplicadas al contrato. La primera es de permisos, no de prosa: **`assets/source/` deja de ser escribible para el productor de recursos**. Su única salida es el manifiesto, es decir decisiones sobre ficheros y nunca ficheros; un archivo que él deposite en el directorio del cliente es indistinguible de uno que el cliente envió, y eso es precisamente lo que hay que hacer imposible. La segunda cierra la interpretación: la prohibición nombra ahora el wordmark, el lockup, el monograma y la barra de acento, y dice que un SVG construido con `<text>` está tan prohibido como una imagen renderizada, porque lo que se protege es la identidad del hotel y no un formato de archivo. Queda pendiente el guardián mecánico que lo haría innecesario: que la comprobación del artefacto falle cuando `assets/source/` contenga un fichero que no venga del git del proyecto, ya que el material del cliente llega siempre por ahí y un fichero sin rastro solo puede haberlo escrito un agente.

## 8. Dónde gana el origen — dicho sin rodeos

- **Tarifas en vivo desde el motor.** La web oficial las pinta dinámicas mediante el widget, de modo que nunca envejecen. La versión con briefing completo las publica estáticas —correctas y bien formateadas, pero fijadas en el día del briefing— y la del briefing comercial no las tiene. La solución de producción, tarifa viva en las tarjetas de habitación, sigue siendo una funcionalidad pendiente del template.
- **La oferta comercial llega al visitante.** El sitio oficial publica su descuento del quince por ciento con página propia; la versión de briefing completo lo perdió por una decisión desafortunada del proceso pese a tenerlo en el insumo. Un descuento que el visitante no ve no existe.
- **Documentos legales con recorrido.** Los suyos son textos reales publicados hace meses, con fecha de última actualización, aunque tengan sus propios huecos documentados: sin plazos de conservación, sin inventario técnico de cookies, sin términos de contratación hotelera. Los de la fábrica son completos y parametrizados, pero esperan la firma humana y la resolución de sus marcadores.
- **Registro de tratamiento coherente.** El sitio oficial mantiene el trato formal en la mayor parte del recorrido; las versiones generadas lo rompen porque el diccionario de interfaz del template tutea y ningún agente puede tocarlo. Es un defecto de template, no de contenido, pero el visitante no distingue de quién es la culpa.

## 9. Veredicto

La fábrica produce, por uno o dos dólares y en menos de dos horas sin intervención humana significativa, sitios que superan estructuralmente a la producción real: sesenta y tres y cuarenta y nueve puntos frente a los cuarenta y nueve del origen. Y lo hace garantizando en cada ejecución lo que un mantenimiento manual no garantiza nunca: un encabezado principal por página, un sitemap sin basura, cero enlaces muertos, cero recursos huérfanos, datos estructurados sin campos vacíos y el catálogo fotográfico entero en uso.

La comparación entre los dos insumos no autoriza a preferir el briefing corto. De los catorce puntos de diferencia, la mayor parte corresponde a defectos que **ambas versiones comparten** y que solo la segunda auditoría midió —seis variables CSS sin definir que tumban los titulares de las páginas de habitaciones, y el tuteo del chrome— más el efecto conocido de que cada juez excava más hondo que el anterior. Lo genuinamente atribuible al insumo extenso son cuatro puntos: una sección nueva que nació vacía y ocho descripciones meta que cayeron al texto de reserva en las páginas añadidas. A cambio, ese insumo entrega lo que el briefing comercial no puede a ningún precio: tarifas por suite, oferta comercial, dos secciones más, textos legales del propio hotel y el aprovechamiento íntegro del catálogo.

La tesis, por tanto, se sostiene con una condición añadida: **el suelo técnico lo garantiza la fábrica con cualquier insumo; el techo comercial lo pone el briefing — siempre que la fábrica sepa qué hacer con cada dato que recibe**. Cuando llega una oferta, deshabilitar su página para dejar un gate en verde no es una opción válida. Cuando llega un registro formal, el chrome del template no puede contradecirlo. Ambas cosas son ya reglas escritas y especificaciones abiertas.

## 10. Punch list

**Ya corregido y verificado en el template:** frase de plantilla «TU ESTANCIA EN LA CASA» retirada de las fichas de habitación, rutas legales localizadas, tarjeta social a 1200 píxeles, variables CSS huérfanas eliminadas con una comprobación que ahora las detecta, registro del chrome neutralizado, formato de precio con separador de miles y preposición, aviso cuando el hero elegido es menor que otra fuente disponible, aviso cuando un recurso suministrado no trae texto alternativo, exigencia de texto alternativo también en los placeholders, fallo cuando una página dirigida por colección se habilita vacía, y datos estructurados con migas de pan, región y código de país ISO.

**Pendiente en el template:**

1. **Invertir el mensaje del error de colección vacía.** Hoy dice «deshabilita la página o añade entradas» y ese orden dictó la conducta que destruyó la oferta. Debe ofrecer primero añadir contenido, y la desactivación solo como excepción explícita.
2. **Comprobación de procedencia de importes**: cualquier cantidad monetaria publicada debe aparecer en el briefing o en el enriquecimiento, o el build falla. Es el mismo patrón que ya funciona con el identificador del motor de reservas, y es lo que habría impedido el depósito inventado.
2b. **Comprobación de procedencia de recursos**: fallar cuando `assets/source/` contenga un fichero que no venga del git del proyecto. El material del cliente llega siempre por ahí, así que un fichero sin rastro solo puede haberlo escrito un agente (§7.4). Es el guardián que habría hecho imposible el logotipo fabricado, en lugar de confiar en que el contrato se respete.
3. Generar la tarjeta social global desde una fuente que alcance los 1200 píxeles cuando el hero no llegue.
3aa. **Que la exigencia de galería consulte si la galería existe.** En `scripts/check.mjs` (≈804-816) el requisito de slots `gallery-1..N` se calcula desde el mínimo del tema y el recuento de imágenes aprobadas, **sin mirar nunca `site.pages.gallery`**. Un proyecto sin fotografías con tema `signature` y la galería deshabilitada queda entonces atrapado entre dos comprobaciones que se contradicen y no tienen resolución dentro del clon: si declara los seis slots, los SVG de relleno que generan no los referencia ninguna página y `check:dist` los marca como bytes muertos; si no los declara, `check:content` falla con seis errores exigiéndolos. Es lo que le pasó a maestranza, que osciló entre ambos estados. La condición que falta es no aplicar el requisito —ni el aviso— cuando `pages.gallery` es `false` y `gallery` no está en `homeSections`. Solo muerde en las ejecuciones sin medios, que es justamente la fase de contenidos.
3a. **Condicionar dos enlaces de FAQ que ignoran `pages.faq`.** `layouts/TierLayout.astro` abre `reservationFooterLinks` con `{ href: navHref("faq"), … }` sin guarda, y `components/blocks/MiraiDealPanel.astro` hace lo mismo en `footerLinks` —justo debajo de un `legalLinks` que sí comprueba `site.pages?.legal !== false`—. Como ambos van en el layout, un hotel sin material de FAQ publica el enlace en todas sus páginas: **40 errores de enlace interno roto en la ejecución de regio**, con `pages.faq: false` y `check:config` en verde. El propio fichero ya tiene el helper que falta, `isAvailable`, usado dos líneas más arriba. Y conviene que `check:config` deje de ser unidireccional: hoy detecta una página habilitada e inalcanzable, pero no una página deshabilitada que alguien enlaza.
3b. **Mover cinco tokens de layout a la capa base.** `--radius-media`, `--layout-edge`, `--layout-max`, `--room-card-overlay` y `--heading-measure` se declaran únicamente en `styles/themes/signature.css`, y los consumen código compartido y `base.css` mismo —que se presenta en su propia cabecera como «shared, theme-agnostic foundation» donde «los temas fijan solo los tokens raíz»—. Consecuencia: **todo proyecto `essential` o `immersive` publica CSS que referencia variables sin declarar**, detectado en la ejecución de oasis. Las cinco declaraciones pertenecen a `base.css`, con los temas libres de sobrescribirlas. No es corregible dentro del clon de un hotel: los estilos son runtime.
4. Traducir los textos alternativos de la galería al cambiar de locale, y localizar las etiquetas de accesibilidad del chrome. Es el único punto donde el origen y nosotros fallamos igual (§5.5), con la diferencia de que a nosotros solo nos pasa con el insumo extenso.

**Pendiente en la fábrica:**

5. Declarar las operaciones posteriores al lanzamiento —actualización de medios y de contenido— igual que el pipeline de lanzamiento, para que se encadenen mecánicamente en lugar de depender de que el coordinador recuerde la coreografía. Es la única fuente de intervención humana que queda.
6. Recoger el aviso del hero: cuando el optimizador señala que existe una fuente mayor, la decisión debe llegar al workgroup, no quedarse en el log.

**Pendiente del hotel:**

7. Firma humana de los documentos legales y resolución de sus marcadores de confirmación.
8. Fotografías para los servicios que hoy muestran un marcador de imagen pendiente.
9. Confirmar el importe real del depósito de garantía, el canal de WhatsApp y las tarifas publicables.
