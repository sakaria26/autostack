#!/usr/bin/env python3
import os
import sys
import platform
import subprocess
import time
import shutil

# --- Colors and Constants ---
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
NC = "\033[0m"

APP_NAME = "AUTOSTACK"
VERSION = "1.1.0"

# --- ASCII Art ---
ASCII_ART = f"""
{BLUE}
   _         _         ____  _             _    
  / \\  _   _| |_ ___  / ___|| |_ __ _  ___| | __
 / _ \\| | | | __/ _ \\ \\___ \\| __/ _` |/ __| |/ /
/ ___ \\ |_| | || (_) | ___) | || (_| | (__|   < 
/_/   \\_\\__,_|\\__\\___/ |____/ \\__\\__,_|\\___|_|\\_\\
{NC}
{YELLOW}   [ Smart Engineering Interface v{VERSION} ]{NC}
"""

def clear_screen():
    os.system('cls' if platform.system() == 'Windows' else 'clear')

def get_status_label(status):
    if status == "OK" or status == "Installed" or status == "Running":
        return f"{GREEN}{status}{NC}"
    if status == "Missing" or status == "Not Running":
        return f"{RED}{status}{NC}"
    return f"{YELLOW}{status}{NC}"

def check_docker():
    try:
        subprocess.check_output(["docker", "info"], stderr=subprocess.STDOUT)
        return True
    except:
        return False

def check_env():
    env_path = os.path.join("autostack-engine", ".env")
    if not os.path.exists(env_path):
        return False, "Missing"
    
    with open(env_path, "r") as f:
        content = f.read()
        if "GEMINI_API_KEY=$" in content or "GEMINI_API_KEY=\n" in content or "GEMINI_API_KEY= " in content:
            return True, "API Key Missing"
    return True, "OK"

