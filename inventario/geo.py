import math


def haversine_km(lat1, lon1, lat2, lon2):
    """Distancia en kilómetros entre dos coordenadas (fórmula de Haversine)."""
    radio_tierra = 6371.0
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return radio_tierra * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))