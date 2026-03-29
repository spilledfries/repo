import subprocess
import time
from rich.live import Live
from rich.table import Table

INTERFACE = "wlp16s0"

def get_signal_strength():
    result = subprocess.run(
        ["iw", "dev", INTERFACE, "link"],
        capture_output=True,
        text=True
    )

    for line in result.stdout.split("\n"):
        if "signal:" in line:
            return int(line.split("signal:")[1].split()[0])

    return None


def signal_bar(signal):
    if signal is None:
        return "No Signal"

    strength = max(min((signal + 100) // 5, 20), 0)
    return "█" * strength + "░" * (20 - strength)


def build_table(signal):

    table = Table(title="📡 WiFi Signal Monitor")

    table.add_column("Interface")
    table.add_column("Signal")
    table.add_column("Strength")

    table.add_row(
        INTERFACE,
        f"{signal} dBm",
        signal_bar(signal)
    )

    return table


with Live(build_table(-100), refresh_per_second=2) as live:

    while True:
        signal = get_signal_strength()
        live.update(build_table(signal))
        time.sleep(2)
