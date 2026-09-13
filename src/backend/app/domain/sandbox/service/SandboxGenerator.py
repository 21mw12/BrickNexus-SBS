import random

from .SandboxFaultRuntime import SandboxFaultRuntime, sandbox_fault_runtime


class SandboxGenerator:
    def __init__(
        self,
        fault_runtime: SandboxFaultRuntime = sandbox_fault_runtime,
        rng: random.Random | None = None,
    ) -> None:
        self.fault_runtime = fault_runtime
        self.rng = rng or random.Random()

    def generate(self, sandbox_id: str, config: dict, tick: int) -> list[dict]:
        rows = []
        for terminal in config.get("terminals", []):
            for sensor in terminal.get("sensors", []):
                for point in sensor.get("points", []):
                    generator = point["generator"]
                    noise = self.fault_runtime.noise(
                        sandbox_id, point["id"], tick, float(generator["noise"])
                    )
                    value = float(point["base_value"]) + self.rng.gauss(0, noise)
                    value = min(max(value, float(generator["min"])), float(generator["max"]))
                    value = self.fault_runtime.apply(
                        sandbox_id, point["id"], tick, value
                    )
                    rows.append({
                        "sandbox_id": sandbox_id,
                        "point_id": point["id"],
                        "tick": tick,
                        "value": value,
                    })
        return rows


sandbox_generator = SandboxGenerator()
