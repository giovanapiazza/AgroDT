#!/usr/bin/env python3
"""Controlador do simulador AgroDT: Gazebo, Husky, PX4 e missões independentes."""

from __future__ import annotations

import argparse
import atexit
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
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
        [str(x) for x in args],
        env=env,
        cwd=cwd,
        check=check,
        text=True,
        capture_output=capture,
        timeout=timeout,
    )


def output(args, *, env=None, cwd=None, timeout=None) -> str:
    result = run(args, env=env, cwd=cwd, check=False, capture=True, timeout=timeout)
    return result.stdout


def command_exists(name: str, env=None) -> bool:
    return shutil.which(name, path=(env or os.environ).get("PATH")) is not None


def shlex_quote(value: str) -> str:
    import shlex
    return shlex.quote(value)


def sourced_environment(files: list[Path]) -> dict[str, str]:
    env = os.environ.copy()
    existing = [path for path in files if path.is_file()]
    if not existing:
        return env

    command = (
        "set +u; "
        + "; ".join(f"source {shlex_quote(str(path))}" for path in existing)
        + "; env -0"
    )
    result = subprocess.run(
        ["bash", "-c", command],
        check=True,
        capture_output=True,
        env=env,
    )
    for entry in result.stdout.split(b"\0"):
        if b"=" in entry:
            key, value = entry.split(b"=", 1)
            env[key.decode(errors="surrogateescape")] = value.decode(
                errors="surrogateescape"
            )
    return env


def project_env(require_ros: bool = True) -> dict[str, str]:
    if require_ros and not ROS_SETUP.is_file():
        die("[ERRO] ROS 2 Jazzy não encontrado em /opt/ros/jazzy.")

    env = sourced_environment([ROS_SETUP, WS / "install/setup.bash"])
    env["HUSKY_ISOBUS_SIM_ROOT"] = str(ROOT)
    env["PX4_DIR"] = str(ROOT / "third_party/PX4-Autopilot")
    env["MICRO_XRCE_DDS_AGENT_DIR"] = str(
        ROOT / "third_party/Micro-XRCE-DDS-Agent"
    )
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
    return "\n".join(
        path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()[-count:]
    )


def world_name() -> str:
    cfg = load_yaml(ROOT / "config/simulation.yaml")
    return str(cfg.get("world", {}).get("name", "AgroDTField"))


def world_file() -> Path:
    cfg = load_yaml(ROOT / "config/simulation.yaml")
    relative = cfg.get("world", {}).get("file", "worlds/AgroDTField.sdf")
    return ROOT / str(relative)


def world_running(world: str, env: dict[str, str]) -> bool:
    return f"/world/{world}/" in output(["gz", "service", "-l"], env=env)


def ros_topic_list(env: dict[str, str]) -> list[str]:
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
    return next(
        (topic for topic in ros_topic_list(env) if pattern.match(topic)),
        None,
    )


def topic_has_publisher(topic: str, env: dict[str, str]) -> bool:
    info = output(["ros2", "topic", "info", topic], env=env)
    match = re.search(r"Publisher count:\s*(\d+)", info)
    return bool(match and int(match.group(1)) > 0)


def topic_once(topic: str, env: dict[str, str], timeout_s: float = 3) -> bool:
    commands = (
        ["ros2", "topic", "echo", topic, "--once"],
        [
            "ros2", "topic", "echo", topic, "--once",
            "--qos-reliability", "best_effort",
        ],
    )
    for command in commands:
        try:
            result = run(
                command,
                env=env,
                check=False,
                capture=True,
                timeout=timeout_s,
            )
            if result.returncode == 0:
                return True
        except subprocess.TimeoutExpired:
            pass
    return False


