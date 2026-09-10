#!/usr/bin/env python3
"""Controlador Python do simulador Husky + ISOBUS + PX4."""

from __future__ import annotations

import argparse
import atexit
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
RUNTIME = ROOT / ".runtime"
WS = ROOT / "ros2_ws"
ROS_SETUP = Path("/opt/ros/jazzy/setup.bash")
PX4_REF = "v1.17.0"


class AppError(RuntimeError):
    pass


def say(message: str = "", *, error: bool = False) -> None:
    print(message, file=sys.stderr if error else sys.stdout, flush=True)


def die(message: str) -> None:
    raise AppError(message)


def run(args, *, env=None, cwd=None, check=True, capture=False, timeout=None):
    return subprocess.run(
        [str(x) for x in args], env=env, cwd=cwd, check=check,
        text=True, capture_output=capture, timeout=timeout,
    )


def output(args, *, env=None, cwd=None, timeout=None) -> str:
    result = run(args, env=env, cwd=cwd, check=False, capture=True, timeout=timeout)
    return result.stdout


def command_exists(name: str, env=None) -> bool:
    return shutil.which(name, path=(env or os.environ).get("PATH")) is not None


def sourced_environment(files: list[Path]) -> dict[str, str]:
    env = os.environ.copy()
    existing = [p for p in files if p.is_file()]
    if not existing:
        return env
    command = "set +u; " + "; ".join(f"source {shlex_quote(str(p))}" for p in existing) + "; env -0"
    result = subprocess.run(
        ["bash", "-c", command], check=True, capture_output=True, env=env,
    )
    for entry in result.stdout.split(b"\0"):
        if b"=" in entry:
            key, value = entry.split(b"=", 1)
            env[key.decode(errors="surrogateescape")] = value.decode(errors="surrogateescape")
    return env


def shlex_quote(value: str) -> str:
    import shlex
    return shlex.quote(value)


def project_env(require_ros: bool = True) -> dict[str, str]:
    if require_ros and not ROS_SETUP.is_file():
        die("[ERRO] ROS 2 Jazzy não encontrado em /opt/ros/jazzy.")
    env = sourced_environment([ROS_SETUP, WS / "install/setup.bash"])
    env["HUSKY_ISOBUS_SIM_ROOT"] = str(ROOT)
    env["AGROBOT_SIM_DIR"] = env.get(
        "AGROBOT_SIM_DIR", str(Path.home() / "AgroDT/Isobus/agrobot-simulation")
    )
    env["PX4_DIR"] = str(ROOT / "third_party/PX4-Autopilot")
    env["MICRO_XRCE_DDS_AGENT_DIR"] = str(ROOT / "third_party/Micro-XRCE-DDS-Agent")
    return env


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def process_alive(process: subprocess.Popen | None) -> bool:
    return process is not None and process.poll() is None


def terminate(process: subprocess.Popen | None) -> None:
    if process_alive(process):
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def write_pid(name: str, process: subprocess.Popen) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    (RUNTIME / name).write_text(str(process.pid), encoding="utf-8")


def tail(path: Path, count: int = 80) -> str:
    if not path.is_file():
        return f"[log ausente: {path}]"
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-count:])


def world_running(world: str, env: dict[str, str]) -> bool:
    return f"/world/{world}/" in output(["gz", "service", "-l"], env=env)


def ros_topic_list(env: dict[str, str]) -> list[str]:
    # Evita o grafo em cache do daemon, que frequentemente fica desatualizado
    # depois de encerrar e reiniciar Gazebo / PX4 no mesmo terminal.
    try:
        direct = run(
            ["ros2", "topic", "list", "--no-daemon", "--spin-time", "1"],
            env=env,
            check=False,
            capture=True,
            timeout=8,
        )
        if direct.returncode == 0:
            return direct.stdout.splitlines()
    except subprocess.TimeoutExpired:
        pass
    return output(["ros2", "topic", "list"], env=env).splitlines()


def find_status_topic(env: dict[str, str]) -> str | None:
    pattern = re.compile(r"^/fmu/out/vehicle_status(?:_v\d+)?$")
    return next((topic for topic in ros_topic_list(env) if pattern.match(topic)), None)


def topic_has_publisher(topic: str, env: dict[str, str]) -> bool:
    info = output(["ros2", "topic", "info", topic], env=env)
    match = re.search(r"Publisher count:\s*(\d+)", info)
    return bool(match and int(match.group(1)) > 0)


