# Scrapers Fantasy - Liga Chilena

Sistema de scrapers para recolectar información de jugadores y equipos de la liga chilena de fútbol.

## 📁 Estructura del Proyecto

```
scrapers-fantasy/
├── .env                      # Variables de entorno
├── .gitignore               # Archivos ignorados por Git
├── requirements.txt         # Dependencias de Python
├── db_config.py            # Configuración de base de datos
├── scripts/
│   ├── sync_plantillas.py   # Sincronización de plantillas de equipos
│   ├── sync_estados.py      # Actualización de estados de jugadores
│   ├── procesar_partido.py  # Procesamiento de partidos
│   └── sync_calendario.py   # Sincronización de calendario
└── logs/                    # Directorio de logs
```



## 📝 Scripts Disponibles

- `sync_plantillas.py`: Sincroniza plantillas de todos los equipos desde Transfermarkt
- `sync_estados.py`: Actualiza estados de jugadores (lesionados, suspendidos)
- `sync_fixture.py`: Sincroniza calendario de partidos

## 📦 Dependencias

- `requests`: Peticiones HTTP
- `beautifulsoup4`: Parsing de HTML
- `psycopg2-binary`: Conexión a PostgreSQL
- `python-dotenv`: Carga de variables de entorno

**Nota**: Este proyecto es parte de un sistema de fantasy football para la liga chilena.
