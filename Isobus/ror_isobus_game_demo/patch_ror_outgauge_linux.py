#!/usr/bin/env python3
from pathlib import Path
import re
import shutil
import sys

DEFAULT = Path.home() / "rigs-of-rods-source/rigs-of-rods/source/main/network/OutGauge.cpp"
path = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT

if not path.exists():
    raise SystemExit(f"Arquivo nao encontrado: {path}")

text = path.read_text(encoding="utf-8")
if "[RoR|OutGauge] Linux support enabled" in text:
    print("O arquivo ja foi corrigido para Linux.")
    raise SystemExit(0)

if "// TODO: fix linux" not in text:
    raise SystemExit(
        "A versao do OutGauge.cpp e diferente da esperada. "
        "Nao apliquei alteracoes automaticamente."
    )

backup = path.with_suffix(path.suffix + ".before-isobus")
if not backup.exists():
    shutil.copy2(path, backup)

include_marker = "#include <Ogre.h>\n"
linux_includes = """#include <Ogre.h>\n\n#ifndef _WIN32\n#include <arpa/inet.h>\n#include <cerrno>\n#include <cstring>\n#include <sys/socket.h>\n#include <unistd.h>\n#endif\n"""
if include_marker not in text:
    raise SystemExit("Nao encontrei o bloco de includes esperado.")
text = text.replace(include_marker, linux_includes, 1)

close_start = text.index("void OutGauge::Close(void)")
connect_start = text.index("void OutGauge::Connect()", close_start)
new_close = r'''void OutGauge::Close(void)
{
    if (sockfd >= 0)
    {
#ifdef _WIN32
        closesocket(sockfd);
#else
        ::close(sockfd);
#endif
        sockfd = -1;
    }
    working = false;
}

'''
text = text[:close_start] + new_close + text[connect_start:]

connect_start = text.index("void OutGauge::Connect()")
update_start = text.index("bool OutGauge::Update", connect_start)
new_connect = r'''void OutGauge::Connect()
{
#ifdef _WIN32
    WSADATA wsd;
    if (WSAStartup(MAKEWORD(2, 2), &wsd) != 0)
    {
        LOG("[RoR|OutGauge] Error starting up winsock. OutGauge disabled.");
        return;
    }
#endif

    sockfd = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (sockfd < 0)
    {
        LOG(String("[RoR|OutGauge] Error creating socket for OutGauge: ").append(strerror(errno)));
        return;
    }

    sockaddr_in sendaddr{};
    sendaddr.sin_family = AF_INET;
    sendaddr.sin_port = htons(App::io_outgauge_port->getInt());

    const std::string ip = App::io_outgauge_ip->getStr();
    if (::inet_pton(AF_INET, ip.c_str(), &sendaddr.sin_addr) != 1)
    {
        LOG(String("[RoR|OutGauge] Invalid IPv4 address: ").append(ip));
        Close();
        return;
    }

    if (::connect(sockfd, reinterpret_cast<sockaddr*>(&sendaddr), sizeof(sendaddr)) < 0)
    {
        LOG(String("[RoR|OutGauge] Error connecting socket for OutGauge: ").append(strerror(errno)));
        Close();
        return;
    }

    LOG("[RoR|OutGauge] Linux support enabled; connected successfully");
    working = true;
}

'''
text = text[:connect_start] + new_connect + text[update_start:]

update_start = text.index("bool OutGauge::Update")
update = text[update_start:]
update = update.replace("#if defined(_WIN32) && defined(USE_SOCKETW)\n", "", 1)
update = update.replace(
    "    send(sockfd, (const char*)&gd, sizeof(gd), NULL);",
    "    ::send(sockfd, reinterpret_cast<const char*>(&gd), sizeof(gd), 0);",
    1,
)
update = re.sub(
    r"\n#else\s*\n\s*// TODO: fix linux\s*\n\s*return false;\s*\n#endif // _WIN32\s*\n}",
    "\n}",
    update,
    count=1,
)
text = text[:update_start] + update

if "// TODO: fix linux" in text:
    raise SystemExit("A alteracao ficou incompleta; o arquivo original foi preservado no backup.")

path.write_text(text, encoding="utf-8")
print(f"Correcao aplicada: {path}")
print(f"Backup: {backup}")
print("Agora recompile o jogo com: ninja -C build -j4")