def topic_once(topic: str, env: dict[str, str], timeout_s: float = 3) -> bool:
    # Tenta o QoS padrão e também Best Effort. /clock e tópicos PX4 podem
    # anunciar QoS diferente conforme a versão dos pacotes instalados.
    commands = (
        ["ros2", "topic", "echo", topic, "--once"],
        ["ros2", "topic", "echo", topic, "--once", "--qos-reliability", "best_effort"],
    )
    for command in commands:
        try:
            result = run(
                command, env=env, check=False, capture=True, timeout=timeout_s,
            )
            if result.returncode == 0:
                return True
        except subprocess.TimeoutExpired:
            pass
    return False


def cmd_env(_args) -> int:
    env = project_env()
    for key in ("HUSKY_ISOBUS_SIM_ROOT", "AGROBOT_SIM_DIR", "PX4_DIR", "MICRO_XRCE_DDS_AGENT_DIR"):
        say(f"{key}={env[key]}")
    return 0


def cmd_preflight(_args) -> int:
    errors = 0
    say("== Verificação estática do simulador ==")
    if ROS_SETUP.is_file():
        env = project_env()
        say("[OK] ROS 2 Jazzy encontrado e ambiente carregado")
    else:
        env = os.environ.copy(); errors += 1
        say("[ERRO] ROS 2 Jazzy não encontrado", error=True)
    for command in ("python3", "ros2", "colcon", "gz"):
        if command_exists(command, env): say(f"[OK] comando {command}")
        else: errors += 1; say(f"[ERRO] comando ausente: {command}", error=True)
    if command_exists("ros2", env):
        for package in ("ros_gz_sim", "ros_gz_bridge", "clearpath_gz", "gz_ros2_control"):
            result = run(["ros2", "pkg", "prefix", package], env=env, check=False, capture=True)
            if result.returncode == 0: say(f"[OK] pacote ROS: {package}")
            else: errors += 1; say(f"[ERRO] pacote ROS ausente: {package}", error=True)
    try:
        for path in sorted((ROOT / "config").rglob("*.yaml")):
            load_yaml(path); say(f"[OK] YAML: {path.relative_to(ROOT)}")
        for path in sorted((WS / "src").glob("*/package.xml")):
            ET.parse(path); say(f"[OK] XML: {path.relative_to(ROOT)}")
    except Exception as exc:
        errors += 1; say(f"[ERRO] configuração inválida: {exc}", error=True)
    world = Path(env.get("AGROBOT_SIM_DIR", "")) / "AgrobotScene/AgrobotScene.sdf"
    say(f"[OK] mundo externo: {world}" if world.is_file() else f"[AVISO] mundo ausente: {world}")
    if errors:
        say(f"Falha: {errors} requisito(s) obrigatório(s) ausente(s).", error=True)
        return 1
    say("Verificação concluída sem erros obrigatórios.")
    return 0


def cmd_build(_args) -> int:
    env = project_env()
    if not (WS / "src/px4_msgs").is_dir():
        say("[AVISO] px4_msgs ausente; para usar o drone rode setup_all.py.")
    for name in ("build", "install", "log"):
        path = WS / name
        if path.exists(): shutil.rmtree(path)
    if command_exists("rosdep", env):
        run(["rosdep", "install", "--from-paths", "src", "--ignore-src", "-r", "-y"], env=env, cwd=WS, check=False)
    run(["colcon", "build", "--symlink-install"], env=env, cwd=WS)
    say("\n[OK] workspace compilado.")
    return 0


def fresh_px4_clone(px4: Path) -> None:
    if px4.exists(): shutil.rmtree(px4)
    say(f"[PX4] Fazendo instalação limpa de {PX4_REF}...")
    run(["git", "clone", "--branch", PX4_REF, "--recurse-submodules", "https://github.com/PX4/PX4-Autopilot.git", px4])
    run(["git", "-C", px4, "submodule", "sync", "--recursive"])
    run(["git", "-C", px4, "submodule", "update", "--init", "--recursive", "--force", "--jobs", str(os.cpu_count() or 2)])


