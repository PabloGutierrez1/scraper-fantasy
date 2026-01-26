import requests
from bs4 import BeautifulSoup
import psycopg2
from datetime import datetime
import re
import os
from dotenv import load_dotenv

load_dotenv()

URL_OFICIAL = "https://www.campeonatochileno.cl/ligas/liga-de-primera-mercado-libre/"
ANIO_TEMPORADA = 2026
TEMPORADA_ID = 1 
JORNADA_INICIO = 1

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
}

MAPEO_EQUIPOS = {
    "Universidad de Chile": "Universidad de Chile",
    "Colo Colo": "Colo Colo",
    "Universidad Católica": "Universidad Catolica",
    "U. Católica": "Universidad Catolica",
    "Audax Italiano": "Audax Italiano",
    "Palestino": "Palestino",
    "Coquimbo Unido": "Coquimbo Unido",
    "Everton": "Everton",
    "Unión La Calera": "Union La Calera",
    "Huachipato": "Huachipato",
    "Cobresal": "Cobresal",
    "O'Higgins": "O'Higgins",
    "Ñublense": "Nublense",
    "Deportes Limache": "Deportes Limache",
    "Deportes La Serena": "Deportes La Serena",
    "Deportes Concepción": "Deportes Concepcion",
    "Universidad de Concepción": "Universidad de Concepcion"
}

def conectar_db():
    try:
        conn = psycopg2.connect(
            host=os.getenv('DB_HOST'),
            database=os.getenv('DB_NAME'),
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            port=os.getenv('DB_PORT', '5432')
        )
        return conn
    except Exception as e:
        print(f"Error DB: {e}")
        return None

def parsear_fecha(texto_fecha):
    try:
        texto = texto_fecha.lower().replace("hrs", "").strip()
        match_con_hora = re.search(r'(\d+)\s+de\s+(\w+).*?(\d+):(\d+)', texto)
        
        if match_con_hora:
            dia, mes_nombre, hora, minuto = match_con_hora.groups()
            mes_num = MESES.get(mes_nombre, 1)
            return datetime(ANIO_TEMPORADA, mes_num, int(dia), int(hora), int(minuto))
        
        match_sin_hora = re.search(r'(\d+)\s+de\s+(\w+)', texto)
        if match_sin_hora:
            dia, mes_nombre = match_sin_hora.groups()
            mes_num = MESES.get(mes_nombre, 1)
            return datetime(ANIO_TEMPORADA, mes_num, int(dia), 0, 0)
            
    except Exception as e:
        print(f"Error parseando fecha '{texto_fecha}': {e}")
    
    return None

def parsear_resultado(texto):
    match_resultado = re.search(r'(\d+)\s*[-–]\s*(\d+)', texto)
    if match_resultado:
        goles_local = int(match_resultado.group(1))
        goles_visita = int(match_resultado.group(2))
        return goles_local, goles_visita, 'finalizado'
    return None, None, 'programado'

