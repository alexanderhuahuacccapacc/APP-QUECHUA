# APP-QUECHUA

ASUS2 es un prototipo de investigación para el quechua Cusco-Collao. Su flujo de voz transcribe audio en quechua y traduce la transcripción al español. También admite texto en quechua como entrada para la traducción al español. El paquete está diseñado para ejecutar ambos componentes de forma local.

> **Solo para pruebas no comerciales.** Está prohibido vender ASUS2 o sus pesos, ofrecerlos comercialmente, atribuirse su autoría o registrarlos a nombre propio. Consulta la [licencia de ASUS2](LICENSE).

## Instalación y ejecución

### Desarrollo desde un clon limpio en Windows

Ejecuta los comandos en **CMD**. La instalación inicial usa internet para
descargar las bibliotecas y las voces auxiliares. Los pesos ajustados de ASUS2
suman 4,4 GB y se descargan con una cuenta SSH autorizada en la red del servidor.

Si faltan Git o `uv`, instálalos y vuelve a abrir CMD.

```cmd
winget install --id Git.Git -e --source winget
winget install --id astral-sh.uv -e --source winget
```

Clona el código y prepara el entorno Python 3.12. Sustituye `TU_USUARIO_SSH`
por tu cuenta del servidor ASUS2. La contraseña se ingresa cuando el
instalador la solicita. El comando verifica el servidor y los pesos y guarda
los modelos en `models/`.

```cmd
git clone --branch main https://github.com/alexanderhuahuacccapacc/APP-QUECHUA.git
cd APP-QUECHUA
uv sync --python 3.12 --locked --no-dev
.venv\Scripts\python.exe -m scripts.install_asus2 --user TU_USUARIO_SSH
```

#### Interfaz de escritorio

```cmd
.venv\Scripts\python.exe -B -m app
```

#### Traducción directa en CMD

```cmd
chcp 65001
set "PYTHONUTF8=1"
set "HF_HUB_OFFLINE=1"
set "TRANSFORMERS_OFFLINE=1"
set "HF_HUB_DISABLE_TELEMETRY=1"
.venv\Scripts\python.exe -B asus.py --root models\ASUS2 --device cpu --text "Allin punchay"
```

Para transcribir y traducir voz Collao, sustituye `--text "Allin punchay"`
por `--audio "C:\ruta\frase.wav"`. Para traducir texto del español al Collao,
usa `--reverse --text "Buenos días"`. La interfaz y CMD funcionan sin internet
después de instalar los modelos.

### Instalador de Windows

El asistente para Windows 10 (versión 2004 o posterior) y Windows 11 de 64 bits está en preparación. Mostrará la licencia con la opción **Acepto el acuerdo** y permitirá seleccionar una copia local completa del modelo.

Para construir el instalador, usa Inno Setup y una compilación de escritorio que contenga `Xandar.exe` y `_internal/`.

```powershell
ISCC.exe '/DAHuaCcBundle=C:\ruta\Xandar' packaging\installer.iss
```

El ejecutable del instalador se genera en `dist/`. Incluye la aplicación y su entorno incorporado. El modelo se usa desde la carpeta local seleccionada, junto con `model_index.json` y los pesos de ambos componentes.

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
.\.venv\Scripts\python.exe asus.py --text "imaynallan kashanki" --alternatives 3
.\.venv\Scripts\python.exe asus.py --reverse --text "¿Cómo estás?"
```

**Linux y macOS**

```sh
python3 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python asus.py --text "Allin p'unchay"
./.venv/bin/python asus.py --audio segmento.wav
./.venv/bin/python asus.py --text "imaynallan kashanki" --alternatives 3
./.venv/bin/python asus.py --reverse --text "¿Cómo estás?"
```

El programa devuelve JSON. La entrada de audio devuelve la transcripción, la confianza de cada palabra reconocida y la traducción. La entrada de texto devuelve la traducción. `--alternatives N` añade hasta tres traducciones distintas. `--reverse` traduce texto en español al quechua; esta dirección es experimental y solo admite texto. Puedes añadir `--device cpu` para ejecutar la inferencia en CPU. El audio debe durar entre 0,1 y 60 segundos y el texto admite hasta 512 tokens.

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
- **Instalador de Windows.** Las etiquetas `asus2-windows-vX.Y.Z` se reservan para las versiones descargables del asistente de instalación.
- **Paquete completo.** La primera versión está prevista con la etiqueta `asus2-v1.0.0`. La publicación de los pesos requiere confirmar el alcance de los permisos de Yachasunchis y revisar las condiciones de QuEsT que figuran en el registro de procedencia.

Una vez autorizada la distribución, el paquete completo se adjuntará a la versión correspondiente en partes de hasta 1,8 GB, con el SHA-256 de cada peso. Para descargarlo, elige **Latest** o una etiqueta concreta en Releases, descarga todas las partes en una misma carpeta y extrae el paquete desde la primera parte con una herramienta compatible. Compara los SHA-256 de los pesos extraídos con los de la versión elegida. [Límites de GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas)

En GitHub Free y Pro, el límite de Git LFS es 2 GB por archivo y el peso de traducción lo supera. En GitHub Team, el límite de 4 GB por archivo permitiría usar Git LFS si se elige esa modalidad. [Límites de Git LFS por plan](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)

Para publicar un avance, crea la etiqueta en el commit ya subido a `main` y envíala al remoto. Usa un número de versión nuevo en cada publicación.

```sh
git tag -a asus2-code-v0.2.1 -m "Avance de ASUS2"
git push origin asus2-code-v0.2.1
```

Si el ZIP de una etiqueta existente queda pendiente, abre **Actions → Publicar avance de ASUS2 → Run workflow** e introduce la etiqueta en el campo `tag`.

## Modelos base

- La transcripción adapta MMS-1B-all de Meta con el adaptador de quechua de Cusco (`quz`). [Ficha de MMS-1B-all](https://huggingface.co/facebook/mms-1b-all)
- La traducción adapta NLLB-200-distilled-600M de Meta. Usa el identificador de quechua de Ayacucho (`quy_Latn`) para representar la entrada Cusco-Collao y `spa_Latn` para la salida en español. [Ficha de NLLB-200](https://huggingface.co/facebook/nllb-200-distilled-600M)

## Licencia y atribuciones

Los aportes propios de ASUS2 se ofrecen bajo la [licencia para pruebas no comerciales](LICENSE). Los modelos base MMS y NLLB de Meta conservan su licencia [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.es). Los conjuntos de datos y las bibliotecas se rigen por sus respectivos permisos y licencias.