def repair_px4(px4: Path) -> None:
    binary = px4 / "build/px4_sitl_default/bin/px4"
    if os.access(binary, os.X_OK):
        say(f"[OK] PX4 SITL já compilado: {binary}"); return
    if not (px4 / ".git").is_dir():
        fresh_px4_clone(px4)
    else:
        say(f"REPARO DO PX4 {PX4_REF}")
        commands = [
            ["git", "-C", px4, "fetch", "--tags", "--force"],
            ["git", "-C", px4, "checkout", "--detach", PX4_REF],
            ["git", "-C", px4, "reset", "--hard", PX4_REF],
            ["git", "-C", px4, "submodule", "sync", "--recursive"],
            ["git", "-C", px4, "submodule", "update", "--init", "--recursive", "--force", "--jobs", str(os.cpu_count() or 2)],
        ]
        try:
            for command in commands: run(command)
        except subprocess.CalledProcessError:
            say("[AVISO] Clone inconsistente; refazendo a dependência.")
            fresh_px4_clone(px4)
    status = output(["git", "-C", px4, "submodule", "status", "--recursive"])
    bad = [line for line in status.splitlines() if line.startswith(("-", "+", "U"))]
    if bad: die("[ERRO] Submódulos não sincronizados:\n" + "\n".join(bad))
    for relative in ("src/lib/heatshrink/heatshrink", "src/drivers/gps/devices", "Tools/simulation/gz"):
        if not (px4 / relative / ".git").exists(): die(f"[ERRO] Submódulo ausente: {relative}")
    say("[OK] Submódulos PX4 sincronizados.")


def cmd_repair_px4(_args) -> int:
    repair_px4(ROOT / "third_party/PX4-Autopilot"); return 0


def cmd_setup_all(_args) -> int:
    env = project_env()
    if output(["lsb_release", "-rs"]).strip() != "24.04":
        say("[AVISO] Projeto preparado para Ubuntu 24.04 + ROS 2 Jazzy.")
    tp = ROOT / "third_party"; tp.mkdir(parents=True, exist_ok=True)
    px4 = tp / "PX4-Autopilot"; px4_bin = px4 / "build/px4_sitl_default/bin/px4"
    agent = tp / "Micro-XRCE-DDS-Agent"; px4_msgs = WS / "src/px4_msgs"
    say("SETUP COMPLETO - HUSKY + PX4 X500")
    packages = "git cmake build-essential ninja-build ccache python3-pip python3-dev python3-setuptools python3-wheel python3-colcon-common-extensions python3-rosdep python3-yaml python3-can python3-pytest rsync unzip zip bc can-utils libssl-dev libxml2-dev libxml2-utils libunwind-dev cppzmq-dev ros-jazzy-ros-gz ros-jazzy-clearpath-simulator ros-jazzy-gz-ros2-control ros-jazzy-ros2-control ros-jazzy-ros2-controllers".split()
    run(["sudo", "apt", "update"]); run(["sudo", "apt", "install", "-y", *packages])
    run(["sudo", "rosdep", "init"], env=env, check=False); run(["rosdep", "update"], env=env, check=False)
    say("[1/5] Preparando PX4 v1.17.0...")
    if not os.access(px4_bin, os.X_OK):
        repair_px4(px4)
        say("[2/5] Dependências Python do PX4...")
        run([sys.executable, "-m", "pip", "install", "--user", "--break-system-packages", "-r", px4 / "Tools/setup/requirements.txt"])
        say("[3/5] Compilando PX4 SITL..."); run(["make", "-C", px4, "px4_sitl"])
        if not os.access(px4_bin, os.X_OK): die(f"[ERRO] binário não gerado: {px4_bin}")
    else: say("[OK] PX4 SITL já compilado; preservando.")
    if not (agent / ".git").is_dir():
        say("[4/5] Baixando Micro XRCE-DDS Agent v2.4.3...")
        run(["git", "clone", "--branch", "v2.4.3", "--depth", "1", "https://github.com/eProsima/Micro-XRCE-DDS-Agent.git", agent])
    run(["cmake", "-S", agent, "-B", agent / "build"])
    run(["cmake", "--build", agent / "build", f"-j{os.cpu_count() or 2}"])
    run(["sudo", "cmake", "--install", agent / "build"]); run(["sudo", "ldconfig", "/usr/local/lib"], check=False)
    if not (px4_msgs / ".git").is_dir():
        if px4_msgs.exists(): shutil.rmtree(px4_msgs)
        say("[5/5] Baixando px4_msgs release/1.17...")
        run(["git", "clone", "--branch", "release/1.17", "--depth", "1", "https://github.com/PX4/px4_msgs.git", px4_msgs])
    cmd_build(None)
    say("\n[OK] SETUP CONCLUÍDO")
    say("1) python3 scripts/start_simulation.py\n2) python3 scripts/start_drone.py\n3) python3 scripts/check_all.py\n4) python3 scripts/start_drone_mission.py")
    return 0


