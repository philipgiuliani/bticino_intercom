"""Tests for the BTicino sensor platform."""

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bticino_intercom.const import DOMAIN

from .conftest import (
    BRIDGE_MAC,
    EXT_UNIT_MODULE_ID,
    EXTERNAL_UNIT_2_ID,
    EXTERNAL_UNIT_2_NAME,
    EXTERNAL_UNIT_NAME,
)


def _get_coordinator(hass: HomeAssistant, entry: MockConfigEntry):
    """Get the coordinator from hass data."""
    return hass.data[DOMAIN][entry.entry_id]["coordinator"]


async def test_sensor_entities_created(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """Test that expected sensor entities are created."""
    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    # last_event_type, last_call_timestamp, uptime, wifi, ws_status, local_ip
    assert len(states) >= 6


async def test_event_sensor_state(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """Test event sensor shows the latest event type."""
    # Find the last_event_type sensor
    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    event_entity = [s for s in states if "last_event_type" in s]
    assert len(event_entity) == 1

    state = hass.states.get(event_entity[0])
    assert state is not None
    # From our fixture data, the first subevent type is "missed_call"
    assert state.state == "missed_call"


async def test_event_sensor_attributes(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """Test event sensor has expected attributes."""
    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    event_entity = next(s for s in states if "last_event_type" in s)
    state = hass.states.get(event_entity)

    assert state.attributes.get("event_id") == "evt_1"
    assert state.attributes.get("event_module_id") == EXT_UNIT_MODULE_ID
    assert "snapshot_url" in state.attributes


async def test_event_sensor_updates_on_websocket(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """Test event sensor updates when coordinator gets a websocket event."""
    coordinator = _get_coordinator(hass, mock_setup_entry)
    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    event_entity = next(s for s in states if "last_event_type" in s)

    # Simulate a websocket call event (RTC offer format)
    from .conftest import BRIDGE_MAC

    message = {
        "push_type": "BNC1-rtc",
        "extra_params": {
            "device_id": BRIDGE_MAC,
            "session_id": "sess_test_001",
            "data": {
                "type": "offer",
                "session_description": {
                    "type": "call",
                    "module_id": EXT_UNIT_MODULE_ID,
                    "sdp": "v=0\r\n",
                },
            },
        },
    }
    await coordinator._process_websocket_event(message)
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = hass.states.get(event_entity)
    # After processing an "incoming_call" event, the sensor state should reflect it
    assert state.state == "incoming_call"


async def test_last_call_timestamp_sensor(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """Test last call timestamp sensor has a valid timestamp."""
    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    ts_entity = [s for s in states if "last_call_timestamp" in s]
    assert len(ts_entity) == 1

    state = hass.states.get(ts_entity[0])
    assert state is not None
    # Should be a valid ISO timestamp from the fixture data
    assert state.state != "unknown"
    assert state.state != "unavailable"


async def test_bridge_uptime_sensor(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """Test bridge uptime/last boot sensor."""
    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    boot_entity = [s for s in states if "last_boot" in s or "uptime" in s]
    assert len(boot_entity) == 1

    state = hass.states.get(boot_entity[0])
    assert state is not None
    # Now a timestamp sensor showing boot time, should be a valid ISO date
    assert state.state != "unknown"
    assert state.state != "unavailable"


async def test_bridge_wifi_strength_sensor(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """Test bridge WiFi strength sensor shows negative RSSI."""
    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    wifi_entity = [s for s in states if "wifi_strength" in s]
    assert len(wifi_entity) == 1

    state = hass.states.get(wifi_entity[0])
    assert state is not None
    # From fixture: wifi_strength = 65, should be made negative
    assert int(state.state) == -65


async def test_bridge_websocket_status_sensor(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """Test bridge websocket status sensor."""
    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    ws_entity = [s for s in states if "websocket_status" in s]
    assert len(ws_entity) == 1

    state = hass.states.get(ws_entity[0])
    assert state is not None
    assert state.state == "connected"


async def test_bridge_local_ip_sensor(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """Test bridge local IP sensor."""
    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    ip_entity = [s for s in states if "local_ip" in s]
    assert len(ip_entity) == 1

    state = hass.states.get(ip_entity[0])
    assert state is not None
    assert state.state == "192.168.1.100"


async def test_sensor_unavailable_on_coordinator_failure(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
    mock_account,
) -> None:
    """Test sensors become unavailable when coordinator update fails."""
    coordinator = _get_coordinator(hass, mock_setup_entry)
    from pybticino.exceptions import ApiError

    mock_account.async_update_topology.side_effect = ApiError(500, "fail")
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    uptime_entity = [s for s in states if "uptime" in s]
    if uptime_entity:
        state = hass.states.get(uptime_entity[0])
        assert state.state == "unavailable"


def _sensor_id(hass: HomeAssistant, entry: MockConfigEntry, unique_suffix: str) -> str:
    """Resolve a sensor entity id from its unique-id suffix."""
    registry = er.async_get(hass)
    unique_id = f"{entry.entry_id}_{unique_suffix}"
    entity_id = registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)
    assert entity_id is not None, unique_id
    return entity_id


async def test_global_event_sensor_names_the_door(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """The whole-home last-event sensor reports which station the event belongs to."""
    states = hass.states.async_entity_ids(SENSOR_DOMAIN)
    event_entity = next(s for s in states if "last_event_type" in s)
    state = hass.states.get(event_entity)
    assert state.attributes.get("module_id") == EXT_UNIT_MODULE_ID
    assert state.attributes.get("module_name") == EXTERNAL_UNIT_NAME


async def test_per_door_event_sensors_stay_separate(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """Each outdoor station keeps its own last event and last ring."""
    strada_event = _sensor_id(hass, mock_setup_entry, f"{EXT_UNIT_MODULE_ID}_last_event")
    ingresso_event = _sensor_id(hass, mock_setup_entry, f"{EXTERNAL_UNIT_2_ID}_last_event")
    strada_ring = _sensor_id(hass, mock_setup_entry, f"{EXT_UNIT_MODULE_ID}_last_ring")
    ingresso_ring = _sensor_id(hass, mock_setup_entry, f"{EXTERNAL_UNIT_2_ID}_last_ring")

    strada = hass.states.get(strada_event)
    ingresso = hass.states.get(ingresso_event)
    assert strada is not None and ingresso is not None
    assert strada.state == "missed_call"
    assert strada.attributes.get("module_id") == EXT_UNIT_MODULE_ID
    assert strada.attributes.get("module_name") == EXTERNAL_UNIT_NAME
    assert strada.attributes.get("snapshot_url") == "https://example.com/snapshot.jpg"
    assert EXTERNAL_UNIT_NAME in strada.attributes["friendly_name"]
    # The other station has no history, so it must not inherit Strada's call.
    # It stays online (unknown) until that door rings for the first time.
    assert ingresso.state == "unknown"
    assert ingresso.attributes.get("module_id") == EXTERNAL_UNIT_2_ID
    assert ingresso.attributes.get("module_name") == EXTERNAL_UNIT_2_NAME

    ring = hass.states.get(strada_ring)
    assert ring is not None
    assert ring.state not in ("unknown", "unavailable")
    assert ring.attributes.get("event_type") == "missed_call"
    assert hass.states.get(ingresso_ring).state == "unknown"


async def test_per_door_event_sensor_follows_only_its_station(
    hass: HomeAssistant,
    mock_setup_entry: MockConfigEntry,
) -> None:
    """A ring at one station does not change the other station's last event."""
    coordinator = _get_coordinator(hass, mock_setup_entry)
    strada_event = _sensor_id(hass, mock_setup_entry, f"{EXT_UNIT_MODULE_ID}_last_event")
    ingresso_event = _sensor_id(hass, mock_setup_entry, f"{EXTERNAL_UNIT_2_ID}_last_event")
    ingresso_ring = _sensor_id(hass, mock_setup_entry, f"{EXTERNAL_UNIT_2_ID}_last_ring")

    message = {
        "push_type": "BNC1-rtc",
        "extra_params": {
            "device_id": BRIDGE_MAC,
            "session_id": "sess_ingresso",
            "data": {
                "type": "offer",
                "session_description": {
                    "type": "call",
                    "module_id": EXTERNAL_UNIT_2_ID,
                    "sdp": "v=0\r\n",
                },
            },
        },
    }
    await coordinator._process_websocket_event(message)
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    assert hass.states.get(strada_event).state == "missed_call"
    assert hass.states.get(ingresso_event).state == "incoming_call"
    assert hass.states.get(ingresso_event).attributes.get("module_name") == EXTERNAL_UNIT_2_NAME
    assert hass.states.get(ingresso_ring).state not in ("unknown", "unavailable")
    assert hass.states.get(ingresso_ring).attributes.get("module_id") == EXTERNAL_UNIT_2_ID
