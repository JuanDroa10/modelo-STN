# test_fuente_xm.py
"""Invariantes de la fuente de punto de operacion desde XM.

    python test_fuente_xm.py          # todo
    python test_fuente_xm.py -k cober # solo lo que case con 'cober'

POR QUE EXISTE. `fuentes/xm_snapshot.py` tiene que producir EXACTAMENTE el
mismo contrato que `data_integration.integrar()` + `desagregacion.desglose_de()`
para que la fase 2 pueda intercambiarlas sin que el motor de dinamica se entere.
Aqui se fija ese contrato, y la cobertura minima por debajo de la cual el punto
de operacion no sirve para un estudio de frecuencia.

NO comprueban que el resultado sea el del caso de PowerFactory: son casos
distintos, de dias distintos. Eso lo cubre `test_regresion_pf.py`, y solo para
la fuente de PowerFactory.
"""

import sys

import pandas as pd

from stn.fuentes import descarga_xm as DX
from stn.fuentes import nombres as N
from stn.fuentes.xm_snapshot import FuenteXM, fechas_disponibles

FECHA = '2026-10-20'
PERIODO = 19

# Umbrales de aceptacion de la fase 1. Medidos sobre las 24 horas del
# 2026-10-20: generacion 98,54-99,26 %, demanda 98,92-99,08 %.
COBERTURA_GEN_MIN = 98.0
COBERTURA_DEM_MIN = 98.0
# El balance ubicado no puede alejarse del crudo mas que esto, o la demanda
# que falta se estaria colando como perdidas. Ver fuentes/calidad.py.
SESGO_MAX_MW = 60.0

_CACHE = {}


def fuente(periodo=PERIODO):
    if periodo not in _CACHE:
        _CACHE[periodo] = FuenteXM(FECHA, periodo, verbose=False)
    return _CACHE[periodo]


def _hay_snapshot():
    assert FECHA in fechas_disponibles(), (
        f'no hay snapshot de {FECHA}; las pruebas no pueden correr. '
        f'Disponibles: {fechas_disponibles()}')


# ---------------------------------------------------------------------------
# El contrato con el resto del modelo
# ---------------------------------------------------------------------------

def test_el_desglose_conserva_la_inyeccion_neta():
    """Gen(b) - Carga(b) = P(b). El mismo invariante que exige el modelo.

    Aqui deberia salir exacto, no aproximado: la generacion y la demanda
    llegan separadas de origen, asi que P es una RESTA, no una atribucion.
    """
    _hay_snapshot()
    for h in (1, 10, 19, 24):
        f = fuente(h)
        iny = f.inyecciones()
        gen, carga = f.desglose()
        d = (gen - carga - iny.P).abs().max()
        assert d < 1e-9, f'periodo {h}: |gen-carga-P| = {d:.3e} MW'


def test_las_inyecciones_tienen_las_columnas_del_contrato():
    _hay_snapshot()
    iny = fuente().inyecciones()
    assert list(iny.columns) == ['P', 'Q', 'v_set'], (
        f'columnas {list(iny.columns)}, se esperaba [P, Q, v_set]')
    assert iny.index.name == 'bus'
    assert not iny.P.isna().any(), 'hay P a NaN'
    assert not iny.Q.isna().any(), 'hay Q a NaN'


def test_todos_los_buses_existen_en_el_modelo():
    """Una inyeccion en un bus que la red no tiene se pierde sin aviso."""
    _hay_snapshot()
    f = fuente()
    sobran = sorted(set(f.inyecciones().index) - set(f.buses_modelo))
    assert not sobran, f'buses que el modelo no tiene: {sobran[:8]}'


def test_la_consigna_de_tension_es_uniforme_por_nivel():
    """v_set fijo por nivel, nunca heredado de otro caso.

    XM no publica tension por barra. Se fija una consigna, que es lo que un
    operador hace; heredar el perfil del caso de PowerFactory se midio y daba
    1,162 pu, porque ese perfil es la SOLUCION de otro despacho.
    """
    _hay_snapshot()
    from stn.fuentes.xm_snapshot import V_SET_POR_NIVEL
    iny = fuente().inyecciones()
    assert not iny.v_set.isna().any(), 'hay barras sin consigna'
    for bus, v in iny.v_set.items():
        _, nivel, _ = N.subestacion_de_bus(bus, {})
        esperado = V_SET_POR_NIVEL.get(N.nivel_modelo(nivel), 1.0)
        assert abs(v - esperado) < 1e-12, (
            f'{bus}: v_set {v}, se esperaba {esperado}')


def test_la_consigna_llega_a_las_barras_sin_inyeccion():
    """Si no, los 16 autotrafos se quedan en toma 1,0.

    `_ajustar_taps` solo ajusta un transformador si sus DOS barras traen
    consigna, y `asignar_inyecciones` solo recorre las filas de
    `inyecciones`. Las barras de 500 kV de transito no reciben ni carga ni
    generacion de XM: si el indice se limitara a las que tienen dato, se
    ajustarian 0 de 16.
    """
    _hay_snapshot()
    f = fuente()
    faltan = sorted(set(f.buses_modelo) - set(f.inyecciones().index))
    assert not faltan, (
        f'{len(faltan)} barras del modelo sin fila: {faltan[:6]}')


def test_las_barras_sin_dato_no_inventan_inyeccion():
    """Estan en el indice por su consigna, pero con P y Q a cero."""
    _hay_snapshot()
    f = fuente()
    iny, c = f.inyecciones(), f.calidad()
    assert c.buses_sin_datos, 'se esperaba alguna barra sin dato de XM'
    sub = iny.loc[list(c.buses_sin_datos)]
    assert (sub.P.abs() < 1e-12).all(), 'una barra sin dato trae P'
    assert (sub.Q.abs() < 1e-12).all(), 'una barra sin dato trae Q'


def test_la_demanda_entra_con_signo_de_consumo():
    """P<0 y Q<0 en las barras que solo tienen carga."""
    _hay_snapshot()
    f = fuente()
    iny = f.inyecciones()
    gen, carga = f.desglose()
    solo_carga = iny.index[(gen == 0) & (carga > 0)]
    assert len(solo_carga) > 20, 'muy pocas barras de solo carga; sospechoso'
    assert (iny.loc[solo_carga, 'P'] < 0).all(), 'una barra de carga inyecta P'
    assert (iny.loc[solo_carga, 'Q'] <= 0).all(), 'una barra de carga inyecta Q'


# ---------------------------------------------------------------------------
# Cobertura: lo que no se ubica tiene que ser poco Y estar contado
# ---------------------------------------------------------------------------

def test_la_cobertura_supera_el_umbral_en_las_24_horas():
    _hay_snapshot()
    malas = []
    for h in range(1, 25):
        c = FuenteXM(FECHA, h, verbose=False).calidad()
        if c.cobertura_despacho_pct < COBERTURA_GEN_MIN:
            malas.append(f'p{h} gen {c.cobertura_despacho_pct:.2f} %')
        if c.cobertura_demanda_pct < COBERTURA_DEM_MIN:
            malas.append(f'p{h} dem {c.cobertura_demanda_pct:.2f} %')
    assert not malas, 'cobertura por debajo del umbral: ' + ', '.join(malas)


