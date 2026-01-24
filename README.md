# Scrapers Fantasy - Liga Chilena

Sistema de scrapers para recolectar información de jugadores y equipos de la liga chilena de fútbol.

## 📁 Estructura del Proyecto

```
scrapers-fantasy/
├── .env                      # Variables de entorno (NO subir a GitHub)
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

## ⚙️ Configuración Inicial

1. **Clonar el repositorio**
   ```bash
   git clone <tu-repositorio>
   cd scrapers-fantasy
   ```

2. **Crear entorno virtual**
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variables de entorno**
   
   Crea un archivo `.env` en la raíz del proyecto con tus credenciales:
   ```env
   DB_HOST=localhost
   DB_NAME=liga_fantasy_db
   DB_USER=tu_usuario
   DB_PASSWORD=tu_contraseña
   DB_PORT=5432
   ```

## 🚀 Uso

### Sincronización de Plantillas

```bash
python scripts/sync_plantillas.py
```

**Modos disponibles:**
- **Modo Interactivo (1)**: Permite elegir equipos específicos uno por uno
- **Modo Automático (2)**: Sincroniza todos los equipos secuencialmente

### Para Raspberry Pi

Para ejecutar automáticamente en Raspberry Pi:

1. Sigue las instrucciones en los comentarios del código
2. Elimina la función `modo_interactivo()`
3. Simplifica el `if __name__ == "__main__":` para ejecutar solo `ejecutar_scraper()`

## 🔒 Seguridad

- **NUNCA** subas el archivo `.env` a GitHub
- Las credenciales están protegidas mediante variables de entorno
- El archivo `.gitignore` está configurado para proteger información sensible

## 📝 Scripts Disponibles

- `sync_plantillas.py`: Sincroniza plantillas de todos los equipos desde Transfermarkt
- `sync_estados.py`: Actualiza estados de jugadores (lesionados, suspendidos) *(Por implementar)*
- `procesar_partido.py`: Procesa estadísticas de partidos *(Por implementar)*
- `sync_calendario.py`: Sincroniza calendario de partidos *(Por implementar)*

## 📦 Dependencias

- `requests`: Peticiones HTTP
- `beautifulsoup4`: Parsing de HTML
- `psycopg2-binary`: Conexión a PostgreSQL
- `python-dotenv`: Carga de variables de entorno

## 🤝 Contribuir

1. Crear una rama para tu feature
2. Realizar cambios
3. Hacer commit con mensajes descriptivos
4. Crear Pull Request

---

**Nota**: Este proyecto es parte de un sistema de fantasy football para la liga chilena.
