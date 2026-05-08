console.log("AgroDT interface loaded");

const fileButton = document.getElementById("fileButton");
const fileDropdown = document.getElementById("fileDropdown");

const aasInput = document.getElementById("aasInput");
const projectInput = document.getElementById("projectInput");

const aasEmpty = document.getElementById("aasEmpty");
const aasLoadedArea = document.getElementById("aasLoadedArea");
const aasTree = document.getElementById("aasTree");
const aasFileName = document.getElementById("aasFileName");
const aasSearchInput = document.getElementById("aasSearchInput");

const initialMessage = document.getElementById("initialMessage");
const addTranslatorMessage = document.getElementById("addTranslatorMessage");
const translatorArea = document.getElementById("translatorArea");

const translatorButton = document.getElementById("translatorButton");
const exportButton = document.getElementById("exportButton");
const translatorModal = document.getElementById("translatorModal");
const exportModal = document.getElementById("exportModal");

const tabs = document.getElementById("tabs");

const mqttPanel = document.getElementById("mqttPanel");
const mavlinkPanel = document.getElementById("mavlinkPanel");
const modbusPanel = document.getElementById("modbusPanel");

const mqttAasProperty = document.getElementById("mqttAasProperty");
const mavAasProperty = document.getElementById("mavAasProperty");
const modbusAasProperty = document.getElementById("modbusAasProperty");

const mqttTable = document.getElementById("mqttTable");
const mavlinkTable = document.getElementById("mavlinkTable");
const modbusTable = document.getElementById("modbusTable");

let loadedAASData = null;
let activeTranslator = "MQTT";
let selectedTranslators = ["Modbus", "MQTT", "MAVLink"];
let selectedAASProperty = "";

let mqttMappings = [
    {
        topic: "sensors/temperature",
        fieldName: "value",
        dataType: "Float",
        aasProperty: "Asset > Submodel A > Property 1",
        status: "active"
    },
    {
        topic: "sensors/humidity",
        fieldName: "value",
        dataType: "Float",
        aasProperty: "Asset > Submodel A > Property 2",
        status: "active"
    },
    {
        topic: "actuators/valve",
        fieldName: "state",
        dataType: "Boolean",
        aasProperty: "Asset > Submodel B > Property 3",
        status: "pending"
    }
];

let mavlinkMappings = [
    {
        message: "GLOBAL_POSITION_INT",
        field: "lat",
        dataType: "Int32",
        aasProperty: "Asset > Submodel A > Property 1",
        status: "active"
    },
    {
        message: "GLOBAL_POSITION_INT",
        field: "lon",
        dataType: "Int32",
        aasProperty: "Asset > Submodel A > Property 2",
        status: "active"
    },
    {
        message: "ATTITUDE",
        field: "roll",
        dataType: "Float",
        aasProperty: "Asset > Submodel B > Property 3",
        status: "pending"
    }
];

let modbusMappings = [
    {
        registerType: "Holding Register",
        address: "40001",
        dataType: "Float",
        aasProperty: "Asset > Submodel A > Property 1",
        status: "active"
    },
    {
        registerType: "Input Register",
        address: "30002",
        dataType: "Int16",
        aasProperty: "Asset > Submodel A > Property 2",
        status: "active"
    },
    {
        registerType: "Coil",
        address: "00001",
        dataType: "Boolean",
        aasProperty: "Asset > Submodel B > Property 3",
        status: "pending"
    }
];

fileButton.addEventListener("click", function(event) {
    event.stopPropagation();
    fileDropdown.classList.toggle("hidden");
});

document.addEventListener("click", function() {
    fileDropdown.classList.add("hidden");
});

function setStatus(type, message) {
    const footer = document.querySelector(".statusbar");

    footer.innerHTML = `
        <strong>${type}:</strong>
        <span>${message}</span>
    `;
}

function importAAS() {
    aasInput.click();
}