def test_lo_que_no_se_ubica_esta_contado_y_con_razon():
    """Nada desaparece en silencio: cada MW ausente tiene fila y motivo."""
    _hay_snapshot()
    c = fuente().calidad()

    suma_g = c.recursos_no_ubicados.p_mw.sum() if len(
        c.recursos_no_ubicados) else 0.0
    assert abs(suma_g - c.p_despacho_no_ubicado_mw) < 1e-6, (
        f'generacion sin ubicar: el detalle suma {suma_g:.3f} MW pero el '
        f'agregado dice {c.p_despacho_no_ubicado_mw:.3f} MW')

    suma_d = c.nodos_no_ubicados.p_mw.sum() if len(
        c.nodos_no_ubicados) else 0.0
    assert abs(suma_d - c.p_demanda_no_ubicada_mw) < 1e-6, (
        f'demanda sin ubicar: el detalle suma {suma_d:.3f} MW pero el '
        f'agregado dice {c.p_demanda_no_ubicada_mw:.3f} MW')

    for df, col in ((c.recursos_no_ubicados, 'recurso'),
                    (c.nodos_no_ubicados, 'nodo')):
        if len(df):
            vacias = df[df.razon.isna() | (df.razon.astype(str).str.strip() == '')]
            assert not len(vacias), f'{len(vacias)} filas sin razon en {col}'


def test_la_demanda_ausente_no_se_disfraza_de_perdidas():
    """El balance ubicado no puede alejarse del crudo del snapshot.

    Si se aleja, la demanda que falta la esta absorbiendo el slack y aparece
    como perdidas. Con una version anterior del mapeo que dejaba 215 MW sin
    ubicar, las perdidas salian 267,8 MW en vez de 181,0.
    """
    _hay_snapshot()
    malas = []
    for h in range(1, 25):
        c = FuenteXM(FECHA, h, verbose=False).calidad()
        if abs(c.sesgo_de_perdidas_mw) > SESGO_MAX_MW:
            malas.append(f'p{h}: {c.sesgo_de_perdidas_mw:+.1f} MW')
    assert not malas, ('el balance se aleja del crudo: ' + ', '.join(malas))


def test_el_balance_es_positivo_y_del_orden_de_las_perdidas():
    """Generacion > demanda, y por un margen de perdidas creible (0,5-4 %)."""
    _hay_snapshot()
    malas = []
    for h in range(1, 25):
        c = FuenteXM(FECHA, h, verbose=False).calidad()
        pct = 100.0 * c.balance_mw / c.p_demanda_ubicada_mw
        if not 0.5 <= pct <= 4.0:
            malas.append(f'p{h}: {c.balance_mw:.1f} MW ({pct:.2f} %)')
    assert not malas, 'balance fuera del rango de perdidas: ' + ', '.join(malas)


def test_la_generacion_sin_ubicar_tambien_descalifica_el_punto():
    """No basta con vigilar la demanda, y eso costo descubrirlo.

    El 2026-09-16 tiene 99,0 % de demanda ubicada ---perfecto--- y se colaba
    como apto con un 95,4 % de generacion. Los MW que faltan no desaparecen:
    los pone el SLACK, una sola maquina, que acababa generando +380 MW sobre
    su programa en 20 de las 24 horas.
    """
    from stn.fuentes.calidad import (ReporteCalidad,
                                 UMBRAL_DESPACHO_NO_UBICADO_PCT)

    # demanda impecable, generacion coja: tiene que salir NO apto
    c = ReporteCalidad(
        p_demanda_total_mw=10000.0, p_demanda_ubicada_mw=9950.0,
        p_despacho_total_mw=10000.0, p_despacho_ubicado_mw=9500.0)
    assert not c.apto_para_frecuencia, (
        'un punto con el 5 % del despacho sin ubicar paso como apto')
    assert any('despacho' in m for m in c.motivos_no_apto), (
        f'el motivo no menciona el despacho: {c.motivos_no_apto}')

    # y justo por debajo del umbral, si
    falta = UMBRAL_DESPACHO_NO_UBICADO_PCT / 100.0 * 0.9
    ok = ReporteCalidad(
        p_demanda_total_mw=10000.0, p_demanda_ubicada_mw=9950.0,
        p_despacho_total_mw=10000.0,
        p_despacho_ubicado_mw=10000.0 * (1 - falta))
    assert ok.apto_para_frecuencia, ok.motivos_no_apto


def test_una_correccion_sin_evidencia_no_entra():
    """Mover cientos de MW de subestacion exige dejar la fuente."""
    import os
    import tempfile
    from stn.fuentes.xm_snapshot import cargar_correcciones
    with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False,
                                     encoding='utf-8') as fh:
        fh.write('recurso,subestacion,nota\nX,CERROMATOSO,\n')
        p = fh.name
    try:
        cargar_correcciones(p)
    except ValueError as e:
        assert 'nota' in str(e), f'mensaje poco claro: {e}'
        return
    finally:
        os.unlink(p)
    raise AssertionError('se acepto una correccion sin nota')


def test_la_correccion_curada_ubica_gecelca():
    """GECELCA no tiene NINGUNA linea en PARATEC: sin la correccion, 240 MW
    los ponia el slack en silencio."""
    _hay_snapshot()
    from stn.fuentes.xm_snapshot import cargar_correcciones
    corr = cargar_correcciones()
    assert 'GECELCA 32' in corr, 'falta la correccion de GECELCA 32'
    f = FuenteXM('2026-09-16', 11, verbose=False)
    sin = set(f.calidad().recursos_no_ubicados.recurso)
    assert 'GECELCA 32' not in sin, 'GECELCA 32 sigue sin ubicarse'
    tr = f.calidad().traslados
    assert (tr.tipo == 'generacion (curado)').any(), (
        'el traslado curado no quedo registrado en el reporte de calidad')


def test_el_punto_es_apto_para_un_estudio_de_frecuencia():
    _hay_snapshot()
    c = fuente().calidad()
    assert c.apto_para_frecuencia, (
        f'falta el {100*c.p_demanda_no_ubicada_mw/c.p_demanda_total_mw:.2f} % '
        f'de la demanda; el EDAC dimensionaria sobre una base incompleta')


# ---------------------------------------------------------------------------
# Que no se invente ni se pierda energia por el camino
# ---------------------------------------------------------------------------

def test_el_reparto_entre_barras_conserva_el_despacho():
    """Un recurso que cae en varias barras reparte su P, no la multiplica."""
    _hay_snapshot()
    f = fuente()
    c = f.calidad()
    gen, _ = f.desglose()
    assert abs(gen.sum() - c.p_despacho_ubicado_mw) < 1e-6, (
        f'la generacion por bus suma {gen.sum():.3f} MW y lo ubicado es '
        f'{c.p_despacho_ubicado_mw:.3f} MW')
    assert gen.sum() <= c.p_despacho_total_mw + 1e-6, (
        'se ubico mas generacion de la que hay en el despacho')


