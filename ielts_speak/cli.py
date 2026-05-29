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
from .llm import generate, review_pronunciation, LLMError
from .storage import save_interlinked, list_saved
from .audio import generate_tts_for_word, get_practice_text, record_and_transcribe

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
    if Confirm.ask("\nSave to Obsidian vault? (generates interlinked notes)", default=True):
        try:
            files = save_interlinked(word, content)
            main = files[0]
            sub_count = len(files) - 1
            console.print(f"\n[green]Saved {main.name}[/green] + [cyan]{sub_count} linked notes[/cyan]")
            console.print(f"[dim]Main: {main.parent}[/dim]")
            console.print("[dim]Sub:  synonyms/  antonyms/  collocations/  topics/[/dim]")
        except OSError as e:
            console.print(f"[red]Failed to save:[/red] {e}")
    else:
        console.print("[dim]Skipped.[/dim]")


def prompt_tts(word: str, content: str):
    """Ask if user wants to generate TTS audio for the sample answers."""
    if not Confirm.ask("\nGenerate audio sample (MP3, British English)?", default=True):
        console.print("[dim]Skipped audio.[/dim]")
        return

    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        mp3_path = generate_tts_for_word(word, content, config.OUTPUT_DIR)
        if mp3_path:
            console.print(f"[green]Audio saved:[/green] {mp3_path}")
        else:
            console.print("[dim]No English sample text found to generate audio.[/dim]")
    except RuntimeError as e:
        console.print(f"[red]TTS failed:[/red] {e}")


def prompt_reading_test(word: str, content: str):
    """Ask if user wants to do a pronunciation reading test with STT + LLM review."""
    if not Confirm.ask("\nReading test? (record yourself and get pronunciation feedback)", default=False):
        console.print("[dim]Skipped reading test.[/dim]")
        return

    practice_text = get_practice_text(content)
    if not practice_text:
        console.print("[dim]No English sample text found for reading practice.[/dim]")
        return

    console.print()
    console.print("[bold]Read this aloud:[/bold]")
    console.print(Panel(practice_text, border_style="yellow", padding=(1, 2)))

    console.print("\n[dim]Press Enter when ready to start recording...[/dim]")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]Cancelled.[/dim]")
        return

    console.print("[bold yellow]🎤 Recording... speak now![/bold yellow]")
    try:
        transcribed = record_and_transcribe()
    except RuntimeError as e:
        console.print(f"\n[red]Recording failed:[/red] {e}")
        return

    console.print(f"\n[dim]You said:[/dim] {transcribed}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Analyzing pronunciation...", total=None)
        try:
            feedback = review_pronunciation(practice_text, transcribed)
            progress.remove_task(task)
        except LLMError as e:
            progress.remove_task(task)
            console.print(f"\n[red]Review failed:[/red] {e}")
            return

    console.print()
    console.print(Panel(
        Markdown(feedback),
        title="[bold green]Pronunciation Feedback[/bold green]",
        border_style="green",
        padding=(1, 2),
    ))


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

        # Collect user's personal context
        console.print()
        console.print(
            "[bold yellow]💡 考官提问：[/bold yellow]"
            "如果要在 Part 2 或 Part 3 中用到 "
            f"[cyan]{user_input}[/cyan]，"
            "你打算结合什么经历来展开？"
        )
        console.print("[dim]（用中文或简短英文输入你的思路）[/dim]")
        try:
            user_thought = Prompt.ask("\n[bold]Your thought[/bold]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Cancelled.[/dim]")
            continue

        if not user_thought:
            console.print("[dim]No input provided, using generic context.[/dim]")

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
                content = generate(user_input, user_thought)
                progress.remove_task(task)
            except LLMError as e:
                progress.remove_task(task)
                console.print(f"\n[red]Error:[/red] {e}")
                continue

        if not content:
            console.print("[bold red]No response received.[/bold red] The API returned empty content — check the model or API key.")
            continue

        show_result(user_input, content)
        prompt_save(user_input, content)
        prompt_tts(user_input, content)
        prompt_reading_test(user_input, content)