aasInput.addEventListener("change", function(event) {
    const file = event.target.files[0];

    if (!file) return;

    const fileName = file.name.toLowerCase();

    if (!fileName.endsWith(".json") && !fileName.endsWith(".aasx")) {
        setStatus("ERROR", "Invalid AAS file. Use .json or .aasx");
        return;
    }

    if (fileName.endsWith(".aasx")) {
        aasFileName.textContent = "Industrial Asset Model";
        showMockAASTree();
        showAddTranslatorState();
        setStatus("SUCCESS", "AAS loaded successfully");
        return;
    }

    const reader = new FileReader();

    reader.onload = function(e) {
        try {
            loadedAASData = JSON.parse(e.target.result);
            aasFileName.textContent = "Industrial Asset Model";
            renderAASTree(loadedAASData);
            showAddTranslatorState();
            setStatus("SUCCESS", "AAS loaded successfully");
        } catch (error) {
            setStatus("ERROR", "Failed to read JSON file");
        }
    };

    reader.readAsText(file);
});

function showAddTranslatorState() {
    initialMessage.classList.add("hidden");
    translatorArea.classList.add("hidden");
    addTranslatorMessage.classList.remove("hidden");

    aasEmpty.classList.add("hidden");
    aasLoadedArea.classList.remove("hidden");
}

function showTranslatorState() {
    initialMessage.classList.add("hidden");
    addTranslatorMessage.classList.add("hidden");
    translatorArea.classList.remove("hidden");

    renderTabs();
    showPanel(activeTranslator);
    renderAllTables();
}

function showMockAASTree() {
    const mockAAS = {
        Asset: {
            "Submodel A": {
                "Property 1": "Available",
                "Property 2": "Available"
            },
            "Submodel B": {
                "Property 3": "Available"
            }
        }
    };

    loadedAASData = mockAAS;
    renderAASTree(mockAAS);

    aasEmpty.classList.add("hidden");
    aasLoadedArea.classList.remove("hidden");
}

function renderAASTree(data) {
    aasTree.innerHTML = "";
    const root = createTreeNode("Asset", data, "Asset");
    aasTree.appendChild(root);
}

function createTreeNode(key, value, path) {
    const wrapper = document.createElement("div");

    const row = document.createElement("div");
    row.className = "tree-row";

    const isObject = value !== null && typeof value === "object";

    const toggle = document.createElement("span");
    toggle.className = "tree-toggle";
    toggle.textContent = isObject ? "⌄" : "•";

    const keySpan = document.createElement("span");
    keySpan.textContent = key;

    row.appendChild(toggle);
    row.appendChild(keySpan);

    wrapper.appendChild(row);

    let childrenContainer = null;

    if (isObject) {
        childrenContainer = document.createElement("div");
        childrenContainer.className = "tree-children";

        Object.keys(value).forEach(childKey => {
            childrenContainer.appendChild(
                createTreeNode(childKey, value[childKey], `${path} > ${childKey}`)
            );
        });

        wrapper.appendChild(childrenContainer);
    }

    row.addEventListener("click", function(event) {
        event.stopPropagation();

        document.querySelectorAll(".tree-row").forEach(item => {
            item.classList.remove("selected-node");
        });

        row.classList.add("selected-node");

        selectedAASProperty = path;
        mqttAasProperty.value = path;
        mavAasProperty.value = path;
        modbusAasProperty.value = path;

        if (childrenContainer) {
            childrenContainer.classList.toggle("hidden");
            toggle.textContent = childrenContainer.classList.contains("hidden") ? "›" : "⌄";
        }

        setStatus("SUCCESS", path + " selected");
    });

    return wrapper;
}

aasSearchInput.addEventListener("input", function() {
    const search = aasSearchInput.value.toLowerCase();

    document.querySelectorAll(".tree-row").forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(search)
            ? "flex"
            : "none";
    });
});

translatorButton.addEventListener("click", function() {
    translatorModal.classList.remove("hidden");
});

exportButton.addEventListener("click", function() {
    exportModal.classList.remove("hidden");
});

function closeTranslatorModal() {
    translatorModal.classList.add("hidden");
}

function closeExportModal() {
    exportModal.classList.add("hidden");
}

function applyTranslators() {
    selectedTranslators = Array.from(
        document.querySelectorAll(".translator-check:checked")
    ).map(item => item.value);

    if (selectedTranslators.length === 0) {
        setStatus("WARNING", "Select at least one translator");
        return;
    }

    activeTranslator = selectedTranslators.includes("MQTT")
        ? "MQTT"
        : selectedTranslators[0];

    closeTranslatorModal();
    showTranslatorState();

    setStatus("SUCCESS", "Translators selected");
}