def cmd_setup_vcan(args) -> int:
    if os.geteuid() != 0: die("[ERRO] execute: sudo python3 scripts/setup_vcan.py")
    iface = args.interface
    run(["modprobe", "vcan"])
    if run(["ip", "link", "show", iface], check=False).returncode != 0:
        run(["ip", "link", "add", "dev", iface, "type", "vcan"])
    run(["ip", "link", "set", "up", iface]); run(["ip", "-brief", "link", "show", iface])
    return 0


def cmd_remove_vcan(args) -> int:
    if os.geteuid() != 0: die("[ERRO] execute: sudo python3 scripts/remove_vcan.py")
    if run(["ip", "link", "show", args.interface], check=False).returncode == 0:
        run(["ip", "link", "set", "down", args.interface], check=False)
        run(["ip", "link", "delete", args.interface, "type", "vcan"])
    return 0


def cmd_start_dds_agent(_args) -> int:
    env = project_env(); cfg = load_yaml(ROOT / "config/drone.yaml"); port = int(cfg.get("dds", {}).get("port", 8888))
    if run(["pgrep", "-af", "MicroXRCEAgent.*udp4"], check=False, capture=True).returncode == 0:
        say("[INFO] MicroXRCEAgent já está rodando."); return 0
    binary = shutil.which("MicroXRCEAgent", path=env.get("PATH")) or str(Path(env["MICRO_XRCE_DDS_AGENT_DIR"]) / "build/MicroXRCEAgent")
    if not os.access(binary, os.X_OK): die("[ERRO] MicroXRCEAgent ausente. Rode setup_all.py")
    os.execvpe(binary, [binary, "udp4", "-p", str(port)], env)
    return 0


def cmd_start_drone(_args) -> int:
    env = project_env(); RUNTIME.mkdir(parents=True, exist_ok=True)
    cfg = load_yaml(ROOT / "config/drone.yaml"); p = cfg.get("px4", {}); spawn = cfg.get("spawn", {}); dds = cfg.get("dds", {})
    model = str(p.get("model", "gz_x500")); autostart = int(p.get("autostart", 4001)); world = str(p.get("world", "AgrobotScene"))
    pose = [float(spawn.get(k, default)) for k, default in (("x",0),("y",0),("z",1.5),("roll",0),("pitch",0),("yaw",0))]
    port = int(dds.get("port", 8888)); px4 = Path(env["PX4_DIR"]); px4_bin = px4 / "build/px4_sitl_default/bin/px4"
    rootfs = px4 / "build/px4_sitl_default/rootfs"
    if not os.access(px4_bin, os.X_OK): die("[ERRO] PX4 não compilado. Rode setup_all.py")
    if not world_running(world, env): die(f"[ERRO] mundo '{world}' não está rodando.")
    dds_process = None; px4_process = None
    def cleanup():
        terminate(px4_process); terminate(dds_process)
        for name in ("px4.pid", "dds_agent.pid"):
            (RUNTIME / name).unlink(missing_ok=True)
    atexit.register(cleanup)
    if run(["pgrep", "-af", "MicroXRCEAgent.*udp4"], check=False, capture=True).returncode != 0:
        say(f"[1/3] Iniciando Micro XRCE-DDS Agent UDP {port}...")
        agent = shutil.which("MicroXRCEAgent", path=env.get("PATH")) or str(Path(env["MICRO_XRCE_DDS_AGENT_DIR"]) / "build/MicroXRCEAgent")
        if not os.access(agent, os.X_OK): die("[ERRO] MicroXRCEAgent ausente. Rode setup_all.py")
        log = (RUNTIME / "dds_agent.log").open("w", encoding="utf-8")
        dds_process = subprocess.Popen([agent, "udp4", "-p", str(port)], env=env, stdout=log, stderr=subprocess.STDOUT)
        write_pid("dds_agent.pid", dds_process); time.sleep(1)
    else: say("[1/3] DDS Agent já estava ativo.")
    env.pop("GZ_SIM_SERVER_CONFIG_PATH", None)
    resources = [Path(env["AGROBOT_SIM_DIR"]) / "AgrobotScene", px4 / "Tools/simulation/gz/models", px4 / "Tools/simulation/gz/worlds"]
    env["GZ_SIM_RESOURCE_PATH"] = ":".join(map(str, resources)) + ":" + env.get("GZ_SIM_RESOURCE_PATH", "")
    env.update({"PX4_GZ_STANDALONE":"1", "PX4_GZ_WORLD":world, "PX4_GZ_MODEL_POSE":",".join(map(str,pose)), "PX4_SYS_AUTOSTART":str(autostart), "PX4_SIM_MODEL":model, "GZ_IP":"127.0.0.1"})
    say(f"[2/3] Iniciando PX4 v1.17.0 em modo standalone no mundo '{world}'...")
    say(f"      modelo={model} pose={','.join(map(str,pose))}")
    log = (RUNTIME / "px4.log").open("w", encoding="utf-8")
    px4_process = subprocess.Popen([str(px4_bin)], cwd=rootfs, env=env, stdout=log, stderr=subprocess.STDOUT)
    write_pid("px4.pid", px4_process)
    status_topic = None
    for attempt in range(180):
        if px4_process.poll() is not None: die("[ERRO] PX4 encerrou:\n" + tail(RUNTIME / "px4.log", 80))
        if dds_process is not None and dds_process.poll() is not None:
            die("[ERRO] Micro XRCE-DDS Agent encerrou:\n" + tail(RUNTIME / "dds_agent.log", 100))
        status_topic = find_status_topic(env)
        if status_topic and topic_once(status_topic, env, 2): break
        if attempt == 30:
            say("      renovando descoberta do grafo ROS 2...")
            run(["ros2", "daemon", "stop"], env=env, check=False, capture=True)
            time.sleep(1)
        if attempt and attempt % 20 == 0: say(f"      aguardando PX4/DDS... {attempt // 2}s")
        time.sleep(0.5)
    else:
        discovered = "\n".join(topic for topic in ros_topic_list(env) if "/fmu/" in topic)
        die(
            "[ERRO] vehicle_status indisponível após 90 s.\n"
            f"ROS_DOMAIN_ID={env.get('ROS_DOMAIN_ID', '0')}\n"
            f"RMW_IMPLEMENTATION={env.get('RMW_IMPLEMENTATION', 'padrão')}\n"
            "\nTópicos /fmu descobertos:\n"
            + (discovered or "(nenhum)")
            + "\n\nDDS Agent:\n"
            + tail(RUNTIME / "dds_agent.log", 100)
            + "\n\nPX4:\n"
            + tail(RUNTIME / "px4.log", 100)
        )
    say(f"[3/3] PX4 + DDS conectados.\n[OK] DRONE X500 PRONTO\nROS 2: {status_topic}")
    return px4_process.wait()


