/* PC Monitor Launcher — runs PC Monitor.bat with custom icon */
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;

class Program {
    static void Main() {
        string dir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string bat = Path.Combine(dir, "PC Monitor.bat");

        Process.Start(new ProcessStartInfo {
            FileName = bat,
            WorkingDirectory = dir,
            WindowStyle = ProcessWindowStyle.Hidden,
            UseShellExecute = true,
        });
    }
}
