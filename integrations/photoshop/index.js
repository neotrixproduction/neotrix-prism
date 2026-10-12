const {entrypoints} = require("uxp");
async function send(command) {
    const status = document.getElementById("status");
    try {
        const response = await fetch("http://localhost:16400/prism", {
            method:"POST", headers:{"Content-Type":"application/json"},
            body:JSON.stringify({app:"photoshop", command:command})
        });
        status.textContent = response.ok ? "Connected · action opened in Neotrix Prism" : "The action could not be opened.";
    } catch(error) { status.textContent = "Start Neotrix Prism on your desktop, then try again."; }
}
entrypoints.setup({panels:{neotrixPanel:{
    show() {
        [["saveVersionBtn","saveVersion"],["projectBrowserBtn","projectBrowser"],
         ["exportBtn","export"],["settingsBtn","settings"]].forEach(function(pair) {
            const item = document.getElementById(pair[0]);
            if(item) item.onclick = function(){ send(pair[1]); };
        });
        send("connectPhotoshop");
    }
}}});
