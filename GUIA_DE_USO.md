# Guía de uso del modelo del STN

Esta guía explica cómo utilizar el modelo y describe el funcionamiento de cada opción del menú, pregunta por pregunta.

El [README](README.md) presenta el modelo y explica el procedimiento de instalación. Esta guía parte de ese punto y se centra en el uso del menú una vez iniciado.

```bash
python menu.py
```

---

## Índice

1. [Selección del punto de operación](#1-selección-del-punto-de-operación)
2. [Navegación por el menú](#2-navegación-por-el-menú)
3. [Simular](#3-simular) — opciones 1 a 8
4. [Consultar el modelo](#4-consultar-el-modelo) — opciones 9 a 14
5. [Análisis](#5-análisis) — opciones 15 a 19
6. [Ejecución desde la línea de comandos](#6-ejecución-desde-la-línea-de-comandos)
7. [Consideraciones para interpretar los resultados](#7-consideraciones-para-interpretar-los-resultados)
8. [Problemas frecuentes](#8-problemas-frecuentes)
9. [Verificación del modelo](#9-verificación-del-modelo)

---

## 1. Selección del punto de operación

El menú no solicita en primer lugar el análisis que se desea ejecutar, sino el **sistema sobre el cual se trabajará**. Esta selección se mantiene durante toda la sesión y se muestra en una banda situada en la cabecera de las pantallas.

```text
SOBRE QUE SISTEMA QUIERES TRABAJAR
   Punto de operacion:
     * 1) punta nocturna 18-22 h  (el caso MEDIDO y validado)
       2) diurno 10-11 h  (con sol; DERIVADO de la punta, no validado)
       3) una fecha concreta  (despacho y pronostico reales de XM)
```

El asterisco (`*`) identifica la opción predeterminada. Al pulsar Enter, se selecciona la punta nocturna.

> **Nota sobre el rótulo de la punta nocturna.** El texto que imprime el menú describe la punta como «caso MEDIDO y validado». El caso procede de PowerFactory y corresponde a un **escenario de planeamiento** (estudio a 31-12-2042, etapa de expansión P20), no a una medición. En esta guía se denomina «caso de referencia» y se indica que fue contrastado contra PowerFactory.

### Diferencias en el respaldo de los puntos de operación

Los tres puntos de operación no tienen el mismo nivel de respaldo. Por esta razón, el menú identifica su procedencia y condición en cada pantalla:

| Punto | Fuente | Respaldo |
|---|---|---|
| **Punta nocturna** | Caso de flujo de carga de PowerFactory (caso de referencia, de planeamiento). | Contrastado contra PowerFactory. El menú lo rotula «MEDIDO y validado contra PowerFactory». |
| **Diurno** | Se deriva de la punta mediante factores horarios de XM. | **DERIVADO**. Hereda la validación de la red, pero no cuenta con una validación independiente del punto de operación. |
| **Una fecha concreta** | Despacho `dDEC` y pronóstico `PRON_BARRA` de XM. | **CONSTRUIDO** a partir de los datos disponibles para la fecha. Hereda la validación de la red, pero no la del punto de operación. |

Aunque los tres escenarios se procesan mediante el mismo código, su respaldo documental es diferente. Por tanto, los resultados obtenidos para el escenario diurno o para una fecha específica también dependen de la calidad y representatividad de los datos de despacho utilizados.

### Opción 1 — Punta nocturna

No requiere información adicional. Corresponde al caso de referencia entre las 18:00 y las 22:00, sin generación solar y con demanda máxima.

### Opción 2 — Diurno

Solicita seleccionar el intervalo horario:

```text
Que hora:
  * 1) 10:00-11:00 (maxima penetracion solar)
    2) 13:00-14:00
```

El primer intervalo corresponde al escenario de **máxima penetración solar** y, por tanto, al de menor inercia síncrona dentro de los escenarios diurnos considerados. Las claves horarias utilizadas por XM (`HourNN`) son 11 y 13, respectivamente.

### Opción 3 — Una fecha concreta

El menú muestra las fechas disponibles en el directorio de datos. La última entrada permite descargar una fecha adicional desde XM:

```text
Fechas en disco:
   1) 2026-09-16
   2) 2026-10-20
   3) 2026-10-21
   4) 2026-10-24
   5) otra fecha  ---  descargarla de XM ahora
```

La pregunta `cual (1-5)` tiene como valor predeterminado la última fecha disponible en disco, es decir, la entrada 4 en el ejemplo anterior, y no la entrada de descarga.

Al seleccionar la última entrada, el menú describe el procedimiento y solicita una fecha en formato `AAAA-MM-DD` (`fecha (AAAA-MM-DD)`; por defecto, el día siguiente). El modelo descarga del portal público de XM los dos archivos correspondientes a esa fecha: el **despacho programado** (`dDEC`) y el **pronóstico de demanda por barra** (`PRON_BARRA`). Ambos archivos ocupan aproximadamente 150 kB en conjunto. Estos son los únicos datos que requieren conexión a internet durante este proceso.

> **Información que no se descarga:** el directorio de PARATEC —que contiene la información de subestaciones, líneas y unidades— se toma del snapshot más reciente disponible en disco. Esto se debe a que **PARATEC no dispone de información histórica**: su API devuelve el registro vigente, independientemente de la fecha solicitada. El archivo `manifest.json` registra el snapshot utilizado como referencia. Si un recurso del despacho no figura en ese directorio, no se incorpora de forma implícita: la cobertura disminuye, y esa condición se muestra a continuación en el menú.

XM publica el despacho de un día durante la tarde anterior. Por esta razón, la fecha más reciente que se puede solicitar es el día siguiente a la fecha de publicación. Si la fecha seleccionada ya está disponible en disco, el menú informa esta condición, utiliza los archivos existentes y no realiza una nueva descarga.

A continuación, se solicita el **periodo horario** (`periodo horario (1-24; 19 es la punta)`), mediante un índice entre 1 y 24 que corresponde a las horas del día en los archivos de XM. El periodo predeterminado es el 19, correspondiente a la punta nocturna.

### Generación programada o generación real

Después de elegir la fecha, el menú pregunta **de dónde sale la generación**:

```text
Generacion de la fecha:
  * 1) despacho programado de XM (dDEC; el que se ha usado hasta ahora)
    2) generacion real medida por XM (la demanda se lleva al total real)
```

Las dos opciones no dan el mismo sistema. El **despacho programado** es lo que XM publica la víspera; la **generación real** es lo que se generó. Las diferencias pueden ser grandes: el 1-nov-2026 a las 12 h, Ituango estaba programado en 300 MW y generó 907 MW, y dos plantas a gas programadas con 358 MW no generaron. La opción predeterminada es el despacho programado, de modo que un Enter de más reproduce el caso de siempre.

Con la generación real el modelo sustituye el despacho programado por la generación medida de cada recurso (métrica `Gene` de XM) y lleva el pronóstico de demanda por barra, en cada periodo, al total de la demanda real del sistema (`DemaReal`). Todo lo demás es idéntico: la ubicación en barras, la elevación de STR a STN y las consignas de tensión. Los archivos se descargan del servicio de datos de XM la primera vez que se piden y quedan en disco. La generación real de un día suele estar disponible con un día de rezago; si todavía no está publicada, el menú lo dice y no continúa.

Tres advertencias:

- La **demanda por barra sigue siendo el pronóstico**, solo reescalado al total. XM no publica la demanda real por barra del STN.
- El listado de recursos con su tipo y combustible es el **vigente el día de la descarga**, no el de la fecha. Un recurso retirado desde entonces aparece sin combustible.
- La banda del punto de operación indica `(generacion real)` y los ficheros de salida llevan el sufijo `_real`, de modo que no pisan los del caso programado.

Desde la línea de comandos se pide con `--origen real`, por ejemplo `python -m stn.contingencias --fecha 2026-11-01 --periodo 13 --origen real`, y en `comparar_casos` con `2026-11-01:13:real`.

### Verificación de la cobertura de los datos

Una vez seleccionada la fecha, el menú construye el punto de operación y muestra los porcentajes de cobertura antes de continuar:

```text
generacion ubicada:  99.92 %   demanda ubicada:  99.02 %
cobertura suficiente para estudios de frecuencia
```

Las cifras anteriores corresponden a un ejemplo real del 2026-11-01. Los porcentajes se calculan nuevamente para cada fecha.

Si una parte de la demanda no puede ubicarse en la red, el menú muestra una advertencia en rojo con los MW de demanda sin ubicar. Esta condición afecta los resultados: **el EDAC dimensiona el deslastre a partir de la demanda representada en el modelo**. Si parte de la demanda queda sin asignar, el deslastre calculado puede ser insuficiente y el nadir de frecuencia puede resultar optimista. Las fechas anteriores a septiembre de 2026 utilizan códigos de nodo antiguos y, por lo general, no cumplen el filtro de cobertura.

---

## 2. Navegación por el menú

| Tecla | Función |
|---|---|
| `1`…`18` | Abre la opción correspondiente. |
| `p` | Permite cambiar el punto de operación sin cerrar el menú. |
| `q` | Cierra el menú. |
| Enter | No ejecuta ninguna opción en la pantalla principal y no cierra la sesión. |

Cualquier otra entrada produce el mensaje `opcion no valida`. Al finalizar cada opción, el menú solicita pulsar Enter para volver a la pantalla principal.

### Comportamiento general

- **Cada opción presenta una descripción antes de ejecutarse.** El menú informa qué procedimiento realiza, qué supuestos utiliza y cuál es su tiempo de ejecución aproximado, entre otros aspectos relevantes.
- **Enter acepta el valor predeterminado** en las preguntas de cada opción. Por tanto, es posible recorrer las opciones utilizando los valores predeterminados. En las listas cortas de opciones, el valor predeterminado se identifica con un asterisco (`*`). En los demás tipos de preguntas —incluidas las listas numeradas de fechas y elementos— se muestra entre corchetes al final de la línea, por ejemplo, `[3000.0]`.
- **Las opciones que ejecutan módulos independientes muestran el comando correspondiente** antes de iniciar el proceso. Por ejemplo:

  ```bash
  python -m stn.contingencias --fecha 2026-10-20 --periodo 19
  ```

  Esto permite identificar los parámetros utilizados, repetir la ejecución desde la línea de comandos o incorporar el comando en un cuaderno de trabajo. Este comportamiento corresponde a las ocho opciones de **Simular** y a la opción 18. Las opciones de **Consultar** y las opciones 15, 16 y 17 de **Análisis** se ejecutan dentro del propio menú y no muestran un comando independiente.

  Al finalizar un módulo, el menú indica su duración en segundos. Si el módulo termina con un código distinto de cero, el menú advierte que la salida anterior no constituye un resultado válido.

### Ubicación de los resultados

Los archivos de salida se guardan en el directorio `resultados/`. El nombre de los archivos incluye un sufijo asociado al punto de operación —por ejemplo, `_diurno11` o `_20261020p19`— para evitar que una ejecución sobrescriba los resultados de otra. Los archivos correspondientes a la punta nocturna no incluyen sufijo.

### Tiempo de la primera consulta

La construcción y resolución del caso base tarda aproximadamente 20 segundos. El menú realiza este proceso **una sola vez por sesión** y reutiliza el caso resuelto en las consultas posteriores. Por ello, después de la primera consulta, las opciones que utilizan este caso responden de forma prácticamente inmediata.

Al cambiar el punto de operación mediante `p`, el caso almacenado en caché se descarta y se construye uno nuevo. De esta manera, se evita presentar consultas asociadas a un sistema y ejecutar simulaciones sobre otro.

Las simulaciones de mayor duración se ejecutan en un proceso independiente, ya que modifican el estado de la red. Esta separación evita que dichas modificaciones afecten el caso base almacenado en caché por el menú.

---

## 3. Simular

### Opción 1 — Caso base y flujo de carga

Reconstruye la red a partir de los datos disponibles, resuelve el **flujo de carga AC mediante el método de Newton-Raphson** y presenta el balance por área, la reconciliación de la demanda y los totales del sistema. También genera el mapa de la red y los archivos de exportación.

Esta opción no requiere parámetros adicionales y tarda aproximadamente un minuto. Constituye el punto de partida de los demás análisis; por tanto, si la construcción o la solución del caso base falla, los resultados de las opciones que dependen de él no serán confiables.

---

### Opción 2 — Simular contingencias

Retira elementos de servicio de forma individual o combinada y evalúa el comportamiento de la red ante cada contingencia. Comprueba tres condiciones principales: que el flujo de carga **converja**, que ningún elemento supere su **límite de emergencia** y que las tensiones de las barras permanezcan dentro del intervalo de 0,9 a 1,1 pu.

> **Criterio de recuento de las violaciones.** Las tensiones fuera de banda se cuentan de forma incremental: se descuentan las del caso base, de modo que `n_v_bajas` y `n_v_altas` corresponden únicamente a las que añade la contingencia. El radial de Arauca presenta 4 barras por debajo de 0,9 pu sin que ocurra ninguna contingencia; contarlas en los 296 casos equivaldría a contabilizar 296 veces el mismo problema. Las sobrecargas siguen el mismo criterio desde el 12-nov-2026: `n_sobrecargas` cuenta los elementos que superan su límite tras la contingencia y que el caso base **no** traía sobrecargados, más los que ya lo estaban y la contingencia empeora en más de 5 puntos. El recuento en absoluto se conserva en `n_sobrecargas_total`. Antes se contaban en absoluto, y un caso base que ya arrancaba con un autotransformador sobrecargado hacía que cientos de contingencias lo contaran como propio. En la punta y el diurno de PowerFactory el caso base no tiene sobrecargas, así que sus resultados no cambian.

**Primera pregunta — tipo de simulación:**

```text
Que quieres simular:
  * 1) el barrido completo (lineas y trafos, 296 casos, ~2 min)
    2) solo 500 kV (55 casos, rapido)
    3) un area concreta
    4) UNA contingencia concreta: el N-1 de un elemento que eliges
    5) dobles contingencias N-2 en 500 kV
```

Las alternativas disponibles son:

- **Barrido completo:** evalúa individualmente cada línea y cada transformador.
- **Solo 500 kV:** limita el análisis a los elementos del nivel de tensión de 500 kV. Reduce el número de casos y el tiempo de ejecución.
- **Un área concreta:** solicita el nombre del área que se desea analizar. Los valores válidos son `Caribe`, `Antioquia`, `Oriental`, `Nordeste` y `Suroccidental`. El valor predeterminado es `Caribe`.
- **Una contingencia concreta:** permite seleccionar un elemento específico para evaluar su salida de servicio bajo el criterio N-1. El procedimiento de selección se describe a continuación.
- **N-2 en 500 kV:** evalúa las combinaciones de dos elementos del sistema de 500 kV.

#### Selección de un elemento para la contingencia N-1

Los nombres de los elementos en el modelo pueden ser extensos, por ejemplo, `ANTIOQUIA 500 - CERROMATOSO 500 1`. Para facilitar su selección, el menú permite filtrar los elementos mediante una búsqueda por nombre.

```text
parte del nombre (Enter = las mas cargadas) []:
```

- **Al introducir un texto**, el menú muestra los elementos cuyo nombre coincide con el criterio de búsqueda. Las coincidencias se ordenan de mayor a menor cargabilidad y se presentan hasta 25 resultados. Si existen más coincidencias, el menú informa esta condición y solicita precisar el texto de búsqueda.
- **Al pulsar Enter sin introducir texto**, se muestran los elementos con mayor cargabilidad en el caso base. Esta vista permite identificar los elementos que operan más cerca de sus límites antes de aplicar la contingencia.

Cada resultado incluye el tipo de elemento, su nombre y su cargabilidad expresada como porcentaje de `s_nom`. La selección se realiza mediante el número asignado a cada elemento (pregunta `cual (1-N, 0 = ninguna)`, con valor predeterminado 1). La opción `0` cancela el proceso.

La cargabilidad del caso base que muestra el selector se expresa sobre el límite nominal. El límite de emergencia es, en la mediana, 1,30 veces el nominal; por ello, una misma línea presenta una cargabilidad menor cuando se expresa sobre el límite de emergencia. En el análisis N-1, en cambio, la cargabilidad se mide contra el límite de emergencia.

Al finalizar la simulación de una contingencia específica, se presenta un **resumen del resultado N-1** en una línea. Este indica si la contingencia no genera violaciones, si el flujo converge pero aparecen sobrecargas o tensiones fuera de los límites establecidos, si la red se divide en islas eléctricas —incluyendo la cantidad de carga y generación que queda fuera de servicio— o si el flujo de carga no converge.

**Segunda pregunta — aplicación de la curva de capacidad:**

```text
Imponer la curva de capacidad de los generadores (PV->PQ)?
  * 1) no (mas rapido)
    2) si (mas lento, detecta colapsos de tension)
```

Por defecto, el reactivo de las barras PV es ilimitado. La aplicación de los límites de potencia reactiva de los generadores —equivalente a la bandera `--con-limites` en la línea de comandos— es necesaria para evaluar adecuadamente la estabilidad de tensión. **Si no se imponen estos límites, las barras PV pueden mantener su consigna de tensión sin una restricción efectiva sobre la potencia reactiva que deben suministrar o absorber.** En esas condiciones, el modelo no representa la saturación de la capacidad reactiva de los generadores y, por construcción, no puede identificar el colapso de tensión asociado a dicha limitación. Los resultados publicados del trabajo se obtuvieron con esta opción activada. En los puntos construidos a partir de XM (`--fecha`), el generador que alcanza su límite permanece en él y no vuelve a regular tensión; el resultado es más conservador que el de la punta y el diurno, pero el barrido converge.

Cuando se aplican los límites, cada generador que alcanza o supera su curva de capacidad puede pasar de PV a PQ (conmutación PV→PQ). El proceso requiere resolver nuevamente el flujo de carga después de los cambios de tipo de barra, por lo que una contingencia puede necesitar varias soluciones sucesivas.

Con los límites activados, el barrido completo tarda aproximadamente 15 minutos; el menú informa el tiempo estimado antes de iniciar. La evaluación de una sola contingencia tarda unos segundos.

---

### Opción 3 — Dinámica de frecuencia (EDAC y AGC)

Simula la respuesta del sistema ante una pérdida súbita de generación. El módulo integra la **ecuación de oscilación**, aplica los escalones del EDAC de acuerdo con el **Acuerdo 2105 del CNO**, calcula el deslastre de carga y representa la respuesta del AGC para compensar el desequilibrio restante. El procedimiento finaliza con un flujo de carga AC del estado posterior al evento.

**Primera pregunta — tipo de evento:**

```text
Que evento simular:
  * 1) perdida de N MW de generacion
    2) perdida de un area completa
    3) perdida de generadores concretos
```

| Alternativa | Información solicitada | Valor predeterminado |
|---|---|---|
| Pérdida de N MW | Magnitud de la generación perdida, en MW (`MW que se pierden`). | `3000` |
| Pérdida de un área | Nombre del área afectada (`area`). | `Antioquia` |
| Pérdida de generadores concretos | Nombres de los generadores, separados por espacios. | `gen_ANTIOQUIA__500` |

Para consultar el nombre exacto de un generador, se puede utilizar previamente la opción 10 (**Buscar una barra, generador o línea**).

**Segunda pregunta — método de distribución del deslastre:**

```text
Como repartir el deslastre:
  * 1) edac (proporcional, como el esquema regulado)
    2) optimo (OPF que elige donde cortar)
    3) comparar los dos
```

- **EDAC:** utiliza el reparto proporcional establecido por el esquema regulado. Representa la distribución convencional del deslastre y corresponde a lo que ejecutaría el sistema real.
- **Óptimo:** utiliza un problema de flujo óptimo de potencia (OPF) para determinar las barras en las que se debe realizar el corte de carga.
- **Comparar:** ejecuta ambos métodos y presenta sus resultados de forma conjunta.

---

### Opción 4 — Comparar dos horas lado a lado

Compara **dos puntos de operación** mediante las mismas pruebas y presenta los resultados en columnas, junto con las diferencias entre ambos. La comparación incluye la configuración de la red, el balance de potencia, el estado del flujo de carga, la respuesta de frecuencia, la respuesta ante una misma perturbación, la contingencia de mayor magnitud, el balance por área, los resultados N-1 y el conjunto de generación BTM.

La **columna A corresponde siempre al punto de operación activo** en la sesión, es decir, al punto seleccionado o modificado mediante `p`. El menú solicita seleccionar el segundo punto de operación (`Contra que comparar el punto activo`). Las alternativas disponibles dependen del punto activo:

| Punto activo | Alternativas de comparación |
|---|---|
| Una fecha de XM | Otro periodo de la misma fecha, la punta nocturna, el escenario diurno u otra fecha. |
| Diurno | La punta nocturna, el escenario diurno en otro horario u otra fecha. |
| Punta nocturna | El escenario diurno en un horario seleccionado o una fecha de XM. |

Según la alternativa elegida, el menú solicita datos adicionales:

| Alternativa | Pregunta | Valor predeterminado |
|---|---|---|
| Otro periodo de la misma fecha | `periodo horario de la otra columna (1-24)` | 5; si el periodo activo ya es el 5, 19. |
| El punto diurno | `hora del diurno (clave HourNN de XM; 11 = 10:00-11:00)` | `11` |
| Otra fecha de XM ya descargada | Número de la fecha (`cual`) y `periodo horario (1-24; 19 es la punta)` | Última fecha en disco; periodo `19`. |

Cuando el punto activo corresponde a una fecha de XM, la alternativa **otro periodo de la misma fecha** aparece en primer lugar. Esto facilita comparar la hora crítica con la hora de máxima demanda del mismo día.

El valor predeterminado depende del periodo activo. Si el periodo seleccionado no es el 5, el menú propone el periodo 5, debido a que el barrido de las 24 horas sitúa la hora crítica en el periodo 4 o 5 de la madrugada, y no en el periodo de máxima demanda. Si el periodo activo ya es el 5, propone el periodo 19, correspondiente a la punta nocturna. De esta manera, al aceptar el valor predeterminado se comparan los dos extremos del día considerados por el análisis.

Si los dos puntos de operación seleccionados son iguales, el menú informa esta condición y no ejecuta la comparación.

**Parámetros adicionales:**

- **Perturbación de referencia en MW:** por defecto, `3000` MW. Se aplica el mismo evento, expresado en MW absolutos, a los dos sistemas. Esto permite comparar la respuesta ante una perturbación de igual magnitud.
- **Barrido N-1:** permite utilizar los archivos CSV generados previamente —opción más rápida y predeterminada— o ejecutar nuevamente el análisis. La segunda alternativa tarda varios minutos por cada punto de operación.

#### Interpretación de la salida

Los comentarios que acompañan cada bloque se generan a partir de los resultados de las dos columnas y no están redactados de antemano. Por ejemplo, el menú identifica si un punto presenta una demanda mayor y, al mismo tiempo, una energía cinética menor. También explica las diferencias en el número de generadores en servicio: una unidad se incluye en el modelo cuando el despacho la establece como generadora durante el periodo analizado, y el compromiso de unidades influye directamente en la inercia del sistema.

La casilla de **demanda bruta** aparece vacía en las columnas construidas a partir de fechas de XM. Esto se debe a que `PRON_BARRA` contiene la demanda neta y el modelo no dispone de información suficiente para separar la componente de generación embebida.

---

### Opción 5 — Deslastre considerando generación BTM

Esta opción implementa el algoritmo principal del trabajo. Distribuye la generación detrás del medidor (*behind-the-meter*, BTM) entre las barras, representa la desconexión súbita de la fracción conectada mediante inversores y resuelve un **modelo de programación lineal entera mixta (MILP)**. El modelo asigna las barras a los escalones del EDAC considerando cuánta generación BTM sana se perdería junto con la carga desconectada.

> **Consideración para la punta nocturna:** cuando el punto de operación activo es la punta nocturna, la generación solar es nula. En consecuencia, el evento de desconexión de generación solar no está presente en este escenario y la pérdida de BTM corresponde únicamente a la componente no solar. Para analizar una desconexión asociada a generación solar, se debe seleccionar el escenario diurno o una fecha de XM con generación solar.

> **Consideración para el escenario diurno derivado:** en el diurno derivado del caso de referencia, el esquema solo actúa si cae aproximadamente el 63 % o más del BTM con inversor (umbral de caída). La afirmación de que, a media mañana, el EDAC dispara es válida únicamente para ese escenario diurno derivado; no es aplicable al despacho real de XM.

**Pregunta 1 — fuente de información del BTM:**

```text
De donde sale el BTM:
  * 1) agpe (CASO BASE: el BTM real de hoy, 740,8 MW segun UPME)
    2) agpe_gd (sensibilidad: + generacion distribuida, 1.346,8 MW)
    3) sintetico (penetracion supuesta, para escenarios futuros)
    4) ambas (el pool viejo AGPE+menores; NO es BTM, solo para reproducir
       cifras previas al 31-10-2026)
```

La cuarta alternativa se conserva para reproducir resultados de versiones anteriores del modelo. **Las plantas menores no se clasifican como generación BTM**, ya que la CREG 086 de 1996 establece que esta figura es excluyente con la de autogenerador.

**Pregunta 2 — únicamente para la alternativa `sintetico`:** solicita la penetración supuesta como porcentaje de la demanda (`penetracion supuesta en % de la demanda`). El valor predeterminado es `20`.

**Pregunta 3 — fracción de BTM con inversor que se desconecta:** se introduce como porcentaje (`% del BTM con inversor que se desconecta`). El valor predeterminado es `80`. Este parámetro representa la magnitud de la desconexión considerada en el evento.

**Pregunta 4 — pérdida convencional adicional:** permite añadir una pérdida de generación convencional, expresada en MW. El valor predeterminado es `0`, que corresponde a no incluir una pérdida adicional. Esta opción permite evaluar conjuntamente la desconexión del BTM y una pérdida de generación síncrona.

**Pregunta 5 — criterio para evaluar la suficiencia del deslastre:**

```text
Con que vara exigir la suficiencia del deslastre:
  * 1) peor_escenario (robustez de peor caso, recomendada)
    2) estimado (se fia de la estimacion)
    3) piso (garantia literal de Das, sobrecorta)
```

Esta selección define **cómo se incorpora el error de estimación del BTM** en el cálculo:

- `peor_escenario` considera un criterio robusto frente al error de estimación.
- `estimado` utiliza directamente el valor estimado del BTM.
- `piso` aplica la garantía literal de Das, lo que puede producir un deslastre superior al estrictamente necesario.

**Pregunta 6 — peso `lambda`:** define el peso de la penalización asociada a la desconexión de generación BTM que permanece en servicio (`peso lambda de la penalizacion por destruir BTM sano`). El valor predeterminado es `5`. Antes de modificarlo, se recomienda consultar la opción 17, que analiza su sensibilidad.

**Pregunta 7 — comparación con el EDAC proporcional** (`Comparar contra el reparto proporcional del EDAC actual?`): permite comparar el resultado del MILP con el reparto proporcional del EDAC actual. La opción está activada por defecto (`si`). Esta comparación proporciona la referencia necesaria para interpretar el resultado; sin ella, la ejecución entrega una cifra aislada.

---

### Opción 6 — Cascada multironda

A diferencia de un análisis N-1 convencional, esta opción no supone que el sistema resiste el primer evento. Representa una **secuencia de eventos y acciones de protección**, que incluye aperturas de elementos, deslastre de carga y disparos sucesivos, en una sola línea de tiempo. El proceso se desarrolla ronda tras ronda, hasta que el sistema se estabiliza o alcanza una condición de colapso.

**Pregunta 1 — escenario de simulación:**

```text
Que escenario:
  * 1) btm (cae el BTM con inversor)
    2) iberia (secuencia tipo apagon iberico)
    3) cascada (4 perdidas de 600 MW encadenadas)
    4) simple (una perdida en t=0)
    5) abrir las N lineas mas cargadas
```

**Parámetros que dependen del escenario:**

| Escenario | Parámetro solicitado | Valor predeterminado |
|---|---|---|
| `btm` | Fracción del BTM que se desconecta (`fraccion del BTM que cae`). | `0.9` |
| `iberia`, únicamente en la punta nocturna | Generación solar en producción, en MW (`solar EN PRODUCCION en MW (0 = punta nocturna)`). | `0.0` |
| `abrir las N` | Número de líneas que se deben abrir (`cuantas lineas`). | `6` |

La generación solar únicamente se solicita cuando el punto activo es la punta nocturna. En el escenario diurno y en las fechas de XM, el punto de operación ya contiene la generación solar correspondiente —en el caso de una fecha, según el despacho—. Por tanto, solicitar nuevamente este parámetro implicaría reemplazar un dato disponible por una hipótesis adicional; en esos casos el menú informa que la generación solar queda fijada por el punto activo.

Cuando se utiliza la punta nocturna, el menú advierte que cualquier valor de generación solar introducido corresponde a un supuesto y no a un dato del punto de operación.

---

### Opción 7 — Barrido de las 24 horas de una fecha

Evalúa las 24 horas de una fecha mediante **las mismas pruebas y una perturbación de igual magnitud en MW absolutos**. Los resultados se almacenan en un archivo CSV. Este análisis permite identificar cuantitativamente la hora crítica del día; en los casos evaluados, esta se encuentra en el periodo 4 o 5 de la madrugada y no coincide con el periodo de demanda máxima.

Esta opción requiere una fecha de XM y, por tanto, **no utiliza directamente el punto de operación activo**. La punta nocturna y el escenario diurno representan intervalos horarios específicos, no un día completo. Si el punto activo corresponde a una fecha de XM, el menú la propone automáticamente en primer lugar; en caso contrario, solicita seleccionar una fecha. Si no hay fechas en disco, el menú lo indica y remite a la tecla `p` o al descargador (`python -m stn.fuentes.descarga_xm --fecha AAAA-MM-DD`).

Las fechas se presentan **de la más reciente a la más antigua**. El catálogo de nodos se actualizó a finales de octubre de 2026 y las fechas anteriores a septiembre de ese año suelen presentar limitaciones de cobertura. Las horas que no cumplen el filtro de cobertura se excluyen del resumen del barrido.

**Parámetros solicitados:**

| Parámetro | Valor predeterminado |
|---|---|
| Fecha que se analizará (`cual (numero)`). | `1` |
| `Barrer mas fechas para comparar` (solo si hay más de una fecha disponible; alternativas: `no, solo esa` y `todas las descargadas (varios minutos)`). | `no, solo esa` |
| Magnitud de la pérdida de generación, en MW (`evento de generacion perdida en MW`). | `3000` |
| `Grafico de las 24 horas`. | `si` |

Cuando se seleccionan varias fechas, el menú presenta una comparación al finalizar. Esto permite distinguir comportamientos asociados a las características del sistema de aquellos que dependen de las condiciones particulares de una fecha. El tiempo de ejecución es de aproximadamente **3 minutos por fecha**.

---

### Opción 8 — Mapa interactivo

Genera un archivo HTML con la representación georreferenciada de la red. Las líneas se colorean de acuerdo con su cargabilidad, las barras se identifican según su nivel de tensión y los autotransformadores se muestran en el mapa. Esta opción no requiere parámetros adicionales.

La geometría y el trazado de la red se mantienen constantes entre fechas; los flujos y los colores cambian de acuerdo con el punto de operación. Los elementos que se encuentran fuera de servicio se representan mediante líneas discontinuas en lugar de eliminarse del mapa. Esto permite comparar diferentes fechas y distinguir los elementos desconectados de aquellos que no forman parte de la red modelada.

---

## 4. Consultar el modelo

Las seis opciones de esta sección consultan el caso base almacenado en caché. Por lo general, no requieren parámetros adicionales y, una vez construido el caso base, presentan los resultados prácticamente de inmediato.

### Opción 9 — Resumen del sistema

Presenta las principales características del sistema en cinco bloques:

- **RED:** número de barras, líneas, transformadores, generadores y cargas.
- **POTENCIA:** consignas de generación, demanda, pérdidas y potencia activa suministrada por la barra slack para cerrar el balance.
- **TENSIÓN:** rango de tensiones en pu y número de barras con tensiones por debajo o por encima de los límites establecidos.
- **FRECUENCIA:** inercia equivalente `H`, capacidad de generación acoplada `S_base`, energía cinética `H·S`, estatismo equivalente y reserva.
- **MEZCLA POR TECNOLOGÍA:** potencia nominal instalada (MW de placa) por tecnología. También indica cuántas máquinas de cada tecnología tienen un valor de inercia `H` declarado y cuántas utilizan el valor predeterminado.

La información sobre los valores de inercia permite distinguir qué parte de los datos corresponde a parámetros declarados y qué parte depende de supuestos del modelo.

### Opción 10 — Buscar una barra, generador o línea

Solicita un texto de búsqueda. La búsqueda no distingue entre mayúsculas y minúsculas y muestra la información disponible en el modelo para los elementos que coinciden con el criterio introducido:

- **Barras:** tensión, generación, carga y todas las líneas conectadas. Para cada línea se muestra el flujo desde la perspectiva de la barra consultada y su cargabilidad.
- **Generadores:** potencia despachada, tecnología, potencia nominal en MVA e inercia. También se indica si el valor de `H` corresponde a un dato declarado o a un valor asignado por tecnología.
- **Líneas:** flujo de potencia y `s_nom`, con un máximo de 25 resultados. Este bloque se muestra únicamente cuando la búsqueda no coincide con ninguna barra. Si se busca por el nombre de una subestación, sus líneas aparecen en el bloque de barras, que incluye información adicional sobre las conexiones. Para consultar líneas individuales, se recomienda utilizar un término de búsqueda que no coincida con el nombre de una barra.

Esta opción permite consultar el nombre exacto de un generador antes de seleccionarlo en la opción 3.

### Opción 11 — Cobertura de datos: qué es dato y qué es supuesto

Presenta dos listas para identificar el nivel de información disponible y los parámetros que dependen de hipótesis.

La primera muestra **cuántas máquinas tienen declarado cada parámetro** con respecto al total del modelo. Incluye la inercia `H` —junto con el porcentaje de potencia nominal que cubren esos datos—, el estatismo, los límites `Q_min` y `Q_max`, la tecnología y el número de líneas que pueden contrastarse con PowerFactory.

La segunda lista identifica los **parámetros que provienen de la literatura o de supuestos adoptados en el estudio**, junto con sus valores. Incluye el amortiguamiento de carga (1,5 %/%Hz), la constante del gobernador (8,0 s), la reserva primaria (10 % de la capacidad en giro, solo máquinas síncronas), el factor de potencia nominal (0,90), el límite de subexcitación (0,35), la caída síncrona (0 %, supuesto propio), la correlación espacial del BTM (0,90, extrapolación propia) y las impedancias genéricas de los 16 autotransformadores (X = 0,12; R = 0,004).

Esta consulta permite identificar qué parámetros cuentan con respaldo en los datos de entrada y cuáles requieren justificación como hipótesis durante la presentación o discusión de los resultados.

### Opción 12 — Qué información falta

Presenta la información de generación que no queda representada explícitamente en el modelo. Incluye la generación total reportada, los nodos que no tienen una conexión trazable al STN, los valores que informa el modelo y los MW que quedan excluidos por el filtro de 30 % aplicado (479,2 MW).

La opción identifica los ocho nodos con mayor generación no atribuida y finaliza con una lista priorizada, por orden de retorno, de la información que sería conveniente solicitar para mejorar la representación del sistema.

### Opción 13 — El BTM colombiano

Presenta la composición del BTM registrado en Colombia por tecnología y área. Para el caso base, el BTM corresponde a los **AGPE, con una capacidad de 740,83 MW según la UPME**. De este total, el **96,9 % corresponde a generación solar**. En la representación utilizada por el modelo, esta es la componente que se desconecta en bloque ante un hueco de tensión.

La distribución por subárea y tecnología se obtiene de PARATEC, mientras que la capacidad total corresponde a la información de la UPME.

La tabla por área se ordena según el porcentaje de generación conectada mediante inversores. En tres de las cinco áreas, este porcentaje es del 100 %.

La opción finaliza con tres indicadores que deben interpretarse conjuntamente:

1. La penetración de generación conectada mediante inversores con respecto a la demanda del modelo.
2. La misma penetración al incluir la generación distribuida, considerada como un escenario de sensibilidad y no como el caso base.
3. El umbral de penetración a partir del cual actúa el EDAC, medido sobre el caso de referencia: 5,13 %, con un intervalo de 3,8 % a 6,5 % según las hipótesis.

Si el primer indicador supera el umbral indicado en el tercero, el punto de operación se encuentra por encima de dicho umbral. El intervalo resulta de variar la hipótesis sobre la capacidad aparente no declarada (opción 16) y constituye una cota inferior: los MW que el modelo no representa no se incluyen en `S_base` y, de incluirse, la aumentarían.

La opción también incluye una advertencia sobre la clasificación de las plantas menores: **no se consideran generación BTM**, de acuerdo con la interpretación de la CREG 086 de 1996. Hasta el 31-10-2026, este panel incluía dichas plantas (1.496,2 MW) en el cálculo.

### Opción 14 — Balance por área operativa

Presenta la generación, demanda, pérdidas e intercambio de cada una de las cinco áreas operativas. Un valor positivo de `InterP` indica que el área exporta potencia. La generación `GenP` corresponde al despacho resuelto; por ello incluye la potencia que la barra slack aporta para cerrar el balance y supera ligeramente la suma de consignas que presenta la opción 9.

A continuación, compara los resultados con los **límites de importación publicados por XM** en sus informes de planeamiento operativo e identifica el criterio que establece cada límite: Caribe, 2.000 MW (contingencia sencilla en 500 kV); Oriental, 900 MW (contingencia Primavera–Bacatá 500 kV); Suroccidental, 560 MW (sobrecarga de un autotransformador de San Marcos o Virginia). Para las demás áreas el menú indica que no hay límite publicado. Estos valores no se encuentran en PARATEC. Además, varios límites están determinados por condiciones de estabilidad y no por restricciones térmicas. Por esta razón, el análisis N-1 del modelo —que evalúa límites térmicos y de tensión— no identifica necesariamente las restricciones de transferencia asociadas a estabilidad.

> **Consideración para la interpretación:** el caso de PowerFactory utilizado como referencia representa una red futura (estudio a 31-12-2042, etapa P20), mientras que los límites de importación incluidos en la comparación corresponden a la red de 2024. Una red con refuerzos puede admitir mayores transferencias; por tanto, superar uno de esos límites no demuestra, por sí solo, que el caso modelado sea irrealizable, y el límite aplicable a la red reforzada no se conoce. La demanda del caso sí es actual: 12.472,5 MW en el reporte completo, un 3 % por encima del récord del SIN de 2025.

---

## 5. Análisis

Las cuatro primeras opciones de esta sección permiten reproducir los principales resultados del trabajo; la 19 es una gráfica de consulta y vive en el último grupo del menú, «Gráficas». Algunas requieren tiempos de ejecución mayores que las opciones de consulta, por lo que es importante considerar los supuestos y las observaciones que acompañan cada resultado.

### Opción 15 — Umbral de penetración con inversor

Evalúa distintos niveles de penetración de BTM conectado mediante inversores para identificar **a partir de qué nivel una desconexión masiva provoca la activación del EDAC**.

El único parámetro solicitado es el porcentaje del BTM conectado mediante inversores que se desconecta. El valor predeterminado es `90`.

El análisis recorre diez niveles de penetración (5; 5,37, identificado como el valor actual; 6; 7; 8; 8,5; 10; 15; 20 y 40 %). Para cada nivel presenta los MW desconectados, el nadir de frecuencia y el número de escalones del EDAC que se activan. La marca `<- dispara` aparece **en cada fila en la que se activa el EDAC**, no únicamente en la primera. El umbral corresponde al primer nivel de penetración en el que aparece esta marca; por debajo de ese nivel, la columna no presenta activaciones.

#### Dependencia del punto de operación

El umbral depende del punto de operación utilizado. Los dos resultados que se presentan a continuación corresponden a sistemas diferentes y, por tanto, no son directamente intercambiables:

- Sobre **el caso de referencia**, cuyo parque de generación corresponde a 2042, el valor central del umbral es 5,13 % de penetración con inversor, con un intervalo de 3,8 % a 6,5 % según las hipótesis. La penetración de Colombia (6,25 %) queda **por encima** del umbral.
- Sobre **la generación real medida de XM del 18-09-2026, periodo 11**, la generación por convertidor es considerablemente menor (0,8 % frente a 12,9 % en el caso de referencia) y el BTM aporta su producción medida, no su capacidad instalada. El umbral es 8,1 % de la demanda de ese punto y el AGPE actual representa 6,5 %. Colombia queda **por debajo** del umbral, con un margen de 1,6 puntos porcentuales, y el esquema no actúa.

Las dos medidas están expresadas en bases distintas: capacidad instalada en el primer caso y producción medida en el segundo. Por esta razón, se interpretan como **dos puntos de operación** independientes, sin relación de continuidad entre ellos. Para evaluar el comportamiento sobre una fecha, se puede seleccionarla mediante `p` y ejecutar nuevamente la opción.

Los 587,6 MW de generación sin atribuir y los 479,2 MW excluidos por el filtro no se incluyen en `S_base`; de incluirse, la aumentarían, por lo que el valor obtenido constituye una cota inferior.

### Opción 16 — Sensibilidad del umbral

Cuantifica la variación del umbral cuando se modifican las hipótesis utilizadas en su cálculo. Esta opción no requiere parámetros adicionales.

Presenta una tabla con cuatro escenarios:

1. El parque completo de generación acoplado.
2. Una unidad adicional por planta.
3. El número mínimo de unidades necesario para cubrir el despacho, correspondiente al caso base.
4. El mismo escenario anterior, pero incluyendo la reserva del 3 % exigida por la CREG.

Para cada escenario se presenta la capacidad síncrona, la inercia `H`, la reserva y el umbral resultante.

Los dos primeros escenarios requieren conocer **el número de unidades que componen cada planta**. Si el punto de operación activo no contiene esta información, la tabla presenta únicamente dos escenarios en lugar de cuatro. Con los datos de PARATEC incluidos en el repositorio, se pueden calcular los cuatro.

Las hipótesis que tienen mayor influencia en el umbral son el número de unidades acopladas y la cantidad de reserva disponible. Ninguna de estas variables se conoce con precisión a partir de la información disponible: no se cuenta con el despacho por unidad y la reserva puede interpretarse de dos maneras válidas (el mínimo que exige la norma o el margen físico de las máquinas en giro).

Esta opción permite evaluar cuánto depende el resultado de estas incertidumbres. Por ello, la conclusión debe considerar el intervalo obtenido y no únicamente un valor puntual: el umbral se sitúa entre 3,8 % y 6,5 % según las hipótesis, con 5,13 % como valor central, y Colombia (6,25 %) se ubica por encima del centro y en el tercio superior del intervalo. Sobre la generación real medida de XM del 18-09-2026 (periodo 11), el umbral es 8,1 %.

La opción también resume cómo se modificó el umbral al sustituir supuestos por datos: 6,0 % con `H` por tecnología; 8,07 % con la capacidad aparente real de PARATEC; 7,67 % al excluir de la reserva los parques eólicos, que no pueden aportarla; y 6,22 % al considerar acopladas únicamente las unidades necesarias, en lugar de la planta completa.

### Opción 17 — Barrido del peso lambda

Evalúa la sensibilidad del peso de la penalización por desconectar generación BTM que permanece en servicio. El análisis considera **tres regímenes de operación**: el evento de desconexión de BTM, la operación normal actual y la operación normal con alta penetración.

El menú únicamente solicita confirmar si se desea continuar (`Continuar?`). El análisis tarda aproximadamente **8 minutos** y ejecuta 24 problemas MILP completos, correspondientes a cuatro valores de `lambda`, tres regímenes y dos semillas.

Los resultados permiten justificar el valor predeterminado de `lambda` utilizado en la opción 5. Si la calibración se realiza únicamente para el evento de desconexión de BTM, se obtiene un valor elevado de `lambda` (25). Sin embargo, cuando existe una penetración alta y el BTM no se desconecta, ese valor puede hacer que el optimizador prefiera no realizar cortes de carga. En consecuencia, **el esquema deja de actuar en el régimen normal**.

Por esta razón, el régimen normal establece una restricción para la selección de `lambda` que no se identifica al calibrar exclusivamente con el evento. La tabla señala con la marca `<- el rele no corta` las filas en las que se presenta este comportamiento.

### Opción 18 — MILP frente al EDAC proporcional

Ejecuta un mismo evento con los dos métodos de distribución del deslastre y compara la cantidad de generación embebida sana que desconecta cada método **para obtener el mismo alivio de potencia**.

La opción no solicita parámetros adicionales y utiliza un escenario fijo: penetración sintética del 20 %, desconexión del 90 % del BTM y una pérdida convencional adicional de 600 MW.

La última columna permite identificar una diferencia relevante entre los métodos: el MILP concentra el deslastre en un número menor de barras que el reparto proporcional. Esta concentración puede dejar una mayor carga sobre la red restante. Por tanto, este efecto debe presentarse junto con la reducción de generación embebida desconectada al discutir las ventajas y limitaciones del método.

### Opción 19 — Participación de cada tecnología (gráfica)

Dibuja el porcentaje de la generación que aporta cada tecnología —solar, hidroeléctrica, gas, carbón, otras térmicas y eólica— en un periodo o en un rango de una fecha. **No depende del punto de operación activo**: sirve para cualquier fecha, aunque el modelo no la tenga construida.

El menú pregunta tres cosas:

1. **La fecha** (`fecha (AAAA-MM-DD)`). El valor predeterminado es la fecha del punto activo, o la última descargada.
2. **La generación**: la **real** medida por XM (se baja sola si no está en disco y no necesita el snapshot de la fecha), la **programada** (el despacho dDEC, que sí necesita ese snapshot) o **ambas**, que dibuja las dos para ver cuánto se desvió el programa de lo ocurrido.
3. **El momento**: un periodo (gráfica de barras), un rango de periodos (curvas) o el día entero.

El gas y el carbón salen del **combustible que XM declara para cada recurso**, dato que PARATEC no trae. «Otras térmicas» agrupa el ACPM, el combustóleo, el jet, el bagazo, la biomasa y el biogás, y una cogeneración que quema gas se cuenta ahí y no como gas. Los porcentajes son sobre la generación total de cada periodo, no sobre la demanda. La opción imprime también la tabla con los porcentajes y deja el PNG en `resultados/` con un nombre que incluye la fecha, el origen y el tramo (por ejemplo `participacion_20261101_ambos_p9-15.png`).

Desde la línea de comandos: `python -m stn.participacion --fecha 2026-11-01 --desde 9 --hasta 15 --origen ambos`.

---

## 6. Ejecución desde la línea de comandos

Las opciones de **Simular** y la opción 18 ejecutan módulos independientes. Antes de iniciarlos, el menú muestra el comando correspondiente. La guía completa de comandos, con la lista de módulos y parámetros, se encuentra en el README, sección [Ejecución desde la línea de comandos](README.md#ejecución-desde-la-línea-de-comandos).

Las opciones de **Consultar** (9 a 14) y las opciones 15, 16 y 17 de **Análisis** no tienen un equivalente directo en la línea de comandos. La 19 sí lo tiene: `python -m stn.participacion`. Estas funciones están implementadas dentro de `menu.py` y se ejecutan desde el menú.

### Selección del punto de operación

Los módulos de simulación aceptan las mismas opciones para definir el punto de operación. Por ejemplo:

```bash
python -m stn.contingencias --fecha 2026-10-20 --periodo 19
python -m stn.deslastre_btm --diurno 11 --comparar
```

Si no se especifica ninguna opción de punto de operación, los módulos utilizan la punta nocturna.

### Comparación de dos puntos de operación

El módulo `stn.comparar_casos` constituye una excepción porque trabaja con **dos puntos de operación**. Cada caso se especifica mediante uno de los siguientes formatos: `punta`, `diurno:HORA` o `AAAA-MM-DD:PERIODO`.

```bash
python -m stn.comparar_casos --caso-a 2026-10-20:5 --caso-b 2026-10-20:19
```

### Descarga de una fecha

Para descargar los archivos de una fecha sin utilizar el menú:

```bash
python -m stn.fuentes.descarga_xm --fecha 2026-11-01
python -m stn.fuentes.descarga_xm --listar
```

---

## 7. Consideraciones para interpretar los resultados

Antes de utilizar o presentar una cifra, se recomienda realizar las siguientes comprobaciones:

1. **Identificar el punto de operación.** Todas las salidas incluyen una cabecera con esta información. Comparar una cifra del escenario diurno con otra de la punta nocturna sin especificar esta diferencia puede conducir a conclusiones incorrectas.
2. **Verificar la cobertura cuando se utiliza una fecha de XM.** Si una parte de la demanda no está ubicada en la red, el EDAC dimensiona el deslastre con una demanda inferior a la real. En consecuencia, el nadir calculado puede resultar optimista.
3. **Comprobar que no se haya producido un colapso antes de interpretar el nadir.** Si la frecuencia del sistema desciende por debajo de 57,5 Hz, el mínimo de la señal puede corresponder al instante en que se detiene el integrador y no a un nadir físico. Por esta razón, los módulos no publican el valor del nadir en ese caso.
4. **Distinguir las variaciones de tensión de las sobrecargas en el análisis N-1.** Las barras fuera de banda y las sobrecargas se contabilizan con respecto al caso base (de las sobrecargas, solo las nuevas o las que empeoran más de 5 puntos; el recuento en absoluto está en `n_sobrecargas_total`). Adicionalmente, la cargabilidad del caso base se expresa sobre el límite nominal, mientras que en el N-1 se mide contra el límite de emergencia.
5. **Verificar la activación de `--con-limites` al analizar estabilidad de tensión.** Sin esta opción, las barras PV pueden mantener su consigna de tensión sin una restricción efectiva de potencia reactiva. En consecuencia, el análisis no puede representar el colapso de tensión asociado a la saturación de los límites reactivos de los generadores.
6. **Interpretar el umbral de penetración como dependiente del punto de operación.** Los valores obtenidos sobre el caso de referencia y sobre el despacho real de XM están expresados en bases distintas (capacidad instalada frente a producción medida) y corresponden a dos puntos de operación, sin relación de continuidad entre ellos.

---

## 8. Problemas frecuentes

**El intérprete de `python` corresponde a la versión 3.10 o a una anterior.** PyPSA 1.x no distribuye paquetes `wheel` para versiones anteriores a Python 3.11, por lo que la instalación puede fallar y mostrar un mensaje de error extenso sin identificar claramente la causa. Se recomienda comprobar la versión instalada mediante `py --list` en Windows o `python3 --version` en macOS y Linux, y crear el entorno virtual con un intérprete compatible. El modelo también verifica la versión al iniciarse y muestra una advertencia cuando no cumple el requisito.

**El menú solo muestra cuatro fechas.** Estas son las fechas incluidas inicialmente en el repositorio. La quinta entrada de la lista —`otra fecha, descargarla de XM ahora`— permite solicitar una fecha adicional.

**Se produce un error de certificado al descargar una fecha.** Este problema puede presentarse al trabajar detrás del proxy de una empresa que utiliza un certificado raíz propio que Python no reconoce. En ese caso, se debe configurar `SSL_CERT_FILE` para que apunte a un almacén de certificados que incluya la autoridad correspondiente. El mensaje de error proporciona la instrucción específica para el sistema operativo utilizado. En Windows, normalmente no es necesario realizar esta configuración.

**No hay fechas disponibles en disco.** El descargador necesita al menos una fecha existente para heredar el directorio de PARATEC. Se deben recuperar los archivos incluidos en el repositorio dentro de `data/xm/paratec/`.

**Una fecha antigua no cumple el filtro de cobertura.** Las fechas anteriores a septiembre de 2026 utilizan códigos de nodo que todavía no están cubiertos por la tabla de equivalencias. En consecuencia, pueden generar resultados de frecuencia optimistas. Se recomienda utilizar fechas más recientes o interpretar estos resultados considerando la limitación de cobertura.

**El barrido N-1 de la opción 4 indica que faltan resultados.** La comparación utiliza los archivos CSV generados previamente. Para completar el análisis, se debe ejecutar primero el N-1 para cada punto de operación o seleccionar la opción que permite realizar el barrido durante la comparación. Esta última alternativa requiere varios minutos por cada punto de operación.

---

## 9. Verificación del modelo

El menú está diseñado para el **uso del modelo**. Las pruebas y comprobaciones internas se ejecutan mediante comandos independientes:

```bash
python -m stn.validacion            # Contraste contra PowerFactory
python -m tests.test_invariantes    # 34 invariantes del modelo
python -m tests.test_regresion_pf   # 18 regresiones contra el caso congelado
python -m tests.test_fuente_xm      # 62 pruebas de la fuente de datos de XM
python -m tests.verificar_sistema   # 44 comprobaciones externas
python -m stn.limites_reactivos     # Curva de capacidad de reactivo
python -m stn.escenario_diurno      # Derivación del caso diurno
```
