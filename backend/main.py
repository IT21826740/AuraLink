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
        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        table.add_column("Component", style="cyan")
        table.add_column("Status")
        
        for component, (status, color) in self.system_status.items():
            table.add_row(component.upper(), f"[{color}]{status}[/{color}]")
            
        return Panel(table, title="System Status", border_style="cyan")

    def update_status(self, component: str, status: str, color: str):
        new_status = self.system_status.copy()
        new_status[component] = (status, color)
        self.system_status = new_status


class SensorWidget(Static):
    
    sensor_data = reactive({})

    def render(self) -> Panel:
        if not self.sensor_data:
            return Panel("Waiting for sensor data...", title="Sensor Data", border_style="yellow")

        table = Table(show_header=False, box=box.SIMPLE, padding=(0, 1))
        table.add_column("Metric", style="yellow")
        table.add_column("Value", style="white")
        
        table.add_row("Temperature", f"{self.sensor_data.get('temperature', 'N/A')}°C")
        table.add_row("Humidity", f"{self.sensor_data.get('humidity', 'N/A')}%")
        table.add_row("Air Quality", f"{self.sensor_data.get('airQuality', 'N/A')}")
        table.add_row("Updated", self.sensor_data.get('timestamp', 'N/A'))
        
        return Panel(table, title="Sensor Data", border_style="yellow")


class MessageWidget(Static):

    latest_message = reactive(None)

    def render(self) -> Panel:
        if not self.latest_message:
            return Panel("No messages generated yet", title="Latest Message to Device", border_style="green")
        
        message_content = Text()
        message_content.append("Quote:\n", style="bold green")
        message_content.append(f"{self.latest_message.get('quote', 'N/A')}\n\n", style="italic")
        message_content.append("Email Summary:\n", style="bold blue")
        message_content.append(f"{self.latest_message.get('email_summary', 'No emails')}\n\n")
        
        priority = self.latest_message.get('priority', 'low')
        priority_colors = {'high': 'red', 'medium': 'yellow', 'low': 'green'}
        message_content.append("Priority: ", style="bold")
        message_content.append(priority.upper(), style=f"bold {priority_colors.get(priority, 'white')}")
        
        return Panel(message_content, title="Latest Message to Device", border_style="green")


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
        return Text(
            f"Uptime: {self.uptime_str} | "
            f"Readings: {self.stats['sensor_readings']} | "
            f"Messages: {self.stats['messages_sent']} | "
            f"Emails: {self.stats['emails_processed']}",
            justify="center",
            style="dim"
        )


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
        yield Header(name="AuraLink Smart IoT System")
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
        self.log_widget.write("[yellow]TUI mounted. Initializing system in background...[/yellow]")
        self.run_worker(self.system.initialize_components, group="init_worker", thread=True)
        self.log_widget.write("[yellow]System initialization worker started.[/yellow]")

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
        self.log_widget.write(message)

    def log_warning(self, message: str):
        self.log_widget.write(f"[yellow]WARN:[/] {message}")

    def log_error(self, message: str):
        self.log_widget.write(f"[red]ERROR:[/] {message}")

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
    #main-grid {
        layout: grid;
        grid-size: 2;
        grid-columns: 35% 1fr;
        grid-rows: 1fr;
        height: 100%;
        width: 100%;
    }
    
    #left-column {
        height: 100%;
        layout: vertical;
    }
    
    #right-column {
        height: 100%;
        layout: vertical;
    }

    #status {
        height: 10;
        border: solid cyan;
    }
    
    #sensor {
        height: 1fr;
        border: solid yellow;
    }
    
    #message {
        height: 1fr;
        border: solid green;
    }
    
    #logs {
        height: 1fr;
        border: solid grey;
    }
    
    #stats-footer {
        dock: bottom;
        height: 1;
        width: 100%;
        background: $surface;
    }
    """
    with open("app.tcss", "w") as f:
        f.write(css)

    app = AuraLinkTUI()
    app.run()