def test_la_demanda_incluye_las_perdidas_pstr():
    """P = Ener.Act. + Perd.PSTR, el mismo criterio que sinsim."""
    _hay_snapshot()
    f = fuente()
    d = f.tablas['demand']
    d = d[d.period == PERIODO]
    esperado = float((d.p_act_mw + d.p_pstr_mw).sum())
    assert abs(f.calidad().p_demanda_total_mw - esperado) < 1e-6, (
        'la demanda total no coincide con Ener.Act. + Perd.PSTR')
    solo_act = float(d.p_act_mw.sum())
    assert abs(f.calidad().p_demanda_total_mw - solo_act) > 1.0, (
        'parece que se esta ignorando Perd.PSTR')


def test_la_misma_entrada_da_el_mismo_resultado():
    """Determinista: el BFS recorre conjuntos, y un set no tiene orden."""
    _hay_snapshot()
    a = FuenteXM(FECHA, PERIODO, verbose=False).inyecciones()
    b = FuenteXM(FECHA, PERIODO, verbose=False).inyecciones()
    assert list(a.index) == list(b.index), 'el indice cambia entre corridas'
    d = (a[['P', 'Q']] - b[['P', 'Q']]).abs().max().max()
    assert d == 0.0, f'dos construcciones difieren en {d:.3e}'


# ---------------------------------------------------------------------------
# Nombres
# ---------------------------------------------------------------------------

def test_los_diacriticos_no_separan_barras():
    assert N.norm('CAÑO LIMON') == N.norm('CANO LIMON') == 'CANO LIMON'
    assert N.norm('OCAÑA') == 'OCANA'
    assert N.norm('  el   rio ') == 'EL RIO'


def test_el_nivel_agrupa_200_a_400_kv_en_230():
    for kv in (220, 230, 240):
        assert N.nivel_modelo(kv) == 230, f'{kv} kV no cae en 230'
    assert N.nivel_modelo(500) == 500
    assert N.nivel_modelo(115) == 115


def test_los_restos_del_nombre_del_tramo_se_limpian():
    casos = {'PALENQUE 1 230 KV__230': 'PALENQUE',
             'SOGAMOSO 2 230 KV__230': 'SOGAMOSO',
             'PURNIO (230)__230': 'PURNIO',
             'LA VIRGINIA (500 230)__500': 'LA VIRGINIA',
             'CANO LIMON__230': 'CANO LIMON'}
    for bus, esperado in casos.items():
        sub, _, _ = N.subestacion_de_bus(bus, {})
        assert sub == esperado, f'{bus!r} -> {sub!r}, se esperaba {esperado!r}'


def test_la_barra_de_unidad_no_desplaza_a_la_barra_base():
    """HIDROSOGAMOSO__230_U1 y SOGAMOSO__230 conviven; gana la base."""
    m = N.buses_por_subestacion(
        ['SOGAMOSO__230', 'SOGAMOSO__230_U1', 'SOGAMOSO__230_U2'], {})
    assert m['SOGAMOSO'] == 'SOGAMOSO__230', (
        f"la carga de SOGAMOSO subiria a {m['SOGAMOSO']!r}")


def test_una_colision_de_nombres_se_levanta_no_se_resuelve_sola():
    """Dos barras distintas del modelo en la misma clave tienen que fallar.

    Es el fallo que ya se pago con MIEL I y PORCE II: misma firma, placa
    repartida a partes iguales, y nadie se entero.
    """
    try:
        N.buses_por_subestacion(['GUAVIO__230', 'GUAVIO SUBT DUCTO__230'],
                                {'GUAVIO SUBT DUCTO': 'GUAVIO'})
    except ValueError as e:
        assert 'colision' in str(e).lower(), f'mensaje poco claro: {e}'
        return
    raise AssertionError('la colision no salto: dos barras se fusionaron')


def test_un_alias_sin_evidencia_no_entra():
    """La columna `nota` es obligatoria: un alias sin fuente es una suposicion."""
    import os
    import tempfile
    with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False,
                                     encoding='utf-8') as f:
        f.write('juancho,paratec,nota\nA,B,\n')
        p = f.name
    try:
        N.cargar_alias(p)
    except ValueError as e:
        assert 'nota' in str(e), f'mensaje poco claro: {e}'
        return
    finally:
        os.unlink(p)
    raise AssertionError('se acepto un alias sin nota')


# ---------------------------------------------------------------------------
# Enlaces internacionales
# ---------------------------------------------------------------------------

def test_el_enlace_con_ecuador_sale_como_inactivo():
    """El 2026-10-20 los dos enlaces estan a 0 MW las 24 horas."""
    _hay_snapshot()
    for h in (1, 12, 19, 24):
        inac = FuenteXM(FECHA, h, verbose=False).enlaces_inactivos()
        assert any(e['recurso'] == 'ECUADOR230_1' for e in inac), (
            f'periodo {h}: ECUADOR230_1 no sale como inactivo')


def test_abrir_el_enlace_retira_solo_la_barra_del_exterior():
    """PIMAMPIRO es una hoja: abrir sus cuatro circuitos no arrastra nada mas."""
    _hay_snapshot()
    import logging
    logging.disable(logging.INFO)
    from stn.data_loader import load_lines
    from stn.network_builder import build_network
    from stn.fuentes.xm_snapshot import abrir_enlaces

    red = build_network(load_lines(verbose=False), verbose=False)
    n_buses, n_lineas = len(red.buses), len(red.lines)
    lin, buses = abrir_enlaces(red, fuente().enlaces_inactivos(), verbose=False)
    assert len(lin) == 4, f'se abrieron {len(lin)} circuitos, se esperaban 4'
    assert buses == ['PIMAMPIRO__230'], f'barras retiradas: {buses}'
    assert len(red.buses) == n_buses - 1
    assert len(red.lines) == n_lineas - 4


def test_un_enlace_activo_no_se_abre():
    """La regla es el programa, no el nombre del recurso."""
    _hay_snapshot()
    from stn.fuentes.xm_snapshot import cargar_enlaces
    f = fuente()
    d = f.tablas['dispatch']
    d = d[d.period == PERIODO]
    prog = {N.norm(r.resource): float(r.p_mw) for _, r in d.iterrows()}
    inac = {e['recurso'] for e in f.enlaces_inactivos()}
    for e in cargar_enlaces():
        p = prog.get(N.norm(e['recurso']), 0.0)
        if abs(p) > 1e-9:
            assert e['recurso'] not in inac, (
                f"{e['recurso']} despacha {p} MW y se marco inactivo")


