"""Utilities for resolving optimal Livekit voice nodes based on geographic location."""

from math import atan2, cos, radians, sin, sqrt

from stoat import InstanceLivekitVoiceNode
from timezonefinder import get_geometry
from tzlocal import get_localzone


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate the great-circle distance between two points on Earth.

    Args:
        lat1: Latitude of first point in degrees.
        lng1: Longitude of first point in degrees.
        lat2: Latitude of second point in degrees.
        lng2: Longitude of second point in degrees.

    Returns:
        Distance between the two points in kilometers.
    """
    r = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)

    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return r * c


def node_from_timezone(nodes: list[InstanceLivekitVoiceNode]) -> InstanceLivekitVoiceNode:
    """Select the closest Livekit voice node to the user's local timezone.

    Args:
        nodes: List of available Livekit voice nodes.

    Returns:
        The node closest to the user's geographic location based on timezone.

    Raises:
        TypeError: If nodes list is empty.
    """
    if len(nodes) == 1:
        return nodes[0]

    timezone = get_localzone()
    lng, lat = get_geometry(timezone.key, coords_as_pairs=True)[0][0][0]

    return min(nodes, key=lambda node: _haversine(lat, lng, node.latitude, node.longitude))
