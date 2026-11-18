# fuentes/generacion_real.py
# Generacion REAL por recurso de XM, y lo que se puede hacer con ella.
#
# -------------------------------------------------------------------------
# POR QUE EXISTE
# -------------------------------------------------------------------------
# `xm_snapshot` construye una fecha con el despacho PROGRAMADO (dDEC) y el
# pronostico de demanda (PRON_BARRA), publicados la vispera. Son datos de XM,
# pero describen un PROGRAMA, no lo que ocurrio: el propio manifiesto de sinsim
# lo advierte. El 1-nov-2026, a las 12 h, Ituango estaba programado en 300 MW y
# genero 907; dos plantas a gas programadas (358 MW) no generaron. Con el
# programa la hidroelectrica salia con 21,2 % y la real fue 26,9 %.
#
# Este modulo trae lo MEDIDO, del servicio de datos de XM (servapibi):
#
#   Gene             generacion por recurso y hora (kWh)
#   ListadoRecursos  tipo y COMBUSTIBLE de cada recurso (EnerSource)
#   DemaReal         demanda real del sistema por hora (kWh)
#
# El combustible es lo que PARATEC no da: permite separar gas de carbon.
#
# -------------------------------------------------------------------------
# COMO SE USA EN EL MODELO
# -------------------------------------------------------------------------
# `FuenteXM(fecha, periodo, origen='real')` sustituye el despacho programado
# por la generacion real, y lleva el pronostico de demanda al total medido
# (DemaReal) en cada periodo. Todo lo demas ---la ubicacion en barras, la
# elevacion de STR a STN, las consignas--- es identico.
#
# LIMITES, y conviene saberlos:
#  * El listado de recursos es el VIGENTE el dia de la descarga, no el de la
#    fecha. Un recurso retirado desde entonces aparece sin combustible.
#  * La demanda por barra sigue siendo el pronostico, solo reescalado al total.
#    XM no publica la demanda real por barra del STN.
#  * Los enlaces con otros paises y las plantas menores que el listado no trae
#    se dejan como venian en el dDEC.
#  * La generacion real de un dia suele estar disponible con un dia de rezago.

import argparse
import json
import os
import ssl
import time
import urllib.error
import urllib.request

import pandas as pd

from stn.fuentes.xm_snapshot import DIR_XM

URL_HORARIA = 'https://servapibi.xm.com.co/hourly'
URL_LISTAS = 'https://servapibi.xm.com.co/lists'
AGENTE = 'modelo-stn/1.0 (estudio academico del STN)'
TIEMPO_MAX_S = 120
ESPERA_S = 0.5

FAMILIAS = ('solar', 'hidroeléctrica', 'gas', 'carbón', 'otras térmicas',
            'eólica')

# Recursos del dDEC que el listado de XM no trae y que NO son generacion
# propia del sistema o son plantas menores: se conservan tal cual.
_CONSERVAR_DEL_DDEC = 'ECUADOR|VENEZ|AUTOG|GD |COGEN'

_ultima = [0.0]


class ErrorGeneracionReal(Exception):
    """No se pudo traer o usar la generacion real. El mensaje dice que hacer."""


# ---------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------

def _dir(fecha, raiz=None):
    return os.path.join(raiz or DIR_XM, 'xm_real', str(fecha))