def test_un_enlace_sin_evidencia_no_entra():
    """Abrir una linea del modelo sin dejar la fuente no se admite."""
    import os
    import tempfile
    from stn.fuentes.xm_snapshot import cargar_enlaces
    with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False,
                                     encoding='utf-8') as fh:
        fh.write('recurso,bus_colombia,bus_exterior,nota\nX,A__230,B__230,\n')
        p = fh.name
    try:
        cargar_enlaces(p)
    except ValueError as e:
        assert 'nota' in str(e), f'mensaje poco claro: {e}'
        return
    finally:
        os.unlink(p)
    raise AssertionError('se acepto un enlace sin nota')


def test_el_enlace_internacional_activo_se_ubica_en_su_barra():
    """Un enlace que despacha no puede caer en 'sin unidades en PARATEC'.

    Los enlaces no tienen unidades: su potencia entra por la barra de
    conexion. El 2026-10-20 estan a 0 y no se nota, que es justo lo que lo
    hacia facil de pasar por alto.
    """
    _hay_snapshot()
    c = fuente().calidad()
    if not len(c.recursos_no_ubicados):
        return
    malos = [r for r in c.recursos_no_ubicados.recurso
             if str(r).upper().startswith('ECUADOR')]
    assert not malos, f'enlaces reportados como no ubicados: {malos}'


# ---------------------------------------------------------------------------
# La costura: caso_base tiene que aceptar una fuente sin enterarse de cual
# ---------------------------------------------------------------------------

def test_las_dos_fuentes_cumplen_el_protocolo():
    from stn.fuentes.base import FuentePuntoOperacion
    from stn.fuentes.powerfactory import FuentePowerFactory
    for f in (FuentePowerFactory(verbose=False), FuenteXM(FECHA, PERIODO,
                                                          verbose=False)):
        assert isinstance(f, FuentePuntoOperacion), (
            f'{type(f).__name__} no cumple el protocolo')
        for m in ('inyecciones', 'desglose', 'calidad', 'preparar_red'):
            assert callable(getattr(f, m, None)), (
                f'{type(f).__name__} no tiene {m}()')


def test_sin_fuente_el_caso_base_sigue_siendo_el_de_powerfactory():
    """La omision no puede cambiar: es lo que defiende el golden."""
    import logging
    logging.disable(logging.INFO)
    from stn import contingencias as C
    from tools import golden_pf

    red, diag = C.caso_base(verbose=False)
    meta, _ = golden_pf.cargar()
    g = meta['diagnostico']
    assert abs(diag['carga_MW'] - g['carga_MW']) < 1e-3, (
        f"carga {diag['carga_MW']} vs golden {g['carga_MW']}")
    assert abs(diag['v_min'] - g['v_min']) < 1e-6


def test_el_caso_base_acepta_la_fuente_de_xm():
    """El mismo motor, otro punto: 147 buses porque Pimampiro se retira."""
    _hay_snapshot()
    import logging
    logging.disable(logging.INFO)
    from stn import contingencias as C

    f = FuenteXM(FECHA, PERIODO, verbose=False)
    red, diag = C.caso_base(verbose=False, fuente=f)
    assert len(red.buses) == len(f.buses_modelo) - 1, (
        f'{len(red.buses)} buses; se esperaba uno menos que '
        f'{len(f.buses_modelo)} al abrir el enlace')
    assert 'PIMAMPIRO__230' not in red.buses.index
    assert abs(diag['carga_MW'] - f.calidad().p_demanda_ubicada_mw) < 1.0, (
        'la carga de la red no es la demanda ubicada por la fuente')


def test_la_dinamica_corre_sobre_el_punto_de_xm():
    """Lo que justifica toda la integracion: el motor no se toca.

    Y de paso se ve el premio: la inercia deja de ser un numero fijo y pasa a
    depender del compromiso de unidades real de cada hora.
    """
    _hay_snapshot()
    import logging
    logging.disable(logging.INFO)
    from stn import agc_deslastre as AGC
    from stn import contingencias as C

    inercia = {}
    for h in (3, 19):
        red, _ = C.caso_base(verbose=False,
                             fuente=FuenteXM(FECHA, h, verbose=False))
        sis = AGC.Sistema(red)
        assert sis.P_carga > 0 and sis.S_base > 0 and sis.H > 0
        inercia[h] = sis.H * sis.S_base
    assert inercia[19] > inercia[3], (
        f'la punta deberia tener mas inercia que la madrugada: {inercia}')


def test_una_fuente_que_no_conserva_la_inyeccion_se_rechaza():
    """El invariante se comprueba ANTES de montar la red.

    Si no, el sintoma aparece mucho mas tarde ---en el nadir--- donde ya no se
    puede atribuir a la fuente.
    """
    import pandas as pd
    from stn.fuentes.base import FuenteBase, verificar_contrato

    class Rota(FuenteBase):
        nombre = 'rota'

        def inyecciones(self):
            return pd.DataFrame({'P': [10.0], 'Q': [0.0], 'v_set': [1.0]},
                                index=['A__230'])

        def desglose(self):
            return (pd.Series({'A__230': 10.0}),
                    pd.Series({'A__230': 5.0}))      # 10 - 5 != 10

    try:
        verificar_contrato(Rota())
    except ValueError as e:
        assert 'inyeccion neta' in str(e), f'mensaje poco claro: {e}'
        return
    raise AssertionError('se acepto una fuente que no conserva la inyeccion')


# ---------------------------------------------------------------------------
# El factor de produccion solar y su uso en el BTM
# ---------------------------------------------------------------------------

def test_la_solar_sigue_el_dia():
    """Cero de noche, maximo a mediodia. Si esto falla, el dato esta mal."""
    _hay_snapshot()
    pu = {}
    for h in (3, 7, 12, 19, 23):
        _, _, pu[h] = FuenteXM(FECHA, h, verbose=False).produccion_solar_pu()
    assert pu[3] == 0.0 and pu[23] == 0.0, f'la solar no es cero de noche: {pu}'
    assert pu[12] > 0.5, f'al mediodia solo {pu[12]:.3f} pu'
    assert pu[12] > pu[7] > pu[19], f'el perfil no sigue el dia: {pu}'
    for h, v in pu.items():
        assert 0.0 <= v <= 1.0, f'periodo {h}: {v} pu fuera de [0, 1]'


def test_la_placa_solar_no_cambia_con_la_hora():
    """La placa es del parque, no del momento: solo varia la produccion."""
    _hay_snapshot()
    placas = {h: FuenteXM(FECHA, h, verbose=False).produccion_solar_pu()[1]
              for h in (3, 12, 19)}
    assert len(set(round(p, 6) for p in placas.values())) == 1, (
        f'la placa cambia con la hora: {placas}')


