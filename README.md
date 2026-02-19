# Scrapers Fantasy - Liga Chilena

Sistema de scrapers que extraen y sincronizan plantillas, estados físicos y el fixture oficial de la Primera División chilena para alimentar el entorno de fantasy football.

## Requisitos previos

1. Python 3.11+ (cualquier versión moderna que soporte requests, bs4, psycopg2 y python-dotenv).
2. Un archivo .env en la raíz con las variables de conexión a la base de datos.
3. (Opcional) Acceso por SSH al servidor de base de datos para activar el túnel seguro desde la estación local.

## Configuración de entorno

Copiar .env.example (si existe) o crear un .env nuevo que contenga al menos estas variables:

- DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD (para conectar directamente a PostgreSQL).
- SSH_HOST, SSH_USER, SSH_PASSWORD (solo cuando se ejecuta localmente y se debe montar un túnel SSH).

La lógica de db_config.py elige automáticamente entre conexión directa y túnel SSH según qué variables estén definidas. Siempre cierra el túnel una vez terminado el script.

## Dependencias

Instalar el stack completo con:

```
pip install -r requirements.txt
```

## Estructura del proyecto

```
scraper-fantasy/
├── db_config.py          # Conexión elegante a PostgreSQL, opcional túnel SSH
├── logs/                # Directorio donde los scripts pueden guardar trazas
├── requirements.txt     # Dependencias listadas
└── scripts/
    ├── sync_plantillas.py
    ├── sync_estados.py
    └── sync_fixture.py
```

## Scripts disponibles

- scripts/sync_plantillas.py
  - Toma cada equipo de la liga chilena y raspa su plantilla en Transfermarkt.
  - Convierte posiciones a códigos internos (POR, MI, DC, etc.), obtiene dorsales y detecta estados (activo, lesionado, suspendido).
  - Inserta jugadores nuevos, actualiza dorsales/posiciones/estado y marca como transferidos a los que desaparecieron de Transfermarkt.
  - Imprime un reporte por equipo con agregados, omitidos y transferidos.

- scripts/sync_estados.py
  - Lee nuevamente las plantillas para detectar lesiones o sanciones por dorsal.
  - Solo actualiza el campo estado cuando hay discrepancias para evitar actualizaciones innecesarias.
  - Respeta suspensiones solo en competencias nacionales (no modifica sanciones por torneos externos).

- scripts/sync_fixture.py
  - Descarga el calendario oficial desde campeonatochileno.cl y mapea los nombres de equipos a los IDs internos.
  - Inserta partidos nuevos y actualiza fecha, goles y estado (programado o finalizado) cuando corresponda.
  - Llama a sync_jornadas_fechas para ajustar las jornadas con los partidos sincronizados.

## Ejecutar un script

1. Asegurar que .env esté configurado.
2. Activar el entorno virtual si aplica.
3. Ejecutar con Python:

```
python scripts/sync_plantillas.py
python scripts/sync_estados.py
python scripts/sync_fixture.py
```

Los scripts escriben su salida por consola; no crean artefactos adicionales salvo los logs que decida almacenar el equipo.

## Conexión a la base de datos

db_config.py expone conectar_db() (o obtener_conexion()) para reutilizar en los scripts. Crea un túnel SSH cuando SSH_HOST está presente y, en caso contrario, hace una conexión directa con los datos DB_*. Siempre cierra la conexión y el túnel al finalizar.
