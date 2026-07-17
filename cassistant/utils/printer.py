from rich.console import Console

console = Console()

def print_success(message: str):
    console.print(f"[bold green]✓[/bold green] {message}")

def print_warning(message: str):
    console.print(f"[bold yellow]⚠️  {message}[/bold yellow]")

def print_info(message: str):
    console.print(f"[blue]ℹ[/blue] {message}")

def print_error(message: str):
    console.print(f"[bold red]✗ {message}[/bold red]")