def cmd_start_drone_mission(_args) -> int:
    env = project_env(); topic = find_status_topic(env)
    if not topic or not topic_once(topic, env): die("[ERRO] PX4/DDS indisponível. Rode start_drone.py.")
    mission = load_yaml(ROOT / "config/drone.yaml").get("mission", {})
    height = float(mission.get("takeoff_height_m", 3)); hover = float(mission.get("hover_seconds", 8))
    os.execvpe("ros2", ["ros2", "run", "drone_offboard", "offboard_demo", "--ros-args", "-p", f"takeoff_height_m:={height}", "-p", f"hover_seconds:={hover}"], env)
    return 0


def cmd_start_bridge(_args) -> int:
    env = project_env(); cfg = ROOT / "config/bridge.yaml"
    if run(["ip", "link", "show", "vcan0"], check=False).returncode != 0: die("[ERRO] vcan0 ausente.")
    info = output(["ros2", "topic", "info", "/a200_0000/platform/odom"], env=env)
    if not re.search(r"Publisher count: [1-9]\d*", info): die("[ERRO] Husky sem odometria.")
    os.execvpe("ros2", ["ros2", "run", "husky_isobus_bridge", "python_can_bridge", "--ros-args", "-p", f"config_file:={cfg}"], env)
    return 0


def cmd_monitor_vcan(_args) -> int:
    env = project_env(); cfg = ROOT / "config/bridge.yaml"
    if run(["ip", "link", "show", "vcan0"], check=False).returncode != 0: die("[ERRO] vcan0 ausente.")
    os.execvpe("ros2", ["ros2", "run", "husky_isobus_bridge", "vcan_motion_monitor", "--config", str(cfg)], env)
    return 0


def cmd_run_tests(_args) -> int:
    env = project_env(False); env["PYTHONPATH"] = str(WS / "src/husky_isobus_bridge") + ":" + env.get("PYTHONPATH", "")
    return run([sys.executable, "-m", "pytest", "-q", "tests"], env=env, cwd=ROOT, check=False).returncode


