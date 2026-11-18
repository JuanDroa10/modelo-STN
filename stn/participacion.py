# stn/participacion.py
"""Participacion de cada tecnologia en la generacion, en un momento o en un rango.

    python -m stn.participacion --fecha 2026-11-01 --periodo 13
    python -m stn.participacion --fecha 2026-11-01 --desde 9 --hasta 15
    python -m stn.participacion --fecha 2026-11-01                      # el dia entero
    python -m stn.participacion --fecha 2026-11-01 --origen ambos       # real y programado

Las familias son solar, hidroelectrica, gas, carbon, otras termicas y eolica.
Gas y carbon salen del COMBUSTIBLE que XM declara para cada recurso, que es lo
que PARATEC no da; "otras termicas" agrupa ACPM, combustoleo, jet, bagazo,
biomasa y biogas.

`--origen`:
    real        la generacion MEDIDA por XM (se baja sola si no esta en disco)
    programado  el despacho dDEC que usa el modelo por defecto; necesita el
                snapshot de la fecha (`python -m stn.fuentes.descarga_xm`)
    ambos       las dos, para ver cuanto se desvio el programa de lo ocurrido

Un periodo da un grafico de barras; un rango, las curvas por periodo. Los
porcentajes son sobre la generacion total de cada periodo, no sobre la demanda.
"""

import argparse
import os
import sys

from stn.fuentes import generacion_real as GR

COLORES = {'solar': '#ff9f1c', 'hidroeléctrica': '#1f77b4', 'gas': '#6a3d9a',
           'carbón': '#333333', 'otras térmicas': '#a0a0a0',
           'eólica': '#2ca02c'}
ROTULO = {'solar': 'Solar', 'hidroeléctrica': 'Hidroeléctrica', 'gas': 'Gas',
          'carbón': 'Carbón', 'otras térmicas': 'Otras térmicas',
          'eólica': 'Eólica'}
PRINCIPALES = ('solar', 'hidroeléctrica', 'gas', 'carbón')


def _coma(v, dec=1):
    return f'{v:,.{dec}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def calcular(fecha, origen, periodos):
    """(MW, %) por familia, columnas = los periodos pedidos."""
    mw = GR.mw_por_familia(fecha, origen)[list(periodos)]
    return mw, GR.participacion_pct(mw)


def asegurar_real(fecha, verbose=True):
    """Baja la generacion real si no esta en disco."""
    if not GR.disponible(fecha):
        if verbose:
            print(f"  bajando de XM la generacion real de {fecha}...")
        GR.descargar(fecha, verbose=verbose)


def tabla(fecha, orig, periodos, mw, pct):
    """Texto con los MW y el porcentaje de cada familia."""
    cab = '  periodo ' + ''.join(f'{ROTULO[k][:11]:>13s}' for k in mw.index)
    lineas = [f"\n  {orig.upper()}  {fecha}", cab]
    for p in periodos:
        lineas.append(f'  {p:>7d}  ' + ''.join(
            f"{_coma(pct.loc[k, p]):>7s} %  " for k in mw.index))
    if len(periodos) > 1:
        lineas.append('    media  ' + ''.join(
            f"{_coma(pct[list(periodos)].mean(axis=1)[k]):>7s} %  "
            for k in mw.index))
    return '\n'.join(lineas)


