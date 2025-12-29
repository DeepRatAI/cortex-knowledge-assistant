#!/usr/bin/env python3
"""
Cortex Knowledge Assistant - Launcher Interactivo

Este es el punto de entrada principal para ejecutar Cortex KA.
Proporciona un menú interactivo para:
  - Iniciar/detener servicios
  - Verificar estado del sistema
  - Configuración inicial
  - Administración básica

Uso:
    python cortex_launcher.py          # Menú interactivo
    python cortex_launcher.py start    # Arranque directo
    python cortex_launcher.py stop     # Detención directa
    python cortex_launcher.py status   # Ver estado

Requisitos:
    - Python 3.10+
    - Docker y docker compose
    - Node.js 18+ (para UI)

Autor: Cortex Engineering Team
Fecha: 2025-12-02
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from typing import Optional
import json


# Colores ANSI
class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    MAGENTA = "\033[0;35m"
    BOLD = "\033[1m"
    NC = "\033[0m"  # No color


def clear_screen():
    os.system("clear" if os.name != "nt" else "cls")


def print_banner():
    print(f"""
{Colors.CYAN}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   {Colors.BOLD}CORTEX KNOWLEDGE ASSISTANT{Colors.NC}{Colors.CYAN}                               ║
║   ─────────────────────────────────────                      ║
║   Sistema de Asistencia Inteligente                          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{Colors.NC}
""")


def print_status_line(service: str, status: bool, url: Optional[str] = None):
    """Imprime una línea de estado de servicio."""
    icon = f"{Colors.GREEN}●{Colors.NC}" if status else f"{Colors.RED}○{Colors.NC}"
    status_text = (
        f"{Colors.GREEN}ACTIVO{Colors.NC}"
        if status
        else f"{Colors.RED}INACTIVO{Colors.NC}"
    )
    url_text = f" → {Colors.BLUE}{url}{Colors.NC}" if url and status else ""
    print(f"  {icon} {service:<20} [{status_text}]{url_text}")


def check_port(port: int) -> bool:
    """Verifica si un puerto está escuchando (IPv4 o IPv6)."""
    import socket

    # Intentar IPv4 primero
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        if s.connect_ex(("127.0.0.1", port)) == 0:
            return True
    # Intentar IPv6
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            if s.connect_ex(("::1", port)) == 0:
                return True
    except Exception:
        pass
    return False


def check_docker_container(name: str) -> bool:
    """Verifica si un contenedor Docker está corriendo."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() == "true"
    except Exception:
        return False


def get_system_status() -> dict:
    """Obtiene el estado completo del sistema."""
    return {
        "api": check_port(8088),
        "ui": check_port(3000),
        "qdrant": check_port(6333),
        "redis": check_port(6379),
        "ollama": check_port(11434),
        "docker_qdrant": check_docker_container("cortex_qdrant"),
        "docker_redis": check_docker_container("cortex_redis"),
        "docker_ollama": check_docker_container("cortex_ollama"),
    }


def print_system_status():
    """Muestra el estado actual del sistema."""
    print(f"\n{Colors.BOLD}Estado del Sistema:{Colors.NC}\n")

    status = get_system_status()

    print(f"  {Colors.CYAN}Servicios Principales:{Colors.NC}")
    print_status_line("API (FastAPI)", status["api"], "http://localhost:8088")
    print_status_line("UI (React/Vite)", status["ui"], "http://localhost:3000")

    print(f"\n  {Colors.CYAN}Infraestructura Docker:{Colors.NC}")
    print_status_line("Qdrant (vectores)", status["qdrant"], "http://localhost:6333")
    print_status_line("Redis (cache)", status["redis"], "localhost:6379")
    print_status_line("Ollama (LLM local)", status["ollama"], "http://localhost:11434")

    # Estado general
    all_core = status["api"] and status["ui"] and status["qdrant"]
    if all_core:
        print(f"\n  {Colors.GREEN}✓ Sistema operativo{Colors.NC}")
    elif status["api"] or status["ui"]:
        print(f"\n  {Colors.YELLOW}⚠ Sistema parcialmente operativo{Colors.NC}")
    else:
        print(f"\n  {Colors.RED}✗ Sistema detenido{Colors.NC}")

    return status


def run_script(script_name: str, args: list = None) -> int:
    """Ejecuta un script bash del directorio scripts/."""
    root = Path(__file__).parent
    script_path = root / "scripts" / script_name

    if not script_path.exists():
        print(f"{Colors.RED}Error: Script {script_name} no encontrado{Colors.NC}")
        return 1

    cmd = ["bash", str(script_path)]
    if args:
        cmd.extend(args)

    return subprocess.call(cmd)


def start_services():
    """Inicia todos los servicios."""
    print(f"\n{Colors.BOLD}Iniciando Cortex...{Colors.NC}\n")
    return run_script("start_cortex_full.sh")


def stop_services(stop_docker: bool = False):
    """Detiene los servicios."""
    print(f"\n{Colors.BOLD}Deteniendo Cortex...{Colors.NC}\n")
    args = ["--all"] if stop_docker else []
    return run_script("stop_cortex.sh", args)


def check_health_api():
    """Verifica la salud de la API con detalle."""
    import urllib.request
    import urllib.error

    print(f"\n{Colors.BOLD}Diagnóstico de API:{Colors.NC}\n")

    endpoints = [
        ("Health básico", "http://localhost:8088/health"),
        ("Estado del sistema", "http://localhost:8088/api/system/status"),
    ]

    for name, url in endpoints:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                print(f"  {Colors.GREEN}✓{Colors.NC} {name}")
                if isinstance(data, dict):
                    for key, value in data.items():
                        if isinstance(value, dict):
                            print(f"      {key}:")
                            for k, v in value.items():
                                print(f"        {k}: {v}")
                        else:
                            print(f"      {key}: {value}")
        except urllib.error.URLError as e:
            print(f"  {Colors.RED}✗{Colors.NC} {name}: {e.reason}")
        except Exception as e:
            print(f"  {Colors.RED}✗{Colors.NC} {name}: {e}")

    print()


