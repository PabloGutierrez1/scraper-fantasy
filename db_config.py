import os
import psycopg2
from dotenv import load_dotenv
from sshtunnel import SSHTunnelForwarder

load_dotenv()

# Variables globales para mantener el túnel vivo si es necesario
tunnel = None


def _es_host_supabase(db_host):
    if not db_host:
        return False
    return 'supabase.com' in db_host.lower()

def obtener_conexion():
    """
    Crea un túnel SSH automático y conecta a la base de datos.
    Funciona tanto en local (PC) como en producción (VPS).
    """
    global tunnel
    
    # Datos de la DB
    db_host = os.getenv('DB_HOST')
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_pass = os.getenv('DB_PASSWORD')
    db_port = int(os.getenv('DB_PORT', 5432))

    # Datos SSH (Solo existen en tu PC)
    ssh_host = os.getenv('SSH_HOST')
    ssh_user = os.getenv('SSH_USER')
    ssh_pass = os.getenv('SSH_PASSWORD')
    ssh_port = int(os.getenv('SSH_PORT', 22))

    usar_tunel_ssh = bool(ssh_host) and not _es_host_supabase(db_host)
    
    # Lógica inteligente:
    # Si tenemos datos SSH, significa que estamos en TU PC -> Usamos Túnel
    # Si NO tenemos datos SSH, significa que el script corre en el VPS -> Conexión Directa
    
    if usar_tunel_ssh:
        try:
            # Iniciamos el túnel solo si no existe
            if tunnel is None:
                tunnel = SSHTunnelForwarder(
                    (ssh_host, ssh_port),
                    ssh_username=ssh_user,
                    ssh_password=ssh_pass,
                    remote_bind_address=('127.0.0.1', 5432)
                )
                tunnel.start()
                print(f"[OK] Tunel SSH abierto exitosamente en el puerto {tunnel.local_bind_port}")

            # Nos conectamos al puerto local que creó el túnel
            conn = psycopg2.connect(
                host='127.0.0.1',
                port=tunnel.local_bind_port, # Puerto dinámico del túnel
                user=db_user,
                password=db_pass,
                database=db_name
            )
            return conn

        except Exception as e:
            print(f"[ERROR] Error creando el tunel SSH: {e}")
            return None
    
    else:
        try:
            connect_kwargs = {
                'host': db_host,
                'port': db_port,
                'user': db_user,
                'password': db_pass,
                'database': db_name,
            }

            if _es_host_supabase(db_host):
                connect_kwargs['sslmode'] = 'require'

            conn = psycopg2.connect(
                **connect_kwargs
            )
            return conn
        except Exception as e:
            print(f"[ERROR] Error de conexion directa: {e}")
            return None

def cerrar_todo(conn):
    global tunnel
    if conn:
        conn.close()
    if tunnel:
        tunnel.stop()
        tunnel = None
        print("[CERRADO] Tunel cerrado")


def conectar_db():
    """Mantiene compatibilidad con los scripts existentes."""
    return obtener_conexion()