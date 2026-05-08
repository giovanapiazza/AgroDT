# AgroDT Translator Configurator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Framework: Django](https://img.shields.io/badge/framework-Django-green.svg)](https://www.djangoproject.com/)

## Overview
This repository provides a web-based Graphical User Interface (GUI) developed in **Python with Django** to configure protocol translators for the **AgroDT** project.

The system's primary objective is to streamline the creation of configuration files for translators that convert data from protocols such as **MQTT, Modbus, and MAVLink** to **OPC UA**, using the **Asset Administration Shell (AAS)** model as a reference. This tool serves as the operational link between static model definitions and real-time data flows.

## Objectives
The main objectives of this repository are:

*   **Standardized Mapping:** Provide an intuitive tool for mapping field protocols to standardized AAS properties.
*   **Multi-Asset Support:** Support configuration creation for multiple agricultural assets (UAVs, crops, machinery).
*   **Traceability:** Ensure persistence and versioning of mapping projects performed by users.
*   **Documentation:** Document translation procedures and integration between data and communication layers.
*   **Ecosystem Integration:** Ensure interoperability with other repositories in the AgroDT ecosystem.

---

## Scope and Non-Goals

### In Scope
This repository covers the configuration interface, logical mapping, and the generation of integration artifacts.

*   **Interface and Tooling**
    *   Hierarchical visualization (tree view) of imported AAS structures.
    *   Specific mapping modules for MQTT, Modbus, and MAVLink protocols.
    *   Automatic generation of configuration files for reference translators.
    *   Validation scripts to ensure mapping adheres to the original AAS model.
*   **Interface Documentation**
    *   User guides for the graphical interface and internal API routes.

### Out of Scope
*   **Model Editing:** The software does not modify the AAS structure; it acts solely as a model consumer.
*   **Runtime Execution:** This repository does not execute the actual data translation; it only generates its configuration.
*   **Cloud Orchestration:** Large-scale runtime deployment or orchestration of translation servers.

---

## Conceptual Pipeline
The repository is integrated into the AgroDT integration pipeline as follows:

```mermaid
graph TD
    A[AAS Models] --> B[AgroDT Translator Configurator]
    B --> C[Configuration Files .json/.yaml]
    C --> D[Translators / OPC UA Server]

# AgroDT Translator Configurator

## Repository Philosophy
This repository is designed to be the operational control point for the data pipeline.

*   **Configuration as Code:** While using a GUI, the final output consists of declarative and versionable configuration files.
*   **Model Fidelity:** Mapping is strictly tied to the version of the imported AAS.
*   **User-Centric Design:** Abstraction of complex protocols for users focused on agronomy or data management.

## Versioning Strategy
*   Generated configurations must inherit the version of the reference AAS model.
*   Changes in interface logic that alter the export format must trigger a new tool version (e.g., **v1.0**, **v1.1**).
*   Previous interface versions should be maintained in specific branches for compatibility with legacy models.

---

## Contribution Guidelines

### Branching Policy
*   Contributors should work on short-lived feature branches.
*   **Suggested naming convention:** `<issue-number>-add-<protocol>-support`
*   **Example:** `15-add-mavlink-config`

### Commit Message Convention
All commits must follow the **Conventional Commits** format:

*   `feat(ui)`: adding new protocol support or visual components.
*   `fix(parser)`: fixes in AAS file reading.
*   `docs(manual)`: updates to the interface user manual.
*   `chore(deps)`: updates to Django dependencies or JS libraries.

### Pull Requests
Recommended for changes involving new communication protocols, modifications to file export logic, or performance improvements in **AAS** tree rendering.

---

## Methodology Documentation
The methodology applied for protocol mapping and translation logic is documented under the `docs/` directory, including:

*   Data type conversion strategies (e.g., **MAVLink float** to **OPC UA Real**).
*   Mapping integrity validation rules.
*   Alignment with **AgroDT** architectural principles.

---

## Project Structure

```text
agrodt_ui/
├── manage.py              # Django CLI
├── config/                # Project settings and routing
└── interface/             # Core application logic
    ├── models.py          # Database (SQLite) for project persistence
    ├── views.py           # AAS parsing and export logic
    ├── templates/         # UI Components (home.html)
    └── static/            # CSS and JS for dynamic tree visualization
