/* PC Monitor Launcher — runs pythonw.exe run.py with custom icon */
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;

class Program {
    [DllImport("kernel32.dll")]
    static extern IntPtr GetConsoleWindow();
    [DllImport("user32.dll")]
    static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    static void Main() {
        // Hide console
        ShowWindow(GetConsoleWindow(), 0);

        string dir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string pythonw = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "Programs", "Python", "Python311", "pythonw.exe");
        if (!File.Exists(pythonw)) pythonw = "pythonw.exe";

        Process.Start(new ProcessStartInfo {
            FileName = pythonw,
            Arguments = "\"" + Path.Combine(dir, "run.py") + "\"",
            WorkingDirectory = dir,
            WindowStyle = ProcessWindowStyle.Hidden,
            UseShellExecute = true,
        });
    }
}