def cmd_check_all(_args) -> int:
    env = project_env(); world = str(load_yaml(ROOT / "config/simulation.yaml").get("world", {}).get("name", "AgrobotScene"))
    agrobot = Path(env["AGROBOT_SIM_DIR"]); say("== Diagnóstico ==")
    say(f"[OK] {agrobot}" if (agrobot / "AgrobotScene/AgrobotScene.sdf").is_file() else "[ERRO] AgrobotScene ausente")
    say(f"[OK] mundo {world}" if world_running(world, env) else f"[ERRO] mundo {world} ausente")
    info = output(["ros2", "topic", "info", "/a200_0000/platform/odom"], env=env)
    say("[OK] Husky odom" if re.search(r"Publisher count: [1-9]", info) else "[ERRO] Husky sem odom")
    px4_bin = Path(env["PX4_DIR"]) / "build/px4_sitl_default/bin/px4"; say(f"[OK] PX4: {px4_bin}" if os.access(px4_bin, os.X_OK) else "[ERRO] PX4 ausente")
    topic = find_status_topic(env); say(f"[OK] DDS: {topic}" if topic else "[INFO] drone não iniciado")
    run(["ip", "-brief", "link", "show", "vcan0"], check=False)
    return 0


def cmd_stop_all(_args) -> int:
    say("Encerrando PX4, DDS, Husky e Gazebo...")
    for name in ("px4.pid", "dds_agent.pid", "husky_spawn.pid", "clock_bridge.pid", "gazebo.pid"):
        path = RUNTIME / name
        if path.is_file():
            try: os.kill(int(path.read_text().strip()), signal.SIGTERM)
            except (ValueError, ProcessLookupError, PermissionError): pass
            path.unlink(missing_ok=True)
    patterns = ("px4_sitl_default/bin/px4", "MicroXRCEAgent.*udp4", "robot_spawn.launch.py", "gz_sim.launch.py", "parameter_bridge.*clock", "gz sim.*AgrobotScene")
    for pattern in patterns: run(["pkill", "-TERM", "-f", pattern], check=False)
    say("[OK] encerramento solicitado."); return 0