def test_el_btm_sigue_siendo_exogeno_sobre_un_punto_de_xm():
    """El pool BTM sale de PARATEC, NO del despacho de XM.

    Es la propiedad que no se puede perder: las 536 plantas que PARATEC marca
    "No Despachada Centralmente" aparecen TODAS en el dDEC, asi que lo que
    esta detras del contador es invisible ahi. Si algun dia el pool empezara a
    salir del snapshot, estaria contando generacion que YA esta en el
    despacho, y el deficit del evento saldria inflado.
    """
    _hay_snapshot()
    import logging
    logging.disable(logging.INFO)
    from stn import contingencias as C
    from stn import deslastre_btm as DB
    from stn import zonas

    esc = DB.EscenarioBTM()
    placas = {}
    for h in (3, 12):
        red, _ = C.caso_base(verbose=False,
                             fuente=FuenteXM(FECHA, h, verbose=False))
        placas[h] = float(DB.repartir_btm(red, esc,
                                          zonas.area_por_bus(red)).sum())
    # La PLACA del BTM es la misma a las 3 y a las 12: es un inventario de
    # PARATEC. Lo que cambia con la hora es cuanto de ella produce.
    assert abs(placas[3] - placas[12]) < 1.0, (
        f'la placa del BTM depende de la hora del despacho: {placas}. '
        f'El pool deberia venir solo de PARATEC.')
    assert placas[12] > 0, 'el pool BTM salio vacio'


# ---------------------------------------------------------------------------
# El barrido de 24 horas
# ---------------------------------------------------------------------------

def test_el_barrido_mide_lo_que_dice_medir():
    """Tres periodos bastan: lo caro es la hora, no el recorrido.

    Se comprueba que las columnas existen y que son coherentes entre si, no
    que valgan un numero concreto: eso cambia legitimamente al mejorar los
    datos y seria una prueba tautologica.
    """
    _hay_snapshot()
    import logging
    logging.disable(logging.INFO)
    from stn import barrido

    df = barrido.barrer(FECHA, [3, 12, 19], evento_mw=1500.0, verbose=False)
    assert len(df) == 3
    assert df.convergio.all(), f'alguna hora no resolvio: {df.nota.tolist()}'
    for c in ('demanda_MW', 'HS_MVAs', 'S_base_MVA', 'H_s', 'nadir_Hz',
              'RoCoF_Hz_s', 'edac_escalones', 'cob_dem_pct', 'apto'):
        assert c in df.columns, f'falta la columna {c}'
    # H*S tiene que ser el producto de sus dos factores
    d = (df.HS_MVAs - df.H_s * df.S_base_MVA).abs().max()
    assert d < 1e-6, f'H*S no es H por S_base: {d:.3e}'
    # el nadir de un evento de 1500 MW tiene que estar por debajo de 60 Hz
    assert (df.nadir_Hz < 60.0).all(), 'un evento de 1500 MW no bajo la f'
    assert (df.nadir_Hz > 50.0).all(), 'nadir imposible'
    # la punta tiene mas maquinas acopladas que la madrugada
    assert df.loc[19, 'S_base_MVA'] > df.loc[3, 'S_base_MVA']


def test_el_barrido_marca_las_horas_que_no_son_de_fiar():
    """`apto` tiene que venir de la cobertura, no de la convergencia.

    Una hora puede resolver perfectamente y aun asi no servir para un estudio
    de frecuencia si le falta demanda por ubicar.
    """
    _hay_snapshot()
    import logging
    logging.disable(logging.INFO)
    from stn import barrido

    df = barrido.barrer(FECHA, [19], evento_mw=1500.0, verbose=False)
    fila = df.loc[19]
    cal = FuenteXM(FECHA, 19, verbose=False).calidad()
    assert bool(fila.apto) == cal.apto_para_frecuencia
    assert abs(fila.cob_dem_pct - cal.cobertura_demanda_pct) < 1e-9


# ---------------------------------------------------------------------------
# Errores de uso
# ---------------------------------------------------------------------------

def test_un_periodo_fuera_de_rango_falla_pronto():
    for h in (0, 25, -1):
        try:
            FuenteXM(FECHA, h, verbose=False)
        except ValueError:
            continue
        raise AssertionError(f'el periodo {h} no fallo')


def test_una_fecha_sin_snapshot_dice_como_descargarla():
    try:
        FuenteXM('1999-01-01', 1, verbose=False)
    except FileNotFoundError as e:
        assert 'descarga_xm' in str(e), (
            f'el mensaje no dice como arreglarlo: {e}')
        return
    raise AssertionError('una fecha inexistente no fallo')


# ---------------------------------------------------------------------------
# El descargador
#
# NINGUNA de estas toca la red: el portal de XM no es nuestro y un banco de
# pruebas que dependa de el falla los dias que XM este de mantenimiento, que
# es la peor forma de fallar ---la que enseña a ignorar el rojo---. Lo que se
# fija aqui son los dos formatos y las comprobaciones que impiden construir
# un punto de operacion con un fichero a medias.
# ---------------------------------------------------------------------------

def _ddec(filas, totales=None):
    """Un dDEC sintetico: {recurso: [24 valores]}."""
    if totales is None:
        totales = [sum(v[i] for v in filas.values()) for i in range(24)]
    lineas = [f'"{k}",' + ','.join(f'{x:.4f}' for x in v)
              for k, v in filas.items()]
    lineas.append('"Total",' + ','.join(f'{x:.4f}' for x in totales))
    return '\n'.join(lineas)


def test_la_version_del_despacho_sale_del_nombre():
    casos = {'dDEC1101.txt': 0, 'dDEC1101_V1.txt': 1, 'dDEC1101_V12.txt': 12,
             'DDEC1101_v3.TXT': 3, 'PRON_BARRA1101.txt': None,
             'dDEC1101.csv': None, 'dDEC110.txt': None}
    for nombre, esperado in casos.items():
        v = DX.version_ddec(nombre)
        assert v == esperado, f'{nombre}: {v} en vez de {esperado}'


def test_el_despacho_se_lee_en_MW_por_periodo():
    t = _ddec({'A': [10.0] * 24, 'B': [5.5] * 24})
    d = DX.leer_ddec(t, 'x')
    assert list(d.columns) == ['resource', 'period', 'p_mw', 'source_id']
    assert len(d) == 48, f'{len(d)} filas en vez de 48'
    assert set(d.period) == set(range(1, 25))
    # Un periodo dura una hora, asi que los MWh del estandar YA son los MW
    # medios: si alguien mete un factor de conversion, esto lo caza.
    assert abs(float(d[d.resource == 'A'].p_mw.iloc[0]) - 10.0) < 1e-9
    assert abs(float(d.p_mw.sum()) - (10.0 + 5.5) * 24) < 1e-6


def test_un_despacho_que_no_cuadra_con_su_Total_se_rechaza():
    malos = [sum_ for sum_ in ([15.5] * 24,)]            # el bueno seria 15,5
    t = _ddec({'A': [10.0] * 24, 'B': [5.5] * 24},
              totales=[x + 1.0 for x in malos[0]])
    try:
        DX.leer_ddec(t, 'x')
    except DX.ErrorDescarga as e:
        assert 'Total' in str(e), f'el mensaje no habla del Total: {e}'
        return
    raise AssertionError('un despacho descuadrado se acepto: construiria un '
                         'punto de operacion con generacion que XM no declara')