def show_logs(service: str):
    """Muestra los últimos logs de un servicio."""
    root = Path(__file__).parent
    log_file = root / "logs" / f"{service}.log"

    if not log_file.exists():
        print(f"{Colors.YELLOW}No hay logs para {service}{Colors.NC}")
        return

    print(f"\n{Colors.BOLD}Últimos logs de {service}:{Colors.NC}\n")
    subprocess.call(["tail", "-30", str(log_file)])
    print()


def show_credentials():
    """Muestra las credenciales de acceso."""
    print(f"""
{Colors.BOLD}Credenciales de Acceso:{Colors.NC}

  {Colors.CYAN}Administrador:{Colors.NC}
    Usuario:  gguerra.admin
    Password: Admin@123

  {Colors.CYAN}Usuario de Soporte:{Colors.NC}
    Usuario:  llucci.support
    Password: (contactar admin)

  {Colors.CYAN}Cliente Demo:{Colors.NC}
    Usuario:  cliente_cli-81093
    Password: Demo!CLI-81093

  {Colors.YELLOW}Nota: Cambie las contraseñas después del primer acceso.{Colors.NC}
""")


def show_urls():
    """Muestra las URLs de acceso."""
    print(f"""
{Colors.BOLD}URLs de Acceso:{Colors.NC}

  {Colors.CYAN}Aplicación Principal:{Colors.NC}
    UI Web:       http://localhost:3000
    API REST:     http://localhost:8088
    API Docs:     http://localhost:8088/docs

  {Colors.CYAN}Infraestructura:{Colors.NC}
    Qdrant:       http://localhost:6333/dashboard
    Ollama:       http://localhost:11434

  {Colors.CYAN}Endpoints Útiles:{Colors.NC}
    Health:       http://localhost:8088/health
    Status:       http://localhost:8088/api/system/status
""")


def interactive_menu():
    """Menú interactivo principal."""
    while True:
        clear_screen()
        print_banner()
        print_system_status()

        print(f"""
{Colors.BOLD}Opciones:{Colors.NC}

  {Colors.CYAN}Servicios:{Colors.NC}
    1) Iniciar Cortex completo
    2) Detener Cortex (mantener Docker)
    3) Detener todo (incluyendo Docker)
    4) Reiniciar servicios

  {Colors.CYAN}Diagnóstico:{Colors.NC}
    5) Ver estado detallado
    6) Ver logs de API
    7) Ver logs de UI
    8) Diagnóstico de API

  {Colors.CYAN}Información:{Colors.NC}
    9) Ver credenciales
    0) Ver URLs de acceso

  {Colors.CYAN}Salir:{Colors.NC}
    q) Salir del launcher
""")

        choice = (
            input(f"{Colors.BOLD}Seleccione una opción: {Colors.NC}").strip().lower()
        )

        if choice == "1":
            start_services()
            input("\nPresione Enter para continuar...")
        elif choice == "2":
            stop_services(stop_docker=False)
            input("\nPresione Enter para continuar...")
        elif choice == "3":
            stop_services(stop_docker=True)
            input("\nPresione Enter para continuar...")
        elif choice == "4":
            stop_services(stop_docker=False)
            time.sleep(2)
            start_services()
            input("\nPresione Enter para continuar...")
        elif choice == "5":
            clear_screen()
            print_banner()
            print_system_status()
            input("\nPresione Enter para continuar...")
        elif choice == "6":
            clear_screen()
            show_logs("api")
            input("\nPresione Enter para continuar...")
        elif choice == "7":
            clear_screen()
            show_logs("ui")
            input("\nPresione Enter para continuar...")
        elif choice == "8":
            clear_screen()
            check_health_api()
            input("\nPresione Enter para continuar...")
        elif choice == "9":
            clear_screen()
            show_credentials()
            input("\nPresione Enter para continuar...")
        elif choice == "0":
            clear_screen()
            show_urls()
            input("\nPresione Enter para continuar...")
        elif choice in ("q", "exit", "quit"):
            print(f"\n{Colors.GREEN}¡Hasta luego!{Colors.NC}\n")
            break
        else:
            print(f"{Colors.YELLOW}Opción no válida{Colors.NC}")
            time.sleep(1)


def main():
    """Punto de entrada principal."""
    # Asegurarse de estar en el directorio correcto
    os.chdir(Path(__file__).parent)

    # Procesar argumentos de línea de comandos
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "start":
            start_services()
        elif command == "stop":
            stop_all = "--all" in sys.argv
            stop_services(stop_docker=stop_all)
        elif command == "restart":
            stop_services(stop_docker=False)
            time.sleep(2)
            start_services()
        elif command == "status":
            print_banner()
            print_system_status()
        elif command == "health":
            check_health_api()
        elif command == "logs":
            service = sys.argv[2] if len(sys.argv) > 2 else "api"
            show_logs(service)
        elif command in ("help", "-h", "--help"):
            print(__doc__)
        else:
            print(f"Comando desconocido: {command}")
            print("Use 'python cortex_launcher.py help' para ver opciones.")
            sys.exit(1)
    else:
        # Modo interactivo
        try:
            interactive_menu()
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Interrumpido por el usuario{Colors.NC}\n")
            sys.exit(0)


if __name__ == "__main__":
    main()
