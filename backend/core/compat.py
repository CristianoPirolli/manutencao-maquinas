"""Ajustes de compatibilidade de plataforma."""

import asyncio
import sys
import warnings


def configurar_event_loop_windows() -> None:
    """Usa o ``SelectorEventLoop`` no Windows, como no roteiro original.

    O loop padrão do Windows (Proactor) causa avisos intermitentes ao encerrar
    conexões com ``uvicorn --reload``. A API de *policies* foi marcada como
    obsoleta no Python 3.14, então o aviso de depreciação é silenciado aqui.
    """
    if sys.platform != "win32":
        return

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
