#include "demo_common.hpp"
#include "isobus/hardware_integration/can_hardware_interface.hpp"
#include "isobus/hardware_integration/socket_can_interface.hpp"
#include "isobus/isobus/can_network_manager.hpp"
#include "isobus/isobus/isobus_speed_distance_messages.hpp"

#include <atomic>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <iomanip>
#include <iostream>
#include <memory>
#include <string>
#include <thread>

namespace
{
constexpr std::uint8_t SPRAYER_PREFERRED_ADDRESS = 0x90;
constexpr double TARGET_RATE_LITRES_PER_HECTARE = 150.0;
constexpr double BOOM_WIDTH_METRES = 12.0;
constexpr int SECTION_COUNT = 6;
constexpr std::uint64_t MESSAGE_TIMEOUT_MS = 500;

std::atomic_bool running(true);
std::atomic<std::uint16_t> receivedSpeedMmps(0);
std::atomic<std::uint32_t> receivedDistanceMm(0);
std::atomic<std::uint64_t> receivedMessages(0);
std::atomic<std::uint64_t> lastMessageTimeMs(0);
std::atomic<std::uint8_t> receivedSourceAddress(0xFE);
std::atomic<std::uint8_t> receivedDirection(
    static_cast<std::uint8_t>(isobus::SpeedMessagesInterface::MachineDirection::NotAvailable));
std::atomic<std::uint8_t> receivedSpeedSource(
    static_cast<std::uint8_t>(
        isobus::SpeedMessagesInterface::MachineSelectedSpeedData::SpeedSource::NotAvailable));
std::atomic<std::uint8_t> receivedLimitStatus(
    static_cast<std::uint8_t>(
        isobus::SpeedMessagesInterface::MachineSelectedSpeedData::LimitStatus::NotAvailable));
std::atomic<std::uint8_t> receivedExitReason(
    static_cast<std::uint8_t>(
        isobus::SpeedMessagesInterface::MachineSelectedSpeedData::ExitReasonCode::NotAvailable));

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

const char *direction_to_text(isobus::SpeedMessagesInterface::MachineDirection direction)
{
    switch (direction)
    {
        case isobus::SpeedMessagesInterface::MachineDirection::Reverse:
            return "RE";
        case isobus::SpeedMessagesInterface::MachineDirection::Forward:
            return "FRENTE";
        case isobus::SpeedMessagesInterface::MachineDirection::Error:
            return "ERRO";
        case isobus::SpeedMessagesInterface::MachineDirection::NotAvailable:
        default:
            return "INDISPONIVEL";
    }
}

const char *speed_source_to_text(
    isobus::SpeedMessagesInterface::MachineSelectedSpeedData::SpeedSource source)
{
    using SpeedSource =
        isobus::SpeedMessagesInterface::MachineSelectedSpeedData::SpeedSource;
    switch (source)
    {
        case SpeedSource::WheelBasedSpeed:
            return "Wheel Based";
        case SpeedSource::GroundBasedSpeed:
            return "Ground Based";
        case SpeedSource::NavigationBasedSpeed:
            return "Navigation Based";
        case SpeedSource::Blended:
            return "Blended";
        case SpeedSource::Simulated:
            return "Simulated";
        case SpeedSource::Reserved_1:
        case SpeedSource::Reserved_2:
            return "Reserved";
        case SpeedSource::NotAvailable:
        default:
            return "Not Available";
    }
}

const char *limit_status_to_text(
    isobus::SpeedMessagesInterface::MachineSelectedSpeedData::LimitStatus status)
{
    using LimitStatus =
        isobus::SpeedMessagesInterface::MachineSelectedSpeedData::LimitStatus;
    switch (status)
    {
        case LimitStatus::NotLimited:
            return "Not Limited";
        case LimitStatus::OperatorLimitedControlled:
            return "Operator Limited";
        case LimitStatus::LimitedHigh:
            return "Limited High";
        case LimitStatus::LimitedLow:
            return "Limited Low";
        case LimitStatus::NonRecoverableFault:
            return "Non-recoverable Fault";
        case LimitStatus::Reserved_1:
        case LimitStatus::Reserved_2:
            return "Reserved";
        case LimitStatus::NotAvailable:
        default:
            return "Not Available";
    }
}

void on_machine_selected_speed(
    const std::shared_ptr<isobus::SpeedMessagesInterface::MachineSelectedSpeedData> data,
    bool)
{
    if (nullptr == data)
    {
        return;
    }

    receivedSpeedMmps = data->get_machine_speed();
    receivedDistanceMm = data->get_machine_distance();
    receivedDirection = static_cast<std::uint8_t>(data->get_machine_direction_of_travel());
    receivedSpeedSource = static_cast<std::uint8_t>(data->get_speed_source());
    receivedLimitStatus = static_cast<std::uint8_t>(data->get_limit_status());
    receivedExitReason = data->get_exit_reason_code();

    const auto sender = data->get_sender_control_function();
    if (nullptr != sender)
    {
        receivedSourceAddress = sender->get_address();
    }

    ++receivedMessages;
    lastMessageTimeMs = monotonic_milliseconds();
}

void draw_dashboard(std::uint8_t address, const std::string &canInterfaceName)
{
    const std::uint16_t speedMmps = receivedSpeedMmps.load();
    const double speedKmh = static_cast<double>(speedMmps) * 3.6 / 1000.0;
    const double calculatedFlowLitresPerMinute =
        speedKmh * BOOM_WIDTH_METRES * TARGET_RATE_LITRES_PER_HECTARE / 600.0;
    const double distanceMetres = receivedDistanceMm.load() / 1000.0;
    const std::uint64_t now = monotonic_milliseconds();
    const std::uint64_t last = lastMessageTimeMs.load();
    const bool connected = (last != 0) && ((now - last) < MESSAGE_TIMEOUT_MS);

    const auto direction = static_cast<isobus::SpeedMessagesInterface::MachineDirection>(
        receivedDirection.load());
    const auto speedSource =
        static_cast<isobus::SpeedMessagesInterface::MachineSelectedSpeedData::SpeedSource>(
            receivedSpeedSource.load());
    const auto limitStatus =
        static_cast<isobus::SpeedMessagesInterface::MachineSelectedSpeedData::LimitStatus>(
            receivedLimitStatus.load());

    const bool applying = connected &&
                          (direction == isobus::SpeedMessagesInterface::MachineDirection::Forward) &&
                          (speedKmh >= 0.5);
    const double commandedFlowLitresPerMinute =
        applying ? calculatedFlowLitresPerMinute : 0.0;

    std::cout << "\033[2J\033[H";
    std::cout << "============================================================\n";
    std::cout << "       PULVERIZADOR VIRTUAL - IMPLEMENTO ISOBUS\n";
    std::cout << "============================================================\n";
    std::cout << "Interface CAN           : " << canInterfaceName << "\n";
    std::cout << "Endereco do implemento : 0x" << std::hex << std::uppercase
              << static_cast<int>(address) << std::dec << "\n";
    std::cout << "NAME                    : IG=2, DeviceClass=6, Function=128 (Rate Control)\n";
    std::cout << "PGN recebido            : 0xF022 / 61474 - Machine Selected Speed\n";
    std::cout << "Conexao com a TECU      : " << (connected ? "ONLINE" : "AGUARDANDO...") << "\n";
    std::cout << "Endereco da TECU        : 0x" << std::hex << std::uppercase
              << static_cast<int>(receivedSourceAddress.load()) << std::dec << "\n\n";

    std::cout << std::fixed << std::setprecision(1);
    std::cout << "Velocidade do trator    : " << std::setw(7) << speedKmh << " km/h\n";
    std::cout << "Direcao                 : " << direction_to_text(direction) << "\n";
    std::cout << "Fonte da velocidade     : " << speed_source_to_text(speedSource) << "\n";
    std::cout << "Status de limitacao     : " << limit_status_to_text(limitStatus) << "\n";
    std::cout << "Codigo de saida         : "
              << static_cast<unsigned int>(receivedExitReason.load()) << "\n";
    std::cout << "Distancia percorrida    : " << std::setw(7) << distanceMetres << " m\n";
    std::cout << "Taxa configurada        : " << std::setw(7)
              << TARGET_RATE_LITRES_PER_HECTARE << " L/ha\n";
    std::cout << "Largura da barra        : " << std::setw(7) << BOOM_WIDTH_METRES << " m\n";
    std::cout << "Vazao comandada         : " << std::setw(7)
              << commandedFlowLitresPerMinute << " L/min\n";
    std::cout << "Mensagens recebidas     : " << receivedMessages.load() << "\n\n";

    std::cout << "Estado da aplicacao     : " << (applying ? "APLICANDO" : "PARADO") << "\n";
    std::cout << "Secoes da barra         : ";
    for (int section = 1; section <= SECTION_COUNT; ++section)
    {
        std::cout << (applying ? "[ON ]" : "[OFF]");
    }
    std::cout << "\n";
    std::cout << "                            1    2    3    4    5    6\n\n";

    if (!connected)
    {
        std::cout << "Aguardando a mensagem periodica da Tractor ECU.\n";
    }
    else if (direction == isobus::SpeedMessagesInterface::MachineDirection::Reverse)
    {
        std::cout << "Marcha a re: aplicacao local desativada por seguranca.\n";
    }
    else if (applying)
    {
        std::cout << "A ECU ajustou a vazao localmente para manter 150 L/ha.\n";
    }
    else
    {
        std::cout << "Sem movimento suficiente: valvulas locais fechadas.\n";
    }

    std::cout << "\nObservacao: a logica de secoes e vazao desta tela e uma simulacao\n";
    std::cout << "local; este exemplo transmite apenas o PGN padronizado de velocidade.\n";
    std::cout << "\nPressione Ctrl+C para encerrar.\n" << std::flush;
}
}

