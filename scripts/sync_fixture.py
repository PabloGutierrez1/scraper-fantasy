import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from db_config import conectar_db

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
    match_resultado = re.search(r'(\d+)\s*[-–]?\s*(\d+)', texto)
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

    partidos_html = soup.find_all('div', class_='anwp-fl-game')
    print(f"Encontrados {len(partidos_html)} partidos en la web...")
    
    for partido in partidos_html:
        equipo_local_elem = partido.find('div', class_='match-slim__team-home-title')
        equipo_visita_elem = partido.find('div', class_=lambda x: x and 'team-away-title' in str(x) or x and 'team_away' in str(x))

        if not equipo_visita_elem:
            equipo_visita_elem = partido.find('div', class_='match-slim__team-away-title')
        
        if not equipo_local_elem or not equipo_visita_elem:
            continue
        
        nombre_local_web = equipo_local_elem.get_text(strip=True)
        nombre_visita_web = equipo_visita_elem.get_text(strip=True)

        nombre_local = MAPEO_EQUIPOS.get(nombre_local_web)
        nombre_visita = MAPEO_EQUIPOS.get(nombre_visita_web)
        
        if not nombre_local or not nombre_visita:
            print(f"  Equipos no mapeados: {nombre_local_web} vs {nombre_visita_web}")
            continue

        fecha_data = partido.get('data-fl-game-datetime')
        if fecha_data:
            from datetime import datetime
            fecha_obj = datetime.fromisoformat(fecha_data.replace('Z', '+00:00'))
        else:
            fecha_elem = partido.find('div', class_=lambda x: x and 'date' in str(x).lower())
            if not fecha_elem:
                print(f"  Sin fecha: {nombre_local} vs {nombre_visita}")
                continue
            
            fecha_texto = fecha_elem.get_text(strip=True)
            fecha_obj = parsear_fecha(fecha_texto)
            if not fecha_obj:
                print(f"  Error parseando fecha '{fecha_texto}': {nombre_local} vs {nombre_visita}")
                continue

        score_wrapper = partido.find('div', class_='match-slim__scores-wrapper')
        goles_local = None
        goles_visita = None
        estado = 'programado'
        
        if score_wrapper:
            score_nums = score_wrapper.find_all('span', class_='match-slim__scores-number')
            if len(score_nums) >= 2:
                gol_local_texto = score_nums[0].get_text(strip=True)
                gol_visita_texto = score_nums[1].get_text(strip=True)

                if gol_local_texto.isdigit() and gol_visita_texto.isdigit():
                    goles_local = int(gol_local_texto)
                    goles_visita = int(gol_visita_texto)
                    estado = 'finalizado'

        try:
            cursor.execute("SELECT equipo_id FROM equipos WHERE nombre = %s", (nombre_local,))
            res_local = cursor.fetchone()
            cursor.execute("SELECT equipo_id FROM equipos WHERE nombre = %s", (nombre_visita,))
            res_visita = cursor.fetchone()
            
            if not res_local or not res_visita:
                print(f"  Equipos no encontrados en DB: {nombre_local} o {nombre_visita}")
                continue
            
            equipo_local_id = res_local[0]
            equipo_visita_id = res_visita[0]

            sql_find = """
                SELECT p.partido_id, p.jornada_id, j.numero_jornada, p.fecha_partido, 
                        p.goles_local, p.goles_visita, p.estado 
                FROM partidos p
                JOIN jornadas j ON p.jornada_id = j.jornada_id
                WHERE p.equipo_local_id = %s AND p.equipo_visita_id = %s AND p.temporada_id = %s
            """
            cursor.execute(sql_find, (equipo_local_id, equipo_visita_id, TEMPORADA_ID))
            partido_existente = cursor.fetchone()
            
            if partido_existente:
                partido_id = partido_existente[0]
                jornada_id = partido_existente[1]
                numero_jornada = partido_existente[2]
                fecha_db = partido_existente[3]
                goles_local_db = partido_existente[4]
                goles_visita_db = partido_existente[5]
                estado_db = partido_existente[6]
                
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
                    
                    resultado_msg = f" {goles_local}-{goles_visita}" if goles_local is not None else ""
                    estado_msg = f" [{estado}]" if estado == 'finalizado' else ""
                    print(f"  J{numero_jornada} Actualizado: {nombre_local} vs {nombre_visita}{resultado_msg}{estado_msg} - {', '.join(cambios)}")
                    partidos_actualizados += 1
                else:
                    partidos_sin_cambios += 1
            else:
                cursor.execute("""
                    SELECT jornada_id, numero_jornada, fecha_inicio, fecha_fin
                    FROM jornadas
                    WHERE temporada_id = %s
                    ORDER BY ABS(EXTRACT(EPOCH FROM (fecha_inicio - %s)))
                    LIMIT 1
                """, (TEMPORADA_ID, fecha_obj))
                res_jornada = cursor.fetchone()
                
                if not res_jornada:
                    print(f"  No se encontró jornada para fecha {fecha_obj}")
                    continue
                
                jornada_id = res_jornada[0]
                numero_jornada = res_jornada[1]
                sql_insert = """
                    INSERT INTO partidos 
                    (jornada_id, equipo_local_id, equipo_visita_id, fecha_partido, goles_local, goles_visita, estado, temporada_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql_insert, (jornada_id, equipo_local_id, equipo_visita_id, 
                                            fecha_obj, goles_local, goles_visita, estado, TEMPORADA_ID))
                
                resultado_msg = f" {goles_local}-{goles_visita}" if goles_local is not None else ""
                estado_msg = f" [{estado}]" if estado == 'finalizado' else ""
                print(f"  J{numero_jornada} Insertado: {nombre_local} vs {nombre_visita} - {fecha_obj.strftime('%d/%m %H:%M')}{resultado_msg}{estado_msg}")
                partidos_insertados += 1
        
        except Exception as e:
            print(f"  Error procesando {nombre_local} vs {nombre_visita}: {e}")
    
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