def test_un_despacho_sin_fila_Total_se_rechaza():
    t = '\n'.join(['"A",' + ','.join(['1.0'] * 24)])
    try:
        DX.leer_ddec(t, 'x')
    except DX.ErrorDescarga:
        return
    raise AssertionError('un despacho sin Total se acepto')


def test_el_despacho_acepta_los_dos_separadores_de_XM():
    coma = _ddec({'A': [1.0] * 24})
    puntoycoma = coma.replace(',', ';')
    a = DX.leer_ddec(coma, 'x')
    b = DX.leer_ddec(puntoycoma, 'x')
    assert a.p_mw.tolist() == b.p_mw.tolist(), (
        'el separador cambia el resultado')


def _pron(nodos):
    """Un PRON_BARRA sintetico: {(ucp, nodo, kv): {concepto: [24]}}."""
    lineas = []
    for (ucp, nodo, kv), conc in nodos.items():
        for etiqueta, vals in conc.items():
            lineas.append(f'{ucp},{nodo},{kv},{etiqueta},'
                          + ','.join(f'{x:.4f}' for x in vals))
    return '\n'.join(lineas)


def test_la_demanda_separa_la_activa_de_las_perdidas_PSTR():
    t = _pron({('U1', 'N1', '115'): {'Ener.Act.': [100.0] * 24,
                                     'Ener.Reac': [30.0] * 24,
                                     'Perd.PSTR': [2.0] * 24}})
    d = DX.leer_pron_barra(t, 'x')
    assert len(d) == 24, f'{len(d)} filas en vez de 24'
    f = d.iloc[0]
    # La activa del caso es la SUMA de las dos, pero el snapshot las guarda
    # aparte y quien suma es el modelo. Fundirlas aqui escondería las
    # perdidas por referir la carga a otro nivel de tension.
    assert abs(float(f.p_act_mw) - 100.0) < 1e-9
    assert abs(float(f.p_pstr_mw) - 2.0) < 1e-9
    assert abs(float(f.q_mvar) - 30.0) < 1e-9
    assert abs(float(f.vn_kv) - 115.0) < 1e-9


def test_los_conceptos_valen_con_y_sin_punto_final():
    con = _pron({('U', 'N', '115'): {'Ener.Act.': [1.0] * 24,
                                     'Ener.Reac.': [2.0] * 24,
                                     'Perd.PSTR.': [3.0] * 24}})
    sin = _pron({('U', 'N', '115'): {'Ener.Act': [1.0] * 24,
                                     'Ener.Reac': [2.0] * 24,
                                     'Perd.PSTR': [3.0] * 24}})
    a, b = DX.leer_pron_barra(con, 'x'), DX.leer_pron_barra(sin, 'x')
    assert a.p_act_mw.tolist() == b.p_act_mw.tolist()


def test_un_nodo_al_que_le_falta_un_concepto_se_rechaza():
    t = _pron({('U', 'N', '115'): {'Ener.Act.': [1.0] * 24,
                                   'Ener.Reac': [2.0] * 24}})
    try:
        DX.leer_pron_barra(t, 'x')
    except DX.ErrorDescarga as e:
        assert 'Perd.PSTR' in str(e) or 'p_pstr' in str(e), (
            f'el mensaje no dice cual falta: {e}')
        return
    raise AssertionError('un nodo incompleto se acepto: su demanda saldria '
                         'por debajo de la real')


def test_no_se_aceptan_fechas_que_XM_no_ha_publicado():
    import datetime
    assert DX.comprobar_fecha('2026-10-20') == datetime.date(2026, 10, 20)
    # La forma basica de ISO 8601 tambien vale, y se normaliza: la carpeta
    # del snapshot sale siempre de .isoformat(), nunca de lo que se tecleo.
    assert DX.comprobar_fecha('20261020') == datetime.date(2026, 10, 20)
    lejos = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    for malo in ('ayer', '2026-13-01', '20-10-2026', lejos):
        try:
            DX.comprobar_fecha(malo)
        except DX.ErrorDescarga:
            continue
        raise AssertionError(f'{malo!r} se acepto como fecha')


def test_el_listado_del_portal_se_lee_de_su_envoltura():
    import json as _json

    crudo = _json.dumps({'ficheros': [
        {'nombre': 'dDEC1101.txt', 'fechaModificacion': '2026-10-31T14:24:36'},
        {'nombre': 'dDEC1101_V1.txt'},
        {'nombre': 'OTRA_COSA.txt'},
    ], 'cantidadFicheros': 3}).encode('utf-8')

    vistos = []

    def falso(url, params=None):
        vistos.append(params)
        return crudo

    real, DX._get = DX._get, falso
    try:
        r = DX.listar(DX.DIR_DESPACHO, '2026-11', 'dDEC1101')
    finally:
        DX._get = real
    assert [n for n, _ in r] == ['dDEC1101.txt', 'dDEC1101_V1.txt'], (
        f'el prefijo no filtro: {r}')
    assert r[0][1] == '2026-10-31T14:24:36'
    assert vistos[0]['ruta'] == f'{DX.DIR_DESPACHO}/2026-11'


def test_un_listado_con_otra_forma_se_denuncia():
    def falso(url, params=None):
        return b'<html>mantenimiento</html>'

    real, DX._get = DX._get, falso
    try:
        DX.listar(DX.DIR_DESPACHO, '2026-11', 'dDEC')
    except DX.ErrorDescarga as e:
        assert 'API' in str(e) or 'JSON' in str(e), (
            f'el mensaje no apunta a la API: {e}')
        return
    finally:
        DX._get = real
    raise AssertionError('una respuesta que no es JSON se acepto')


# ---------------------------------------------------------------------------

def test_el_n1_con_limites_converge_en_un_caso_de_xm():
    """Sobre un caso construido desde XM el N-1 con limites SI converge.

    El lazo PV/PQ con vuelta a PV no se asienta ahi (EL COPEY y TERMOCOL
    oscilan sin fin) y 289 de 292 contingencias salian como «no converge».
    `main()` pasa `vuelta_a_pv=False` solo para `--fecha`. Esta prueba fija que
    con ese parametro el caso resuelve y que el defecto de `simular` sigue
    siendo True: punta y diurno no deben cambiar.
    """
    import inspect
    from stn import contingencias as C
    por_defecto = inspect.signature(C.simular).parameters['vuelta_a_pv'].default
    assert por_defecto is True, (
        'el defecto de simular() debe seguir siendo True: punta y diurno '
        'dependen del lazo con vuelta a PV')
    base, diag = C.caso_base(verbose=False, fuente=fuente())
    r = C.simular(base, [('Line', 'LA VIRGINIA - SAN CARLOS 1 500 kV')], diag,
                  con_limites=True, vuelta_a_pv=False)
    assert r['convergio'], f"no converge: {r.get('motivo')}"
    assert r['gen_en_limite'] > 0, 'no se impuso ningun limite de reactivo'


