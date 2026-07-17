import click

def confirm_action(prompt_text: str, default: bool = False) -> bool:
    """Helper to prompt for user validation (Human-in-the-loop)."""
    return click.confirm(prompt_text, default=default)
