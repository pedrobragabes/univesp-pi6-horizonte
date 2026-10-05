"""Small shared contract checks; no application or database is initialized here."""
from datetime import datetime, timezone
import hmac
import math


def secret_matches(supplied: object, expected: object) -> bool:
    if not isinstance(supplied, str) or not isinstance(expected, str):
        return False
    try:
        return hmac.compare_digest(supplied.encode('utf-8'), expected.encode('utf-8'))
    except UnicodeEncodeError:
        return False


def one_of(value: object, choices: set[str]) -> bool:
    return isinstance(value, str) and value in choices


def bounded_number(value: object, minimum: float, maximum: float) -> float:
    # Check the range before converting an arbitrarily large Python integer.
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum:
        raise ValueError('Medição fora das faixas aceitas.')
    if not math.isfinite(value):
        raise ValueError('Medição deve ser um número finito.')
    return float(value)


def utc_instant(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError('Data de observação inválida.')
    try:
        instant = datetime.fromisoformat(value)
        if instant.tzinfo is None:
            raise ValueError('Data sem fuso.')
        return instant.astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise ValueError('Data de observação inválida ou sem fuso.') from error


def require_recent(instant: datetime) -> None:
    if abs((datetime.now(timezone.utc) - instant).total_seconds()) > 86_400:
        raise ValueError('Data de observação fora da janela de 24 horas.')
