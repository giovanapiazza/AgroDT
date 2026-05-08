# AgroDT Translator Configurator

## Overview

This repository provides a web-based Graphical User Interface (GUI) developed in Python with Django to configure protocol translators for the AgroDT project.

The system's primary objective is to streamline the creation of configuration files for translators that convert data from protocols such as MQTT, Modbus, and MAVLink to OPC UA, using the Asset Administration Shell (AAS) model as a reference.

This tool serves as the operational link between static model definitions and real-time data flows.

---

# Objectives

The main objectives of this repository are:

- Standardized Mapping  
  Provide an intuitive tool for mapping field protocols to standardized AAS properties.

- Multi-Asset Support  
  Support configuration creation for multiple agricultural assets (UAVs, crops, machinery).

- Traceability  
  Ensure persistence and versioning of mapping projects performed by users.

- Documentation  
  Document translation procedures and integration between data and communication layers.

- Ecosystem Integration  
  Ensure interoperability with other repositories in the AgroDT ecosystem.

---

# Scope and Non-Goals

## In Scope

This repository covers the configuration interface, logical mapping, and the generation of integration artifacts.

### Interface and Tooling

- Hierarchical visualization (tree view) of imported AAS structures.
- Specific mapping modules for MQTT, Modbus, and MAVLink protocols.
- Automatic generation of configuration files for reference translators.
- Validation scripts to ensure mapping adheres to the original AAS model.

### Interface Documentation

- User guides for the graphical interface and internal API routes.

---

## Out of Scope

### Model Editing

The software does not modify the AAS structure; it acts solely as a model consumer.

### Runtime Execution

This repository does not execute the actual data translation; it only generates its configuration.

### Cloud Orchestration

Large-scale runtime deployment or orchestration of translation servers.

---

# Conceptual Pipeline

```mermaid
graph TD
    A[AAS Models] --> B[AgroDT Translator Configurator]
    B --> C[Configuration Files .json/.yaml]
    C --> D[Translators / OPC UA Server]