def cmd_start_simulation(_args) -> int:
    env = project_env(); RUNTIME.mkdir(parents=True, exist_ok=True)
    cfg = load_yaml(ROOT / "config/simulation.yaml"); world = str(cfg.get("world", {}).get("name", "AgrobotScene")); spawn = cfg.get("spawn", {})
    x,y,z,yaw = (float(spawn.get(k,d)) for k,d in (("x",0),("y",0),("z",.5),("yaw",0)))
    setup_path = ROOT / "config/clearpath"; world_dir = Path(env["AGROBOT_SIM_DIR"]) / "AgrobotScene"; world_file = world_dir / "AgrobotScene.sdf"
    if not (WS / "install/setup.bash").is_file(): die("[ERRO] Workspace não compilado. Rode setup_all.py.")
    if not world_file.is_file(): die(f"[ERRO] mundo ausente: {world_file}")
    for command in ("gz", "ros2"):
        if not command_exists(command, env): die(f"[ERRO] comando ausente: {command}")
    for package in ("clearpath_gz", "ros_gz_sim", "ros_gz_bridge", "gz_ros2_control"):
        if run(["ros2", "pkg", "prefix", package], env=env, check=False, capture=True).returncode: die(f"[ERRO] pacote ROS ausente: {package}")
    existing = sorted(set(re.findall(r"^/world/([^/]+)/", output(["gz","service","-l"],env=env), re.M)))
    if existing: die("[ERRO] Gazebo já ativo: " + ", ".join(existing))
    clearpath = Path(output(["ros2","pkg","prefix","clearpath_gz"],env=env).strip()); control = Path(output(["ros2","pkg","prefix","gz_ros2_control"],env=env).strip())
    env["GZ_SIM_SYSTEM_PLUGIN_PATH"] = f"{control}/lib:" + env.get("GZ_SIM_SYSTEM_PLUGIN_PATH", "")
    resources = [world_dir, clearpath/"share/clearpath_gz/worlds", clearpath/"share/clearpath_gz/meshes"]
    for prefix in env.get("AMENT_PREFIX_PATH", "").split(":"):
        if prefix: resources.append(Path(prefix)/"share")
    px4 = ROOT/"third_party/PX4-Autopilot"
    if (px4/"Tools/simulation/gz/models").is_dir(): resources += [px4/"Tools/simulation/gz/models", px4/"Tools/simulation/gz/worlds"]
    env["GZ_SIM_RESOURCE_PATH"] = ":".join(map(str,resources)) + ":" + env.get("GZ_SIM_RESOURCE_PATH", "")
    env.pop("WAYLAND_DISPLAY", None); env.pop("GZ_SIM_SERVER_CONFIG_PATH", None); env["QT_QPA_PLATFORM"] = env.get("QT_QPA_PLATFORM", "xcb")
    processes=[]
    def cleanup():
        for process in reversed(processes): terminate(process)
    atexit.register(cleanup)
    # Copia a configuração gráfica da Clearpath e garante que o painel Teleop
    # envie comandos ao tópico correto do Husky simulado.
    gui_args: list[str] = []
    clearpath_gui = clearpath / "share/clearpath_gz/config/gui.config"
    if clearpath_gui.is_file():
        gui_text = clearpath_gui.read_text(encoding="utf-8")
        match = re.search(
            r'<plugin\s+filename="Teleop".*?</plugin>',
            gui_text,
            flags=re.DOTALL,
        )
        if match:
            block = match.group(0)
            if re.search(r"<topic>.*?</topic>", block, flags=re.DOTALL):
                block = re.sub(
                    r"<topic>.*?</topic>",
                    "<topic>/a200_0000/cmd_vel</topic>",
                    block,
                    count=1,
                    flags=re.DOTALL,
                )
            else:
                block = block.replace(
                    ">",
                    ">\n    <topic>/a200_0000/cmd_vel</topic>",
                    1,
                )
            gui_text = gui_text[:match.start()] + block + gui_text[match.end():]
        gui_tmp = RUNTIME / "gui_agrobot_scene.config"
        gui_tmp.write_text(gui_text, encoding="utf-8")
        gui_args = ["--gui-config", str(gui_tmp)]
    say(f"[1/5] Abrindo {world} pelo ros_gz_sim...")
    gz_log=(RUNTIME/"gazebo.log").open("w",encoding="utf-8")
    gz_arguments = ["-r", "-v", "4", *gui_args, str(world_file)]
    gazebo=subprocess.Popen(["ros2","launch","ros_gz_sim","gz_sim.launch.py",f"gz_args:={' '.join(gz_arguments)}"],cwd=world_dir,env=env,stdout=gz_log,stderr=subprocess.STDOUT); processes.append(gazebo); write_pid("gazebo.pid",gazebo)
    for _ in range(180):
        if gazebo.poll() is not None: die("[ERRO] Gazebo encerrou:\n"+tail(RUNTIME/"gazebo.log"))
        if world_running(world,env): break
        time.sleep(.5)
    else: die(f"[ERRO] mundo {world} não carregou.")
    # Alguns mundos externos permanecem pausados apesar do argumento -r.
    # Enviar WorldControl explicitamente garante avanço do tempo simulado.
    control_result = run(
        [
            "gz", "service", "-s", f"/world/{world}/control",
            "--reqtype", "gz.msgs.WorldControl",
            "--reptype", "gz.msgs.Boolean",
            "--timeout", "3000",
            "--req", "pause: false",
        ],
        env=env,
        check=False,
        capture=True,
    )
    if control_result.returncode == 0:
        say("[OK] mundo em execução (pause=false).")
    else:
        say("[AVISO] não foi possível confirmar pause=false; continuando.")
    say(f"[OK] mundo '{world}' carregado.\n[2/5] Validando /clock...")
    if not topic_once("/clock",env):
        # Dependendo do SDF e da versão do Gazebo, o relógio pode estar em
        # /clock ou em /world/<nome>/clock no Gazebo Transport.
        gz_clock_topics = [
            topic for topic in output(["gz", "topic", "-l"], env=env).splitlines()
            if topic == "/clock" or topic.endswith("/clock")
        ]
        preferred_clock = f"/world/{world}/clock"
        if preferred_clock in gz_clock_topics:
            gz_clock_topic = preferred_clock
        elif "/clock" in gz_clock_topics:
            gz_clock_topic = "/clock"
        elif gz_clock_topics:
            gz_clock_topic = gz_clock_topics[0]
        else:
            die(
                "[ERRO] Gazebo não publicou nenhum tópico de relógio.\n"
                "Verifique .runtime/gazebo.log."
            )
        say(f"      criando ponte {gz_clock_topic} -> /clock...")
        clock_cfg=RUNTIME/"clock_bridge.yaml"; clock_cfg.write_text(f'- ros_topic_name: "/clock"\n  gz_topic_name: "{gz_clock_topic}"\n  ros_type_name: "rosgraph_msgs/msg/Clock"\n  gz_type_name: "gz.msgs.Clock"\n  direction: GZ_TO_ROS\n  qos_profile: CLOCK\n',encoding="utf-8")
        clock_log=(RUNTIME/"clock.log").open("w",encoding="utf-8"); clock=subprocess.Popen(["ros2","run","ros_gz_bridge","parameter_bridge","--ros-args","-p",f"config_file:={clock_cfg}"],env=env,stdout=clock_log,stderr=subprocess.STDOUT); processes.append(clock); write_pid("clock_bridge.pid",clock)
        clock_ready = False
        for attempt in range(60):
            if clock.poll() is not None:
                die("[ERRO] ponte /clock encerrou:\n" + tail(RUNTIME/"clock.log", 80))
            if topic_once("/clock",env,1):
                clock_ready = True
                break
            # Se a ponte já registrou um publisher, não bloqueamos o spawn por
            # causa de uma limitação do ros2 topic echo com Clock/QoS. Damos
            # alguns segundos para a descoberta DDS antes de aceitar.
            if attempt >= 8 and topic_has_publisher("/clock", env):
                say("[OK] publisher de /clock detectado.")
                clock_ready = True
                break
            time.sleep(.25)
        if not clock_ready:
            die(
                "[ERRO] /clock indisponível.\n"
                f"Tópico Gazebo usado: {gz_clock_topic}\n"
                + tail(RUNTIME/"clock.log", 80)
            )
    say("[OK] /clock ativo.\n[3/5] Gerando e inserindo Husky A200...")
    for name in ("platform","sensors","manipulators"):
        path=setup_path/name
        if path.exists(): shutil.rmtree(path)
    spawn_log=(RUNTIME/"husky_spawn.log").open("w",encoding="utf-8")
    robot=subprocess.Popen(["ros2","launch","clearpath_gz","robot_spawn.launch.py",f"setup_path:={setup_path}/",f"world:={world}","rviz:=false","use_sim_time:=true","generate:=true",f"x:={x}",f"y:={y}",f"z:={z}",f"yaw:={yaw}"],env=env,stdout=spawn_log,stderr=subprocess.STDOUT); processes.append(robot); write_pid("husky_spawn.pid",robot)
    cm=f"/a200_0000/controller_manager/list_controllers"; say("[4/5] Verificando ros2_control...")
    for _ in range(120):
        if cm in output(["ros2","service","list"],env=env): break
        if robot.poll() is not None: break
        time.sleep(.5)
    else: pass
    if cm not in output(["ros2","service","list"],env=env): die("[ERRO] controller_manager não apareceu.\n"+tail(RUNTIME/"husky_spawn.log"))
    say("[OK] controller_manager encontrado.\n[5/5] Validando odometria...")
    for _ in range(120):
        info=output(["ros2","topic","info","/a200_0000/platform/odom"],env=env)
        if re.search(r"Publisher count: [1-9]",info): break
        time.sleep(.5)
    else: die("[ERRO] odometria indisponível.")
    say("[OK] AGROBOTSCENE + HUSKY PRONTOS")
    return robot.wait()


