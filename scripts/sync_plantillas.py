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

def limpiar_posicion(texto_sucio):
    texto = texto_sucio.lower()
    mapa = {
        'portero': 'POR', 'defensa central': 'DFC', 'lateral izquierdo': 'LI', 'lateral derecho': 'LD',
        'pivote': 'MCD', 'mediocentro': 'MC', 'mediocentro ofensivo': 'MCO',
        'interior izquierdo': 'MI', 'interior derecho': 'MD',
        'extremo izquierdo': 'EI', 'extremo derecho': 'ED',
        'mediapunta': 'MCO', 'delantero centro': 'DC', 'segundo delantero': 'SD'
    }
    for largo, corto in mapa.items():
        if largo in texto: return corto
    return 'MC'

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

LIGA_KEYWORDS = ('liga de primera', 'primera división', 'campeonato nacional', 'liga chilena', 'liga profesional')
def es_suspension_de_liga(titulo):
    texto = (titulo or '').lower()
    return any(keyword in texto for keyword in LIGA_KEYWORDS)

def obtener_estado(fila):
    celda = fila.find('td', class_='posrela')
    if not celda: return 'activo'
    avisos = celda.find_all('span', class_='icons_sprite')
    for aviso in avisos:
        clases = aviso.get('class', [])
        titulo = aviso.get('title', '').lower()
        if 'verletzt-table' in clases: return 'lesionado'
        if any(w in titulo for w in ['lesi', 'baja', 'enfermo', 'cirug', 'desgarro']): return 'lesionado'

        if ('roja' in titulo or 'sanci' in titulo or 'suspen' in titulo):
            competencias_externas = ['copa chile', 'libertadores', 'sudamericana', 'supercopa', 'recopa', 'amistoso']
            es_externa = any(comp in titulo for comp in competencias_externas)
            if not es_externa:
                return 'suspendido'
    return 'activo'


def marcar_transferido_en_otras_plantillas(cursor, nombre, equipo_id):
    cursor.execute(
        """
        UPDATE jugadores
        SET estado = 'transferido', precio_actual = 0
        WHERE nombre = %s AND equipo_id != %s AND estado != 'transferido'
        """,
        (nombre, equipo_id)
    )
    return cursor.rowcount


def reasignar_referencias_jugador(cursor, jugador_id_origen, jugador_id_destino):
    cursor.execute(
        """
        DELETE FROM estadisticas_partido dup
        USING estadisticas_partido can
        WHERE dup.jugador_id = %s
          AND can.jugador_id = %s
          AND dup.partido_id = can.partido_id
        """,
        (jugador_id_origen, jugador_id_destino)
    )
    cursor.execute(
        """
        UPDATE estadisticas_partido
        SET jugador_id = %s
        WHERE jugador_id = %s
        """,
        (jugador_id_destino, jugador_id_origen)
    )

    cursor.execute(
        """
        DELETE FROM jugadores_alineacion dup
        USING jugadores_alineacion can
        WHERE dup.jugador_id = %s
          AND can.jugador_id = %s
          AND dup.alineacion_jornada_id = can.alineacion_jornada_id
        """,
        (jugador_id_origen, jugador_id_destino)
    )
    cursor.execute(
        """
        UPDATE jugadores_alineacion
        SET jugador_id = %s
        WHERE jugador_id = %s
        """,
        (jugador_id_destino, jugador_id_origen)
    )

    cursor.execute(
        """
        UPDATE plantilla_fantasy
        SET jugador_id = %s
        WHERE jugador_id = %s
        """,
        (jugador_id_destino, jugador_id_origen)
    )
    cursor.execute(
        """
        UPDATE resumen_temporada
        SET jugador_id = %s
        WHERE jugador_id = %s
        """,
        (jugador_id_destino, jugador_id_origen)
    )
    cursor.execute(
        """
        UPDATE tienda_diaria
        SET jugador_id = %s
        WHERE jugador_id = %s
        """,
        (jugador_id_destino, jugador_id_origen)
    )

    cursor.execute(
        """
        DELETE FROM jugadores
        WHERE jugador_id = %s
        """,
        (jugador_id_origen,)
    )


