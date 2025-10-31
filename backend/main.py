"""
AuraLink backend
"""
import os
import sys
import time
import signal
import logging
from datetime import datetime
from threading import Thread, Event
from pathlib import Path
from dotenv import load_dotenv
from functools import partial

from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from rich import box

from textual.app import App, ComposeResult
from textual.containers import Grid, Vertical
from textual.widgets import Header, Footer, Static, RichLog
from textual.reactive import reactive

BACKEND_DIR = Path(__file__).parent.absolute()
ROOT_DIR = BACKEND_DIR.parent.absolute()
os.chdir(BACKEND_DIR)

env_path = ROOT_DIR / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

from llm_agent import LLMAgent
from mqtt_client import MQTTCLIENT
from email_handler import EmailHandler


class AuraLinkSystem:
    """Main system coordinator"""
    
    def __init__(self, app_instance: 'AuraLinkTUI'):
        self.app = app_instance
        self.running = Event()
        self.running.set()
        
        self.llm_agent = None
        self.mqtt_client = None
        self.email_handler = None
        
        self.latest_sensor_data = {}

    def log_from_thread(self, message: str, level: str = "info"):
        """Logging from non-worker threads (like MQTT callback)"""
        log_func = getattr(self.app, f"log_{level}", self.app.log_info)
        self.app.call_from_thread(log_func, f"SYS: {message}")

    def initialize_components(self):
        """Initialize all system components (runs in worker thread)"""
        self.log_from_thread("[bold cyan]Initializing AuraLink System[/bold cyan]")
        
        try:
            self.log_from_thread("Loading LLM Agent...")
            self.llm_agent = LLMAgent()
            self.app.call_from_thread(self.app.update_status, 'llm', 'Ready', 'green')
            self.log_from_thread("LLM Agent... [green]✓[/green]")
        except Exception as e:
            self.app.call_from_thread(self.app.update_status, 'llm', f'Error: {str(e)[:30]}', 'red')
            self.log_from_thread(f"LLM Agent... [red]✗[/red] {str(e)}", "error")
            return False
        
        try:
            self.log_from_thread("Connecting to Gmail API...")
            self.email_handler = EmailHandler()
            self.app.call_from_thread(self.app.update_status, 'email', 'Connected', 'green')
            self.log_from_thread("Gmail API... [green]✓[/green]")
        except Exception as e:
            self.app.call_from_thread(self.app.update_status, 'email', f'Error: {str(e)[:30]}', 'yellow')
            self.log_from_thread(f"Gmail API... [yellow]⚠[/yellow] {str(e)}", "warning")
        
        try:
            self.log_from_thread("Connecting to MQTT Broker...")
            self.mqtt_client = MQTTCLIENT(on_sensor_data_callback=self.handle_sensor_data)
            if self.mqtt_client.connect():
                self.app.call_from_thread(self.app.update_status, 'mqtt', 'Connected', 'green')
                self.log_from_thread("MQTT Broker... [green]✓[/green]")
            else:
                self.app.call_from_thread(self.app.update_status, 'mqtt', 'Connection Failed', 'red')
                self.log_from_thread("MQTT Broker... [red]✗[/red]", "error")
                return False
        except Exception as e:
            self.app.call_from_thread(self.app.update_status, 'mqtt', f'Error: {str(e)[:30]}', 'red')
            self.log_from_thread(f"MQTT Broker... [red]✗[/red] {str(e)}", "error")
            return False
        
        self.log_from_thread("[bold green]System Initialized Successfully[/bold green]")
        return True
    
    def handle_sensor_data(self, sensor_data):
        """Callback for incoming sensor data from MQTT (runs in MQTT thread)"""
        if not self.running.is_set():
            return
            
        sensor_data['timestamp'] = datetime.now().isoformat()
        self.latest_sensor_data = sensor_data
        
        self.app.call_from_thread(self.app.update_sensor, sensor_data)
        
        work_to_run = partial(self.process_and_respond, sensor_data)
        self.app.run_worker(work_to_run, exclusive=True, group="processing")
    
    def force_process(self):
        """Manually trigger processing with the latest data"""
        if self.latest_sensor_data:
            self.app.log_info("[yellow]Forcing manual data process...[/yellow]")
            work_to_run = partial(self.process_and_respond, self.latest_sensor_data)
            self.app.run_worker(work_to_run, exclusive=True, group="processing")
        else:
            self.app.log_warning("[red]No sensor data received yet. Cannot force process.[/red]")

    async def process_and_respond(self, sensor_data):
        """Process sensor data with LLM (runs in Textual worker)"""
        if not self.llm_agent:
            self.app.log_warning("SYS: LLM not ready. Skipping process.")
            return

        try:
            emails = []
            if self.email_handler:
                try:
                    self.app.log_info("SYS: Checking for new emails...")
                    emails = self.email_handler.get_recent_emails(max_results=5, hours=24)
                    self.app.increment_stat('emails_processed', len(emails))
                    self.app.log_info(f"SYS: Found {len(emails)} new email(s).")
                except Exception as e:
                    self.app.log_warning(f"SYS: Could not fetch emails: {e}")
            
            self.app.log_info("SYS: Generating message with LLM...")
            combined_message = self.llm_agent.generate_combined_message(
                sensor_data, 
                emails
            )
            
            self.app.update_message(combined_message)
            
            if self.mqtt_client and self.mqtt_client.is_mqtt_connected():
                self.mqtt_client.publish_message(combined_message)
                self.app.increment_stat('messages_sent')
                self.app.log_info("SYS: Published message to device.")
                
        except Exception as e:
            self.app.log_error(f"SYS: Processing Error: {str(e)}")
    
    def shutdown(self):
        """Clean shutdown of all components"""
        self.app.log_info("\n[yellow]Shutting down AuraLink System...[/yellow]")
        self.running.clear()
        
        if self.mqtt_client:
            self.mqtt_client.disconnect()
        
        self.app.log_info("[green]System shutdown complete.[/green]\n")