def sync_jornadas_fechas():
    print("Actualizando fechas de inicio y fin de jornadas...")
    
    conn = conectar_db()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT jornada_id, numero_jornada 
        FROM jornadas 
        WHERE temporada_id = %s 
        ORDER BY numero_jornada
    """, (TEMPORADA_ID,))
    
    jornadas = cursor.fetchall()
    jornadas_actualizadas = 0
    
    for jornada_id, numero_jornada in jornadas:
        cursor.execute("""
            SELECT MIN(fecha_partido), MAX(fecha_partido)
            FROM partidos
            WHERE jornada_id = %s
        """, (jornada_id,))
        
        resultado = cursor.fetchone()
        fecha_inicio = resultado[0]
        fecha_fin = resultado[1]
        
        if fecha_inicio and fecha_fin:
            cursor.execute("""
                UPDATE jornadas
                SET fecha_inicio = %s, fecha_fin = %s
                WHERE jornada_id = %s
            """, (fecha_inicio, fecha_fin, jornada_id))
            
            print(f"  Jornada {numero_jornada}: {fecha_inicio.strftime('%d/%m/%Y %H:%M')} - {fecha_fin.strftime('%d/%m/%Y %H:%M')}")
            jornadas_actualizadas += 1
        else:
            print(f"  Jornada {numero_jornada}: Sin partidos programados")
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*50}")
    print(f"Total jornadas actualizadas: {jornadas_actualizadas}")
    print(f"{'='*50}")

def sync_fixture():
    print("Sincronizando fixture oficial...")
    
    r = requests.get(URL_OFICIAL)
    if r.status_code != 200:
        print("Error conectando a la web oficial")
        return
        
    soup = BeautifulSoup(r.content, 'html.parser')
    
    conn = conectar_db()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    partidos_insertados = 0
    partidos_actualizados = 0
    partidos_sin_cambios = 0
    
    texto_completo = soup.get_text()
    lineas = texto_completo.split('\n')
    
    jornada_actual = JORNADA_INICIO
    i = 0
    partidos_procesados = []
    
    print(f"Analizando {len(lineas)} lineas...")
    
    while i < len(lineas):
        linea = lineas[i].strip()
        
        if re.search(r'^Fecha\s+(\d+)$', linea):
            match_jornada = re.search(r'^Fecha\s+(\d+)$', linea)
            if match_jornada:
                jornada_actual = int(match_jornada.group(1))
                print(f"\n=== Jornada {jornada_actual} ===")
                i += 1
                continue
        
        fecha_match = re.search(r'(\d+)\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)', linea, re.IGNORECASE)
        if fecha_match:
            fecha_texto = linea
            hora_texto = ""
            
            for k in range(i+1, min(i+10, len(lineas))):
                hora_match = re.search(r'(\d+):(\d+)\s+hrs', lineas[k])
                if hora_match:
                    hora_texto = lineas[k].strip()
                    break
            
            fecha_completa = f"{fecha_texto} {hora_texto}".strip()
            
            equipos_encontrados = []
            for j in range(i+1, min(i+30, len(lineas))):
                linea_check = lineas[j].strip()
                
                for nombre_web, nombre_db in MAPEO_EQUIPOS.items():
                    if linea_check == nombre_web:
                        equipos_encontrados.append(nombre_db)
                        break
                
                if len(equipos_encontrados) >= 2:
                    break
            
            if len(equipos_encontrados) >= 2:
                local = equipos_encontrados[0]
                visita = equipos_encontrados[1]
                
                partido_key = f"{local}|{visita}"
                if partido_key in partidos_procesados:
                    i += 1
                    continue
                
                partidos_procesados.append(partido_key)
                
                fecha_obj = parsear_fecha(fecha_completa)
                if not fecha_obj:
                    print(f"  Error parseando fecha: {fecha_completa}")
                    i += 1
                    continue
                
                try:
                    cursor.execute("SELECT equipo_id FROM equipos WHERE nombre = %s", (local,))
                    res_local = cursor.fetchone()
                    cursor.execute("SELECT equipo_id FROM equipos WHERE nombre = %s", (visita,))
                    res_visita = cursor.fetchone()
                    
                    if not res_local or not res_visita:
                        print(f"  Equipos no encontrados en DB: {local} o {visita}")
                        i += 1
                        continue
                    
                    equipo_local_id = res_local[0]
                    equipo_visita_id = res_visita[0]
                    
                    cursor.execute("SELECT jornada_id FROM jornadas WHERE temporada_id = %s AND numero_jornada = %s", 
                                 (TEMPORADA_ID, jornada_actual))
                    res_jornada = cursor.fetchone()
                    
                    if not res_jornada:
                        print(f"  Jornada {jornada_actual} no encontrada en DB")
                        i += 1
                        continue
                    
                    jornada_id = res_jornada[0]
                    
                    sql_find = """
                        SELECT partido_id, fecha_partido, goles_local, goles_visita, estado 
                        FROM partidos 
                        WHERE equipo_local_id = %s AND equipo_visita_id = %s
                    """
                    cursor.execute(sql_find, (equipo_local_id, equipo_visita_id))
                    partido_existente = cursor.fetchone()
                    
                    goles_local, goles_visita, estado = None, None, 'programado'
                    
                    if partido_existente:
                        partido_id = partido_existente[0]
                        fecha_db = partido_existente[1]
                        goles_local_db = partido_existente[2]
                        goles_visita_db = partido_existente[3]
                        estado_db = partido_existente[4]
                        
                        cambios = []
                        
                        if fecha_db != fecha_obj:
                            cambios.append("fecha")
                        
                        if goles_local is not None and goles_local_db != goles_local:
                            cambios.append("goles_local")
                        
                        if goles_visita is not None and goles_visita_db != goles_visita:
                            cambios.append("goles_visita")
                        
                        if estado != estado_db:
                            cambios.append("estado")
                        
                        if cambios:
                            if goles_local is not None and goles_visita is not None:
                                sql_update = """
                                    UPDATE partidos 
                                    SET fecha_partido = %s, goles_local = %s, goles_visita = %s, estado = %s
                                    WHERE partido_id = %s
                                """
                                cursor.execute(sql_update, (fecha_obj, goles_local, goles_visita, estado, partido_id))
                            else:
                                sql_update = """
                                    UPDATE partidos 
                                    SET fecha_partido = %s, estado = %s
                                    WHERE partido_id = %s
                                """
                                cursor.execute(sql_update, (fecha_obj, estado, partido_id))
                            
                            print(f"  Actualizado: {local} vs {visita} - {', '.join(cambios)}")
                            partidos_actualizados += 1
                        else:
                            partidos_sin_cambios += 1
                    else:
                        sql_insert = """
                            INSERT INTO partidos 
                            (jornada_id, equipo_local_id, equipo_visita_id, fecha_partido, goles_local, goles_visita, estado)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(sql_insert, (jornada_id, equipo_local_id, equipo_visita_id, 
                                                   fecha_obj, goles_local, goles_visita, estado))
                        
                        print(f"  Insertado: {local} vs {visita} - {fecha_obj.strftime('%d/%m %H:%M')}")
                        partidos_insertados += 1
                
                except Exception as e:
                    print(f"  Error procesando {local} vs {visita}: {e}")
        
        i += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*50}")
    print(f"Resumen:")
    print(f"  Insertados: {partidos_insertados}")
    print(f"  Actualizados: {partidos_actualizados}")
    print(f"  Sin cambios: {partidos_sin_cambios}")
    print(f"  Total: {partidos_insertados + partidos_actualizados + partidos_sin_cambios}")
    print(f"{'='*50}")

if __name__ == "__main__":
    print("\n" + "="*50)
    print("SINCRONIZADOR DE FIXTURE - EJECUCIÓN AUTOMÁTICA")
    print("="*50)
    print()
    
    sync_fixture()
    print()
    sync_jornadas_fechas()