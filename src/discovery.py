import re

SENSOR_MAP = {}
DEFAULT_EXPIRE_AFTER = 7200
QUANTITY_LABELS = {}


def parse_topic(topic: str) -> dict | None:
    pass


def sanitize_object_id(s: str) -> str:
    pass


def build_object_id(alias: str, resource: str, address: str, quantity: str) -> str:
    pass


def sensor_meta(resource: str, quantity: str, overrides: dict | None = None) -> dict | None:
    pass


def build_device_name(alias: str, location_labels: dict | None = None,
                      name_overrides: dict | None = None) -> str:
    pass


def build_entity_name(resource: str, quantity: str, address: str,
                      sibling_count: int = 1,
                      name_overrides: dict | None = None) -> str:
    pass


def build_discovery_payload(
    parsed: dict,
    meta: dict,
    device_name: str,
    entity_name: str,
) -> tuple[str, str, dict]:
    """Returns (object_id, discovery_topic, payload_dict)."""
    pass