function exportConfiguration() {
    const data = {
        mqtt: mqttMappings,
        mavlink: mavlinkMappings,
        modbus: modbusMappings
    };

    downloadJSON(data, "translator_config.json");

    closeExportModal();
    setStatus("SUCCESS", "Configuration exported");
}

translatorModal.addEventListener("click", function(event) {
    if (event.target === translatorModal) closeTranslatorModal();
});

exportModal.addEventListener("click", function(event) {
    if (event.target === exportModal) closeExportModal();
});

function renderTabs() {
    tabs.innerHTML = "";

    selectedTranslators.forEach(translator => {
        const button = document.createElement("button");
        button.className = "tab-button";
        button.textContent = translator;

        if (translator === activeTranslator) {
            button.classList.add("active");
        }

        button.addEventListener("click", function() {
            activeTranslator = translator;
            renderTabs();
            showPanel(translator);
        });

        tabs.appendChild(button);
    });
}

function showPanel(translator) {
    mqttPanel.classList.add("hidden");
    mavlinkPanel.classList.add("hidden");
    modbusPanel.classList.add("hidden");

    if (translator === "MQTT") mqttPanel.classList.remove("hidden");
    if (translator === "MAVLink") mavlinkPanel.classList.remove("hidden");
    if (translator === "Modbus") modbusPanel.classList.remove("hidden");
}

function renderAllTables() {
    renderMQTTTable();
    renderMAVLinkTable();
    renderModbusTable();
}

function renderMQTTTable() {
    mqttTable.innerHTML = "";

    mqttMappings.forEach((item, index) => {
        mqttTable.innerHTML += `
            <tr>
                <td>${item.topic}</td>
                <td>${item.fieldName}</td>
                <td>${item.dataType}</td>
                <td>${item.aasProperty}</td>
                <td><span class="badge ${item.status}">${item.status}</span></td>
                <td><button class="secondary" onclick="deleteMQTTMapping(${index})">🗑</button></td>
            </tr>
        `;
    });
}

function renderMAVLinkTable() {
    mavlinkTable.innerHTML = "";

    mavlinkMappings.forEach((item, index) => {
        mavlinkTable.innerHTML += `
            <tr>
                <td>${item.message}</td>
                <td>${item.field}</td>
                <td>${item.dataType}</td>
                <td>${item.aasProperty}</td>
                <td><span class="badge ${item.status}">${item.status}</span></td>
                <td><button class="secondary" onclick="deleteMAVLinkMapping(${index})">🗑</button></td>
            </tr>
        `;
    });
}

function renderModbusTable() {
    modbusTable.innerHTML = "";

    modbusMappings.forEach((item, index) => {
        modbusTable.innerHTML += `
            <tr>
                <td>${item.registerType}</td>
                <td>${item.address}</td>
                <td>${item.dataType}</td>
                <td>${item.aasProperty}</td>
                <td><span class="badge ${item.status}">${item.status}</span></td>
                <td><button class="secondary" onclick="deleteModbusMapping(${index})">🗑</button></td>
            </tr>
        `;
    });
}

function addMQTTMapping() {
    mqttMappings.push({
        topic: document.getElementById("mqttTopic").value || "new/topic",
        fieldName: document.getElementById("mqttField").value || "value",
        dataType: document.getElementById("mqttDataType").value,
        aasProperty: selectedAASProperty || "No property selected",
        status: "pending"
    });

    renderMQTTTable();
    setStatus("SUCCESS", "MQTT mapping added");
}

function addMAVLinkMapping() {
    mavlinkMappings.push({
        message: document.getElementById("mavMessage").value,
        field: document.getElementById("mavField").value || "field",
        dataType: document.getElementById("mavDataType").value,
        aasProperty: selectedAASProperty || "No property selected",
        status: "pending"
    });

    renderMAVLinkTable();
    setStatus("SUCCESS", "MAVLink mapping added");
}

function addModbusMapping() {
    modbusMappings.push({
        registerType: document.getElementById("modbusRegisterType").value,
        address: document.getElementById("modbusAddress").value || "40001",
        dataType: document.getElementById("modbusDataType").value,
        aasProperty: selectedAASProperty || "No property selected",
        status: "pending"
    });

    renderModbusTable();
    setStatus("SUCCESS", "Modbus mapping added");
}

function deleteMQTTMapping(index) {
    mqttMappings.splice(index, 1);
    renderMQTTTable();
}

