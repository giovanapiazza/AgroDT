console.log("AgroDT UI Loaded");

// ======================================
// FILE MENU
// ======================================

function toggleFileMenu() {

    document
        .getElementById("fileMenu")
        .classList.toggle("hidden");
}

// ======================================
// STATUS BAR
// ======================================

function updateStatus(type, message) {

    const label =
        document.querySelector(".status-label");

    const text =
        label.nextElementSibling;

    label.innerText = type + ":";

    text.innerText = message;
}

// ======================================
// IMPORT AAS
// ======================================

function importAAS() {

    document
        .getElementById("aasFileInput")
        .click();
}

document
.getElementById("aasFileInput")
.addEventListener("change", function(event){

    const file = event.target.files[0];

    if(!file) return;

    updateStatus(
        "Success",
        "AAS loaded successfully: " + file.name
    );

    console.log("AAS imported:", file.name);
});

// ======================================
// OPEN PROJECT
// ======================================

function openProject() {

    document
        .getElementById("projectFileInput")
        .click();
}

document
.getElementById("projectFileInput")
.addEventListener("change", function(event){

    const file = event.target.files[0];

    if(!file) return;

    updateStatus(
        "Success",
        "Project opened: " + file.name
    );

    console.log("Project loaded:", file.name);
});

// ======================================
// SAVE PROJECT
// ======================================

function saveProject() {

    const projectData = {

        translators: [
            "MQTT",
            "Modbus"
        ],

        mqtt: {

            broker: "mqtt.example.com",
            port: 1883
        }
    };

    const blob = new Blob(
        [JSON.stringify(projectData, null, 2)],
        {type:"application/json"}
    );

    const a = document.createElement("a");

    a.href = URL.createObjectURL(blob);

    a.download = "project.agrodt";

    a.click();

    updateStatus(
        "Success",
        "Project saved successfully"
    );
}

// ======================================
// SAVE PROJECT AS
// ======================================

function saveProjectAs() {

    const filename =
        prompt("Enter project name:");

    if(!filename) return;

    const projectData = {

        translators:["MQTT"]
    };

    const blob = new Blob(
        [JSON.stringify(projectData, null, 2)],
        {type:"application/json"}
    );

    const a = document.createElement("a");

    a.href = URL.createObjectURL(blob);

    a.download = filename + ".agrodt";

    a.click();

    updateStatus(
        "Success",
        "Project saved as " + filename
    );
}

// ======================================
// CLOSE PROJECT
// ======================================

function closeProject() {

    if(!confirm("Close current project?"))
        return;

    updateStatus(
        "Status",
        "Project closed"
    );

    console.log("Project closed");
}

// ======================================
// EXIT
// ======================================

function exitApplication() {

    const confirmExit =
        confirm("Exit AgroDT Translator Configurator?");

    if(confirmExit){

        window.close();

        updateStatus(
            "Status",
            "Application closed"
        );
    }
}

// ======================================
// TRANSLATOR MODAL
// ======================================

function openTranslatorModal() {

    document
        .getElementById("translatorModal")
        .classList.remove("hidden");
}

function closeTranslatorModal() {

    document
        .getElementById("translatorModal")
        .classList.add("hidden");
}

// ======================================
// EXPORT MODAL
// ======================================

function openExportModal() {

    document
        .getElementById("exportModal")
        .classList.remove("hidden");
}

function closeExportModal() {

    document
        .getElementById("exportModal")
        .classList.add("hidden");
}

// ======================================
// CLOSE MODALS CLICKING OUTSIDE
// ======================================


window.onclick = function(event){

    const translatorModal =
        document.getElementById("translatorModal");

    const exportModal =
        document.getElementById("exportModal");

    if(event.target === translatorModal){

        closeTranslatorModal();
    }

    if(event.target === exportModal){

        closeExportModal();
    }
}