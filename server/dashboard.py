"""
Dashboard terminal interactif avec Rich
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def create_terminal_dashboard(computers_data):
    """Crée le dashboard terminal interactif avec Rich"""
    console = Console()

    def show_main_menu():
        console.clear()
        console.print(
            "[bold blue]🖥️ Monitoring Dashboard Terminal[/bold blue]", justify="center"
        )
        console.print("=" * 50, justify="center")
        console.print()

        # Statistiques
        total = len(computers_data)
        console.print(f"[green]Ordinateurs connectés: {total}[/green]")
        console.print()

        # Menu
        console.print("[yellow]Menu:[/yellow]")
        console.print("1. Voir tous les ordinateurs")
        console.print("2. Détails d'un ordinateur")
        console.print("3. Statistiques générales")
        console.print("4. Quitter")
        console.print()

    def show_all_computers():
        console.clear()
        table = Table(title="🖥️ Tous les ordinateurs")
        table.add_column("Hostname", style="cyan", no_wrap=True)
        table.add_column("IP", style="magenta")
        table.add_column("CPU %", style="red")
        table.add_column("RAM %", style="green")
        table.add_column("OS", style="yellow")
        table.add_column("Status", style="blue")

        for hostname, data in computers_data.items():
            # Extract IP
            ip = "N/A"
            if data.get("interfaces"):
                for interface_data in data["interfaces"].values():
                    if interface_data.get("addresses"):
                        for addr in interface_data["addresses"]:
                            if (
                                addr.get("type") == "IPv4"
                                and addr.get("address") != "127.0.0.1"
                            ):
                                ip = addr["address"]
                                break
                        if ip != "N/A":
                            break

            cpu = f"{data.get('cpu_percent', 0):.1f}%"
            ram = f"{data.get('memory', {}).get('percent', 0):.1f}%"
            os_info = data.get("system", "N/A")
            status = "En ligne"

            table.add_row(hostname, ip, cpu, ram, os_info, status)

        console.print(table)
        console.print()
        console.input("[dim]Appuyez sur Entrée pour continuer...[/dim]")

    def show_computer_details():
        console.clear()
        if not computers_data:
            console.print("[red]Aucun ordinateur connecté.[/red]")
            console.input("[dim]Appuyez sur Entrée pour continuer...[/dim]")
            return

        console.print("[yellow]Ordinateurs disponibles:[/yellow]")
        for i, hostname in enumerate(computers_data.keys(), 1):
            console.print(f"{i}. {hostname}")

        try:
            choice = int(console.input("\nChoisissez un numéro: ")) - 1
            hostnames = list(computers_data.keys())
            if 0 <= choice < len(hostnames):
                hostname = hostnames[choice]
                data = computers_data[hostname]

                console.clear()
                console.print(f"[bold blue]Détails de {hostname}[/bold blue]")
                console.print("=" * 40)

                # Informations de base
                console.print(f"[cyan]Système:[/cyan] {data.get('system', 'N/A')}")
                console.print(
                    f"[cyan]Version:[/cyan] {data.get('system_version', 'N/A')}"
                )
                console.print(
                    f"[cyan]Architecture:[/cyan] {data.get('architecture', 'N/A')}"
                )

                # IP
                ip = "N/A"
                if data.get("interfaces"):
                    for interface_data in data["interfaces"].values():
                        if interface_data.get("addresses"):
                            for addr in interface_data["addresses"]:
                                if (
                                    addr.get("type") == "IPv4"
                                    and addr.get("address") != "127.0.0.1"
                                ):
                                    ip = addr["address"]
                                    break
                            if ip != "N/A":
                                break
                console.print(f"[cyan]IP:[/cyan] {ip}")

                # Métriques
                console.print(f"[red]CPU:[/red] {data.get('cpu_percent', 0):.1f}%")
                memory = data.get("memory", {})
                console.print(
                    f"[green]RAM:[/green] {memory.get('percent', 0):.1f}% ({(memory.get('used', 0)/(1024**3)):.1f}GB / {(memory.get('total', 0)/(1024**3)):.1f}GB)"
                )

                # Disque
                disk = data.get("disk", {})
                console.print(
                    f"[yellow]Disque:[/yellow] {disk.get('percent', 0):.1f}% ({(disk.get('used', 0)/(1024**3)):.1f}GB / {(disk.get('total', 0)/(1024**3)):.1f}GB)"
                )

                # Réseau - Affichage détaillé
                console.print(f"\n[magenta]📡 Informations Réseau:[/magenta]")
                network = data.get("network", {})
                console.print(
                    f"  [magenta]Débit ↓:[/magenta] {(network.get('bytes_recv_per_sec', 0)/1024):.1f} KB/s"
                )
                console.print(
                    f"  [magenta]Débit ↑:[/magenta] {(network.get('bytes_sent_per_sec', 0)/1024):.1f} KB/s"
                )
                console.print(
                    f"  [magenta]Connexions actives:[/magenta] {network.get('active_connections', 0)}"
                )
                console.print(
                    f"  [magenta]Total ↓:[/magenta] {(network.get('bytes_recv', 0)/(1024**3)):.1f} GB"
                )
                console.print(
                    f"  [magenta]Total ↑:[/magenta] {(network.get('bytes_sent', 0)/(1024**3)):.1f} GB"
                )

                # Interfaces réseau
                if data.get("interfaces"):
                    console.print(f"\n[blue]🌐 Interfaces Réseau:[/blue]")
                    for iface_name, iface_data in data["interfaces"].items():
                        console.print(f"  {iface_name}: ", end="")
                        if iface_data.get("addresses"):
                            ips = [
                                addr.get("address") for addr in iface_data["addresses"]
                            ]
                            console.print(", ".join(ips))
                        else:
                            console.print("Pas d'IP")

                # Protocoles
                if data.get("protocols"):
                    console.print(f"\n[blue]🔌 Protocoles:[/blue]")
                    protocols = data["protocols"]
                    console.print(f"  Total connexions: {protocols.get('total', 0)}")
                    if protocols.get("tcp"):
                        console.print(
                            f"  TCP établies: {protocols['tcp'].get('established', 0)}"
                        )
                        console.print(
                            f"  TCP en écoute: {protocols['tcp'].get('listen', 0)}"
                        )
                    if protocols.get("udp"):
                        console.print(
                            f"  UDP total: {protocols['udp'].get('total', 0)}"
                        )

                # Processus
                processes = data.get("processes", [])
                console.print(f"\n[blue]⚙️ Top 10 Processus:[/blue]")
                proc_table = Table(show_header=True)
                proc_table.add_column("Processus", style="cyan")
                proc_table.add_column("CPU %", style="red")
                proc_table.add_column("RAM %", style="green")
                proc_table.add_column("RAM (MB)", style="yellow")
                proc_table.add_column("IO Lus (MB)", style="blue")
                proc_table.add_column("IO Écrits (MB)", style="magenta")

                for proc in processes[:10]:
                    proc_table.add_row(
                        proc.get("name", "N/A")[:30],
                        f"{proc.get('cpu_percent', 0):.1f}%",
                        f"{proc.get('memory_percent', 0):.1f}%",
                        f"{(proc.get('memory_rss', 0)/(1024**2)):.1f}",
                        f"{(proc.get('io_read_bytes', 0)/(1024**2)):.1f}",
                        f"{(proc.get('io_write_bytes', 0)/(1024**2)):.1f}",
                    )
                console.print(proc_table)

                console.print()
                console.input("[dim]Appuyez sur Entrée pour continuer...[/dim]")
            else:
                console.print("[red]Choix invalide.[/red]")
        except ValueError:
            console.print("[red]Entrée invalide.[/red]")

    def show_general_stats():
        console.clear()
        console.print("[bold blue]📊 Statistiques générales[/bold blue]")
        console.print("=" * 30)

        total = len(computers_data)
        total_cpu = sum(data.get("cpu_percent", 0) for data in computers_data.values())
        total_ram = sum(
            data.get("memory", {}).get("percent", 0) for data in computers_data.values()
        )

        console.print(f"Ordinateurs connectés: {total}")
        if total > 0:
            console.print(f"CPU moyen: {total_cpu/total:.1f}%")
            console.print(f"RAM moyenne: {total_ram/total:.1f}%")

        console.print()
        console.input("[dim]Appuyez sur Entrée pour continuer...[/dim]")

    # Boucle principale du menu
    while True:
        show_main_menu()
        try:
            choice = console.input("[yellow]Votre choix: [/yellow]").strip()

            if choice == "1":
                show_all_computers()
            elif choice == "2":
                show_computer_details()
            elif choice == "3":
                show_general_stats()
            elif choice == "4":
                break
            else:
                console.print("[red]Choix invalide. Appuyez sur Entrée...[/red]")
                console.input()
        except KeyboardInterrupt:
            break

    console.print("\n🛑 Arrêt du dashboard terminal...")
