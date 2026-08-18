from app.domain.system.health import SystemHealth


class GetSystemHealth:
    def execute(self) -> SystemHealth:
        return SystemHealth()
