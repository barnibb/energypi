"""System-DNS ausschließlich für Meross-HTTP-Sitzungen im Lüfterprozess."""


def configure_meross_dns():
    import aiohttp
    import meross_iot.http_api as meross_http
    from aiohttp.resolver import ThreadedResolver

    # MerossIot 0.4.10.4 erzeugt ClientSession intern ohne Connector-Option.
    # Nur seine lokale Factory ersetzen, nicht aiohttp global verändern.
    if getattr(meross_http.ClientSession,'_energypi_system_dns',False):
        return
    original=meross_http.ClientSession

    def client_session(*args,**kwargs):
        if kwargs.get('connector') is None:
            kwargs['connector']=aiohttp.TCPConnector(resolver=ThreadedResolver())
            kwargs['connector_owner']=True
        return original(*args,**kwargs)

    client_session._energypi_system_dns=True
    meross_http.ClientSession=client_session
