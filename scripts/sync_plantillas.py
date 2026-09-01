import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
from bs4 import BeautifulSoup
import time
import random
import re
from datetime import date
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


def obtener_fecha_nacimiento(fila):
    tds = fila.find_all('td')
    if len(tds) > 5:
        texto = tds[5].get_text(' ', strip=True)
        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', texto)
        if match:
            dia, mes, anio = map(int, match.groups())
            try:
                return date(anio, mes, dia)
            except ValueError:
                return None
    return None

LESION_KEYWORDS = ('lesi', 'baja', 'enfermo', 'cirug', 'desgarro', 'rotura', 'fractura')
RED_CARD_KEYWORDS = ('tarjeta roja', 'red card', 'expulsado', 'expulsion')
DOUBLE_YELLOW_KEYWORDS = ('doble amarilla', 'segunda amarilla', '2 amarilla', 'two yellow', 'segunda amarilla')
COMPETICIONES_EXTERNAS = ('copa chile', 'copa de la liga', 'libertadores', 'sudamericana', 'supercopa', 'recopa', 'amistoso', 'conmebol', 'ucl')


def _texto_estado_elemento(elemento):
    partes = []
    for attr in ('title', 'data-original-title', 'data-tippy-content', 'aria-label', 'alt'):
        valor = elemento.get(attr)
        if valor:
            partes.append(valor.lower())

    titulo_svg = elemento.find('title')
    if titulo_svg and titulo_svg.text:
        partes.append(titulo_svg.text.lower())

    return ' '.join(partes)


def _es_sancion_liga_primera(texto_estado):
    """Verifica que la sanción sea de Liga de Primera (no de otras competiciones)"""
    texto_lower = texto_estado.lower()
    
    # Si menciona una competición externa, no es de Liga de Primera
    for competicion in COMPETICIONES_EXTERNAS:
        if competicion in texto_lower:
            return False
    
    # Si no menciona competición externa, asumir que es Liga de Primera
    return True


def obtener_estado(fila):
    if not fila:
        return 'activo'

    lesion_detectada = False
    for elemento in fila.find_all(True):
        clases = ' '.join(elemento.get('class', [])).lower()
        texto_estado = _texto_estado_elemento(elemento)

        if 'verletzt-table' in clases or any(palabra in texto_estado for palabra in LESION_KEYWORDS):
            lesion_detectada = True

        # Detección de sanciones: buscar específicamente tarjeta roja o doble amarilla
        if 'gesperrt-table' in clases:
            if _es_sancion_liga_primera(texto_estado):
                return 'suspendido'

        # Buscar palabras clave de tarjeta roja (más específicas que solo "roja")
        if any(palabra in texto_estado for palabra in RED_CARD_KEYWORDS):
            if _es_sancion_liga_primera(texto_estado):
                return 'suspendido'

        # Buscar palabras clave de doble amarilla
        if any(palabra in texto_estado for palabra in DOUBLE_YELLOW_KEYWORDS):
            if _es_sancion_liga_primera(texto_estado):
                return 'suspendido'

    if lesion_detectada:
        return 'lesionado'

    return 'activo'


