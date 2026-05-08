# AgroDT Translator Configurator

## Overview

This repository provides the graphical configuration environment for the AgroDT ecosystem.

It focuses on the creation, management, validation, and export of protocol translator configurations used to integrate agricultural Digital Twins with standardized OPC UA infrastructures.

The system is implemented as a web-based Graphical User Interface (GUI) using Python and Django, providing an operational environment for configuring translators responsible for converting heterogeneous communication protocols into OPC UA-compatible representations.

The repository acts as the configuration and orchestration layer between:

- Digital Twin models (AAS-based structures)
- Communication protocols
- OPC UA translation services
- Translator runtime environments

Supported communication protocols currently include:

- MQTT
- Modbus
- MAVLink

---

# Objectives

The main objectives of this repository are:

- To provide a centralized graphical environment for translator configuration
- To simplify protocol-to-AAS mapping creation
- To support multiple agricultural asset types and communication protocols
- To enable reusable and versionable translator configurations
- To improve interoperability across AgroDT repositories
- To provide operational tooling for Digital Twin integration workflows
- To abstract low-level protocol complexity from end users

---

# Scope and Non-Goals

## In Scope

This repository covers the graphical configuration environment and the logical representation of translator mappings.

### Interface and Configuration Tooling

- Graphical user interface for translator configuration
- Hierarchical visualization of imported AAS structures
- Interactive AAS Tree navigation
- MQTT translator configuration modules
- Modbus translator configuration modules
- MAVLink translator configuration modules
- Mapping editors between protocol fields and AAS properties
- Validation and consistency checks
- Project save/load functionality
- Export of translator configuration artifacts
- Theme and interface customization
- Operational status and feedback visualization

### Translator Configuration Management

- Protocol parameter configuration
- Mapping persistence
- Translator selection and orchestration
- Configuration export generation
- Validation of required translator fields
- Support for `.json`, `.aasx`, and internal project formats

### Interface Documentation

- Usage instructions
- Configuration workflow documentation
- Translator configuration methodology
- Integration examples

---

## Out of Scope

This repository does not include:

- Runtime execution of translators
- OPC UA server runtime orchestration
- Cloud deployment infrastructure
- Analytics or dashboard systems
- Farm management systems
- AAS authoring or editing
- Real-time protocol brokers
- Production middleware orchestration

The repository is strictly focused on translator configuration and mapping generation.

---

# Conceptual Pipeline

```text
AAS Models
      ↓
AgroDT Translator Configurator
      ↓
Translator Configuration Files
      ↓
Protocol Translators
      ↓
OPC UA Infrastructure
Repository Philosophy

This repository is designed to be the operational control point for protocol translation configuration.

Key principles include:

Configuration as Code

Although the system uses a graphical interface, all generated outputs are declarative and versionable configuration artifacts.

Model Fidelity

Mappings are strictly tied to the imported AAS structure and its version.

User-Centric Design

Complex communication protocols are abstracted into an accessible engineering-oriented configuration interface.

Traceability

Projects, mappings, and exported configurations should remain reproducible and versionable.

Modularity

Protocol translators are designed as independent and extensible configuration modules.

Versioning Strategy
Translator configurations should inherit the version of the imported AAS model whenever applicable
Changes that modify export structures or mapping semantics must generate a new tool version
Legacy interface versions may remain available through dedicated branches
Mapping evolution should preserve compatibility whenever possible
Contribution Guidelines

Although the repository includes executable code and interface components, contributions should prioritize consistency, traceability, and modularity.

Branching Policy

Contributors should use short-lived feature branches.

Suggested naming convention:

<issue-number>-add-<translator>-feature

Example:

18-add-mqtt-mapping-validation
Commit Message Convention

All commits must follow the Conventional Commits specification.

Format:

<type>(<scope>): <description>

Recommended commit types:

feat: new translator features or interface modules
fix: corrections in parsing, mappings, or interface behavior
docs: documentation updates
style: visual/interface adjustments
refactor: internal structural improvements
chore: dependency or project maintenance

Examples:

feat(ui): add MQTT mapping editor
fix(parser): correct AAS JSON parsing
docs(help): update translator workflow instructions
style(theme): improve dark mode contrast
Pull Requests

Pull Requests are recommended for:

new protocol support
export format modifications
major interface redesigns
mapping engine changes
validation logic changes
performance improvements in AAS rendering

Squash merge is recommended when appropriate.

Methodology Documentation

This repository includes methodological documentation describing:

protocol-to-AAS mapping strategies
translator configuration workflows
data type compatibility rules
mapping validation principles
protocol abstraction methodologies
interoperability assumptions
alignment with AgroDT architectural principles

Documentation is maintained under the docs/ directory.

Project Structure
agrodt_ui/
├── manage.py
├── db.sqlite3
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
└── interface/
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── models.py
    ├── tests.py
    ├── views.py
    ├── urls.py
    │
    ├── templates/
    │   └── interface/
    │       └── home.html
    │
    └── static/
        └── interface/
            ├── css/
            │   └── style.css
            │
            └── js/
                └── main.js
Supported Features
AAS Import

Supported formats:

.json
.aasx
Translator Modules

Supported translators:

MQTT
Modbus
MAVLink
Mapping Engine

Supports:

protocol field binding
AAS property selection
mapping validation
translator-specific configuration
Export System

Supports export of:

.json
.yaml
.agrodt

configuration artifacts.

Technologies
Python
Django
HTML5
CSS3
JavaScript
SQLite
Running the Project
Create Virtual Environment
python3 -m venv venv
Activate Environment
source venv/bin/activate
Install Dependencies
pip install django
Run Migrations
python manage.py migrate
Start Development Server
python manage.py runserver

Open:

http://127.0.0.1:8000/
Network Access

To allow devices on the local network to access the interface:

python manage.py runserver 0.0.0.0:8000

Configure:

ALLOWED_HOSTS = ['*']

Retrieve local IP:

hostname -I

Access from another machine:

http://YOUR_IP:8000/
Future Improvements

Planned future developments include:

real .aasx parsing support
OPC UA live integration
runtime translator execution
YAML schema validation
SQLite persistence improvements
online AAS repository integration
multi-user support
advanced validation engines
plugin-based translator architecture
enhanced dark mode support
