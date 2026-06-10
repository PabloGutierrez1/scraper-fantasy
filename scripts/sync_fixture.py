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
        SELECT 
            j.jornada_id, 
            j.numero_jornada, 
            MIN(p.fecha_partido) as nueva_fecha_inicio, 
            MAX(p.fecha_partido) as nueva_fecha_fin,
            j.fecha_inicio as fecha_inicio_actual,
            j.fecha_fin as fecha_fin_actual
        FROM jornadas j
        LEFT JOIN partidos p ON j.jornada_id = p.jornada_id
        WHERE j.temporada_id = %s
        GROUP BY j.jornada_id, j.numero_jornada, j.fecha_inicio, j.fecha_fin
        ORDER BY j.numero_jornada
    """, (TEMPORADA_ID,))
    
    jornadas = cursor.fetchall()
    jornadas_actualizadas = 0
    
    for row in jornadas:
        jornada_id, numero_jornada, n_inicio, n_fin, a_inicio, a_fin = row
        
        if n_inicio and n_fin:
            if n_inicio != a_inicio or n_fin != a_fin:
                cursor.execute("""
                    UPDATE jornadas
                    SET fecha_inicio = %s, fecha_fin = %s
                    WHERE jornada_id = %s
                """, (n_inicio, n_fin, jornada_id))
                
                print(f"  Jornada {numero_jornada} Actualizada: {n_inicio.strftime('%d/%m %H:%M')} - {n_fin.strftime('%d/%m %H:%M')}")
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
    print("Cargando datos en memoria para optimizar consultas...")
    cursor.execute("SELECT equipo_id, nombre FROM equipos")
    equipos_db = {row[1]: row[0] for row in cursor.fetchall()}
    cursor.execute("""
        SELECT p.partido_id, p.equipo_local_id, p.equipo_visita_id, p.fecha_partido, 
               p.goles_local, p.goles_visita, p.estado, j.numero_jornada
        FROM partidos p
        JOIN jornadas j ON p.jornada_id = j.jornada_id
        WHERE p.temporada_id = %s
    """, (TEMPORADA_ID,))

    partidos_db = {}
    for row in cursor.fetchall():
        clave = (row[1], row[2])
        partidos_db[clave] = {
            'partido_id': row[0],
            'fecha': row[3],
            'goles_local': row[4],
            'goles_visita': row[5],
            'estado': row[6],
            'numero_jornada': row[7]
        }
    
    cursor.execute("""
        SELECT jornada_id, numero_jornada, fecha_inicio, fecha_fin
        FROM jornadas
        WHERE temporada_id = %s
        ORDER BY numero_jornada
    """, (TEMPORADA_ID,))
    jornadas_db = cursor.fetchall()
    
    partidos_insertados = 0
    partidos_actualizados = 0
    partidos_sin_cambios = 0

    partidos_html = soup.find_all('div', class_='anwp-fl-game')
    print(f"Encontrados {len(partidos_html)} partidos en la web...")
    
    for partido in partidos_html:
        try:
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
                continue

            equipo_local_id = equipos_db.get(nombre_local)
            equipo_visita_id = equipos_db.get(nombre_visita)
            
            if not equipo_local_id or not equipo_visita_id:
                continue

            fecha_data = partido.get('data-fl-game-datetime')
            if fecha_data:
                fecha_obj = datetime.fromisoformat(fecha_data.replace('Z', '+00:00'))
                fecha_obj = fecha_obj.replace(tzinfo=None)
            else:
                fecha_elem = partido.find('div', class_=lambda x: x and 'date' in str(x).lower())
                if not fecha_elem:
                    continue
                
                fecha_texto = fecha_elem.get_text(strip=True)
                fecha_obj = parsear_fecha(fecha_texto)
                if not fecha_obj:
                    continue

            score_wrapper = partido.find('div', class_='match-slim__scores-wrapper')
            goles_local = None
            goles_visita = None
            estado_web = 'programado'
            
            if score_wrapper:
                score_nums = score_wrapper.find_all('span', class_='match-slim__scores-number')
                if len(score_nums) >= 2:
                    gol_local_texto = score_nums[0].get_text(strip=True)
                    gol_visita_texto = score_nums[1].get_text(strip=True)

                    if gol_local_texto.isdigit() and gol_visita_texto.isdigit():
                        goles_local = int(gol_local_texto)
                        goles_visita = int(gol_visita_texto)
                        estado_web = 'finalizado'

            clave = (equipo_local_id, equipo_visita_id)
            partido_db = partidos_db.get(clave)
            
            if partido_db:
                partido_id = partido_db['partido_id']
                fecha_db = partido_db['fecha'].replace(tzinfo=None) if partido_db['fecha'] else None
                estado_db = partido_db['estado']
                numero_jornada = partido_db['numero_jornada']
                
                actualizar_resultado = (estado_web == 'finalizado' and estado_db == 'programado')
                actualizar_fecha = (fecha_db != fecha_obj)
                
                if actualizar_resultado or actualizar_fecha:
                    cambios = []
                    if actualizar_fecha: cambios.append("fecha")
                    if actualizar_resultado: cambios.append("resultado/estado")
                    
                    if estado_web == 'finalizado':
                        sql_update = """
                            UPDATE partidos 
                            SET fecha_partido = %s, goles_local = %s, goles_visita = %s, estado = %s
                            WHERE partido_id = %s
                        """
                        cursor.execute(sql_update, (fecha_obj, goles_local, goles_visita, estado_web, partido_id))
                        print(f"  J{numero_jornada} Actualizado: {nombre_local} {goles_local}-{goles_visita} {nombre_visita} [{estado_web}] - {', '.join(cambios)}")
                    else:
                        sql_update = """
                            UPDATE partidos 
                            SET fecha_partido = %s, estado = %s
                            WHERE partido_id = %s
                        """
                        cursor.execute(sql_update, (fecha_obj, estado_web, partido_id))
                        print(f"  J{numero_jornada} Actualizado: {nombre_local} vs {nombre_visita} [Programado] - {', '.join(cambios)}")
                    
                    partidos_actualizados += 1
                else:
                    partidos_sin_cambios += 1
            else:
                jornada_id = None
                numero_jornada = 0
                if jornadas_db:
                    mejor_jornada = min(jornadas_db, key=lambda x: abs((x[2] - fecha_obj).total_seconds()) if x[2] else float('inf'))
                    jornada_id = mejor_jornada[0]
                    numero_jornada = mejor_jornada[1]
                
                if not jornada_id:
                    continue

                sql_insert = """
                    INSERT INTO partidos 
                    (jornada_id, equipo_local_id, equipo_visita_id, fecha_partido, goles_local, goles_visita, estado, temporada_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql_insert, (jornada_id, equipo_local_id, equipo_visita_id, 
                                            fecha_obj, goles_local, goles_visita, estado_web, TEMPORADA_ID))
                
                resultado_msg = f" {goles_local}-{goles_visita}" if goles_local is not None else ""
                print(f"  J{numero_jornada} Insertado: {nombre_local} vs {nombre_visita} - {fecha_obj.strftime('%d/%m %H:%M')}{resultado_msg}")
                partidos_insertados += 1

        except Exception as e:
            print(f"  Error procesando partido: {e}")

    
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