COMMANDS = {
    "env": cmd_env, "preflight": cmd_preflight, "build": cmd_build,
    "repair_px4": cmd_repair_px4, "setup_all": cmd_setup_all,
    "setup_vcan": cmd_setup_vcan, "remove_vcan": cmd_remove_vcan,
    "start_dds_agent": cmd_start_dds_agent, "start_drone": cmd_start_drone,
    "start_drone_mission": cmd_start_drone_mission, "start_bridge": cmd_start_bridge,
    "monitor_vcan": cmd_monitor_vcan, "run_tests": cmd_run_tests,
    "check": cmd_check_all, "check_all": cmd_check_all,
    "stop_all": cmd_stop_all, "stop_simulation": cmd_stop_all,
    "start_simulation": cmd_start_simulation,
}


def main(command: str | None = None) -> int:
    command = command or Path(sys.argv[0]).stem
    parser = argparse.ArgumentParser(description=f"Simulador Husky/ISOBUS/PX4: {command}")
    if command in ("setup_vcan", "remove_vcan"):
        parser.add_argument("interface", nargs="?", default="vcan0")
    args = parser.parse_args()
    try:
        return COMMANDS[command](args)
    except AppError as exc:
        say(str(exc), error=True); return 1
    except KeyboardInterrupt:
        say("\n[INFO] interrompido pelo usuário."); return 130
    except subprocess.CalledProcessError as exc:
        say(f"[ERRO] comando falhou ({exc.returncode}): {' '.join(map(str, exc.cmd))}", error=True); return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
