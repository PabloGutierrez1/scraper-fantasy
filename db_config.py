import os
from dotenv import load_dotenv
import psycopg2

# Cargar variables de entorno desde .env
load_dotenv()

def conectar_db():
    """
    Establece conexión con la base de datos PostgreSQL.
    Lee las credenciales desde las variables de entorno (.env)
    
    Returns:
        connection: Objeto de conexión a PostgreSQL
        None: Si hay error en la conexión
    """
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            database=os.getenv('DB_NAME', 'liga_fantasy_db'),
            user=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '5432')
        )
        return conn
    except Exception as e:
        print(f"Error conectando a la BD: {e}")
        return None