def upsert_jugador_unico(cursor, equipo_id, nombre, dorsal, pos_codigo, estado):
    cursor.execute(
        """
        SELECT
            j.jugador_id,
            j.equipo_id,
            j.dorsal,
            j.posicion,
            j.estado,
            j.precio_actual,
            COALESCE(owners.total, 0) AS owners
        FROM jugadores j
        LEFT JOIN (
            SELECT jugador_id, COUNT(*) AS total
            FROM plantilla_fantasy
            GROUP BY jugador_id
        ) owners ON owners.jugador_id = j.jugador_id
        WHERE j.nombre = %s
        ORDER BY COALESCE(owners.total, 0) DESC, j.jugador_id ASC
        """,
        (nombre,)
    )

    filas = cursor.fetchall()
    if not filas:
        insert_query = """
            INSERT INTO jugadores
            (equipo_id, nombre, posicion, dorsal, precio_actual, tier, estado, foto_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_query, (equipo_id, nombre, pos_codigo, dorsal, 10000000, 'B', estado, None))
        return 'insertado', [f"nuevo jugador en equipo {equipo_id}"]

    jugador_id_canonico, equipo_bd, dorsal_bd, pos_bd, estado_bd, precio_bd, _owners = filas[0]
    for fila in filas[1:]:
        jugador_id_duplicado = fila[0]
        reasignar_referencias_jugador(cursor, jugador_id_duplicado, jugador_id_canonico)

    precio_nuevo = precio_bd if precio_bd and precio_bd > 0 else 10000000
    cursor.execute(
        """
        UPDATE jugadores
        SET equipo_id = %s,
            dorsal = %s,
            posicion = %s,
            estado = %s,
            precio_actual = %s
        WHERE jugador_id = %s
        """,
        (equipo_id, dorsal, pos_codigo, estado, precio_nuevo, jugador_id_canonico)
    )

    cambios = []
    if equipo_bd != equipo_id:
        cambios.append(f"equipo {equipo_bd}→{equipo_id}")
    if dorsal_bd != dorsal:
        cambios.append(f"dorsal {dorsal_bd}→{dorsal}")
    if pos_bd != pos_codigo:
        cambios.append(f"pos {pos_bd}→{pos_codigo}")
    if estado_bd != estado:
        cambios.append(f"estado {estado_bd}→{estado}")
    if len(filas) > 1:
        cambios.append(f"duplicados fusionados: {len(filas) - 1}")

    if cambios:
        return 'actualizado', cambios
    return 'omitido', []


def consolidar_duplicados_historicos(cursor):
    cursor.execute(
        """
        SELECT nombre
        FROM jugadores
        GROUP BY nombre
        HAVING COUNT(*) > 1
        ORDER BY nombre
        """
    )
    nombres_duplicados = [fila[0] for fila in cursor.fetchall()]
    if not nombres_duplicados:
        return 0

    duplicados_fusionados = 0
    for nombre in nombres_duplicados:
        cursor.execute(
            """
            SELECT
                j.jugador_id,
                j.equipo_id,
                j.dorsal,
                j.posicion,
                j.estado,
                j.precio_actual,
                COALESCE(owners.total, 0) AS owners
            FROM jugadores j
            LEFT JOIN (
                SELECT jugador_id, COUNT(*) AS total
                FROM plantilla_fantasy
                GROUP BY jugador_id
            ) owners ON owners.jugador_id = j.jugador_id
            WHERE j.nombre = %s
            ORDER BY COALESCE(owners.total, 0) DESC, j.jugador_id ASC
            """,
            (nombre,)
        )
        filas = cursor.fetchall()

        fila_canonica = filas[0]
        jugador_id_canonico = fila_canonica[0]

        fila_datos = sorted(
            filas,
            key=lambda f: (f[4] != 'transferido', f[0]),
            reverse=True
        )[0]

        for fila in filas[1:]:
            jugador_id_duplicado = fila[0]
            reasignar_referencias_jugador(cursor, jugador_id_duplicado, jugador_id_canonico)
            duplicados_fusionados += 1

        precio_canonico = fila_canonica[5]
        precio_datos = fila_datos[5]
        precio_final = precio_datos if precio_datos and precio_datos > 0 else precio_canonico
        if not precio_final or precio_final <= 0:
            precio_final = 10000000

        cursor.execute(
            """
            UPDATE jugadores
            SET equipo_id = %s,
                dorsal = %s,
                posicion = %s,
                estado = %s,
                precio_actual = %s
            WHERE jugador_id = %s
            """,
            (fila_datos[1], fila_datos[2], fila_datos[3], fila_datos[4], precio_final, jugador_id_canonico)
        )

    return duplicados_fusionados

def actualizar_equipo(equipo, conn, cursor):
    print(f"Verificando: {equipo['nombre']}...")
    try:
        r = requests.get(equipo['url'], headers=HEADERS)
        if r.status_code != 200:
            print(f"Error: No se pudo acceder a la URL (código {r.status_code})")
            return 0, 0, 0
        
        soup = BeautifulSoup(r.content, 'html.parser')
        tabla = soup.find('table', class_='items')
        if not tabla:
            print("No se encontró la tabla de jugadores")
            return 0, 0, 0

        filas = tabla.find_all('tr', class_=['odd', 'even'])
        nombres_actuales = set()
        agregados = 0
        omitidos = 0
        
        for fila in filas:
            try:
                dorsal = int(obtener_dorsal(fila))
                
                celda_info = fila.find('td', class_='posrela')
                tabla_info = celda_info.find('table')
                trs_info = tabla_info.find_all('tr')
                
                nombre = trs_info[0].find('a').text.strip()
                nombres_actuales.add(nombre)
                pos_texto = trs_info[1].text.strip()
                pos_codigo = limpiar_posicion(pos_texto)
                estado = obtener_estado(fila)

                accion, cambios = upsert_jugador_unico(
                    cursor,
                    equipo['id_db'],
                    nombre,
                    dorsal,
                    pos_codigo,
                    estado
                )

                if accion == 'insertado':
                    agregados += 1
                    print(f"Agregado nuevo: {nombre} ({pos_codigo}) - Dorsal {dorsal}")
                elif accion == 'actualizado':
                    agregados += 1
                    print(f"Actualizado {nombre}: {', '.join(cambios)}")
                else:
                    omitidos += 1

                transferidos_otros = marcar_transferido_en_otras_plantillas(cursor, nombre, equipo['id_db'])
                if transferidos_otros:
                    print(f"  -> {nombre}: marcado como transferido en {transferidos_otros} equipo(s) anterior(es)")
            except Exception as e:
                try:
                    dorsal_error = obtener_dorsal(fila)
                    print(f"Error procesando jugador con dorsal {dorsal_error}: {e}")
                except:
                    print(f"Error procesando fila (dorsal desconocido): {e}")
                continue

        cursor.execute("""
            SELECT nombre, dorsal FROM jugadores 
            WHERE equipo_id = %s
        """, (equipo['id_db'],))
        
        jugadores_bd = cursor.fetchall()
        transferidos = 0
        
        for nombre_bd, dorsal_bd in jugadores_bd:
            if nombre_bd not in nombres_actuales:
                cursor.execute("""
                    UPDATE jugadores 
                    SET 
                        estado = 'transferido',
                        precio_actual = 0
                    WHERE equipo_id = %s AND nombre = %s AND estado != 'transferido'
                """, (equipo['id_db'], nombre_bd))
                if cursor.rowcount:
                    transferidos += 1
                    print(f"Transferido (ya no en plantilla): {nombre_bd} - Dorsal {dorsal_bd}")
        
        conn.commit() 
        print(f"Reporte {equipo['nombre']}: {agregados} nuevos, {omitidos} existentes, {transferidos} transferidos.")
        time.sleep(random.uniform(2, 4))
        return agregados, omitidos, transferidos

    except Exception as e:
        print(f"Error con equipo {equipo['nombre']}: {e}")
        conn.rollback()
        return 0, 0, 0

def ejecutar_scraper():
    conn = conectar_db()
    if not conn: return
    cursor = conn.cursor()

    duplicados_fusionados = consolidar_duplicados_historicos(cursor)
    if duplicados_fusionados:
        conn.commit()
        print(f"Se fusionaron {duplicados_fusionados} registros duplicados históricos antes del scraping.")

    print(f"--- INICIANDO ACTUALIZACIÓN DE PLANTILLAS ---\n")

    total_agregados = 0
    total_omitidos = 0
    total_transferidos = 0

    for equipo in EQUIPOS:
        agregados, omitidos, transferidos = actualizar_equipo(equipo, conn, cursor)
        total_agregados += agregados
        total_omitidos += omitidos
        total_transferidos += transferidos

    cursor.close()
    conn.close()
    print(f"\n{'='*60}")
    print("ACTUALIZACIÓN COMPLETADA")
    print(f"Total agregados: {total_agregados} | Total existentes: {total_omitidos} | Total transferidos: {total_transferidos}")
    print(f"{'='*60}")

if __name__ == "__main__":
    ejecutar_scraper()