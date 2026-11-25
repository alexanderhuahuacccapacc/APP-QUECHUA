# APP-QUECHUA

ASUS2 es un prototipo de investigación para el quechua Cusco-Collao. Su flujo de voz transcribe audio en quechua y traduce la transcripción al español. También admite texto en quechua como entrada para la traducción al español. El paquete está diseñado para ejecutar ambos componentes de forma local.

> **Solo para pruebas no comerciales.** Está prohibido vender ASUS2 o sus pesos, ofrecerlos comercialmente, atribuirse su autoría o registrarlos a nombre propio. Consulta la [licencia de ASUS2](LICENSE).

## Clonar el repositorio

Con Git instalado, ejecuta estos comandos en una terminal.

```sh
git clone https://github.com/alexanderhuahuacccapacc/APP-QUECHUA.git
cd APP-QUECHUA
```

Por ahora el repositorio contiene la documentación y la licencia. La instalación y la ejecución requieren el código de inferencia, las dependencias y los pesos ajustados de ASUS2, que aún no están publicados aquí.

## Modelos base

- La transcripción adapta MMS-1B-all de Meta con el adaptador de quechua de Cusco (`quz`). [Ficha de MMS-1B-all](https://huggingface.co/facebook/mms-1b-all)
- La traducción adapta NLLB-200-distilled-600M de Meta. Usa el identificador de quechua de Ayacucho (`quy_Latn`) para representar la entrada Cusco-Collao y `spa_Latn` para la salida en español. [Ficha de NLLB-200](https://huggingface.co/facebook/nllb-200-distilled-600M)

## Licencia y atribuciones

Los aportes propios de ASUS2 se ofrecen bajo la [licencia para pruebas no comerciales](LICENSE). Los modelos base MMS y NLLB de Meta conservan su licencia [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.es). Los conjuntos de datos y las bibliotecas se rigen por sus respectivos permisos y licencias.
