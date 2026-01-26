import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from bs4 import BeautifulSoup
import time
import random
import re
from db_config import conectar_db

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

EQUIPOS = [
    {"id_db": 1, "nombre": "Universidad de Chile", "url": "https://www.transfermarkt.es/universidad-de-chile/kader/verein/1037/saison_id/2025/plus/1"},
    {"id_db": 2, "nombre": "Colo Colo", "url": "https://www.transfermarkt.es/csd-colo-colo/kader/verein/2433/saison_id/2025/plus/1"},
    {"id_db": 3, "nombre": "Universidad Católica", "url": "https://www.transfermarkt.es/cd-universidad-catolica/kader/verein/3277/plus/1"},
    {"id_db": 4, "nombre": "Palestino", "url": "https://www.transfermarkt.es/cd-palestino/kader/verein/6536/saison_id/2025/plus/1"},
    {"id_db": 5, "nombre": "O'Higgins", "url": "https://www.transfermarkt.es/cd-ohiggins/kader/verein/11470/saison_id/2025/plus/1"},
    {"id_db": 6, "nombre": "Everton", "url": "https://www.transfermarkt.es/cd-everton/kader/verein/7020/plus/1"},
    {"id_db": 7, "nombre": "Union La Calera", "url": "https://www.transfermarkt.es/union-la-calera/kader/verein/20514/plus/1"},
    {"id_db": 8, "nombre": "Huachipato", "url": "https://www.transfermarkt.es/cd-huachipato/kader/verein/6368/saison_id/2025/plus/1"},
    {"id_db": 9, "nombre": "Audax Italiano", "url": "https://www.transfermarkt.es/audax-italiano/kader/verein/6363/plus/1"},
    {"id_db": 10, "nombre": "Coquimbo Unido", "url": "https://www.transfermarkt.es/coquimbo-unido/kader/verein/11004/plus/1"},
    {"id_db": 11, "nombre": "Cobresal", "url": "https://www.transfermarkt.es/cd-cobresal/kader/verein/17482/plus/1"},
    {"id_db": 12, "nombre": "Ñublense", "url": "https://www.transfermarkt.es/cd-nublense/kader/verein/14723/plus/1"},
    {"id_db": 13, "nombre": "Deportes Limache", "url": "https://www.transfermarkt.es/club-de-deportes-limache/kader/verein/26697/plus/1"},
    {"id_db": 14, "nombre": "Deportes La Serena", "url": "https://www.transfermarkt.es/deportes-la-serena/kader/verein/5747/plus/1"},
    {"id_db": 15, "nombre": "Deportes Concepción", "url": "https://www.transfermarkt.es/deportes-concepcion/kader/verein/14604/plus/1"},
    {"id_db": 16, "nombre": "Universidad de Concepción", "url": "https://www.transfermarkt.es/universidad-concepcion/kader/verein/5622/plus/1"},
]

def obtener_dorsal(fila):
    div_num = fila.find('div', class_='rn_nummer')
    if div_num:
        texto = div_num.text.strip()
        if texto and texto != '-': return texto
    td_num = fila.find('td', class_=lambda value: value and 'rueckennummer' in value)
    if td_num:
        match = re.search(r'\d+', td_num.text.strip())
        if match: return match.group()
    return '0'

def obtener_estado_actualizado(fila):
    celda = fila.find('td', class_='posrela')
    if not celda: return 'activo'
    
    avisos = celda.find_all('span', class_='icons_sprite')
    for aviso in avisos:
        clases = aviso.get('class', [])
        titulo = aviso.get('title', '').lower()
        
        if 'verletzt-table' in clases: return 'lesionado'
        if any(w in titulo for w in ['lesi', 'baja', 'enfermo', 'cirug', 'desgarro', 'esguince']): 
            return 'lesionado'

        if ('roja' in titulo or 'sanci' in titulo or 'suspen' in titulo):
            competencias_externas = ['copa chile', 'libertadores', 'sudamericana', 'supercopa', 'recopa', 'amistoso']
            
            es_externa = any(comp in titulo for comp in competencias_externas)
            
            if not es_externa:
                return 'suspendido'
                
    return 'activo'

def sincronizar_estados_equipo(equipo, conn, cursor):
    print(f"Revisando estados: {equipo['nombre']}...")
    try:
        r = requests.get(equipo['url'], headers=HEADERS)
        if r.status_code != 200:
            print(f"   Error HTTP {r.status_code}")
            return
        
        soup = BeautifulSoup(r.content, 'html.parser')
        tabla = soup.find('table', class_='items')
        if not tabla: return

        filas = tabla.find_all('tr', class_=['odd', 'even'])
        cambios = 0
        
        for fila in filas:
            try:
                dorsal = int(obtener_dorsal(fila))
                if dorsal == 0: continue

                nuevo_estado = obtener_estado_actualizado(fila)
                
                celda_info = fila.find('td', class_='posrela')
                tabla_info = celda_info.find('table')
                nombre = tabla_info.find('a').text.strip()

                cursor.execute("""
                    SELECT estado, nombre FROM jugadores 
                    WHERE equipo_id = %s AND dorsal = %s
                """, (equipo['id_db'], dorsal))
                
                resultado = cursor.fetchone()
                
                if not resultado:
                    continue
                
                estado_actual_db = resultado[0]
                
                if estado_actual_db != nuevo_estado:
                    cursor.execute("""
                        UPDATE jugadores 
                        SET estado = %s 
                        WHERE equipo_id = %s AND dorsal = %s
                    """, (nuevo_estado, equipo['id_db'], dorsal))
                    
                    print(f"   CAMBIO: {nombre} | {estado_actual_db} -> {nuevo_estado}")
                    cambios += 1
                
            except Exception:
                continue
        
        conn.commit()
        if cambios > 0:
            print(f"   Se actualizaron {cambios} jugadores en {equipo['nombre']}.")
        
        time.sleep(random.uniform(2, 4))

    except Exception as e:
        print(f"   Error procesando equipo: {e}")
        conn.rollback()

def ejecutar_sincronizacion():
    conn = conectar_db()
    if not conn: return
    cursor = conn.cursor()

    print(f"\nINICIANDO SINCRONIZACIÓN DE ESTADOS (LESIONES/SANCIONES)\n")

    for equipo in EQUIPOS:
        sincronizar_estados_equipo(equipo, conn, cursor)

    cursor.close()
    conn.close()
    print(f"\nPROCESO TERMINADO. Estados actualizados.")

if __name__ == "__main__":
    ejecutar_sincronizacion()