# ─────────────────────────────────────────
#  ShowMe — commands/open_app.py
#  Command wrapper for opening installed apps.
# ─────────────────────────────────────────

import logging
from commands.base_command import BaseCommand

log = logging.getLogger("showme.cmd.open_app")


class OpenAppCommand(BaseCommand):
    name = "open_app"

    def __init__(self, app_dict: dict):
        self.app_dict = app_dict

    def can_handle(self, query: str) -> bool:
        # this is the fallback — always tries
        return True

    def execute(self, query: str) -> bool:
        from apps.matcher   import find_app
        from core.executor  import execute

        result = find_app(query, self.app_dict)
        if result is None:
            log.warning(f"OpenAppCommand: no match for '{query}'")
            return False

        name, path = result
        return execute(name, path)