def package_prefix(package: str, env: dict[str, str]) -> Path | None:
    result = run(
        ["ros2", "pkg", "prefix", package],
        env=env,
        check=False,
        capture=True,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return Path(value) if value else None


def append_resource_path(env: dict[str, str]) -> None:
    resources = [ROOT / "worlds", ROOT / "models"]

    px4 = ROOT / "third_party/PX4-Autopilot"
    resources.extend(
        [
            px4 / "Tools/simulation/gz/models",
            px4 / "Tools/simulation/gz/worlds",
        ]
    )

    clearpath = package_prefix("clearpath_gz", env)
    if clearpath:
        resources.extend(
            [
                clearpath / "share/clearpath_gz/worlds",
                clearpath / "share/clearpath_gz/meshes",
            ]
        )

    for prefix in env.get("AMENT_PREFIX_PATH", "").split(":"):
        if prefix:
            resources.append(Path(prefix) / "share")

    existing = [str(path) for path in resources if path.exists()]
    env["GZ_SIM_RESOURCE_PATH"] = (
        ":".join(existing)
        + (":" if existing else "")
        + env.get("GZ_SIM_RESOURCE_PATH", "")
    )

    control = package_prefix("gz_ros2_control", env)
    if control:
        env["GZ_SIM_SYSTEM_PLUGIN_PATH"] = (
            f"{control / 'lib'}:"
            + env.get("GZ_SIM_SYSTEM_PLUGIN_PATH", "")
        )


def ensure_clock_bridge(
    env: dict[str, str],
    world: str,
    processes: list[subprocess.Popen],
) -> None:
    if topic_once("/clock", env, 1):
        say("[OK] /clock ativo.")
        return

    gz_topics = [
        topic
        for topic in output(["gz", "topic", "-l"], env=env).splitlines()
        if topic == "/clock" or topic.endswith("/clock")
    ]
    preferred = f"/world/{world}/clock"
    if preferred in gz_topics:
        gz_topic = preferred
    elif "/clock" in gz_topics:
        gz_topic = "/clock"
    elif gz_topics:
        gz_topic = gz_topics[0]
    else:
        die("[ERRO] Gazebo não publicou nenhum tópico de relógio.")

    bridge_cfg = RUNTIME / "clock_bridge.yaml"
    bridge_cfg.write_text(
        f'- ros_topic_name: "/clock"\n'
        f'  gz_topic_name: "{gz_topic}"\n'
        '  ros_type_name: "rosgraph_msgs/msg/Clock"\n'
        '  gz_type_name: "gz.msgs.Clock"\n'
        '  direction: GZ_TO_ROS\n'
        '  qos_profile: CLOCK\n',
        encoding="utf-8",
    )

    log = (RUNTIME / "clock.log").open("w", encoding="utf-8")
    bridge = subprocess.Popen(
        [
            "ros2",
            "run",
            "ros_gz_bridge",
            "parameter_bridge",
            "--ros-args",
            "-p",
            f"config_file:={bridge_cfg}",
        ],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    processes.append(bridge)
    write_pid("clock_bridge.pid", bridge)

    for attempt in range(60):
        if bridge.poll() is not None:
            die(
                "[ERRO] ponte /clock encerrou:\n"
                + tail(RUNTIME / "clock.log")
            )
        if topic_once("/clock", env, 1):
            say("[OK] /clock ativo.")
            return
        if attempt >= 8 and topic_has_publisher("/clock", env):
            say("[OK] publisher de /clock detectado.")
            return
        time.sleep(0.25)

    die(
        "[ERRO] /clock indisponível.\n"
        + tail(RUNTIME / "clock.log")
    )


def cmd_env(_args) -> int:
    env = project_env()
    for key in (
        "HUSKY_ISOBUS_SIM_ROOT",
        "PX4_DIR",
        "MICRO_XRCE_DDS_AGENT_DIR",
    ):
        say(f"{key}={env[key]}")
    return 0


def cmd_preflight(_args) -> int:
    errors = 0
    env = project_env() if ROS_SETUP.is_file() else os.environ.copy()
    say("== Verificação AgroDT ==")

    for command in ("python3", "ros2", "colcon", "gz"):
        if command_exists(command, env):
            say(f"[OK] comando {command}")
        else:
            errors += 1
            say(f"[ERRO] comando ausente: {command}", error=True)

    for package in ("ros_gz_sim", "ros_gz_bridge"):
        if package_prefix(package, env):
            say(f"[OK] pacote ROS: {package}")
        else:
            errors += 1
            say(f"[ERRO] pacote ROS ausente: {package}", error=True)

    if world_file().is_file():
        say(f"[OK] mundo local: {world_file()}")
    else:
        errors += 1
        say(f"[ERRO] mundo ausente: {world_file()}", error=True)

    if package_prefix("clearpath_gz", env):
        say("[OK] Clearpath disponível para inicialização opcional do Husky")
    else:
        say("[INFO] Clearpath não instalado; Gazebo e drone ainda podem ser usados.")

    if errors:
        say(
            f"Falha: {errors} requisito(s) obrigatório(s) ausente(s).",
            error=True,
        )
        return 1

    say("[OK] verificação concluída.")
    return 0


def cmd_build(_args) -> int:
    env = project_env()
    if not (WS / "src/px4_msgs").is_dir():
        say("[AVISO] px4_msgs ausente; rode setup_all.py para usar o drone.")

    for name in ("build", "install", "log"):
        path = WS / name
        if path.exists():
            shutil.rmtree(path)

    if command_exists("rosdep", env):
        run(
            [
                "rosdep",
                "install",
                "--from-paths",
                "src",
                "--ignore-src",
                "-r",
                "-y",
            ],
            env=env,
            cwd=WS,
            check=False,
        )

    run(["colcon", "build", "--symlink-install"], env=env, cwd=WS)
    say("[OK] workspace compilado.")
    return 0


def fresh_px4_clone(px4: Path) -> None:
    if px4.exists():
        shutil.rmtree(px4)
    say(f"[PX4] Instalando {PX4_REF}...")
    run(
        [
            "git",
            "clone",
            "--branch",
            PX4_REF,
            "--recurse-submodules",
            "https://github.com/PX4/PX4-Autopilot.git",
            px4,
        ]
    )


def px4_has_gz_bridge(px4: Path) -> bool:
    """Confirma que a build SITL contém o módulo gz_bridge."""
    build = px4 / "build/px4_sitl_default"
    bridge_lib = (
        build
        / "src/modules/simulation/gz_bridge/libmodules__simulation__gz_bridge.a"
    )
    if bridge_lib.is_file():
        return True

    ninja_file = build / "build.ninja"
    if not ninja_file.is_file():
        return False

    try:
        return "modules__simulation__gz_bridge" in ninja_file.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except OSError:
        return False


def repair_px4(px4: Path) -> None:
    """Prepara uma build PX4 SITL válida, incluindo o bridge do Gazebo."""
    binary = px4 / "build/px4_sitl_default/bin/px4"

    if (
        os.access(binary, os.X_OK)
        and px4_has_gz_bridge(px4)
    ):
        say(f"[OK] PX4 SITL + gz_bridge já compilados: {binary}")
        return

    if not (px4 / ".git").is_dir():
        fresh_px4_clone(px4)
    else:
        say(f"[PX4] Sincronizando fontes {PX4_REF}...")
        commands = [
            ["git", "-C", px4, "fetch", "--tags", "--force"],
            ["git", "-C", px4, "checkout", "--detach", PX4_REF],
            ["git", "-C", px4, "reset", "--hard", PX4_REF],
            ["git", "-C", px4, "submodule", "sync", "--recursive"],
            [
                "git",
                "-C",
                px4,
                "submodule",
                "update",
                "--init",
                "--recursive",
                "--force",
            ],
        ]
        for command in commands:
            run(command)

    setup_script = px4 / "Tools/setup/ubuntu.sh"
    if not setup_script.is_file():
        die(f"[ERRO] instalador oficial do PX4 ausente: {setup_script}")

    say("[PX4] Instalando dependências oficiais do SITL/Gazebo Harmonic...")
    say("      Pode ser solicitada a senha do sudo.")
    run(
        [
            "bash",
            str(setup_script),
            "--no-nuttx",
        ],
        cwd=px4,
    )

    # Uma build CMake criada antes da instalação das bibliotecas Gazebo
    # mantém gz_bridge desabilitado. É necessário reconfigurar do zero.
    say("[PX4] Limpando configuração SITL antiga...")
    run(["make", "-C", px4, "distclean"], check=False)

    say("[PX4] Recompilando px4_sitl com suporte ao Gazebo...")
    run(["make", "-C", px4, "px4_sitl"])

    if not os.access(binary, os.X_OK):
        die(f"[ERRO] binário PX4 não foi gerado: {binary}")

    if not px4_has_gz_bridge(px4):
        die(
            "[ERRO] PX4 recompilou, mas gz_bridge continua ausente.\n"
            "Confirme a instalação do Gazebo Harmonic e execute novamente:\n"
            "  python3 scripts/repair_px4.py"
        )

    say("[OK] PX4 SITL recompilado com gz_bridge.")

def cmd_repair_px4(_args) -> int:
    repair_px4(ROOT / "third_party/PX4-Autopilot")
    return 0


def cmd_setup_all(_args) -> int:
    env = project_env()
    tp = ROOT / "third_party"
    tp.mkdir(parents=True, exist_ok=True)

    packages = (
        "git cmake build-essential ninja-build ccache python3-pip python3-dev "
        "python3-setuptools python3-wheel python3-colcon-common-extensions "
        "python3-rosdep python3-yaml python3-can python3-pytest can-utils "
        "libssl-dev libxml2-dev libxml2-utils libunwind-dev cppzmq-dev "
        "ros-jazzy-ros-gz ros-jazzy-clearpath-simulator "
        "ros-jazzy-gz-ros2-control ros-jazzy-ros2-control "
        "ros-jazzy-ros2-controllers"
    ).split()

    run(["sudo", "apt", "update"])
    run(["sudo", "apt", "install", "-y", *packages])
    run(["sudo", "rosdep", "init"], env=env, check=False)
    run(["rosdep", "update"], env=env, check=False)

    px4 = tp / "PX4-Autopilot"
    # Não basta o binário existir: builds configuradas sem as bibliotecas
    # Gazebo não contêm o módulo gz_bridge e falham no spawn do X500.
    repair_px4(px4)

    agent = tp / "Micro-XRCE-DDS-Agent"
    if not (agent / ".git").is_dir():
        run(
            [
                "git",
                "clone",
                "--branch",
                "v2.4.3",
                "--depth",
                "1",
                "https://github.com/eProsima/Micro-XRCE-DDS-Agent.git",
                agent,
            ]
        )
    run(["cmake", "-S", agent, "-B", agent / "build"])
    run(
        [
            "cmake",
            "--build",
            agent / "build",
            f"-j{os.cpu_count() or 2}",
        ]
    )
    run(["sudo", "cmake", "--install", agent / "build"])
    run(["sudo", "ldconfig"], check=False)

    px4_msgs = WS / "src/px4_msgs"
    if not (px4_msgs / ".git").is_dir():
        if px4_msgs.exists():
            shutil.rmtree(px4_msgs)
        run(
            [
                "git",
                "clone",
                "--branch",
                "release/1.17",
                "--depth",
                "1",
                "https://github.com/PX4/px4_msgs.git",
                px4_msgs,
            ]
        )

    cmd_build(None)
    say("\n[OK] setup concluído.")
    say("Gazebo: python3 scripts/start_simulation.py")
    say("Husky:  python3 scripts/start_husky.py")
    say("Drone:  python3 scripts/start_drone.py")
    say("Missões: python3 scripts/start_drone_mission.py")
    return 0


def cmd_start_simulation(_args) -> int:
    env = project_env()
    RUNTIME.mkdir(parents=True, exist_ok=True)

    world = world_name()
    sdf = world_file()

    if not sdf.is_file():
        die(f"[ERRO] mundo ausente: {sdf}")
    if not package_prefix("ros_gz_sim", env):
        die("[ERRO] pacote ros_gz_sim ausente.")
    if not package_prefix("ros_gz_bridge", env):
        die("[ERRO] pacote ros_gz_bridge ausente.")
    if world_running(world, env):
        die(f"[ERRO] mundo '{world}' já está rodando.")

    append_resource_path(env)
    env.pop("WAYLAND_DISPLAY", None)
    env.pop("GZ_SIM_SERVER_CONFIG_PATH", None)
    env["QT_QPA_PLATFORM"] = env.get("QT_QPA_PLATFORM", "xcb")

    processes: list[subprocess.Popen] = []

    def cleanup():
        for process in reversed(processes):
            terminate(process)

    atexit.register(cleanup)

    say(f"[1/3] Abrindo Gazebo com o mundo {world}...")
    log = (RUNTIME / "gazebo.log").open("w", encoding="utf-8")
    gazebo = subprocess.Popen(
        [
            "ros2",
            "launch",
            "ros_gz_sim",
            "gz_sim.launch.py",
            f"gz_args:=-r -v 4 {sdf}",
        ],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    processes.append(gazebo)
    write_pid("gazebo.pid", gazebo)

    for _ in range(180):
        if gazebo.poll() is not None:
            die(
                "[ERRO] Gazebo encerrou:\n"
                + tail(RUNTIME / "gazebo.log")
            )
        if world_running(world, env):
            break
        time.sleep(0.5)
    else:
        die(f"[ERRO] mundo '{world}' não carregou.")

    say("[2/3] Campo carregado: 4 talhões de milho e corredores centrais.")
    ensure_clock_bridge(env, world, processes)
    say("[3/3] [OK] GAZEBO + PLANTAÇÃO PRONTOS")
    say("Husky e drone devem ser iniciados em terminais separados.")
    return gazebo.wait()


def cmd_start_husky(_args) -> int:
    env = project_env()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    world = world_name()

    if not world_running(world, env):
        die(
            "[ERRO] Gazebo não está rodando. "
            "Rode start_simulation.py primeiro."
        )

    clearpath = package_prefix("clearpath_gz", env)
    if not clearpath:
        die("[ERRO] clearpath_gz ausente. Rode setup_all.py.")

    if not package_prefix("gz_ros2_control", env):
        die("[ERRO] gz_ros2_control ausente. Rode setup_all.py.")

    spawn = (
        load_yaml(ROOT / "config/simulation.yaml")
        .get("husky", {})
        .get("spawn", {})
    )
    x = float(spawn.get("x", -10.0))
    y = float(spawn.get("y", 5.0))
    z = float(spawn.get("z", 0.5))
    yaw = float(spawn.get("yaw", 0.0))
    setup_path = ROOT / "config/clearpath"

    append_resource_path(env)

    for name in ("platform", "sensors", "manipulators"):
        generated = setup_path / name
        if generated.exists():
            shutil.rmtree(generated)

    say(f"[1/3] Inserindo Husky no mundo '{world}'...")
    log = (RUNTIME / "husky_spawn.log").open("w", encoding="utf-8")
    robot = subprocess.Popen(
        [
            "ros2",
            "launch",
            "clearpath_gz",
            "robot_spawn.launch.py",
            f"setup_path:={setup_path}/",
            f"world:={world}",
            "rviz:=false",
            "use_sim_time:=true",
            "generate:=true",
            f"x:={x}",
            f"y:={y}",
            f"z:={z}",
            f"yaw:={yaw}",
        ],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    write_pid("husky_spawn.pid", robot)

    cm = "/a200_0000/controller_manager/list_controllers"
    say("[2/3] Aguardando ros2_control...")
    for _ in range(120):
        if cm in output(["ros2", "service", "list"], env=env):
            break
        if robot.poll() is not None:
            die(
                "[ERRO] spawn do Husky encerrou:\n"
                + tail(RUNTIME / "husky_spawn.log")
            )
        time.sleep(0.5)
    else:
        die(
            "[ERRO] controller_manager não apareceu.\n"
            + tail(RUNTIME / "husky_spawn.log")
        )

    say("[3/3] Validando odometria...")
    for _ in range(120):
        if topic_has_publisher("/a200_0000/platform/odom", env):
            say("[OK] HUSKY PRONTO")
            return robot.wait()
        time.sleep(0.5)

    die("[ERRO] odometria do Husky indisponível.")


def cmd_start_drone(_args) -> int:
    env = project_env()
    RUNTIME.mkdir(parents=True, exist_ok=True)

    cfg = load_yaml(ROOT / "config/drone.yaml")
    px4_cfg = cfg.get("px4", {})
    spawn = cfg.get("spawn", {})
    dds = cfg.get("dds", {})

    model = str(px4_cfg.get("model", "gz_x500"))
    autostart = int(px4_cfg.get("autostart", 4001))
    world = str(px4_cfg.get("world", world_name()))
    pose = [
        float(spawn.get("x", -8.0)),
        float(spawn.get("y", -4.0)),
        float(spawn.get("z", 0.3)),
        float(spawn.get("roll", 0.0)),
        float(spawn.get("pitch", 0.0)),
        float(spawn.get("yaw", 0.0)),
    ]
    port = int(dds.get("port", 8888))

    px4 = Path(env["PX4_DIR"])
    px4_bin = px4 / "build/px4_sitl_default/bin/px4"
    rootfs = px4 / "build/px4_sitl_default/rootfs"

    if not os.access(px4_bin, os.X_OK):
        die("[ERRO] PX4 não compilado. Rode setup_all.py.")

    if not px4_has_gz_bridge(px4):
        die(
            "[ERRO] esta build do PX4 não contém o módulo gz_bridge.\n"
            "Isso acontece quando o PX4 é compilado antes das dependências "
            "do Gazebo Harmonic.\n"
            "Repare uma vez com:\n"
            "  python3 scripts/repair_px4.py\n"
            "Depois execute start_drone.py novamente."
        )

    if not world_running(world, env):
        die(
            f"[ERRO] mundo '{world}' não está rodando. "
            "Rode start_simulation.py primeiro."
        )

    dds_process = None
    px4_process = None

    def cleanup():
        terminate(px4_process)
        terminate(dds_process)

    atexit.register(cleanup)

    if run(
        ["pgrep", "-af", "MicroXRCEAgent.*udp4"],
        check=False,
        capture=True,
    ).returncode != 0:
        say(f"[1/3] Iniciando Micro XRCE-DDS Agent UDP {port}...")
        agent = (
            shutil.which(
                "MicroXRCEAgent",
                path=env.get("PATH"),
            )
            or str(
                Path(env["MICRO_XRCE_DDS_AGENT_DIR"])
                / "build/MicroXRCEAgent"
            )
        )
        if not os.access(agent, os.X_OK):
            die("[ERRO] MicroXRCEAgent ausente. Rode setup_all.py.")

        log = (RUNTIME / "dds_agent.log").open("w", encoding="utf-8")
        dds_process = subprocess.Popen(
            [agent, "udp4", "-p", str(port)],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        write_pid("dds_agent.pid", dds_process)
        time.sleep(1)
    else:
        say("[1/3] DDS Agent já estava ativo.")

    append_resource_path(env)
    env.pop("GZ_SIM_SERVER_CONFIG_PATH", None)
    env.update(
        {
            "PX4_GZ_STANDALONE": "1",
            "PX4_GZ_WORLD": world,
            "PX4_GZ_MODEL_POSE": ",".join(map(str, pose)),
            "PX4_SYS_AUTOSTART": str(autostart),
            "PX4_SIM_MODEL": model,
            "GZ_IP": "127.0.0.1",
        }
    )

    say(f"[2/3] Inserindo PX4 {model} no mundo '{world}'...")
    say("      pose=" + ",".join(map(str, pose)))

    log = (RUNTIME / "px4.log").open("w", encoding="utf-8")
    px4_process = subprocess.Popen(
        [str(px4_bin)],
        cwd=rootfs,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    write_pid("px4.pid", px4_process)

    status_topic = None
    for attempt in range(180):
        if px4_process.poll() is not None:
            die(
                "[ERRO] PX4 encerrou:\n"
                + tail(RUNTIME / "px4.log")
            )
        if dds_process is not None and dds_process.poll() is not None:
            die(
                "[ERRO] Micro XRCE-DDS Agent encerrou:\n"
                + tail(RUNTIME / "dds_agent.log")
            )

        status_topic = find_status_topic(env)
        if status_topic and topic_once(status_topic, env, 2):
            break

        if attempt and attempt % 20 == 0:
            say(
                f"      aguardando PX4/DDS... "
                f"{attempt // 2}s"
            )
        time.sleep(0.5)
    else:
        die(
            "[ERRO] vehicle_status indisponível após 90 s.\n"
            + tail(RUNTIME / "px4.log")
        )

    say(
        f"[3/3] [OK] DRONE X500 PRONTO\n"
        f"ROS 2: {status_topic}"
    )
    return px4_process.wait()


def cmd_start_drone_mission(_args) -> int:
    env = project_env()
    topic = find_status_topic(env)
    if not topic:
        die(
            "[ERRO] drone/PX4 indisponível. "
            "Rode start_drone.py primeiro."
        )

    say("[INFO] Executor de missões iniciado.")
    say("[INFO] Entrada: /agrodt/drone/mission")
    say("[INFO] Status:  /agrodt/drone/mission_status")
    os.execvpe(
        "ros2",
        ["ros2", "run", "drone_offboard", "mission_executor"],
        env,
    )
    return 0


def cmd_send_drone_mission(args) -> int:
    env = project_env()
    mission_path = Path(args.mission)
    if not mission_path.is_absolute():
        mission_path = ROOT / mission_path

    if not mission_path.is_file():
        die(f"[ERRO] missão ausente: {mission_path}")

    data = json.loads(mission_path.read_text(encoding="utf-8"))
    raw = json.dumps(data, separators=(",", ":"))
    message = json.dumps({"data": raw})

    say(f"[INFO] Enviando missão: {mission_path.name}")
    result = run(
        [
            "ros2",
            "topic",
            "pub",
            "--once",
            "/agrodt/drone/mission",
            "std_msgs/msg/String",
            message,
        ],
        env=env,
        check=False,
    )
    if result.returncode != 0:
        die("[ERRO] falha ao publicar missão.")

    say("[OK] missão publicada em /agrodt/drone/mission")
    return 0


def cmd_setup_vcan(args) -> int:
    if os.geteuid() != 0:
        die("[ERRO] execute com sudo.")

    iface = args.interface
    run(["modprobe", "vcan"])
    if run(["ip", "link", "show", iface], check=False).returncode != 0:
        run(["ip", "link", "add", "dev", iface, "type", "vcan"])
    run(["ip", "link", "set", "up", iface])
    run(["ip", "-brief", "link", "show", iface])
    return 0


def cmd_remove_vcan(args) -> int:
    if os.geteuid() != 0:
        die("[ERRO] execute com sudo.")

    if run(
        ["ip", "link", "show", args.interface],
        check=False,
    ).returncode == 0:
        run(
            ["ip", "link", "set", "down", args.interface],
            check=False,
        )
        run(
            [
                "ip",
                "link",
                "delete",
                args.interface,
                "type",
                "vcan",
            ],
            check=False,
        )
    return 0


def cmd_start_bridge(_args) -> int:
    env = project_env()
    cfg = ROOT / "config/bridge.yaml"

    if run(
        ["ip", "link", "show", "vcan0"],
        check=False,
    ).returncode != 0:
        die("[ERRO] vcan0 ausente.")

    if not topic_has_publisher(
        "/a200_0000/platform/odom",
        env,
    ):
        die("[ERRO] Husky não está ativo.")

    os.execvpe(
        "ros2",
        [
            "ros2",
            "run",
            "husky_isobus_bridge",
            "python_can_bridge",
            "--ros-args",
            "-p",
            f"config_file:={cfg}",
        ],
        env,
    )
    return 0


def cmd_monitor_vcan(_args) -> int:
    env = project_env()
    cfg = ROOT / "config/bridge.yaml"
    os.execvpe(
        "ros2",
        [
            "ros2",
            "run",
            "husky_isobus_bridge",
            "vcan_motion_monitor",
            "--config",
            str(cfg),
        ],
        env,
    )
    return 0


def cmd_run_tests(_args) -> int:
    env = project_env(False)
    env["PYTHONPATH"] = (
        str(WS / "src/husky_isobus_bridge")
        + ":"
        + env.get("PYTHONPATH", "")
    )
    return run(
        [sys.executable, "-m", "pytest", "-q", "tests"],
        env=env,
        cwd=ROOT,
        check=False,
    ).returncode


def cmd_check_all(_args) -> int:
    env = project_env()
    world = world_name()

    say("== Estado AgroDT ==")
    say(
        f"[OK] mundo local: {world_file()}"
        if world_file().is_file()
        else f"[ERRO] mundo ausente: {world_file()}"
    )
    say(
        f"[OK] Gazebo: {world}"
        if world_running(world, env)
        else "[INFO] Gazebo não iniciado"
    )
    say(
        "[OK] Husky ativo"
        if topic_has_publisher(
            "/a200_0000/platform/odom",
            env,
        )
        else "[INFO] Husky não iniciado"
    )

    status = find_status_topic(env)
    say(
        f"[OK] Drone/PX4 ativo: {status}"
        if status
        else "[INFO] Drone não iniciado"
    )

    mission_info = output(
        [
            "ros2",
            "topic",
            "info",
            "/agrodt/drone/mission",
        ],
        env=env,
    )
    say(
        "[OK] executor de missão ativo"
        if re.search(
            r"Subscription count:\s*[1-9]",
            mission_info,
        )
        else "[INFO] executor de missão não iniciado"
    )
    return 0


def cmd_stop_all(_args) -> int:
    say("Encerrando Gazebo, Husky, PX4, DDS e executor de missão...")

    for name in (
        "px4.pid",
        "dds_agent.pid",
        "husky_spawn.pid",
        "clock_bridge.pid",
        "gazebo.pid",
    ):
        path = RUNTIME / name
        if path.is_file():
            try:
                os.kill(
                    int(path.read_text().strip()),
                    signal.SIGTERM,
                )
            except (
                ValueError,
                ProcessLookupError,
                PermissionError,
            ):
                pass
            path.unlink(missing_ok=True)

    for pattern in (
        "px4_sitl_default/bin/px4",
        "MicroXRCEAgent.*udp4",
        "robot_spawn.launch.py",
        "gz_sim.launch.py",
        "mission_executor",
        "parameter_bridge.*clock",
    ):
        run(
            ["pkill", "-TERM", "-f", pattern],
            check=False,
        )

    say("[OK] encerramento solicitado.")
    return 0


COMMANDS = {
    "env": cmd_env,
    "preflight": cmd_preflight,
    "build": cmd_build,
    "repair_px4": cmd_repair_px4,
    "setup_all": cmd_setup_all,
    "start_simulation": cmd_start_simulation,
    "start_husky": cmd_start_husky,
    "start_drone": cmd_start_drone,
    "start_drone_mission": cmd_start_drone_mission,
    "send_drone_mission": cmd_send_drone_mission,
    "setup_vcan": cmd_setup_vcan,
    "remove_vcan": cmd_remove_vcan,
    "start_bridge": cmd_start_bridge,
    "monitor_vcan": cmd_monitor_vcan,
    "run_tests": cmd_run_tests,
    "check_all": cmd_check_all,
    "stop_all": cmd_stop_all,
}


def main(command: str | None = None) -> int:
    command = command or Path(sys.argv[0]).stem
    parser = argparse.ArgumentParser(
        description=f"AgroDT simulator: {command}"
    )

    if command in ("setup_vcan", "remove_vcan"):
        parser.add_argument(
            "interface",
            nargs="?",
            default="vcan0",
        )

    if command == "send_drone_mission":
        parser.add_argument(
            "mission",
            nargs="?",
            default="config/mission_test.json",
        )

    args = parser.parse_args()

    try:
        return COMMANDS[command](args)
    except AppError as exc:
        say(str(exc), error=True)
        return 1
    except KeyboardInterrupt:
        say("\n[INFO] interrompido pelo usuário.")
        return 130
    except subprocess.CalledProcessError as exc:
        say(
            f"[ERRO] comando falhou ({exc.returncode}): "
            + " ".join(map(str, exc.cmd)),
            error=True,
        )
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
