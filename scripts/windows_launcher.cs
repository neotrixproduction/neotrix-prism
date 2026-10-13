using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
[assembly: AssemblyTitle("Neotrix Prism")]
[assembly: AssemblyDescription("Neotrix creative project workspace")]
[assembly: AssemblyCompany("Neotrix")]
[assembly: AssemblyProduct("Neotrix Prism")]
[assembly: AssemblyVersion("0.6.0.0")]
internal static class Launcher {
    [STAThread] static int Main(string[] args) {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        bool check = args.Length == 1 && args[0] == "--self-test";
        string python = Path.Combine(root, "runtime", check ? "python.exe" : "pythonw.exe");
        string script = Path.Combine(root, check ? "scripts\\functional_runtime_smoke.py" : "launch.py");
        try {
            if (!File.Exists(python) || !File.Exists(script))
                throw new FileNotFoundException("Extract the whole ZIP first. Keep runtime, assets and the other folders beside Neotrix Prism.exe.");
            ProcessStartInfo info = new ProcessStartInfo(python, "\"" + script + "\"");
            info.WorkingDirectory = root;
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.EnvironmentVariables["NEOTRIX_LAUNCHER_PID"] = Process.GetCurrentProcess().Id.ToString();
            info.RedirectStandardOutput = check;
            info.RedirectStandardError = check;
            using (Process process = Process.Start(info)) {
                if (check) {
                    string output = process.StandardOutput.ReadToEnd();
                    string errors = process.StandardError.ReadToEnd();
                    process.WaitForExit();
                    File.WriteAllText(Path.Combine(root, "launcher-self-test.log"), output + errors);
                } else { process.WaitForExit(); }
                return process.ExitCode;
            }
        } catch (Exception ex) {
            if (!check) MessageBox.Show(ex.Message, "Neotrix Prism", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