def graficar(fecha, series, periodos, destino):
    """`series` = {origen: (mw, pct)}. Escribe el PNG en `destino`."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.ticker import FuncFormatter

    plt.style.use('classic')
    plt.rcParams.update({'font.size': 11, 'figure.facecolor': 'white',
                         'savefig.dpi': 200, 'axes.grid': True,
                         'grid.alpha': 0.3})
    comas = FuncFormatter(lambda v, _: _coma(v, 0))
    nombre = {'real': 'generación real', 'programado': 'despacho programado'}
    una = len(periodos) == 1

    if una:
        p = periodos[0]
        fam = list(next(iter(series.values()))[0].index)
        fig, ax = plt.subplots(figsize=(9, 4.8))
        x = np.arange(len(fam))
        n = len(series)
        ancho = 0.8 / n
        estilos = {'real': '#ff9f1c', 'programado': '#1f77b4'}
        for j, (o, (mw, pct)) in enumerate(series.items()):
            pos = x + (j - (n - 1) / 2) * ancho
            ax.bar(pos, [pct.loc[k, p] for k in fam], ancho, edgecolor='k',
                   color=[COLORES[k] for k in fam] if n == 1 else estilos[o],
                   label=nombre[o])
            for xi, k in zip(pos, fam):
                ax.text(xi, pct.loc[k, p] + 0.6, _coma(pct.loc[k, p]),
                        ha='center', fontsize=8)
        ax.set_xticks(x)
        ax.set_xticklabels([ROTULO[k].replace(' ', '\n') for k in fam],
                           fontsize=9)
        ax.set_ylabel('Participación (%)')
        ax.set_ylim(0, None)
        tot = {o: mw[p].sum() for o, (mw, _) in series.items()}
        sub = ' · '.join(f'{nombre[o]}: {_coma(t, 0)} MW' for o, t in tot.items())
        ax.set_title(f'Participación por tecnología, {fecha} periodo {p}\n{sub}',
                     fontsize=10)
        if n > 1:
            ax.legend(loc='upper right', fontsize=9)
    else:
        fig, ax = plt.subplots(figsize=(10, 5.4))
        fam = PRINCIPALES + ('otras térmicas',)
        for o, (mw, pct) in series.items():
            ls = '-' if o == 'real' else '--'
            for k in fam:
                lw = 1.2 if k == 'otras térmicas' else 2.5
                etq = ROTULO[k] + (f' ({o})' if len(series) > 1 else '')
                ax.plot(list(periodos), [pct.loc[k, p] for p in periodos],
                        color=COLORES[k], lw=lw, ls=ls, label=etq)
        ax.set_xlim(min(periodos), max(periodos))
        ax.set_xlabel('Periodo (1 = 00:00-01:00)')
        ax.set_ylabel('Participación en la generación (%)')
        ax.set_ylim(0, None)
        ax.yaxis.set_major_formatter(comas)
        ax.legend(loc='upper center', ncol=4 if len(series) > 1 else 5,
                  fontsize=8, bbox_to_anchor=(0.5, -0.12))
        t = ' y '.join(nombre[o] for o in series)
        ax.set_title(f'Participación por tecnología, {fecha}, periodos '
                     f'{min(periodos)} a {max(periodos)} ({t})', fontsize=10)
    fig.tight_layout()
    fig.savefig(destino, bbox_inches='tight')
    plt.close(fig)
    return destino


def rango(periodo, desde, hasta):
    """Periodos pedidos: uno, un rango, o el dia entero."""
    if periodo is not None:
        a = b = int(periodo)
    else:
        a = 1 if desde is None else int(desde)
        b = 24 if hasta is None else int(hasta)
    if not (1 <= a <= 24 and 1 <= b <= 24):
        raise ValueError('los periodos van de 1 a 24')
    if a > b:
        a, b = b, a
    return list(range(a, b + 1))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Participacion de cada tecnologia en la generacion, en '
                    'un periodo o en un rango.')
    ap.add_argument('--fecha', required=True, metavar='AAAA-MM-DD')
    ap.add_argument('--periodo', type=int, default=None, metavar='N',
                    help='un solo periodo 1..24 (da un grafico de barras)')
    ap.add_argument('--desde', type=int, default=None, metavar='N')
    ap.add_argument('--hasta', type=int, default=None, metavar='N')
    ap.add_argument('--origen', choices=('real', 'programado', 'ambos'),
                    default='real')
    a = ap.parse_args(argv)

    try:
        periodos = rango(a.periodo, a.desde, a.hasta)
        origenes = ('real', 'programado') if a.origen == 'ambos' else (a.origen,)
        # El listado de recursos (el combustible) hace falta tambien para el
        # programado, y viene con la descarga de la generacion real.
        asegurar_real(a.fecha)
        series = {}
        for o in origenes:
            series[o] = calcular(a.fecha, o, periodos)
    except (GR.ErrorGeneracionReal, FileNotFoundError, ValueError) as e:
        print(f'ERROR: {e}')
        return 1

    for o, (mw, pct) in series.items():
        print(tabla(a.fecha, o, periodos, mw, pct))
    from stn.config import salida
    tramo = f'p{periodos[0]}' if len(periodos) == 1 else \
        f'p{periodos[0]}-{periodos[-1]}'
    dest = salida(f"participacion_{a.fecha.replace('-', '')}_{a.origen}_"
                  f"{tramo}.png")
    graficar(a.fecha, series, periodos, dest)
    print(f'\n  figura guardada en {dest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
