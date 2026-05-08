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
```


# Repository Philosophy

This repository is designed to be the operational control point for protocol translation configuration.

Key principles include:

## Configuration as Code

Although the system uses a graphical interface, all generated outputs are declarative and versionable configuration artifacts.

## Model Fidelity

Mappings are strictly tied to the imported Asset Administration Shell (AAS) structure and its corresponding version.

## User-Centric Design

Complex communication protocols are abstracted into an accessible engineering-oriented configuration interface.

## Traceability

Projects, mappings, and exported configurations should remain reproducible and versionable.

## Modularity

Protocol translators are designed as independent and extensible configuration modules.

---

# Versioning Strategy

- Translator configurations should inherit the version of the imported AAS model whenever applicable.
- Changes that modify export structures or mapping semantics must generate a new tool version.
- Legacy interface versions may remain available through dedicated branches.
- Mapping evolution should preserve compatibility whenever possible.

---

# Contribution Guidelines

Although the repository includes executable code and interface components, contributions should prioritize consistency, traceability, and modularity.

## Branching Policy

Contributors should use short-lived feature branches.

Suggested naming convention:

```text
<issue-number>-add-<translator>-feature

# Naming Convention

Branches related to new protocol integrations should follow the naming pattern below:

## Pattern

```text
<issue-number>-add-<protocol>-support
