# APP-QUECHUA

ASUS2 es un prototipo de investigación para el quechua Cusco-Collao. Su flujo de voz transcribe audio en quechua y traduce la transcripción al español. También admite texto en quechua como entrada para la traducción al español. El paquete está diseñado para ejecutar ambos componentes de forma local.

> **Solo para pruebas no comerciales.** Está prohibido vender ASUS2 o sus pesos, ofrecerlos comercialmente, atribuirse su autoría o registrarlos a nombre propio. Consulta la [licencia de ASUS2](LICENSE).

## Instalación y ejecución

### Clonar el repositorio

Con Git instalado, ejecuta estos comandos en una terminal.

```sh
git clone https://github.com/alexanderhuahuacccapacc/APP-QUECHUA.git
cd APP-QUECHUA
```

### Preparar los pesos

El repositorio incluye `asus.py`, `requirements.txt`, `model_index.json` y la configuración y los tokenizadores de ambos componentes. Para ejecutar la inferencia necesitas el paquete completo de ASUS2, de aproximadamente 4,43 GB.

- `speech/model.safetensors` contiene los pesos ajustados de voz (1,93 GB).
- `translation/model.safetensors` contiene los pesos ajustados de traducción (2,46 GB).

Si tienes una copia local completa, conserva ambos pesos en sus carpetas junto a `model_index.json`, o indica la carpeta del paquete con `--root RUTA`. La descarga pública de los pesos está pendiente de la verificación de permisos indicada en la sección de versiones.

### Ejecutar la inferencia

Con Python instalado, abre una terminal en la carpeta que contiene `asus.py` y `requirements.txt`. Sustituye `segmento.wav` por la ruta de tu archivo de audio.

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe asus.py --text "Allin p'unchay"
.\.venv\Scripts\python.exe asus.py --audio segmento.wav
```

**Linux y macOS**

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python asus.py --text "Allin p'unchay"
./.venv/bin/python asus.py --audio segmento.wav
```

El programa devuelve JSON. La entrada de audio devuelve la transcripción y la traducción. La entrada de texto devuelve la traducción. Puedes añadir `--device cpu` para ejecutar la inferencia en CPU. El audio debe durar entre 0,1 y 60 segundos y el texto admite hasta 512 tokens.

## Resultados frente a los modelos base de Meta

La evaluación de desarrollo usó 196 audios de un hablante y 337 pares para traducción. Ambos conjuntos se consultaron durante la selección del modelo. Se normalizaron Unicode (NFC) y espacios, conservando mayúsculas y puntuación.

| Tarea y métrica | Meta base | ASUS2 mejorado | Cambio |
|---|---:|---:|---:|
| Voz · WER ↓ | 66,44 % | 62,40 % | −4,04 pp |
| Voz · CER ↓ | 12,19 % | 11,73 % | −0,46 pp |
| Traducción · BLEU ↑ | 5,66 | 8,32 | +2,66 puntos |
| Traducción · chrF++ ↑ | 22,87 | 25,54 | +2,67 puntos |
| Traducción · WER ↓ | 105,44 % | 90,13 % | −15,31 pp |
| Traducción · CER ↓ | 75,23 % | 65,64 % | −9,59 pp |

La columna «Cambio» resta el valor de Meta al de ASUS2 usando las cifras mostradas. `pp` significa puntos porcentuales. En WER y CER, un valor menor indica menos errores. En BLEU y chrF++, un valor mayor indica un mejor resultado.

> El trabajo de entrenamiento y evaluación de ASUS2 continúa con el objetivo de reducir WER y CER y mejorar BLEU y chrF++.

## Versiones en GitHub

- **Avances de código.** Una etiqueta `asus2-code-vX.Y.Z` genera una versión preliminar con un ZIP de código y configuración y el SHA-256 del ZIP. [Ver Releases](https://github.com/alexanderhuahuacccapacc/APP-QUECHUA/releases)
- **Paquete completo.** La primera versión está prevista con la etiqueta `asus2-v1.0.0`. La publicación de los pesos requiere confirmar el alcance de los permisos de Yachasunchis y revisar las condiciones de QuEsT que figuran en el registro de procedencia.

Una vez autorizada la distribución, el paquete completo se adjuntará a la versión correspondiente en partes de hasta 1,8 GB, con el SHA-256 de cada peso. Para descargarlo, elige **Latest** o una etiqueta concreta en Releases, descarga todas las partes en una misma carpeta y extrae el paquete desde la primera parte con una herramienta compatible. Compara los SHA-256 de los pesos extraídos con los de la versión elegida. [Límites de GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas)

En GitHub Free y Pro, el límite de Git LFS es 2 GB por archivo y el peso de traducción lo supera. En GitHub Team, el límite de 4 GB por archivo permitiría usar Git LFS si se elige esa modalidad. [Límites de Git LFS por plan](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)

Para publicar un avance, crea la etiqueta en el commit ya subido a `main` y envíala al remoto. Usa un número de versión nuevo en cada publicación.

```sh
git tag -a asus2-code-v0.1.1 -m "Avance de ASUS2"
git push origin asus2-code-v0.1.1
```

Si el ZIP de una etiqueta existente queda pendiente, abre **Actions → Publicar avance de ASUS2 → Run workflow** e introduce la etiqueta en el campo `tag`.

## Modelos base

- La transcripción adapta MMS-1B-all de Meta con el adaptador de quechua de Cusco (`quz`). [Ficha de MMS-1B-all](https://huggingface.co/facebook/mms-1b-all)
- La traducción adapta NLLB-200-distilled-600M de Meta. Usa el identificador de quechua de Ayacucho (`quy_Latn`) para representar la entrada Cusco-Collao y `spa_Latn` para la salida en español. [Ficha de NLLB-200](https://huggingface.co/facebook/nllb-200-distilled-600M)

## Licencia y atribuciones

Los aportes propios de ASUS2 se ofrecen bajo la [licencia para pruebas no comerciales](LICENSE). Los modelos base MMS y NLLB de Meta conservan su licencia [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.es). Los conjuntos de datos y las bibliotecas se rigen por sus respectivos permisos y licencias.