def marcar_transferido_en_otras_plantillas(cursor, nombre, fecha_nacimiento, jugador_id, equipo_id):
    if fecha_nacimiento is not None:
        cursor.execute(
            """
            UPDATE jugadores
            SET estado = 'transferido', precio_actual = 0
            WHERE nombre = %s
              AND fecha_nacimiento = %s
              AND jugador_id != %s
              AND equipo_id != %s
              AND estado != 'transferido'
            """,
            (nombre, fecha_nacimiento, jugador_id, equipo_id)
        )
    else:
        cursor.execute(
            """
            UPDATE jugadores
            SET estado = 'transferido', precio_actual = 0
            WHERE nombre = %s
              AND fecha_nacimiento IS NULL
              AND jugador_id != %s
              AND equipo_id != %s
              AND estado != 'transferido'
            """,
            (nombre, jugador_id, equipo_id)
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


def upsert_jugador_unico(cursor, equipo_id, nombre, dorsal, pos_codigo, estado, fecha_nacimiento):
    select_sql = """
        SELECT
            j.jugador_id,
            j.equipo_id,
            j.dorsal,
            j.posicion,
            j.estado,
            j.precio_actual,
            j.fecha_nacimiento,
            COALESCE(owners.total, 0) AS owners
        FROM jugadores j
        LEFT JOIN (
            SELECT jugador_id, COUNT(*) AS total
            FROM plantilla_fantasy
            GROUP BY jugador_id
        ) owners ON owners.jugador_id = j.jugador_id
        WHERE {condicion}
        ORDER BY COALESCE(owners.total, 0) DESC, j.jugador_id ASC
    """

    # 1) Identidad confirmada por (nombre + fecha de nacimiento)
    if fecha_nacimiento is not None:
        cursor.execute(
            select_sql.format(condicion="j.nombre = %s AND j.fecha_nacimiento = %s"),
            (nombre, fecha_nacimiento)
        )
        filas = cursor.fetchall()

        # 2) Sin match: adoptar fila legacy sin fecha (migración de datos)
        if not filas:
            cursor.execute(
                select_sql.format(condicion="j.nombre = %s AND j.fecha_nacimiento IS NULL"),
                (nombre,)
            )
            filas = cursor.fetchall()
    else:
        # Sin fecha disponible: solo matchear filas legacy sin fecha.
        # Nunca tocar una fila que ya tenga fecha (podría ser un homónimo).
        cursor.execute(
            select_sql.format(condicion="j.nombre = %s AND j.fecha_nacimiento IS NULL"),
            (nombre,)
        )
        filas = cursor.fetchall()

    if not filas:
        insert_query = """
            INSERT INTO jugadores
            (equipo_id, nombre, posicion, dorsal, precio_actual, tier, estado, foto_url, fecha_nacimiento)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING jugador_id
        """
        cursor.execute(
            insert_query,
            (equipo_id, nombre, pos_codigo, dorsal, 10000000, 'B', estado, None, fecha_nacimiento)
        )
        nuevo_id = cursor.fetchone()[0]
        return 'insertado', nuevo_id, [f"nuevo jugador en equipo {equipo_id}"]

    jugador_id_canonico, equipo_bd, dorsal_bd, pos_bd, estado_bd, precio_bd, fecha_bd, _owners = filas[0]
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
            precio_actual = %s,
            fecha_nacimiento = %s
        WHERE jugador_id = %s
        """,
        (equipo_id, dorsal, pos_codigo, estado, precio_nuevo, fecha_nacimiento, jugador_id_canonico)
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
    if fecha_bd != fecha_nacimiento:
        cambios.append(f"fecha nacimiento {fecha_bd}→{fecha_nacimiento}")
    if len(filas) > 1:
        cambios.append(f"duplicados fusionados: {len(filas) - 1}")

    if cambios:
        return 'actualizado', jugador_id_canonico, cambios
    return 'omitido', jugador_id_canonico, []


def consolidar_duplicados_historicos(cursor):
    cursor.execute(
        """
        SELECT nombre, COALESCE(fecha_nacimiento::text, '')
        FROM jugadores
        GROUP BY nombre, COALESCE(fecha_nacimiento::text, '')
        HAVING COUNT(*) > 1
        ORDER BY nombre
        """
    )
    grupos = cursor.fetchall()
    if not grupos:
        return 0

    duplicados_fusionados = 0
    for nombre, fecha_texto in grupos:
        select_sql = """
            SELECT
                j.jugador_id,
                j.equipo_id,
                j.dorsal,
                j.posicion,
                j.estado,
                j.precio_actual,
                j.fecha_nacimiento,
                COALESCE(owners.total, 0) AS owners
            FROM jugadores j
            LEFT JOIN (
                SELECT jugador_id, COUNT(*) AS total
                FROM plantilla_fantasy
                GROUP BY jugador_id
            ) owners ON owners.jugador_id = j.jugador_id
            WHERE j.nombre = %s AND {condicion_fecha}
            ORDER BY COALESCE(owners.total, 0) DESC, j.jugador_id ASC
        """
        if fecha_texto:
            cursor.execute(
                select_sql.format(condicion_fecha="j.fecha_nacimiento = %s"),
                (nombre, fecha_texto)
            )
        else:
            cursor.execute(
                select_sql.format(condicion_fecha="j.fecha_nacimiento IS NULL"),
                (nombre,)
            )
        filas = cursor.fetchall()
        if len(filas) < 2:
            continue

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


def reportar_colisiones_nombre(cursor):
    cursor.execute(
        """
        SELECT nombre, COUNT(DISTINCT COALESCE(fecha_nacimiento::text, ''))
        FROM jugadores
        GROUP BY nombre
        HAVING COUNT(DISTINCT COALESCE(fecha_nacimiento::text, '')) > 1
        ORDER BY nombre
        """
    )
    colisiones = cursor.fetchall()
    if colisiones:
        print("Colisiones de nombre detectadas (mismo nombre, distinta fecha de nacimiento):")
        for nombre, n_fechas in colisiones:
            print(f"  - '{nombre}': {n_fechas} fechas de nacimiento distintas -> revisar manualmente")
    return len(colisiones)

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
                fecha_nacimiento = obtener_fecha_nacimiento(fila)

                accion, jugador_id, cambios = upsert_jugador_unico(
                    cursor,
                    equipo['id_db'],
                    nombre,
                    dorsal,
                    pos_codigo,
                    estado,
                    fecha_nacimiento
                )

                if accion == 'insertado':
                    agregados += 1
                    print(f"Agregado nuevo: {nombre} ({pos_codigo}) - Dorsal {dorsal}")
                elif accion == 'actualizado':
                    agregados += 1
                    print(f"Actualizado {nombre}: {', '.join(cambios)}")
                else:
                    omitidos += 1

                transferidos_otros = marcar_transferido_en_otras_plantillas(cursor, nombre, fecha_nacimiento, jugador_id, equipo['id_db'])
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

    reportar_colisiones_nombre(cursor)

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