# ─────────────────────────────────────────
#  ShowMe — commands/base_command.py
#  Base class all commands inherit from.
# ─────────────────────────────────────────

class BaseCommand:
    name = "base"

    def can_handle(self, query: str) -> bool:
        """Return True if this command can handle the query."""
        raise NotImplementedError

    def execute(self, query: str) -> bool:
        """Execute the command. Return True on success."""
        raise NotImplementedError