def _post(url, cuerpo):
    falta = ESPERA_S - (time.monotonic() - _ultima[0])
    if falta > 0:
        time.sleep(falta)
    _ultima[0] = time.monotonic()
    pet = urllib.request.Request(
        url, data=json.dumps(cuerpo).encode('utf-8'),
        headers={'User-Agent': AGENTE, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(pet, timeout=TIEMPO_MAX_S) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise ErrorGeneracionReal(
            f'XM respondio {e.code} a {url}') from e
    except urllib.error.URLError as e:
        if isinstance(e.reason, ssl.SSLError):
            raise ErrorGeneracionReal(
                'el certificado de servapibi.xm.com.co no se pudo verificar. '
                'Si estas en la red de una empresa, apunta SSL_CERT_FILE al '
                'almacen que tiene su raiz, por ejemplo en macOS: '
                'export SSL_CERT_FILE=/opt/homebrew/etc/ca-certificates/'
                'cert.pem') from e
        raise ErrorGeneracionReal(
            f'no se pudo conectar con XM: {e.reason}') from e
    except ValueError as e:
        raise ErrorGeneracionReal(
            f'XM devolvio algo que no es JSON ({url}); suele pasar cuando el '
            f'servicio esta saturado, repite en un momento') from e


def disponible(fecha, raiz=None):
    """True si la generacion real de la fecha ya esta en disco."""
    d = _dir(fecha, raiz)
    return all(os.path.exists(os.path.join(d, n))
               for n in ('gene.json', 'listado_recursos.json',
                         'dema_real.json'))


def descargar(fecha, raiz=None, forzar=False, verbose=True):
    """Trae Gene, ListadoRecursos y DemaReal de la fecha. Devuelve la carpeta."""
    f = str(fecha)
    d = _dir(f, raiz)
    os.makedirs(d, exist_ok=True)

    def pedir(nombre, url, cuerpo):
        ruta = os.path.join(d, nombre)
        if os.path.exists(ruta) and not forzar:
            return
        if verbose:
            print(f'   {nombre} ...')
        out = _post(url, cuerpo)
        open(ruta, 'w', encoding='utf-8').write(json.dumps(out))

    pedir('listado_recursos.json', URL_LISTAS,
          {'MetricId': 'ListadoRecursos', 'Entity': 'Sistema'})
    pedir('gene.json', URL_HORARIA,
          {'MetricId': 'Gene', 'Entity': 'Recurso', 'StartDate': f,
           'EndDate': f, 'Filter': []})
    pedir('dema_real.json', URL_HORARIA,
          {'MetricId': 'DemaReal', 'Entity': 'Sistema', 'StartDate': f,
           'EndDate': f, 'Filter': []})
    return d


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

def familia(tipo, fuente):
    """Familia de una planta segun su tipo y combustible en XM.

    `gas` y `carbon` son combustibles de plantas termicas. Una cogeneracion
    que quema gas NO cuenta como gas: va con las otras termicas, que es donde
    XM la agrupa por tipo.
    """
    if fuente == 'AGUA':
        return 'hidroeléctrica'
    if fuente == 'RAD SOLAR':
        return 'solar'
    if fuente == 'VIENTO':
        return 'eólica'
    if fuente == 'CARBON':
        return 'carbón'
    if fuente == 'GAS' and tipo != 'COGENERADOR':
        return 'gas'
    return 'otras térmicas'


def listado(fecha, raiz=None):
    """DataFrame (indice Name) con Code, Type, Disp y EnerSource."""
    ruta = os.path.join(_dir(fecha, raiz), 'listado_recursos.json')
    if not os.path.exists(ruta):
        raise ErrorGeneracionReal(
            f'falta el listado de recursos de {fecha}. Descargalo con:  '
            f'python -m stn.fuentes.generacion_real --fecha {fecha}')
    lst = json.load(open(ruta, encoding='utf-8'))
    filas = [i['ListEntities'][0]['Values'] for i in lst['Items']]
    r = pd.DataFrame(filas)
    r['Name'] = r.Name.astype(str).str.strip()
    r = r.drop_duplicates('Name').set_index('Name')
    r['fam'] = [familia(t, e) for t, e in zip(r.Type, r.EnerSource)]
    return r


def cargar(fecha, raiz=None):
    """Generacion real por recurso (MW medios por hora) y demanda real.

    Devuelve (real, demanda) con `real` indexado por nombre de recurso y
    columnas 1..24 en MW (el valor horario en kWh dividido entre 1000), mas
    Type, EnerSource, Disp y fam; `demanda` es una Serie en MW por periodo.
    """
    d = _dir(fecha, raiz)
    if not disponible(fecha, raiz):
        raise ErrorGeneracionReal(
            f'no hay generacion real de {fecha} en disco. Descargala con:  '
            f'python -m stn.fuentes.generacion_real --fecha {fecha}')
    lst = listado(fecha, raiz)
    gene = json.load(open(os.path.join(d, 'gene.json'), encoding='utf-8'))
    filas = {}
    for it in gene.get('Items', []):
        v = it['HourlyEntities'][0]['Values']
        fila = {}
        for h in range(1, 25):
            x = v.get(f'Hour{h:02d}', '')
            fila[h] = float(x) / 1000.0 if x not in ('', None) else 0.0
        filas[v['code']] = fila
    if not filas:
        raise ErrorGeneracionReal(
            f'XM no devolvio generacion real para {fecha}. Si la fecha es de '
            f'hoy o futura, todavia no esta publicada (suele llegar con un '
            f'dia de rezago).')
    g = pd.DataFrame(filas).T
    g.index.name = 'Code'
    por_codigo = lst.reset_index().drop_duplicates('Code').set_index('Code')
    g = g.join(por_codigo[['Name', 'Type', 'Disp', 'EnerSource', 'fam']])
    g['Name'] = g.Name.fillna(g.index.to_series())
    g['fam'] = g.fam.fillna('otras térmicas')
    if g[list(range(1, 25))].to_numpy().sum() <= 0:
        raise ErrorGeneracionReal(
            f'la generacion real de {fecha} llego vacia: todavia no esta '
            f'publicada.')
    g = g.reset_index().set_index('Name')

    dr = json.load(open(os.path.join(d, 'dema_real.json'), encoding='utf-8'))
    v = dr['Items'][0]['HourlyEntities'][0]['Values']
    dem = pd.Series({h: float(v[f'Hour{h:02d}']) / 1000.0
                     for h in range(1, 25)})
    return g, dem


# ---------------------------------------------------------------------------
# Para el modelo
# ---------------------------------------------------------------------------

def despacho(fecha, ddec, raiz=None):
    """Tabla `dispatch` (resource, period, p_mw, source_id) con lo MEDIDO.

    `ddec` es la tabla programada del snapshot: de ella se conservan solo los
    enlaces con otros paises y las plantas menores que el listado no trae.
    """
    real, _ = cargar(fecha, raiz)
    # Las plantas solares se conservan AUNQUE esa hora generen cero. Quien
    # mide cuanto produce la solar (`FuenteXM.produccion_solar_pu`) divide por
    # la placa de los recursos que aparecen en el despacho: si solo aparecen
    # los que generan, de noche quedan dos o tres plantas pequenas que
    # reportan 1 o 2 MW y su placa pequena da una produccion de 3 a 7 %, que
    # no existe. El despacho programado no tiene el problema porque trae todos
    # los recursos, con ceros.
    solares = set(real.index[real.fam == 'solar'])
    filas = []
    for h in range(1, 25):
        s = real.groupby(level=0)[h].sum()
        s = s[(s > 0) | s.index.isin(solares)]
        filas.append(pd.DataFrame({'resource': s.index, 'period': h,
                                   'p_mw': s.values, 'source_id': 'Gene'}))
    nuevo = pd.concat(filas, ignore_index=True)
    en_listado = set(real.index)
    resto = ddec[~ddec.resource.str.strip().isin(en_listado)]
    resto = resto[resto.resource.str.contains(_CONSERVAR_DEL_DDEC, regex=True)]
    if len(resto):
        nuevo = pd.concat([nuevo, resto[nuevo.columns]], ignore_index=True)
    return nuevo


def demanda_al_total_real(demand, fecha, raiz=None):
    """El pronostico por barra, llevado en cada periodo al total medido.

    El modelo usa p_act + p_pstr (energia activa mas perdidas del STR), asi
    que ese es el total que se iguala. Devuelve (tabla, factores por periodo).
    """
    _, dem = cargar(fecha, raiz)
    d = demand.copy()
    factores = {}
    for p in range(1, 25):
        m = d.period == p
        tot = float((d.loc[m, 'p_act_mw'] + d.loc[m, 'p_pstr_mw']).sum())
        f = float(dem[p]) / tot if tot > 0 and dem[p] > 0 else 1.0
        factores[p] = f
        for c in ('p_act_mw', 'p_pstr_mw', 'q_mvar'):
            d.loc[m, c] = d.loc[m, c] * f
    return d, factores


# ---------------------------------------------------------------------------
# Participacion por tecnologia
# ---------------------------------------------------------------------------

def mw_por_familia(fecha, origen='real', raiz=None):
    """MW por familia (filas) y periodo 1..24 (columnas).

    origen='real'       generacion medida (Gene)
    origen='programado' despacho dDEC del snapshot, clasificado con el mismo
                        combustible del listado de XM, para que las dos series
                        sean comparables.
    """
    if origen == 'real':
        real, _ = cargar(fecha, raiz)
        t = real.groupby('fam')[list(range(1, 25))].sum()
    elif origen == 'programado':
        from stn.fuentes.xm_snapshot import cargar_snapshot
        lst = listado(fecha, raiz)
        dd = cargar_snapshot(fecha, raiz)['dispatch'].copy()
        dd['Name'] = dd.resource.str.strip()
        dd = dd.join(lst[['Type', 'EnerSource', 'fam']], on='Name')
        sin = dd.fam.isna()
        dd.loc[sin & dd.Name.str.contains('EOLICO'), 'fam'] = 'eólica'
        dd.loc[dd.fam.isna(), 'fam'] = 'otras térmicas'
        t = dd.pivot_table(index='fam', columns='period', values='p_mw',
                           aggfunc='sum').fillna(0.0)
    else:
        raise ValueError(f"origen '{origen}': usa 'real' o 'programado'")
    return t.reindex(list(FAMILIAS)).fillna(0.0)


def participacion_pct(mw):
    """Porcentaje de cada familia sobre el total de cada periodo."""
    tot = mw.sum(axis=0)
    return mw.div(tot.where(tot > 0), axis=1).fillna(0.0) * 100.0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Descarga la generacion real por recurso de XM.')
    ap.add_argument('--fecha', required=True, metavar='AAAA-MM-DD')
    ap.add_argument('--forzar', action='store_true',
                    help='volver a bajar aunque ya este en disco')
    a = ap.parse_args(argv)
    try:
        d = descargar(a.fecha, forzar=a.forzar)
        real, dem = cargar(a.fecha)
    except ErrorGeneracionReal as e:
        print(f'ERROR: {e}')
        return 1
    print(f'   listo en {d}')
    print(f'   {len(real)} recursos; demanda real p13 = {dem[13]:.1f} MW')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
