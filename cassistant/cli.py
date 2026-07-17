import click
from .config import ensure_config_exists
from .utils.printer import print_info

@click.group()
def cli():
    """Cassistant — Your AI-assisted programming companion."""
    ensure_config_exists()

@cli.command("init")
@click.option("--force", is_flag=True, help="Force overwrite existing indices")
def init(force):
    """Initialize the project codebase analysis and documentation."""
    # Placeholder for command implementation
    from .commands.init import run_init
    run_init(force)

@cli.command("status")
def status():
    """Check the health status of documentation indexing compared to active source code."""
    from .commands.status import run_status
    run_status()

@cli.command("update")
@click.argument("files", nargs=-1)
@click.option("--dirty", is_flag=True, help="Only update files whose hash values don't match")
@click.option("--all", "update_all", is_flag=True, help="Update all documented files")
def update(files, dirty, update_all):
    """Update documentation indexing for changed files."""
    from .commands.update import run_update
    run_update(files, dirty, update_all)

@cli.command("plan")
@click.argument("query")
def plan(query):
    """Analyze a requirement and formulate an implementation plan."""
    from .commands.plan import run_plan
    run_plan(query)

@cli.command("build")
@click.argument("query", required=False)
@click.option("--from-plan", is_flag=True, help="Use the last generated plan output")
def build(query, from_plan):
    """Modify the codebase to fulfill a requirement or apply an implementation plan."""
    from .commands.build import run_build
    run_build(query, from_plan)

@cli.command("rollback")
@click.argument("timestamp", required=False)
def rollback(timestamp):
    """Revert changes back to a specific timestamp snapshot."""
    from .commands.rollback import run_rollback
    run_rollback(timestamp)

def main():
    cli()