class StatusWidget(Static):

    system_status = reactive({
        'mqtt': ('Disconnected', 'red'),
        'llm': ('Not Initialized', 'yellow'),
        'email': ('Not Initialized', 'yellow'),
        'last_update': ('N/A', 'white')
    })

    def render(self) -> Panel:
        table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2), expand=True)
        table.add_column("Component", style="bold cyan", ratio=1)
        table.add_column("Status", ratio=2)

        status_icons = {
            'green': '●',
            'yellow': '▲',
            'red': '✗',
            'white': '○'
        }

        component_labels = {
            'mqtt': 'MQTT Broker',
            'llm': 'LLM Agent',
            'email': 'Email Service',
            'last_update': 'Last Update'
        }

        for component, (status, color) in self.system_status.items():
            icon = status_icons.get(color, '○')
            label = component_labels.get(component, component.upper())
            table.add_row(
                f"{label}",
                f"[{color}]{icon}[/{color}] [{color}]{status}[/{color}]"
            )

        return Panel(
            table,
            title="[bold cyan]═══ System Status ═══[/bold cyan]",
            border_style="bright_cyan",
            padding=(1, 1)
        )

    def update_status(self, component: str, status: str, color: str):
        new_status = self.system_status.copy()
        new_status[component] = (status, color)
        self.system_status = new_status


class SensorWidget(Static):

    sensor_data = reactive({})

    def render(self) -> Panel:
        if not self.sensor_data:
            content = Text()
            content.append("\n   ", style="")
            content.append("◌", style="dim yellow")
            content.append("  Awaiting sensor data stream...\n", style="dim italic")
            return Panel(
                content,
                title="[bold yellow]═══ Environmental Sensors ═══[/bold yellow]",
                border_style="bright_yellow",
                padding=(1, 1)
            )

        table = Table(show_header=False, box=box.ROUNDED, padding=(0, 2), expand=True)
        table.add_column("Metric", style="bold yellow", ratio=2)
        table.add_column("Value", justify="right", style="white", ratio=3)

        temp = self.sensor_data.get('temperature', 'N/A')
        humidity = self.sensor_data.get('humidity', 'N/A')
        air_quality = self.sensor_data.get('airQuality', 'N/A')

        temp_color = "red" if isinstance(temp, (int, float)) and temp > 30 else "cyan" if isinstance(temp, (int, float)) and temp < 18 else "green"
        humidity_color = "yellow" if isinstance(humidity, (int, float)) and (humidity < 30 or humidity > 60) else "green"

        air_quality_status = "N/A"
        air_quality_color = "white"
        if isinstance(air_quality, int):
            if air_quality < 800:
                air_quality_status = "Good"
                air_quality_color = "green"
            elif air_quality < 1500:
                air_quality_status = "Moderate"
                air_quality_color = "yellow"
            else:
                air_quality_status = "Poor"
                air_quality_color = "red"

        table.add_row(
            "[T] Temperature",
            f"[{temp_color}]{temp}°C[/{temp_color}]" if temp != 'N/A' else "N/A"
        )
        table.add_row(
            "[H] Humidity",
            f"[{humidity_color}]{humidity}%[/{humidity_color}]" if humidity != 'N/A' else "N/A"
        )
        table.add_row(
            "[A] Air Quality",
            f"[{air_quality_color}]{air_quality} ({air_quality_status})[/{air_quality_color}]" if air_quality != 'N/A' else "N/A"
        )

        timestamp = self.sensor_data.get('timestamp', 'N/A')
        if timestamp != 'N/A' and 'T' in timestamp:
            timestamp = timestamp.split('T')[1].split('.')[0]

        table.add_row(
            "[*] Last Reading",
            f"[dim]{timestamp}[/dim]"
        )

        return Panel(
            table,
            title="[bold yellow]═══ Environmental Sensors ═══[/bold yellow]",
            border_style="bright_yellow",
            padding=(1, 1)
        )


