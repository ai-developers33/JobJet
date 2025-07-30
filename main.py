#!/usr/bin/env python3
import click
import os
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from src.agent import WorkdayAgent
from src.llm_client import LLMClient

console = Console()

@click.group()
def cli():
    """Workday Desktop Agent - Automatically fill job applications using your resume"""
    pass

@cli.command()
@click.option('--resume', '-r', required=True, help='Path to your resume (PDF or DOCX)')
@click.option('--url', '-u', required=True, help='Workday application URL')
@click.option('--headless', is_flag=True, help='Run browser in headless mode')
def fill(resume, url, headless):
    """Automatically fill a Workday application"""
    
    # Validate resume file
    if not os.path.exists(resume):
        console.print(f"❌ [red]Resume file not found: {resume}[/red]")
        return
    
    if not resume.lower().endswith(('.pdf', '.docx')):
        console.print("❌ [red]Resume must be PDF or DOCX format[/red]")
        return
    
    console.print("🤖 [bold blue]Workday Desktop Agent[/bold blue]")
    console.print(f"📄 Resume: {resume}")
    console.print(f"🌐 URL: {url}")
    
    if not Confirm.ask("\nProceed with automatic application filling?"):
        return
    
    try:
        # Initialize agent
        agent = WorkdayAgent()
        
        # Run the automation
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Filling application...", total=None)
            
            results = agent.auto_fill_application(url, resume)
        
        # Display results
        console.print("\n" + "="*50)
        console.print("📊 [bold]MULTI-PAGE AUTOMATION RESULTS[/bold]")
        console.print("="*50)
        
        if results["success"]:
            console.print("✅ [green]Multi-page application completed successfully![/green]")
        else:
            console.print("❌ [red]Multi-page application failed[/red]")
        
        console.print(f"�  Pages processed: {results.get('pages_completed', 0)}")
        console.print(f"📝 Total fields filled: {results.get('total_fields_filled', 0)}")
        console.print(f"📎 Resume uploaded: {'✅' if results.get('resume_uploaded', False) else '❌'}")
        
        if results.get("errors"):
            console.print("\n⚠️ [yellow]Errors encountered:[/yellow]")
            for error in results["errors"]:
                console.print(f"  • {error}")
        
        console.print(f"\n📸 Screenshots saved in: screenshots/")
        console.print("\n⚠️ [yellow]Please review the application before submitting![/yellow]")
        
    except KeyboardInterrupt:
        console.print("\n🛑 [yellow]Operation cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"\n❌ [red]Unexpected error: {str(e)}[/red]")
    finally:
        # Cleanup
        try:
            agent.cleanup()
        except:
            pass

@cli.command()
@click.option('--resume', '-r', required=True, help='Path to your resume (PDF or DOCX)')
def parse(resume):
    """Parse and preview resume data"""
    
    if not os.path.exists(resume):
        console.print(f"❌ [red]Resume file not found: {resume}[/red]")
        return
    
    try:
        console.print("📄 [blue]Parsing resume...[/blue]")
        
        agent = WorkdayAgent()
        resume_data = agent.load_resume(resume)
        
        # Display parsed data
        console.print("\n" + "="*50)
        console.print("📋 [bold]PARSED RESUME DATA[/bold]")
        console.print("="*50)
        
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Name", resume_data.name)
        table.add_row("Email", resume_data.email)
        table.add_row("Phone", resume_data.phone)
        table.add_row("Address", resume_data.address)
        table.add_row("Summary", resume_data.summary[:100] + "..." if len(resume_data.summary) > 100 else resume_data.summary)
        table.add_row("Skills", ", ".join(resume_data.skills[:5]) + ("..." if len(resume_data.skills) > 5 else ""))
        table.add_row("Experience", f"{len(resume_data.experience)} positions")
        table.add_row("Education", f"{len(resume_data.education)} entries")
        
        console.print(table)
        
        if resume_data.experience:
            console.print("\n💼 [bold]Experience:[/bold]")
            for exp in resume_data.experience[:3]:  # Show first 3
                console.print(f"  • {exp.get('title', 'N/A')} at {exp.get('company', 'N/A')}")
        
    except Exception as e:
        console.print(f"❌ [red]Error parsing resume: {str(e)}[/red]")

@cli.command()
def test():
    """Test system requirements"""
    console.print("🔧 [blue]Testing system requirements...[/blue]")
    
    # Test LLM connection
    try:
        from src.llm_client import OpenRouterClient
        openrouter_key = "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"
        client = OpenRouterClient(openrouter_key, model="deepseek/deepseek-chat")
        if client.test_connection():
            console.print("✅ [green]OpenRouter DeepSeek Chat (FREE) service is working[/green]")
        else:
            console.print("❌ [red]Cannot connect to OpenRouter DeepSeek Chat service[/red]")
    except Exception as e:
        console.print(f"❌ [red]OpenRouter DeepSeek Chat test failed: {str(e)}[/red]")
    
    # Test browser setup
    try:
        agent = WorkdayAgent()
        agent.setup_browser()
        console.print("✅ [green]Browser setup successful[/green]")
        agent.cleanup()
    except Exception as e:
        console.print(f"❌ [red]Browser test failed: {str(e)}[/red]")
        console.print("   Make sure Chrome is installed")

@cli.command()
def demo():
    """Run a demo with sample data"""
    console.print("🎬 [bold blue]Demo Mode[/bold blue]")
    console.print("This will demonstrate the agent with sample data")
    
    if not Confirm.ask("Continue with demo?"):
        return
    
    # Create sample resume for demo
    sample_resume_path = "sample_resume.pdf"
    if not os.path.exists(sample_resume_path):
        console.print("❌ [red]Please create a sample resume file first[/red]")
        console.print("   You can use any PDF resume for testing")
        return
    
    demo_url = Prompt.ask("Enter a Workday application URL for demo", 
                         default="https://example.workday.com/apply")
    
    try:
        agent = WorkdayAgent()
        results = agent.auto_fill_application(demo_url, sample_resume_path)
        console.print("🎉 [green]Demo completed![/green]")
    except Exception as e:
        console.print(f"❌ [red]Demo failed: {str(e)}[/red]")

if __name__ == '__main__':
    cli()