function deleteMAVLinkMapping(index) {
    mavlinkMappings.splice(index, 1);
    renderMAVLinkTable();
}

function deleteModbusMapping(index) {
    modbusMappings.splice(index, 1);
    renderModbusTable();
}

function openProject() {
    projectInput.click();
}

projectInput.addEventListener("change", function(event) {
    const file = event.target.files[0];
    if (!file) return;

    showMockAASTree();
    showTranslatorState();
    setStatus("SUCCESS", "Project opened: " + file.name);
});

function saveProject() {
    const project = {
        software: "AgroDT Translator Configurator",
        aas_loaded: aasFileName.textContent || null,
        mqtt: mqttMappings,
        mavlink: mavlinkMappings,
        modbus: modbusMappings
    };

    downloadJSON(project, "project.agrodt");
    setStatus("SUCCESS", "Project saved");
}

function saveProjectAs() {
    const name = prompt("Project name:", "agrodt_project");
    if (!name) return;

    saveProject();
    setStatus("SUCCESS", "Project saved as " + name + ".agrodt");
}

function closeProject() {
    if (!confirm("Close current project?")) return;

    aasTree.innerHTML = "";
    aasFileName.textContent = "";
    selectedAASProperty = "";

    aasLoadedArea.classList.add("hidden");
    aasEmpty.classList.remove("hidden");

    translatorArea.classList.add("hidden");
    addTranslatorMessage.classList.add("hidden");
    initialMessage.classList.remove("hidden");

    setStatus("STATUS", "No AAS loaded");
}

function exitApp() {
    alert("In the desktop version this would close the application.");
}

function downloadJSON(data, filename) {
    const blob = new Blob(
        [JSON.stringify(data, null, 4)],
        { type: "application/json" }
    );

    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");

    a.href = url;
    a.download = filename;

    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);

    URL.revokeObjectURL(url);
}
const settingsButton = document.getElementById("settingsButton");
const settingsModal = document.getElementById("settingsModal");

let globalSettings = {
    projectMetadata: {},
    aasProvider: {},
    protocolDefaults: {},
    interfaceUX: {},
    exportSettings: {}
};

settingsButton.addEventListener("click", function() {
    settingsModal.classList.remove("hidden");
});

function closeSettingsModal() {
    settingsModal.classList.add("hidden");
}

settingsModal.addEventListener("click", function(event) {
    if (event.target === settingsModal) {
        closeSettingsModal();
    }
});

function saveSettings() {
    globalSettings = {
        projectMetadata: {
            projectName: document.getElementById("projectName").value,
            version: document.getElementById("projectVersion").value,
            author: document.getElementById("projectAuthor").value,
            description: document.getElementById("projectDescription").value
        },

        aasProvider: {
            serverUrl: document.getElementById("aasServerUrl").value,
            authToken: document.getElementById("aasAuthToken").value,
            pollingInterval: document.getElementById("aasPollingInterval").value
        },

        protocolDefaults: {
            defaultSamplingRate: document.getElementById("defaultSamplingRate").value,
            autoBindStrategy: document.getElementById("autoBindStrategy").value,
            endianness: document.getElementById("endianness").value
        },

        interfaceUX: {
            treeDepth: document.getElementById("treeDepth").value,
            validationRules: document.getElementById("validationRules").value,
            theme: document.getElementById("themeMode").value
        },

        exportSettings: {
            yamlFormatting: document.getElementById("yamlFormatting").value,
            includeComments: document.getElementById("includeComments").value,
            outputDirectory: document.getElementById("outputDirectory").value
        }
    };

    applyTheme(globalSettings.interfaceUX.theme);

    closeSettingsModal();

    setStatus("SUCCESS", "Settings saved");
}

function applyTheme(theme) {
    if (theme === "dark") {
        document.body.classList.add("dark-theme");
    } else {
        document.body.classList.remove("dark-theme");
    }
}
const helpButton = document.getElementById("helpButton");
const helpModal = document.getElementById("helpModal");

helpButton.addEventListener("click", function () {
    helpModal.classList.remove("hidden");
});

function closeHelpModal() {
    helpModal.classList.add("hidden");
}

helpModal.addEventListener("click", function(event) {
    if (event.target === helpModal) {
        closeHelpModal();
    }
});