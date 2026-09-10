#include "isobus/hardware_integration/can_hardware_interface.hpp"
#include "isobus/hardware_integration/socket_can_interface.hpp"
#include "isobus/isobus/can_network_manager.hpp"
#include "isobus/isobus/isobus_speed_distance_messages.hpp"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <cstdint>
#include <cstring>
#include <future>
#include <iomanip>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <thread>

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

namespace
{
std::atomic_bool running(true);

#pragma pack(push, 1)
struct OutGaugePacket
{
    std::uint32_t timeMilliseconds;
    char car[4];
    std::uint16_t flags;
    std::uint8_t gear; // Reverse=0, Neutral=1, First=2...
    std::uint8_t playerId;
    float speedMetresPerSecond;
    float rpm;
    float turboBar;
    float engineTemperatureCelsius;
    float fuelFraction;
    float oilPressureBar;
    float oilTemperatureCelsius;
    std::uint32_t dashLights;
    std::uint32_t showLights;
    float throttle;
    float brake;
    float clutch;
    char display1[16];
    char display2[16];
    std::int32_t id;
};
#pragma pack(pop)

static_assert(sizeof(OutGaugePacket) == 96, "Tamanho inesperado do pacote OutGauge");

struct Telemetry
{
    double speedMetresPerSecond = 0.0;
    double rpm = 0.0;
    double throttle = 0.0;
    double brake = 0.0;
    std::uint8_t gear = 1;
    bool received = false;
    std::chrono::steady_clock::time_point lastPacket{};
};

Telemetry telemetry;
std::mutex telemetryMutex;

void signalHandler(int)
{
    running = false;
}

std::uint16_t metresPerSecondToMillimetresPerSecond(double speed)
{
    const double limited = std::max(0.0, std::min(64.255, std::fabs(speed)));
    return static_cast<std::uint16_t>(std::lround(limited * 1000.0));
}

const char *gearName(std::uint8_t gear)
{
    if (gear == 0)
    {
        return "RE";
    }
    if (gear == 1)
    {
        return "NEUTRO";
    }
    return "FRENTE";
}

void receiveOutGauge(std::uint16_t port)
{
    const int udpSocket = ::socket(AF_INET, SOCK_DGRAM, 0);
    if (udpSocket < 0)
    {
        std::perror("socket UDP");
        running = false;
        return;
    }

    int reuse = 1;
    ::setsockopt(udpSocket, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

    timeval timeout{};
    timeout.tv_sec = 0;
    timeout.tv_usec = 250000;
    ::setsockopt(udpSocket, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));

    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_ANY);
    address.sin_port = htons(port);

    if (::bind(udpSocket, reinterpret_cast<sockaddr *>(&address), sizeof(address)) < 0)
    {
        std::perror("bind UDP");
        std::cerr << "A porta " << port << " pode estar sendo usada por outro programa.\n";
        ::close(udpSocket);
        running = false;
        return;
    }

    std::cout << "Aguardando telemetria OutGauge em UDP 127.0.0.1:" << port << "...\n";

    while (running)
    {
        OutGaugePacket packet{};
        const ssize_t receivedBytes = ::recvfrom(udpSocket,
                                                 &packet,
                                                 sizeof(packet),
                                                 0,
                                                 nullptr,
                                                 nullptr);

        if (receivedBytes < 0)
        {
            continue;
        }

        if (receivedBytes != 92 && receivedBytes != 96)
        {
            std::cerr << "Pacote OutGauge ignorado: " << receivedBytes
                      << " bytes; esperado 92 ou 96.\n";
            continue;
        }

        if (!std::isfinite(packet.speedMetresPerSecond) ||
            !std::isfinite(packet.rpm) ||
            !std::isfinite(packet.throttle) ||
            !std::isfinite(packet.brake))
        {
            continue;
        }

        std::lock_guard<std::mutex> lock(telemetryMutex);
        telemetry.speedMetresPerSecond = std::fabs(packet.speedMetresPerSecond);
        telemetry.rpm = std::max(0.0, static_cast<double>(packet.rpm));
        telemetry.throttle = std::max(0.0, std::min(1.0, static_cast<double>(packet.throttle)));
        telemetry.brake = std::max(0.0, std::min(1.0, static_cast<double>(packet.brake)));
        telemetry.gear = packet.gear;
        telemetry.received = true;
        telemetry.lastPacket = std::chrono::steady_clock::now();
    }

    ::close(udpSocket);
}
} // namespace

