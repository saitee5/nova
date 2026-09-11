"""
SensorGenerator — runs on a 5-second loop.
Every cycle: computes realistic sensor values for all zones using a
random walk (previous value ± small delta, bounded by realistic min/max).
Every 4–5 cycles (randomised): injects a spike on one randomly chosen
zone that crosses a warning or critical threshold.
Writes every reading to sensor_readings table.
Broadcasts every reading to UI via existing WS manager.
Does NOT call any LLM — that is the existing Gemini Flash poll's job.
"""

from __future__ import annotations

import asyncio
import logging
import random
import sqlite3
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Realistic bounds per sensor type
SENSOR_CONFIG = {
    "gas_lel": {
        "min": 0.0, "max": 5.0,       # normal operating range (%)
        "spike_min": 16.0, "spike_max": 24.0,  # anomaly range
        "unit": "%LEL",
        "warn_threshold": 8.0,
        "critical_threshold": 20.0
    },
    "pressure_bar": {
        "min": 8.0, "max": 12.0,
        "spike_min": 16.0, "spike_max": 22.0,
        "unit": "bar",
        "warn_threshold": 13.5,
        "critical_threshold": 18.0
    },
    "temp_c": {
        "min": 60.0, "max": 85.0,
        "spike_min": 110.0, "spike_max": 145.0,
        "unit": "°C",
        "warn_threshold": 95.0,
        "critical_threshold": 130.0
    },
    "flow_lpm": {
        "min": 280.0, "max": 380.0,
        "spike_min": 480.0, "spike_max": 620.0,
        "unit": "L/min",
        "warn_threshold": 420.0,
        "critical_threshold": 550.0
    }
}

ZONES = ["Z-01", "Z-02", "Z-03", "Z-04", "Z-05"]


class SensorGenerator:
    def __init__(self, db_path: str, ws_manager: Any = None, orchestrator: Any = None) -> None:
        self.db_path = db_path
        self.ws_manager = ws_manager
        self.orchestrator = orchestrator
        self.cycle_num = 0
        self.zone_idx = 0
        self.next_spike_cycle = self._pick_next_spike_cycle()

        # Track current value per zone+sensor (random walk state)
        self.current_values: dict[str, float] = {}
        for zone in ZONES:
            for sensor, cfg in SENSOR_CONFIG.items():
                key = f"{zone}:{sensor}"
                self.current_values[key] = (cfg["min"] + cfg["max"]) / 2.0

    def _pick_next_spike_cycle(self) -> int:
        """Schedule the next anomaly: 12 cycles (60 seconds / 1 minute) from now."""
        return self.cycle_num + 12

    def _random_walk(self, key: str, sensor_type: str) -> float:
        """Move current value by a small realistic delta, stay in bounds."""
        cfg = SENSOR_CONFIG[sensor_type]
        current = self.current_values[key]
        delta_range = (cfg["max"] - cfg["min"]) * 0.03
        delta = random.uniform(-delta_range, delta_range)
        new_val = current + delta
        new_val = max(cfg["min"], min(cfg["max"], new_val))
        self.current_values[key] = new_val
        return round(new_val, 2)

    def _inject_spike(self, zone_id: str, sensor_type: str) -> float:
        """Return a value in the anomaly range — does NOT update random walk state."""
        cfg = SENSOR_CONFIG[sensor_type]
        spike = random.uniform(cfg["spike_min"], cfg["spike_max"])
        return round(spike, 2)

    async def run(self) -> None:
        """Main loop — runs forever, 5-second interval."""
        logger.info("SensorGenerator running loop on db=%s", self.db_path)
        while True:
            try:
                await self._generate_cycle()
            except Exception as exc:
                logger.error("SensorGenerator exception in cycle: %s", exc)
            await asyncio.sleep(5)

    async def _generate_cycle(self) -> None:
        self.cycle_num += 1
        is_spike_cycle = (self.cycle_num >= self.next_spike_cycle)

        spike_zone = ZONES[self.zone_idx % len(ZONES)] if is_spike_cycle else None
        if is_spike_cycle:
            self.zone_idx += 1
        spike_sensor = random.choice(list(SENSOR_CONFIG.keys())) if is_spike_cycle else None

        readings_this_cycle: list[dict[str, Any]] = []

        for zone in ZONES:
            for sensor_type, cfg in SENSOR_CONFIG.items():
                key = f"{zone}:{sensor_type}"
                is_anomaly = 1 if (is_spike_cycle and zone == spike_zone and sensor_type == spike_sensor) else 0

                if is_anomaly:
                    value = self._inject_spike(zone, sensor_type)
                else:
                    value = self._random_walk(key, sensor_type)

                reading = {
                    "zone_id": zone,
                    "sensor_type": sensor_type,
                    "value": value,
                    "unit": cfg["unit"],
                    "is_anomaly": is_anomaly,
                    "cycle_num": self.cycle_num,
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                readings_this_cycle.append(reading)

        # Write all readings to DB in one transaction
        await self._write_to_db(readings_this_cycle)

        # Broadcast each reading to UI via WS (type: sensor_reading)
        if self.ws_manager:
            for reading in readings_this_cycle:
                try:
                    await self.ws_manager.broadcast({
                        "type": "sensor_reading",
                        "payload": reading,
                        "ts": reading["ts"],
                    })
                except Exception as err:
                    logger.debug("WS broadcast error: %s", err)

        # If spike cycle: also notify orchestrator
        if is_spike_cycle and self.orchestrator:
            spike_reading = next(
                r for r in readings_this_cycle
                if r["zone_id"] == spike_zone and r["sensor_type"] == spike_sensor
            )
            try:
                await self.orchestrator.route({
                    "event_type": "sensor_reading",
                    "source_agent": "sensor_generator",
                    "payload": {
                        "readings": readings_this_cycle,
                        "spike": spike_reading,
                    },
                    "case_id": None,
                    "ts": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as err:
                logger.debug("Orchestrator route error: %s", err)
            self.next_spike_cycle = self._pick_next_spike_cycle()

    async def _write_to_db(self, readings: list[dict[str, Any]]) -> None:
        """Write readings to SQLite in one transaction."""
        def _sync_write() -> None:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.executemany("""
                    INSERT INTO sensor_readings
                        (ts, zone_id, sensor_type, value, unit, is_anomaly, cycle_num)
                    VALUES
                        (:ts, :zone_id, :sensor_type, :value, :unit, :is_anomaly, :cycle_num)
                """, readings)
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_sync_write)