def get_env_vars():
    env_vars = {}
    env_path = os.path.join("autostack-engine", ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    env_vars[key] = value
    return env_vars

def check_backend():
    # Check for poetry lock and .venv
    engine_dir = "autostack-engine"
    lock_exists = os.path.exists(os.path.join(engine_dir, "poetry.lock"))
    # Check if a venv exists (common locations)
    venv_exists = os.path.exists(os.path.join(engine_dir, ".venv")) or \
                  subprocess.run(["python3", "-m", "poetry", "env", "info", "--path"], cwd=engine_dir, capture_output=True).returncode == 0
    
    if venv_exists and lock_exists:
        return "Installed"
    if lock_exists:
        return "Not Installed (Venv Missing)"
    return "Not Installed"

def check_frontend():
    frontend_dir = "autostack"
    node_modules = os.path.exists(os.path.join(frontend_dir, "node_modules"))
    lock_exists = os.path.exists(os.path.join(frontend_dir, "package-lock.json"))
    
    if node_modules and lock_exists:
        return "Installed"
    if lock_exists:
        return "Not Installed (Modules Missing)"
    return "Not Installed"

def print_dashboard():
    print(f"{CYAN}┌──────────────────────────────────────────────────────────┐{NC}")
    print(f"{CYAN}│{NC}  {BLUE}SYSTEM DASHBOARD{NC}                                       {CYAN}│{NC}")
    print(f"{CYAN}├──────────────────────────────────────────────────────────┤{NC}")
    
    docker_status = "Running" if check_docker() else "Not Running"
    env_exists, env_msg = check_env()
    backend_status = check_backend()
    frontend_status = check_frontend()
    
    print(f"{CYAN}│{NC}  Docker:          {get_status_label(docker_status):<40} {CYAN}│{NC}")
    print(f"{CYAN}│{NC}  Environment:     {get_status_label(env_msg):<40} {CYAN}│{NC}")
    print(f"{CYAN}│{NC}  Backend:         {get_status_label(backend_status):<40} {CYAN}│{NC}")
    print(f"{CYAN}│{NC}  Frontend:        {get_status_label(frontend_status):<40} {CYAN}│{NC}")
    print(f"{CYAN}└──────────────────────────────────────────────────────────┘{NC}")

def run_script(script_name):
    script_path = os.path.join("scripts", script_name)
    if platform.system() == "Windows":
        if script_name.endswith(".ps1"):
            subprocess.run(["powershell.exe", "-File", script_path])
        else:
            print(f"{RED}Error: Cannot run .sh script directly on Windows shell.{NC}")
    else:
        subprocess.run(["bash", script_path])

def run_setup():
    backend = check_backend()
    frontend = check_frontend()
    
    if backend == "Installed" and frontend == "Installed":
        print(f"\n{YELLOW}Project is already installed.{NC}")
        choice = input(f"Do you want to (U)pdate dependencies or (R)e-install completely? (u/r/cancel): ").lower()
        if choice == 'u':
            print(f"\n{GREEN}>>> Updating dependencies...{NC}")
            # Quick update logic
            subprocess.run(["python3", "-m", "poetry", "install"], cwd="autostack-engine")
            subprocess.run(["npm", "install"], cwd="autostack")
            print(f"{GREEN}Update complete.{NC}")
            return
        elif choice == 'cancel':
            return
    
    print(f"\n{GREEN}>>> Starting Full Setup...{NC}")
    run_script("setup_autostack.sh")

import socket
import subprocess

# --- Self-Healing Utilities ---

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def kill_process_on_port(port):
    try:
        # Use lsof to find the PID
        output = subprocess.check_output(["lsof", "-t", f"-i:{port}"], stderr=subprocess.STDOUT)
        pids = output.decode().strip().split('\n')
        for pid in pids:
            if pid:
                print(f"{YELLOW}Found process with PID {pid} on port {port}. Killing...{NC}")
                subprocess.run(["kill", "-9", pid])
        return True
    except subprocess.CalledProcessError:
        return False
    except Exception as e:
        print(f"{RED}Error killing process: {e}{NC}")
        return False

def diagnostic_check():
    clear_screen()
    print(f"{CYAN}--- Auto-Stack Self-Healing Diagnostic ---{NC}\n")
    
    # 1. Port Checks
    for port, name in [(8020, "API Gateway"), (4200, "Frontend")]:
        if is_port_in_use(port):
            print(f"{RED}[Conflict]{NC} Port {port} ({name}) is in use.")
            if input(f"   Would you like to kill the process on port {port}? (y/n): ").lower() == 'y':
                kill_process_on_port(port)
        else:
            print(f"{GREEN}[Clean]{NC} Port {port} ({name}) is available.")

    # 2. Docker Space Check
    try:
        docker_stats = subprocess.check_output(["docker", "info", "--format", "{{.MemTotal}}"], stderr=subprocess.STDOUT)
        print(f"{GREEN}[Active]{NC} Docker is responsive.")
    except:
        print(f"{RED}[Error]{NC} Docker is not responsive or not installed.")

    # 3. Database Connectivity (Dependency-free check)
    print(f"\n{CYAN}Testing Database Connectivity...{NC}")
    
    # Check port first
    if is_port_in_use(27017):
        print(f"{GREEN}[Success]{NC} MongoDB port (27017) is open.")
        
        # Try ping via docker exec
        try:
            print(f"   Verifying authentication via Docker...")
            subprocess.check_output(["docker", "exec", "mongo", "mongosh", "--eval", "db.adminCommand('ping')"], stderr=subprocess.STDOUT)
            print(f"{GREEN}[Success]{NC} MongoDB authentication verified.")
        except Exception as e:
            print(f"{RED}[Failure]{NC} MongoDB auth failed or mongosh missing: {e}")
            print(f"   Tip: This might be normal if the container is still starting up or using an older mongo version.")
    else:
        print(f"{RED}[Failure]{NC} MongoDB port (27017) is NOT responsive.")
        print(f"   Tip: Run Option (1) to ensure Docker services are up.")

    input("\nDiagnostic complete. Press Enter to return to menu...")

def main_menu():
    while True:
        clear_screen()
        print(ASCII_ART)
        print_dashboard()
        
        backend = check_backend()
        frontend = check_frontend()
        needs_setup = backend != "Installed" or frontend != "Installed"
        
        print(f"\n{BLUE}Available Actions:{NC}")
        setup_label = "Update/Reinstall Dependencies" if not needs_setup else "Full Project Setup"
        print(f"  {YELLOW}1.{NC} {setup_label}")
        print(f"  {YELLOW}2.{NC} Run Application (Launch Backend + Frontend)")
        print(f"  {YELLOW}3.{NC} {CYAN}Self-Heal / Diagnostics (Process Killing, DB Test){NC}")
        print(f"  {YELLOW}4.{NC} System Maintenance (Prune Docker)")
        print(f"  {YELLOW}5.{NC} {GREEN}Export Project Data (For Research Submit){NC}")
        print(f"  {YELLOW}0.{NC} Exit")
        
        choice = input(f"\n{BLUE}Select an option (0-5): {NC}")
        
        if choice == '1':
            run_setup()
            input("\nPress Enter to return to menu...")
        elif choice == '2':
            if needs_setup:
                print(f"\n{RED}Warning: Project is not fully installed! Running setup first...{NC}")
                run_setup()
            # Before running, check for port conflicts
            conflict = False
            for port in [8020, 4200]:
                if is_port_in_use(port):
                    print(f"{RED}Error: Port {port} is already in use.{NC}")
                    conflict = True
            if conflict:
                if input("Try to auto-fix conflicts? (y/n): ").lower() == 'y':
                    diagnostic_check()
                else:
                    print(f"{YELLOW}Please close the processes manually and try again.{NC}")
                    time.sleep(2)
                    continue
            run_script("run.sh" if platform.system() != "Windows" else "run.ps1")
        elif choice == '3':
            diagnostic_check()
        elif choice == '4':
            confirm = input(f"{RED}This will delete ALL unused Docker data. Continue? (y/n): {NC}")
            if confirm.lower() == 'y':
                print(f"\n{RED}>>> Cleaning up...{NC}")
                subprocess.run(["docker", "system", "prune", "-af", "--volumes"])
                input("\nCleanup finished. Press Enter to return...")
        elif choice == '5':
            export_dir = "exports"
            os.makedirs(export_dir, exist_ok=True)
            timestamp = int(time.time())
            zip_name = f"autostack_export_{timestamp}.zip"
            
            print(f"\n{GREEN}>>> Exporting collections from MongoDB...{NC}")
            collections = [
                "project_chat", "schema_rating", "service_logs", 
                "activity_logs", "projects", "components", 
                "environments", "connections", "technology_configs",
                "project_configs"
            ]
            
            env_vars = get_env_vars()
            mongo_user = env_vars.get("MONGO_USER", "root")
            mongo_pass = env_vars.get("MONGO_PASSWORD", "")
            
            for coll in collections:
                print(f"    Exporting {coll}...")
                try:
                    cmd = [
                        "docker", "exec", "mongo", "mongoexport", 
                        "--db", "autostack", 
                        "--collection", coll, 
                        "--out", f"/tmp/{coll}.json",
                        "--jsonArray"
                    ]
                    
                    if mongo_user and mongo_pass:
                        cmd.extend(["--username", mongo_user, "--password", mongo_pass, "--authenticationDatabase", "admin"])
                    
                    subprocess.run(cmd, check=True, capture_output=True)
                    subprocess.run([
                        "docker", "cp", f"mongo:/tmp/{coll}.json", os.path.join(export_dir, f"{coll}.json")
                    ], check=True)
                except Exception as e:
                    print(f"{RED}    Failed to export {coll}: {e}")
            
            print(f"\n{GREEN}>>> Creating zip archive...{NC}")
            shutil.make_archive(zip_name.replace(".zip", ""), 'zip', export_dir)
            
            print(f"\n{GREEN}Success! Data exported to: {NC}{zip_name}")
            print(f"{YELLOW}Please upload this file to: https://forms.gle/1vYwG1y1dyhiKy2Y9{NC}")
            input("\nPress Enter to return...")
        elif choice == '0':
            print(f"\n{GREEN}Goodbye!{NC}")
            break
        else:
            print(f"{RED}Invalid choice.{NC}")
            time.sleep(1)

if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        print(f"\n{GREEN}Exit signaled. Goodbye!{NC}")
        sys.exit(0)
