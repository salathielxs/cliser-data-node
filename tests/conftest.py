from __future__ import annotations

import pytest

from api.rate_limit import rate_limiter


@pytest.fixture(autouse=True)
def isolate_rate_limiter():
    """
    Mantém o singleton global do rate limiter isolado entre testes.

    O rate limiter é estadoful em produção, mas testes não devem
    herdar eventos produzidos por testes anteriores.
    """
    rate_limiter.clear()

    yield

    rate_limiter.clear()