# ---------------------------------------------------------------------------
# Generacion REAL en vez de despacho programado
# ---------------------------------------------------------------------------

def _real_sintetico():
    """Dos recursos con tres periodos de datos, sin tocar la red."""
    real = pd.DataFrame(
        {h: [100.0, 50.0, 40.0] if h <= 2 else [0.0, 0.0, 0.0]
         for h in range(1, 25)},
        index=['A HIDRO', 'B SOLAR', 'C GAS'])
    real['Type'] = ['HIDRAULICA', 'SOLAR', 'TERMICA']
    real['EnerSource'] = ['AGUA', 'RAD SOLAR', 'GAS']
    real['fam'] = ['hidroeléctrica', 'solar', 'gas']
    dem = pd.Series({h: 200.0 if h <= 2 else 0.0 for h in range(1, 25)})
    return real, dem


def test_el_origen_por_defecto_sigue_siendo_el_programado():
    """Sin pedirlo, ni la fuente ni el punto de operacion cambian de datos."""
    import inspect

    from stn import punto_operacion as PO
    for f in (FuenteXM.__init__, PO.construir):
        d = inspect.signature(f).parameters['origen'].default
        assert d == 'programado', f'{f.__qualname__}: origen por defecto {d!r}'
    assert PO.sufijo(None, '2026-11-01', 13) == '_20261101p13'
    assert PO.sufijo(None, '2026-11-01', 13, 'real') == '_20261101p13_real', \
        'el caso real tiene que escribir en ficheros propios'


def test_la_familia_se_decide_por_el_combustible():
    from stn.fuentes import generacion_real as GR
    casos = [(('HIDRAULICA', 'AGUA'), 'hidroeléctrica'),
             (('SOLAR', 'RAD SOLAR'), 'solar'),
             (('EOLICA', 'VIENTO'), 'eólica'),
             (('TERMICA', 'GAS'), 'gas'),
             (('TERMICA', 'CARBON'), 'carbón'),
             (('TERMICA', 'ACPM'), 'otras térmicas'),
             (('COGENERADOR', 'GAS'), 'otras térmicas')]
    for (t, e), esperado in casos:
        assert GR.familia(t, e) == esperado, (t, e, GR.familia(t, e))


def test_el_despacho_real_conserva_la_energia_y_los_enlaces(monkeypatch=None):
    """Lo que entra por `despacho` suma lo medido; los enlaces se conservan."""
    from stn.fuentes import generacion_real as GR
    real, dem = _real_sintetico()
    original = GR.cargar
    GR.cargar = lambda fecha, raiz=None: (real, dem)
    try:
        ddec = pd.DataFrame({'resource': ['A HIDRO', 'ECUADOR230_1', 'X'],
                             'period': [1, 1, 1], 'p_mw': [999.0, 7.0, 3.0],
                             'source_id': 'dDEC'})
        out = GR.despacho('2026-11-01', ddec)
    finally:
        GR.cargar = original
    p1 = out[out.period == 1].set_index('resource').p_mw
    assert p1['A HIDRO'] == 100.0, 'el programado de la planta no debe colarse'
    assert p1['B SOLAR'] == 50.0 and p1['C GAS'] == 40.0
    assert p1['ECUADOR230_1'] == 7.0, 'el enlace con Ecuador se conserva'
    assert 'X' not in p1.index, 'un recurso suelto del dDEC no se arrastra'
    p3 = out[out.period == 3]
    assert (p3.p_mw == 0).all() and list(p3.resource) == ['B SOLAR'], \
        'sin generacion solo quedan las plantas solares, con cero (su placa ' \
        'es el denominador de la produccion solar)'


def test_la_demanda_se_lleva_al_total_medido_por_periodo():
    from stn.fuentes import generacion_real as GR
    real, dem = _real_sintetico()
    original = GR.cargar
    GR.cargar = lambda fecha, raiz=None: (real, dem)
    try:
        d = pd.DataFrame({'node': ['N1', 'N2'] * 2, 'period': [1, 1, 2, 2],
                          'p_act_mw': [60.0, 30.0, 45.0, 45.0],
                          'p_pstr_mw': [6.0, 4.0, 5.0, 5.0],
                          'q_mvar': [10.0, 10.0, 10.0, 10.0]})
        out, f = GR.demanda_al_total_real(d, '2026-11-01')
    finally:
        GR.cargar = original
    for p in (1, 2):
        m = out.period == p
        tot = float((out.loc[m, 'p_act_mw'] + out.loc[m, 'p_pstr_mw']).sum())
        assert abs(tot - 200.0) < 1e-9, f'periodo {p}: {tot} MW, no 200'
    assert abs(f[1] - 200.0 / 100.0) < 1e-9
    # el reparto entre nodos no cambia, solo la escala
    a = out[out.period == 1].set_index('node').p_act_mw
    assert abs(a['N1'] / a['N2'] - 2.0) < 1e-9


def test_la_participacion_suma_cien_en_cada_periodo():
    from stn.fuentes import generacion_real as GR
    real, dem = _real_sintetico()
    original = GR.cargar
    GR.cargar = lambda fecha, raiz=None: (real, dem)
    try:
        mw = GR.mw_por_familia('2026-11-01', 'real')
    finally:
        GR.cargar = original
    pct = GR.participacion_pct(mw)
    assert abs(pct[1].sum() - 100.0) < 1e-9
    assert abs(pct.loc['hidroeléctrica', 1] - 100.0 * 100 / 190) < 1e-9
    assert pct[3].sum() == 0.0, 'un periodo sin generacion no inventa 100 %'


def test_el_punto_acepta_la_generacion_real_en_comparar_casos():
    from stn import comparar_casos as CC
    assert CC.leer_punto('2026-11-01:13:real') == {
        'hora': None, 'fecha': '2026-11-01', 'periodo': 13, 'origen': 'real'}
    assert 'origen' not in CC.leer_punto('2026-11-01:13'), \
        'sin pedirlo, el punto sigue siendo el programado'
    try:
        CC.leer_punto('2026-11-01:13:medido')
    except ValueError:
        pass
    else:
        raise AssertionError("'medido' no es un origen valido")


def test_los_periodos_de_la_participacion():
    from stn import participacion as PA
    assert PA.rango(13, None, None) == [13]
    assert PA.rango(None, 9, 11) == [9, 10, 11]
    assert PA.rango(None, 11, 9) == [9, 10, 11], 'el orden no importa'
    assert PA.rango(None, None, None) == list(range(1, 25))
    try:
        PA.rango(25, None, None)
    except ValueError:
        pass
    else:
        raise AssertionError('el periodo 25 no existe')