int main(int argc, char **argv)
{
    std::signal(SIGINT, signalHandler);

    std::uint16_t udpPort = 1355;
    if (argc >= 2)
    {
        try
        {
            const int parsedPort = std::stoi(argv[1]);
            if (parsedPort <= 0 || parsedPort > 65535)
            {
                throw std::out_of_range("porta");
            }
            udpPort = static_cast<std::uint16_t>(parsedPort);
        }
        catch (const std::exception &)
        {
            std::cerr << "Porta invalida: " << argv[1] << "\n";
            return 1;
        }
    }

    auto canDriver = std::make_shared<isobus::SocketCANInterface>("can0");
    isobus::CANHardwareInterface::set_number_of_can_channels(1);
    isobus::CANHardwareInterface::assign_can_channel_frame_handler(0, canDriver);

    if ((!isobus::CANHardwareInterface::start()) || (!canDriver->get_is_valid()))
    {
        std::cerr << "Erro: nao foi possivel abrir can0. Rode ./setup_can.sh primeiro.\n";
        return 2;
    }

    isobus::NAME tractorName(0);
    tractorName.set_arbitrary_address_capable(true);
    tractorName.set_industry_group(2);
    tractorName.set_device_class(static_cast<std::uint8_t>(isobus::NAME::DeviceClass::Tractor));
    tractorName.set_function_code(static_cast<std::uint8_t>(isobus::NAME::Function::TractorECU));
    tractorName.set_identity_number(2001);
    tractorName.set_ecu_instance(0);
    tractorName.set_function_instance(0);
    tractorName.set_device_class_instance(0);
    tractorName.set_manufacturer_code(1407);

    auto tractorECU = isobus::CANNetworkManager::CANNetwork.create_internal_control_function(
        tractorName,
        0,
        0x80);

    auto addressClaimed = std::async(std::launch::async, [&tractorECU]() {
        while (running && !tractorECU->get_address_valid())
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
    });

    if (addressClaimed.wait_for(std::chrono::seconds(5)) == std::future_status::timeout)
    {
        std::cerr << "Erro: a TECU nao conseguiu reivindicar um endereco.\n";
        isobus::CANHardwareInterface::stop();
        return 3;
    }

    isobus::SpeedMessagesInterface speedInterface(
        tractorECU,
        false,
        false,
        true,
        false);

    speedInterface.machineSelectedSpeedTransmitData.set_speed_source(
        isobus::SpeedMessagesInterface::MachineSelectedSpeedData::SpeedSource::NavigationBasedSpeed);
    speedInterface.machineSelectedSpeedTransmitData.set_limit_status(
        isobus::SpeedMessagesInterface::MachineSelectedSpeedData::LimitStatus::NotLimited);
    speedInterface.machineSelectedSpeedTransmitData.set_exit_reason_code(
        static_cast<std::uint8_t>(isobus::SpeedMessagesInterface::MachineSelectedSpeedData::ExitReasonCode::NoReasonAllClear));
    speedInterface.initialize();

    std::thread udpThread(receiveOutGauge, udpPort);

    std::uint32_t distanceMillimetres = 0;
    auto previousUpdate = std::chrono::steady_clock::now();
    auto previousPrint = previousUpdate;

    std::cout << "\n=== RIGS OF RODS -> ISOBUS ===\n";
    std::cout << "Endereco da TECU: 0x" << std::hex << std::uppercase
              << static_cast<int>(tractorECU->get_address()) << std::dec << "\n";
    std::cout << "Saida ISOBUS: can0, PGN 0xF022\n";
    std::cout << "Pressione Ctrl+C para encerrar.\n\n";

    while (running)
    {
        const auto now = std::chrono::steady_clock::now();
        const double elapsedSeconds = std::chrono::duration<double>(now - previousUpdate).count();
        previousUpdate = now;

        Telemetry current;
        {
            std::lock_guard<std::mutex> lock(telemetryMutex);
            current = telemetry;
        }

        const bool fresh = current.received &&
                           (std::chrono::duration<double>(now - current.lastPacket).count() < 1.0);

        const double speedMetresPerSecond = fresh ? current.speedMetresPerSecond : 0.0;
        const std::uint16_t speedMillimetresPerSecond =
            metresPerSecondToMillimetresPerSecond(speedMetresPerSecond);

        distanceMillimetres += static_cast<std::uint32_t>(
            static_cast<double>(speedMillimetresPerSecond) * elapsedSeconds);

        isobus::SpeedMessagesInterface::MachineDirection direction =
            isobus::SpeedMessagesInterface::MachineDirection::NotAvailable;

        if (fresh)
        {
            direction = (current.gear == 0)
                            ? isobus::SpeedMessagesInterface::MachineDirection::Reverse
                            : isobus::SpeedMessagesInterface::MachineDirection::Forward;
        }

        speedInterface.machineSelectedSpeedTransmitData.set_machine_speed(speedMillimetresPerSecond);
        speedInterface.machineSelectedSpeedTransmitData.set_machine_distance(distanceMillimetres);
        speedInterface.machineSelectedSpeedTransmitData.set_machine_direction_of_travel(direction);
        speedInterface.update();

        if (std::chrono::duration<double>(now - previousPrint).count() >= 0.5)
        {
            previousPrint = now;
            if (!fresh)
            {
                std::cout << "\rAguardando o jogo enviar OutGauge...                         " << std::flush;
            }
            else
            {
                std::cout << "\rVelocidade: " << std::fixed << std::setprecision(1)
                          << (speedMetresPerSecond * 3.6) << " km/h"
                          << " | RPM: " << std::setprecision(0) << current.rpm
                          << " | Marcha: " << gearName(current.gear)
                          << " | Acelerador: " << std::setprecision(0) << current.throttle * 100.0 << "%"
                          << " | Freio: " << current.brake * 100.0 << "%     "
                          << std::flush;
            }
        }

        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    if (udpThread.joinable())
    {
        udpThread.join();
    }

    isobus::CANHardwareInterface::stop();
    std::cout << "\nGateway encerrado.\n";
    return 0;
}