int main()
{
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    const std::string canInterfaceName = demo::get_can_interface_name();
    auto canDriver = std::make_shared<isobus::SocketCANInterface>(canInterfaceName);
    isobus::CANHardwareInterface::set_number_of_can_channels(1);
    isobus::CANHardwareInterface::assign_can_channel_frame_handler(0, canDriver);

    if ((!isobus::CANHardwareInterface::start()) || (!canDriver->get_is_valid()))
    {
        std::cerr << "Erro: nao foi possivel abrir a interface " << canInterfaceName << ".\n";
        return 1;
    }

    isobus::NAME sprayerName(0);
    sprayerName.set_arbitrary_address_capable(true);
    sprayerName.set_industry_group(static_cast<std::uint8_t>(
        isobus::NAME::IndustryGroup::AgriculturalAndForestryEquipment));
    sprayerName.set_device_class(static_cast<std::uint8_t>(
        isobus::NAME::DeviceClass::Sprayer));
    sprayerName.set_function_code(static_cast<std::uint8_t>(
        isobus::NAME::Function::RateControl));
    sprayerName.set_identity_number(2001);
    sprayerName.set_ecu_instance(0);
    sprayerName.set_function_instance(0);
    sprayerName.set_device_class_instance(0);
    sprayerName.set_manufacturer_code(1407);

    auto sprayerECU = isobus::CANNetworkManager::CANNetwork.create_internal_control_function(
        sprayerName,
        0,
        SPRAYER_PREFERRED_ADDRESS);

    if (!demo::wait_for_address_claim(sprayerECU, running, std::chrono::seconds(5)))
    {
        if (running)
        {
            std::cerr << "Erro: o pulverizador nao conseguiu reivindicar um endereco ISOBUS.\n";
        }
        isobus::CANHardwareInterface::stop();
        return running ? 2 : 130;
    }

    isobus::SpeedMessagesInterface speedReceiver(nullptr);
    speedReceiver.get_machine_selected_speed_data_event_publisher().add_listener(
        on_machine_selected_speed);
    speedReceiver.initialize();

    while (running)
    {
        speedReceiver.update();
        draw_dashboard(sprayerECU->get_address(), canInterfaceName);
        std::this_thread::sleep_for(std::chrono::milliseconds(200));
    }

    isobus::CANHardwareInterface::stop();
    std::cout << "\nPulverizador virtual encerrado.\n";
    return 0;
}