def test_un_caso_con_generacion_real_se_construye_y_cuadra():
    """Con datos de verdad, si estan en disco: cobertura y demanda medida."""
    from stn.fuentes import generacion_real as GR
    f = '2026-11-01'
    if f not in fechas_disponibles() or not GR.disponible(f):
        return          # no hay datos de esa fecha en esta maquina
    fu = FuenteXM(f, 13, verbose=False, origen='real')
    cal = fu.calidad()
    assert cal.cobertura_despacho_pct >= COBERTURA_GEN_MIN, \
        f'generacion ubicada {cal.cobertura_despacho_pct:.2f} %'
    assert cal.cobertura_demanda_pct >= COBERTURA_DEM_MIN
    _, dem = GR.cargar(f)
    # el total de demanda crudo del caso es el real, a la tolerancia de redondeo
    t = fu.tablas['demand']
    t13 = t[t.period == 13]
    tot = float((t13.p_act_mw + t13.p_pstr_mw).sum())
    assert abs(tot - dem[13]) < 0.5, f'{tot:.1f} MW frente a {dem[13]:.1f}'


def test_el_n1_solo_cuenta_las_sobrecargas_que_anade_la_contingencia():
    """Un elemento que el caso base ya trae sobrecargado no cuenta en cada caso."""
    from stn import contingencias as C
    base = pd.Series({'a': 105.0, 'b': 95.0, 'c': 50.0, 'd': 120.0})
    post = pd.Series({'a': 106.0, 'b': 101.0, 'c': 50.0, 'd': 130.0})
    # a ya estaba y casi no cambia (+1); b es nueva; d ya estaba y empeora +10
    assert C.sobrecargas_que_anade(post, base) == {'b', 'd'}
    # sin sobrecargas previas se comporta como el recuento en absoluto
    limpia = pd.Series({k: 50.0 for k in post.index})
    assert C.sobrecargas_que_anade(post, limpia) == {'a', 'b', 'd'}
    # un elemento sin dato en el caso base cuenta como nuevo
    assert C.sobrecargas_que_anade(pd.Series({'z': 120.0}), base) == {'z'}
    # y la contingencia no puede "empeorar" lo que baja
    assert C.sobrecargas_que_anade(pd.Series({'a': 101.0}), base) == set()


# ---------------------------------------------------------------------------
# La fotovoltaica va tras un convertidor: ni inercia ni primaria
# ---------------------------------------------------------------------------

def _red_y_sistema_xm(periodo=11):
    import logging
    logging.disable(logging.INFO)
    from stn import agc_deslastre as AGC
    from stn import contingencias as C
    red, _ = C.caso_base(verbose=False,
                         fuente=FuenteXM(FECHA, periodo, verbose=False))
    return red, AGC.Sistema(red)


def test_la_fv_se_ubica_y_no_supera_el_despacho_de_cada_barra():
    """`generacion_convertidor` es parte de `gen`: nunca puede exceder la barra."""
    _hay_snapshot()
    f = FuenteXM(FECHA, 11, verbose=False)
    conv = f.generacion_convertidor()
    gen, _ = f.desglose()
    assert len(conv) and (conv > 0).all(), 'a las 11 h tiene que haber FV'
    assert (conv <= gen.reindex(conv.index) + 1e-6).all(), (
        'la FV de alguna barra supera su generacion total')
    # coincide con la familia solar del listado de XM (menos lo no ubicado)
    from stn.fuentes import generacion_real as GR
    d = f.tablas['dispatch']
    d = d[d.period == 11]
    lst = GR.listado(FECHA)
    fam = d.resource.str.strip().map(lst['fam'])
    solar_xm = float(d.p_mw[(fam == 'solar').values].sum())
    # los recursos que el listado no trae solo cuentan si PARATEC los da como
    # solares, asi que el techo es el listado mas todo lo que no esta en el
    sin_lst = float(d.p_mw[fam.isna().values].sum())
    assert float(conv.sum()) <= solar_xm + sin_lst + 1e-6, (
        f'{conv.sum():.1f} MW de FV, mas que {solar_xm:.1f} del listado y '
        f'{sin_lst:.1f} sin familia')
    assert float(conv.sum()) >= 0.90 * solar_xm, (
        f'se ubica solo {conv.sum():.1f} de {solar_xm:.1f} MW de FV')


def test_la_fv_no_aporta_inercia_ni_reserva_primaria():
    """En una barra solo FV: s_sinc, H*s_sinc y reserva son cero; y quitar la
    marca de convertidor SOLO puede subir inercia y reserva, nunca bajarlas."""
    _hay_snapshot()
    from stn import agc_deslastre as AGC
    red, s = _red_y_sistema_xm(11)
    g = s.gen
    solo = (g.p_conv > 0) & (g.p_sinc <= 1e-9)
    assert solo.any(), 'a las 11 h hay barras solo con FV'
    assert (s.s_sinc[solo] == 0).all()
    assert (s.reserva_por_gen[solo] == 0).all()
    assert (s.reserva_baja_por_gen[solo] == 0).all()
    assert (s.h_por_gen[solo] * s.s_sinc[solo]).sum() == 0
    # contrafactual: la misma red sin la columna, o sea como antes del arreglo
    red2 = red.copy()
    red2.generators['p_conv'] = 0.0
    s2 = AGC.Sistema(red2)
    assert s2.H * s2.S_base > s.H * s.S_base, 'la FV deberia haber inflado la energia cinetica'
    assert s2.reserva > s.reserva, 'la FV deberia haber inflado la reserva'
    # y la masa de FV es la de la fuente
    assert abs(float(g.p_conv.sum())
               - float(FuenteXM(FECHA, 11, verbose=False).generacion_convertidor().sum())) < 1e-6


def test_de_noche_el_arreglo_de_la_fv_es_despreciable():
    """A las 19 h la FV es ~0: el mismo calculo no puede mover la inercia."""
    _hay_snapshot()
    from stn import agc_deslastre as AGC
    red, s = _red_y_sistema_xm(19)
    red2 = red.copy()
    red2.generators['p_conv'] = 0.0
    s2 = AGC.Sistema(red2)
    assert abs(s2.H * s2.S_base - s.H * s.S_base) < 0.01 * s2.H * s2.S_base


def main():
    filtro = None
    if '-k' in sys.argv:
        filtro = sys.argv[sys.argv.index('-k') + 1].lower()

    pruebas = [(k, v) for k, v in globals().items()
               if k.startswith('test_') and callable(v)
               and (filtro is None or filtro in k.lower())]
    if not pruebas:
        print('ninguna prueba coincide con el filtro')
        return 1

    print(f'{len(pruebas)} pruebas de la fuente XM ({FECHA})\n')
    fallos = []
    for nombre, fn in pruebas:
        etq = nombre[5:].replace('_', ' ')
        try:
            fn()
            print(f'  OK    {etq}')
        except AssertionError as e:
            print(f'  FALLA {etq}\n          {e}')
            fallos.append(nombre)
        except Exception as e:                               # noqa: BLE001
            print(f'  ERROR {etq}\n          {type(e).__name__}: {e}')
            fallos.append(nombre)

    print()
    if fallos:
        print(f'{len(fallos)} de {len(pruebas)} fallan')
        return 1
    print(f'las {len(pruebas)} pasan')
    return 0


if __name__ == '__main__':
    sys.exit(main())
