"""Interactive CLI for IELTS speaking vocabulary practice."""

import sys
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

from . import config
from .llm import generate, LLMError
from .storage import save, list_saved

console = Console()

WELCOME = """
[bold cyan]IELTS Speaking Vocabulary Coach[/bold cyan]
[dim]雅思口语词汇陪练 — 输入单词，获取 Part 1/2/3 场景 + 地道搭配[/dim]

Type [yellow]:help[/yellow] for commands  |  Type [yellow]:q[/yellow] to quit
"""

HELP_TEXT = """
[yellow]:help[/yellow]     Show this help
[yellow]:list[/yellow]    List saved .md files
[yellow]:out[/yellow]     Open output directory
[yellow]:q[/yellow]       Quit
"""


def show_welcome():
    console.clear()
    console.print()
    console.print(WELCOME)


def show_help():
    console.print(HELP_TEXT)


def show_list():
    files = list_saved()
    if not files:
        console.print("[dim]No saved files yet.[/dim]")
        return

    table = Table(title="Saved Files", box=box.ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Filename", style="cyan")
    table.add_column("Size", justify="right", style="dim")

    for i, f in enumerate(files, 1):
        size_kb = f.stat().st_size / 1024
        table.add_row(str(i), f.name, f"{size_kb:.1f} KB")

    console.print()
    console.print(table)


def show_result(word: str, content: str):
    console.print()
    console.print(Panel(
        Markdown(content),
        title=f"[bold cyan]IELTS Speaking: {word}[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))


def prompt_save(word: str, content: str):
    if Confirm.ask("\nSave this result to .md file?", default=True):
        try:
            filepath = save(word, content)
            console.print(f"[green]Saved:[/green] {filepath}")
        except OSError as e:
            console.print(f"[red]Failed to save:[/red] {e}")
    else:
        console.print("[dim]Skipped.[/dim]")


def run():
    show_welcome()

    if not config.API_KEY:
        console.print()
        console.print(Panel(
            "[yellow]API key not configured.[/yellow]\n\n"
            "Set one of these environment variables:\n"
            "  • [cyan]IELTS_API_KEY[/cyan]\n"
            "  • [cyan]OPENAI_API_KEY[/cyan]\n\n"
            "Or create a [dim].env[/dim] file in the project root:\n"
            "  [dim]IELTS_API_KEY=sk-your-key-here[/dim]\n"
            "  [dim]IELTS_API_BASE=https://api.openai.com/v1  # optional[/dim]",
            title="Configuration",
            border_style="yellow",
        ))
        console.print()

    while True:
        try:
            user_input = Prompt.ask("\n[bold]Enter a word[/bold]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith(":"):
            cmd = user_input.lower()
            if cmd == ":q":
                console.print("[dim]Goodbye![/dim]")
                break
            elif cmd == ":help":
                show_help()
            elif cmd == ":list":
                show_list()
            elif cmd == ":out":
                config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                console.print(f"[dim]Output directory: {config.OUTPUT_DIR}[/dim]")
            else:
                console.print(f"[red]Unknown command: {user_input}[/red]")
                console.print("[dim]Type :help for available commands[/dim]")
            continue

        # Generate content
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Generating IELTS material for '{user_input}'...",
                total=None,
            )
            try:
                content = generate(user_input)
                progress.remove_task(task)
            except LLMError as e:
                progress.remove_task(task)
                console.print(f"\n[red]Error:[/red] {e}")
                continue

        if not content:
            console.print("[red]No response received. Try another word.[/red]")
            continue

        show_result(user_input, content)
        prompt_save(user_input, content)
