
import questionary
from typing import Optional

from rich.panel import Panel
from rich import print as rprint
from rich.console import Console

from src.services import (
    PDFService,
    CacheService,
    InspectorAgent
)
from src.db.models import File
from src.db.connection import get_db
from src.services.index_service import IndexService
from src.config import REDIS_HOST, REDIS_PORT, REDIS_DB, OPENAI_API_KEY

console = Console()

class InteractiveInterface:
        
    def initialize(self):
        try:
            self.db = get_db()
            if not self.db:
                rprint("[red]Error: Could not connect to database[/red]")
                return False
            self.index_service = IndexService(OPENAI_API_KEY, self.db)
            self.file_service = PDFService(self.db, self.index_service)
            self.cache_service = CacheService(REDIS_HOST, REDIS_PORT, REDIS_DB)
            self.agent = InspectorAgent(self.index_service, self.cache_service)
            return True
        except Exception as e:
            rprint(f"[red]Error initializing services: {e}[/red]")
            return False
    
    def cleanup(self):
        if self.db:
            self.db.close()
    
    def show_welcome(self):
        welcome_text = """
[bold cyan]Inspector CLI[/bold cyan]
[dim]Intelligent PDF Document Analysis[/dim]

Navigate using arrow keys, press Enter to select.
Press Ctrl+C to exit at any time.
        """
        console.print(Panel(welcome_text, border_style="cyan"))
    
    def main_menu(self) -> Optional[str]:
        choice = questionary.select(
            "What would you like to do?",
            choices=[
                "Query existing file",
                "Load new file",
                "Exit"
            ],
            style=questionary.Style([
                ('highlighted', 'fg:cyan bold'),
                ('pointer', 'fg:cyan bold'),
            ])
        ).ask()
        
        return choice
    
    def load_file_flow(self):
        file_path = questionary.path(
            "Enter the path to your PDF file:",
        ).ask()
        
        if not file_path:
            return
        
        try:
            rprint(f"\n[cyan]Loading file: {file_path}[/cyan]")
            result = self.file_service.load_file(file_path)
            
            if result["status"] == "already_exists":
                rprint(f"[yellow]File already loaded: {result['file_name']}[/yellow]")
                rprint(f"[yellow]File ID: {result['file_id']}[/yellow]")
            elif result["status"] == "overwritten":
                rprint(f"\n[green]✓ Successfully re-indexed file![/green]")
                rprint(f"[green]File ID: {result['file_id']}[/green]")
                rprint(f"[green]File Name: {result['file_name']}[/green]")
            else:
                rprint(f"\n[green]✓ Successfully loaded file![/green]")
                rprint(f"[green]File ID: {result['file_id']}[/green]")
                rprint(f"[green]File Name: {result['file_name']}[/green]")
            
            questionary.press_any_key_to_continue("Press any key to continue...").ask()
            
        except Exception as e:
            rprint(f"\n[red]Error loading file: {e}[/red]")
            questionary.press_any_key_to_continue("Press any key to continue...").ask()
    
    def select_file(self) -> Optional[tuple]:
        try:
            files = self.file_service.list_files()
            if not files:
                rprint("\n[yellow]No files loaded yet. Please load a file first.[/yellow]")
                questionary.press_any_key_to_continue("Press any key to continue...").ask()
                return None
            choices = [
                questionary.Choice(
                    title=f"{file.file_name} (ID: {file.id})",
                    value=(file)
                )
                for file in files
            ]
            
            choices.append(questionary.Choice(title="← Back to main menu", value="back"))
            
            selection = questionary.select(
                "Select a file to query:",
                choices=choices,
                style=questionary.Style([
                    ('highlighted', 'fg:cyan bold'),
                    ('pointer', 'fg:cyan bold'),
                ])
            ).ask()
            
            return selection
            
        except Exception as e:
            rprint(f"\n[red]Error listing files: {e}[/red]")
            questionary.press_any_key_to_continue("Press any key to continue...").ask()
            return None
    
    def chat_interface(self, file: File):
        console.clear()

        history = self.agent.get_chat_history(file.id)
        
        header = f"""
[bold cyan]Chat Interface[/bold cyan]
[dim]Querying: {file.file_name}[/dim]
[dim]Type your questions or 'exit' to return to main menu[/dim]
[dim]Type 'clear' to clear chat history[/dim]
        """
        console.print(Panel(header, border_style="cyan"))
        if history:
            rprint(f"\n[dim]Loaded {len(history)//2} previous messages[/dim]\n")
        
        while True:
            question = questionary.text(
                "\nYour question:",
                style=questionary.Style([
                    ('question', 'fg:cyan bold'),
                ])
            ).ask()
            
            if not question:
                continue
            
            if question.lower() in ['exit', 'quit', 'back']:
                break
            
            if question.lower() == 'clear':
                self.agent.clear_session(file.id)
                rprint("\n[yellow]Chat history cleared[/yellow]")
                continue
            
            try:
                rprint("\n[dim]Thinking...[/dim]")
                result = self.agent.query(
                    question=question,
                    file=file
                )
                answer_text = result["answer"]
                if result.get("cached"):
                    answer_text += "\n\n[dim](Cached result)[/dim]"
                
                console.print(Panel(
                    answer_text,
                    title="[bold green]Answer[/bold green]",
                    border_style="green"
                ))
                
            except Exception as e:
                rprint(f"\n[red]Error processing query: {e}[/red]")
    
    def run(self):
        console.clear()
        self.show_welcome()
        
        if not self.initialize():
            return
        
        try:
            while True:
                choice = self.main_menu()
                
                if choice == "Exit" or choice is None:
                    rprint("\n[cyan]Goodbye![/cyan]")
                    break
                
                elif choice == "Load new file":
                    self.load_file_flow()
                
                elif choice == "Query existing file":
                    file = self.select_file()
                    if file and file != "back":
                        self.chat_interface(file)
        
        except KeyboardInterrupt:
            rprint("\n\n[yellow]Interrupted by user[/yellow]")
        
        finally:
            self.cleanup()


def start_interactive():
    interface = InteractiveInterface()
    interface.run()