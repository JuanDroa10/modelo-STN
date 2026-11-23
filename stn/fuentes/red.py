# stn/fuentes/red.py
"""Lo comun de las descargas por HTTPS (portal de XM y servicio de generacion real).

DOS COSAS, y las dos nacieron de un fallo real en un Windows sin proxy de empresa:

1. EL CONTEXTO TLS. Python verifica el certificado contra una lista de raices y
   NO va a buscar el certificado intermedio que un servidor deje sin enviar. Un
   navegador si lo busca (la extension AIA del certificado), y por eso una pagina
   que Chrome abre sin quejas puede fallar en Python con
   `unable to get local issuer certificate`. `truststore` hace que Python verifique
   con el verificador del propio sistema operativo (Windows, macOS), que se
   comporta como el navegador y ademas conoce las raices que la empresa instala.
   Es opcional: si no esta instalado, o si el usuario fijo `SSL_CERT_FILE` /
   `SSL_CERT_DIR`, se usa el contexto de siempre.

2. EL MENSAJE. El error de Python no decia POR QUE fallo, y el texto que lo
   envolvia suponia siempre un proxy corporativo. Aqui se devuelve la razon real
   (`verify_message`) y una pista que corresponde a esa razon.
"""
import os
import ssl


def contexto_ssl():
    """Contexto para `urlopen(..., context=)`, o None para el de por defecto."""
    if os.environ.get('SSL_CERT_FILE') or os.environ.get('SSL_CERT_DIR'):
        return None                       # eleccion explicita del usuario
    try:
        import truststore
    except ImportError:
        return None
    try:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception:                                        # noqa: BLE001
        return None


def explicar_fallo_ssl(error, host):
    """Texto para un `URLError` cuyo `reason` es un `ssl.SSLError`.

    `error` es el URLError. Dice la razon que da OpenSSL y la accion que le
    corresponde, en vez de culpar siempre a un proxy.
    """
    r = getattr(error, 'reason', error)
    razon = getattr(r, 'verify_message', None) or str(r)
    bajo = razon.lower()
    usa_truststore = contexto_ssl() is not None
    lineas = [f'el certificado de {host} no se pudo verificar.',
              f'Razon que da el sistema: {razon}']
    if 'local issuer' in bajo or 'unable to verify the first' in bajo:
        lineas.append(
            'Falta un certificado en la cadena: el servidor no envio el '
            'intermedio, o la raiz no esta en el almacen de este equipo.')
        if not usa_truststore:
            lineas.append(
                'Prueba con:  pip install truststore  ---Python entonces '
                'verifica como lo hace el navegador y busca el intermedio '
                'que falta---, y repite.')
    elif 'expired' in bajo or 'not yet valid' in bajo:
        lineas.append(
            'Revisa la fecha y la hora del equipo: un reloj desfasado hace '
            'parecer vencido (o futuro) un certificado vigente. Si la fecha '
            'esta bien, el vencido es el del servidor y no hay nada que '
            'hacer de este lado.')
    elif 'self' in bajo or 'self-signed' in bajo:
        lineas.append(
            'Algo en el camino (un proxy, un antivirus que inspecciona HTTPS) '
            'esta firmando con una raiz propia.')
    if usa_truststore or 'local issuer' not in bajo:
        lineas.append(
            'Si el equipo esta tras un proxy de empresa o un antivirus que '
            'inspecciona HTTPS, apunta SSL_CERT_FILE al almacen que tiene su '
            'raiz:  macOS  export SSL_CERT_FILE=/opt/homebrew/etc/'
            'ca-certificates/cert.pem   |   Windows  set '
            'SSL_CERT_FILE=C:\\ruta\\a\\cacert.pem')
    lineas.append(
        'Mientras tanto, la opcion "despacho programado" no necesita este '
        'servicio.' if 'servapibi' in host else '')
    return '\n'.join(l for l in lineas if l)
