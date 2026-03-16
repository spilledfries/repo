from rich.console import Console
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.table import Table
import subprocess
import time
import getpass
import psutil
from datetime import timedelta

console = Console()


def get_cpu_temp() -> str:
    """Return formatted CPU core temperatures from lm-sensors."""
    try:
        raw = subprocess.check_output(
            "sensors 2>/dev/null | grep -E 'Core [0-9]+'", shell=True
        ).decode().strip()
        lines = []
        for line in raw.splitlines():
            parts = line.split()
            # e.g. "Core 0:   +42.0°C  (high = +80.0°C, crit = +100.0°C)"
            if len(parts) >= 3:
                core = f"{parts[0]} {parts[1]}"   # "Core 0:"
                temp = parts[2]                    # "+42.0°C"
                lines.append(f"  {core:<10} {temp}")
        return "\n".join(lines) if lines else "  Temp unavailable"
    except Exception:
        return "  Temp unavailable"


def get_cpu_usage() -> str:
    """Return per-core CPU usage percentages."""
    percents = psutil.cpu_percent(percpu=True)
    overall = psutil.cpu_percent()
    lines = [f"  Overall:   [bold cyan]{overall:>5.1f}%[/bold cyan]"]
    for i, p in enumerate(percents):
        bar = "█" * int(p / 5) + "░" * (20 - int(p / 5))
        lines.append(f"  Core {i:<3}  {bar} {p:>5.1f}%")
    return "\n".join(lines)


def get_ram() -> str:
    """Return formatted RAM usage."""
    vm = psutil.virtual_memory()
    used_gb  = vm.used  / 1024**3
    total_gb = vm.total / 1024**3
    pct      = vm.percent
    bar_len  = 20
    filled   = int(bar_len * pct / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    swap = psutil.swap_memory()
    swap_used_gb  = swap.used  / 1024**3
    swap_total_gb = swap.total / 1024**3
    return (
        f"  RAM:  {bar} {pct:.1f}%\n"
        f"        {used_gb:.2f} GB / {total_gb:.2f} GB\n"
        f"  Swap: {swap_used_gb:.2f} GB / {swap_total_gb:.2f} GB"
    )


def get_disk() -> str:
    """Return disk usage for key mount points."""
    lines = []
    for part in psutil.disk_partitions():
        if part.fstype in ("", "squashfs", "tmpfs", "devtmpfs"):
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
            pct    = usage.percent
            filled = int(pct / 5)
            bar    = "█" * filled + "░" * (20 - filled)
            used_g  = usage.used  / 1024**3
            total_g = usage.total / 1024**3
            lines.append(
                f"  {part.mountpoint:<12} {bar} {pct:.1f}%\n"
                f"               {used_g:.1f} GB / {total_g:.1f} GB"
            )
        except PermissionError:
            continue
    return "\n".join(lines) if lines else "  Disk info unavailable"


def get_uptime() -> str:
    """Return system uptime as a human-readable string."""
    boot_time = psutil.boot_time()
    uptime_sec = time.time() - boot_time
    td = timedelta(seconds=int(uptime_sec))
    days    = td.days
    hours   = td.seconds // 3600
    minutes = (td.seconds % 3600) // 60
    seconds = td.seconds % 60
    return f"  {days}d {hours:02d}h {minutes:02d}m {seconds:02d}s"


_prev_net: dict | None = None
_prev_time: float | None = None


def get_network() -> str:
    """Return IP addresses and live network send/receive rates."""
    global _prev_net, _prev_time

    # IP addresses
    ip_lines = []
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if addr.family.name == "AF_INET" and not addr.address.startswith("127."):
                ip_lines.append(f"  {iface:<12} {addr.address}")

    # Throughput (bytes/sec since last call)
    now = time.time()
    counters = psutil.net_io_counters(pernic=True)

    rate_lines = []
    if _prev_net is not None and _prev_time is not None:
        elapsed = now - _prev_time
        if elapsed > 0:
            for iface, cur in counters.items():
                if iface not in _prev_net:
                    continue
                prev = _prev_net[iface]
                tx_kbs = (cur.bytes_sent - prev.bytes_sent) / elapsed / 1024
                rx_kbs = (cur.bytes_recv - prev.bytes_recv) / elapsed / 1024
                if tx_kbs > 0.01 or rx_kbs > 0.01:
                    rate_lines.append(
                        f"  {iface:<12} ↑ {tx_kbs:>7.2f} KB/s  ↓ {rx_kbs:>7.2f} KB/s"
                    )

    _prev_net  = {iface: cnt for iface, cnt in counters.items()}
    _prev_time = now

    ip_section   = "\n".join(ip_lines)   or "  No external IPs found"
    rate_section = "\n".join(rate_lines) or "  (measuring…)"
    return f"[bold]IP Addresses[/bold]\n{ip_section}\n\n[bold]Throughput[/bold]\n{rate_section}"


def build_layout() -> Layout:
    layout = Layout()
    layout.split(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )
    layout["left"].split(
        Layout(name="cpu"),
        Layout(name="ram"),
    )
    layout["right"].split(
        Layout(name="disk"),
        Layout(name="network"),
    )
    return layout


def main() -> None:
    layout = build_layout()
    user   = getpass.getuser()

    with Live(layout, refresh_per_second=1, screen=True):
        while True:
            layout["header"].update(
                Panel(
                    f"[bold white]⬡ Hardware Monitor[/bold white]  "
                    f"[dim]user:[/dim] [cyan]{user}[/cyan]  "
                    f"[dim]uptime:[/dim] [green]{get_uptime().strip()}[/green]",
                    style="bold blue",
                )
            )

            layout["cpu"].update(
                Panel(
                    f"[bold]Temperatures[/bold]\n{get_cpu_temp()}\n\n"
                    f"[bold]Usage[/bold]\n{get_cpu_usage()}",
                    title="[bold yellow]CPU[/bold yellow]",
                    border_style="yellow",
                )
            )

            layout["ram"].update(
                Panel(
                    get_ram(),
                    title="[bold magenta]Memory[/bold magenta]",
                    border_style="magenta",
                )
            )

            layout["disk"].update(
                Panel(
                    get_disk(),
                    title="[bold green]Disk[/bold green]",
                    border_style="green",
                )
            )

            layout["network"].update(
                Panel(
                    get_network(),
                    title="[bold cyan]Network[/bold cyan]",
                    border_style="cyan",
                )
            )

            layout["footer"].update(
                Panel(
                    "[dim]Refreshes every second  •  Press [bold]CTRL+C[/bold] to exit[/dim]",
                    style="dim",
                )
            )

            time.sleep(1)


if __name__ == "__main__":
    main()
