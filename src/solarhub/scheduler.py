"""Atualização automática no sistema atual: systemd --user (Linux) ou Agendador de Tarefas (Windows)."""
from __future__ import annotations

from solarhub import osutil
from solarhub.errors import TimerError

if osutil.IS_WINDOWS:
    from solarhub import winsched as _impl
else:
    from solarhub import systemd as _impl

__all__ = ["TimerError", "NAME", "enable", "disable", "status", "schedule", "write_units", "available"]

NAME = getattr(_impl, "NAME", "systemd do usuário")
enable = _impl.enable
disable = _impl.disable
status = _impl.status
schedule = _impl.schedule
write_units = _impl.write_units
available = _impl.available
