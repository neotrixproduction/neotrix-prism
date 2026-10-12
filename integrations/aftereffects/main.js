/* Neotrix CEP UI; preserves upstream's ExtendScript transport, on an isolated port. */
const csInterface = new CSInterface();
const net = require("net");
const http = require("http");
const fs = require("fs");
const path = require("path");
const status = document.getElementById("status");
const server = net.createServer(function(socket) {
    socket.on("data", function(data) {
        if (String(data) === "pid") { socket.write(String(process.pid)); return; }
        csInterface.evalScript(String(data), function(result) {
            socket.write(result === "" ? "null" : result);
        });
    });
});
server.on("error", function(error) { status.textContent = "Connection unavailable: " + error.message; });
server.listen(19888, "127.0.0.1");
function send(command) {
    const body = JSON.stringify({app:"aftereffects",command:command});
    const request = http.request({hostname:"127.0.0.1",port:16400,path:"/prism",method:"POST",
        headers:{"Content-Type":"application/json","Content-Length":Buffer.byteLength(body)}}, function(response) {
        response.resume();
        status.textContent = response.statusCode === 202 ? "Connected · action opened in Neotrix Prism" : "Could not run this action.";
    });
    request.on("error", function() { status.textContent = "Start Neotrix Prism on your desktop, then try again."; });
    request.end(body);
}
document.querySelectorAll("[data-command]").forEach(function(button) {
    button.addEventListener("click", function() { send(button.getAttribute("data-command")); });
});
try {
    const config = JSON.parse(fs.readFileSync(path.join(__dirname,"installation.json"),"utf8"));
    const health = http.get("http://127.0.0.1:16400/health", function(response) {
        response.resume();
        status.textContent = "Workspace ready · save and explore from here.";
    });
    health.on("error", function() {
        const child = require("child_process").spawn(path.join(config.root,"runtime","pythonw.exe"),
            [path.join(config.root,"launch.py")], {windowsHide:true,detached:true,stdio:"ignore"});
        child.unref();
        status.textContent = "Workspace starting…";
    });
} catch(error) { status.textContent = "Start Neotrix Prism on your desktop to connect."; }