class MessageWidget(Static):

    latest_message = reactive(None)

    def render(self) -> Panel:
        if not self.latest_message:
            content = Text()
            content.append("\n   ", style="")
            content.append("◌", style="dim green")
            content.append("  No messages sent to device yet\n", style="dim italic")
            return Panel(
                content,
                title="[bold green]═══ Device Messages ═══[/bold green]",
                border_style="bright_green",
                padding=(1, 1)
            )

        message_content = Text()

        message_content.append("┌─ INSPIRATIONAL QUOTE", style="bold bright_green")
        message_content.append("\n│\n", style="bright_green")
        quote_lines = self.latest_message.get('quote', 'N/A').split('\n')
        for line in quote_lines:
            message_content.append("│  ", style="bright_green")
            message_content.append(f"{line}\n", style="italic white")
        message_content.append("└", style="bright_green")
        message_content.append("─" * 50 + "\n\n", style="bright_green")

        message_content.append("┌─ EMAIL SUMMARY", style="bold bright_blue")
        message_content.append("\n│\n", style="bright_blue")
        email_summary = self.latest_message.get('email_summary', 'No emails')
        email_lines = email_summary.split('\n')
        for line in email_lines:
            message_content.append("│  ", style="bright_blue")
            message_content.append(f"{line}\n", style="white")
        message_content.append("└", style="bright_blue")
        message_content.append("─" * 50 + "\n\n", style="bright_blue")

        priority = self.latest_message.get('priority', 'low')
        priority_colors = {'high': 'red', 'medium': 'yellow', 'low': 'green'}
        priority_icons = {'high': '[!]', 'medium': '[~]', 'low': '[✓]'}
        priority_color = priority_colors.get(priority, 'white')
        priority_icon = priority_icons.get(priority, '[·]')

        message_content.append("PRIORITY LEVEL: ", style="bold white")
        message_content.append(f"{priority_icon} {priority.upper()}", style=f"bold {priority_color}")

        return Panel(
            message_content,
            title="[bold green]═══ Device Messages ═══[/bold green]",
            border_style="bright_green",
            padding=(1, 2)
        )


class StatsWidget(Static):

    stats = reactive({
        'messages_sent': 0,
        'emails_processed': 0,
        'sensor_readings': 0,
    })

    uptime_start = reactive(datetime.now())
    uptime_str = reactive("0:00:00")

    def on_mount(self):
        self.set_interval(1.0, self.update_uptime)

    def update_uptime(self):
        uptime_delta = datetime.now() - self.uptime_start
        self.uptime_str = str(uptime_delta).split('.')[0]

    def increment_stat(self, key: str, amount: int = 1):
        new_stats = self.stats.copy()
        new_stats[key] += amount
        self.stats = new_stats

    def render(self) -> Text:
        content = Text(justify="center")
        content.append("[", style="dim")
        content.append("UPTIME", style="bold bright_white")
        content.append("] ", style="dim")
        content.append(f"{self.uptime_str}", style="cyan")
        content.append("  |  ", style="dim")
        content.append("[", style="dim")
        content.append("READINGS", style="bold bright_white")
        content.append("] ", style="dim")
        content.append(f"{self.stats['sensor_readings']}", style="yellow")
        content.append("  |  ", style="dim")
        content.append("[", style="dim")
        content.append("MESSAGES", style="bold bright_white")
        content.append("] ", style="dim")
        content.append(f"{self.stats['messages_sent']}", style="green")
        content.append("  |  ", style="dim")
        content.append("[", style="dim")
        content.append("EMAILS", style="bold bright_white")
        content.append("] ", style="dim")
        content.append(f"{self.stats['emails_processed']}", style="blue")
        return content


