"""Channel services.

Services are intentionally not eagerly imported here: RequestService controls the
collector runtime, while the collector resolves channels, so eager imports would
form a cycle during application startup.
"""

__all__: list[str] = []
