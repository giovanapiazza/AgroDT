#include "isobus/hardware_integration/can_hardware_interface.hpp"
#include "isobus/hardware_integration/socket_can_interface.hpp"
#include "isobus/isobus/can_network_manager.hpp"
#include "isobus/isobus/isobus_speed_distance_messages.hpp"

#include <atomic>
#include <chrono>
#include <cmath>
#include <csignal>
#include <future>
#include <iomanip>
#include <iostream>
#include <memory>
#include <thread>

namespace
{
std::atomic_bool running(true);
std::atomic<std::uint16_t> receivedSpeedMmps(0);
std::atomic<std::uint32_t> receivedDistanceMm(0);
std::atomic<std::uint64_t> receivedMessages(0);
std::atomic<std::uint64_t> lastMessageTimeMs(0);

void signal_handler(int)
{
    running = false;
}

std::uint64_t monotonic_milliseconds()
{
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count());
}

void on_machine_selected_speed(
    const std::shared_ptr<isobus::SpeedMessagesInterface::MachineSelectedSpeedData> data,
    bool)
{
    receivedSpeedMmps = data->get_machine_speed();
    receivedDistanceMm = data->get_machine_distance();
    ++receivedMessages;
    lastMessageTimeMs = monotonic_milliseconds();
}

void draw_dashboard(std::uint8_t address)
{
    constexpr double targetRateLitresPerHectare = 150.0;
    constexpr double boomWidthMetres = 12.0;
    constexpr int sectionCount = 6;

    const std::uint16_t speedMmps = receivedSpeedMmps.load();
    const double speedKmh = static_cast<double>(speedMmps) * 3.6 / 1000.0;
    const double flowLitresPerMinute = speedKmh * boomWidthMetres * targetRateLitresPerHectare / 600.0;
    const double distanceMetres = receivedDistanceMm.load() / 1000.0;
    const bool applying = speedKmh >= 0.5;
    const std::uint64_t now = monotonic_milliseconds();
    const std::uint64_t last = lastMessageTimeMs.load();
    const bool connected = (last != 0) && ((now - last) < 500);

    std::cout << "\033[2J\033[H";
    std::cout << "============================================================\n";
    std::cout << "       PULVERIZADOR VIRTUAL - IMPLEMENTO ISOBUS\n";
    std::cout << "============================================================\n";
    std::cout << "Endereco do implemento : 0x" << std::hex << std::uppercase
              << static_cast<int>(address) << std::dec << "\n";
    std::cout << "PGN recebido           : 0xF022 - Machine Selected Speed\n";
    std::cout << "Conexao com a TECU     : " << (connected ? "ONLINE" : "AGUARDANDO...") << "\n\n";

    std::cout << std::fixed << std::setprecision(1);
    std::cout << "Velocidade do trator   : " << std::setw(6) << speedKmh << " km/h\n";
    std::cout << "Distancia percorrida   : " << std::setw(6) << distanceMetres << " m\n";
    std::cout << "Taxa configurada       : " << std::setw(6) << targetRateLitresPerHectare << " L/ha\n";
    std::cout << "Largura da barra       : " << std::setw(6) << boomWidthMetres << " m\n";
    std::cout << "Vazao calculada        : " << std::setw(6) << flowLitresPerMinute << " L/min\n";
    std::cout << "Mensagens recebidas    : " << receivedMessages.load() << "\n\n";

    std::cout << "Estado da aplicacao    : " << (applying ? "APLICANDO" : "PARADO") << "\n";
    std::cout << "Secoes da barra        : ";
    for (int section = 1; section <= sectionCount; ++section)
    {
        std::cout << (applying ? "[ON ]" : "[OFF]");
    }
    std::cout << "\n";
    std::cout << "                           1    2    3    4    5    6\n\n";

    if (applying)
    {
        std::cout << "A ECU do pulverizador ajustou a vazao automaticamente\n";
        std::cout << "para manter 150 L/ha mesmo com a mudanca de velocidade.\n";
    }
    else
    {
        std::cout << "Sem movimento: valvulas fechadas para evitar aplicacao parada.\n";
    }

    std::cout << "\nPressione Ctrl+C para encerrar.\n" << std::flush;
}
}

int main()
{
    std::signal(SIGINT, signal_handler);

    auto canDriver = std::make_shared<isobus::SocketCANInterface>("can0");
    isobus::CANHardwareInterface::set_number_of_can_channels(1);
    isobus::CANHardwareInterface::assign_can_channel_frame_handler(0, canDriver);

    if ((!isobus::CANHardwareInterface::start()) || (!canDriver->get_is_valid()))
    {
        std::cerr << "Erro: nao foi possivel abrir can0.\n";
        return 1;
    }

    isobus::NAME sprayerName(0);
    sprayerName.set_arbitrary_address_capable(true);
    sprayerName.set_industry_group(2);
    sprayerName.set_device_class(static_cast<std::uint8_t>(isobus::NAME::DeviceClass::Sprayer));
    sprayerName.set_function_code(static_cast<std::uint8_t>(isobus::NAME::Function::ProductDosing));
    sprayerName.set_identity_number(2001);
    sprayerName.set_ecu_instance(0);
    sprayerName.set_function_instance(0);
    sprayerName.set_device_class_instance(0);
    sprayerName.set_manufacturer_code(1407);

    auto sprayerECU = isobus::CANNetworkManager::CANNetwork.create_internal_control_function(
        sprayerName,
        0,
        0x90);

    auto addressClaimed = std::async(std::launch::async, [&sprayerECU]() {
        while (running && !sprayerECU->get_address_valid())
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
    });

    if (addressClaimed.wait_for(std::chrono::seconds(5)) == std::future_status::timeout)
    {
        std::cerr << "Erro: o pulverizador nao conseguiu reivindicar um endereco.\n";
        isobus::CANHardwareInterface::stop();
        return 2;
    }

    isobus::SpeedMessagesInterface speedReceiver(nullptr);
    speedReceiver.get_machine_selected_speed_data_event_publisher().add_listener(
        on_machine_selected_speed);
    speedReceiver.initialize();

    while (running)
    {
        speedReceiver.update();
        draw_dashboard(sprayerECU->get_address());
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }

    isobus::CANHardwareInterface::stop();
    std::cout << "\nPulverizador virtual encerrado.\n";
    return 0;
}