class AuraLinkTUI(App):
    """A Textual app for the AuraLink IoT System"""

    CSS_PATH = "app.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("p", "force_process", "Force Process"),
        ("l", "toggle_logs", "Toggle Logs"),
    ]

    def __init__(self):
        super().__init__()
        self.system = AuraLinkSystem(self)
        
        self.log_widget = RichLog(id="logs", wrap=True, highlight=True, markup=True)
        self.message_widget = MessageWidget(id="message")
        self.sensor_widget = SensorWidget(id="sensor")
        self.status_widget = StatusWidget(id="status")
        self.stats_footer = StatsWidget(id="stats-footer")

    def compose(self) -> ComposeResult:
        yield Header(name="AuraLink IoT Intelligence Platform")
        with Grid(id="main-grid"):
            with Vertical(id="left-column"):
                yield self.status_widget
                yield self.sensor_widget
            with Vertical(id="right-column"):
                yield self.message_widget
                yield self.log_widget
        yield self.stats_footer
        yield Footer()

    async def on_mount(self) -> None:
        self.log_widget.write("[bold bright_cyan]" + "=" * 60 + "[/bold bright_cyan]")
        self.log_widget.write("[bold bright_cyan]        AuraLink IoT Intelligence Platform v1.0[/bold bright_cyan]")
        self.log_widget.write("[bold bright_cyan]" + "=" * 60 + "[/bold bright_cyan]")
        self.log_widget.write("")
        self.log_widget.write("[dim]> Initializing system components...[/dim]")
        self.run_worker(self.system.initialize_components, group="init_worker", thread=True)
        self.log_widget.write("[dim]> System initialization worker started[/dim]")

    def action_quit(self) -> None:
        self.log_info("Shutdown requested by user...")
        self.system.shutdown()
        self.exit()

    def action_force_process(self) -> None:
        self.log_info("[yellow]User triggered manual process...[/yellow]")
        self.system.force_process()

    def action_toggle_logs(self) -> None:
        self.log_widget.display = not self.log_widget.display
        if self.log_widget.display:
            self.message_widget.styles.height = "1fr"
            self.log_info("Log panel shown.")
        else:
            self.message_widget.styles.height = "100%"
            self.notify("Logs hidden (press 'l' to show)")

    def log_info(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_widget.write(f"[dim]{timestamp}[/dim] [cyan]INFO[/cyan]  {message}")

    def log_warning(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_widget.write(f"[dim]{timestamp}[/dim] [yellow]WARN[/yellow]  {message}")

    def log_error(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_widget.write(f"[dim]{timestamp}[/dim] [red]ERROR[/red] {message}")

    def update_status(self, component: str, status: str, color: str):
        self.status_widget.update_status(component, status, color)
        if component == 'last_update':
            self.status_widget.update_status('last_update', status, color)

    def update_sensor(self, sensor_data: dict):
        self.sensor_widget.sensor_data = sensor_data
        self.increment_stat('sensor_readings')
        self.update_status('last_update', datetime.now().strftime("%H:%M:%S"), 'white')

    def update_message(self, message: dict):
        self.message_widget.latest_message = message

    def increment_stat(self, key: str, amount: int = 1):
        self.stats_footer.increment_stat(key, amount)


if __name__ == "__main__":
    css = """
    Screen {
        background: $surface;
    }

    Header {
        background: $primary;
        color: $text;
        text-style: bold;
    }

    Footer {
        background: $panel;
    }

    #main-grid {
        layout: grid;
        grid-size: 2;
        grid-columns: 38% 1fr;
        grid-rows: 1fr;
        height: 100%;
        width: 100%;
        padding: 0 1;
    }

    #left-column {
        height: 100%;
        layout: vertical;
        padding: 0 1 0 0;
    }

    #right-column {
        height: 100%;
        layout: vertical;
        padding: 0 0 0 1;
    }

    #status {
        height: 12;
        margin: 1 0;
        border: rounded $primary;
        background: $surface;
    }

    #sensor {
        height: 1fr;
        margin: 1 0;
        border: rounded $primary;
        background: $surface;
    }

    #message {
        height: 1fr;
        margin: 1 0;
        border: rounded $primary;
        background: $surface;
    }

    #logs {
        height: 1fr;
        margin: 1 0;
        border: rounded $primary;
        background: $surface;
    }

    #stats-footer {
        dock: bottom;
        height: 1;
        width: 100%;
        background: $panel;
        padding: 0 2;
    }

    RichLog {
        scrollbar-gutter: stable;
    }
    """
    with open("app.tcss", "w") as f:
        f.write(css)

    app = AuraLinkTUI()
    app.run()