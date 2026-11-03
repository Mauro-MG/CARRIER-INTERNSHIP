using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading;

namespace WcfEmersonEXELoopbackHost
{
    internal static class Program
    {
        private static object service;
        private static MethodInfo selectDrive;

        public static int Main(string[] args)
        {
            string hostDirectory = AppDomain.CurrentDomain.BaseDirectory;
            string configDirectory = args.Length > 0 ? args[0] : hostDirectory;
            Uri address = new Uri(args.Length > 1 ? args[1] : "http://127.0.0.1:8020/");

            if (!address.IsLoopback || address.Scheme != Uri.UriSchemeHttp)
            {
                Console.Error.WriteLine("Only a loopback HTTP address is allowed.");
                return 2;
            }

            string originalExe = Path.Combine(hostDirectory, "WcfEmersonEXE.original.exe");
            if (!File.Exists(originalExe))
                originalExe = Path.Combine(hostDirectory, "WcfEmersonEXE.exe");

            Assembly assembly = Assembly.LoadFrom(originalExe);
            Type serviceType = assembly.GetType("WcfEmersonEXE.Service1", true);
            FieldInfo configField = serviceType.GetField(
                "configDirectory", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
            configField.SetValue(null, configDirectory);
            service = Activator.CreateInstance(serviceType);
            selectDrive = serviceType.GetMethod("selectDrive", BindingFlags.Instance | BindingFlags.Public);

            IPAddress ip = address.Host.Equals("localhost", StringComparison.OrdinalIgnoreCase)
                ? IPAddress.Loopback
                : IPAddress.Parse(address.Host);
            TcpListener listener = new TcpListener(ip, address.Port);
            listener.Start();
            Console.WriteLine("WcfEmersonEXE is listening at " + address);
            Console.WriteLine("Press Ctrl+C to stop.");

            while (true)
            {
                TcpClient client = listener.AcceptTcpClient();
                ThreadPool.QueueUserWorkItem(delegate { HandleClient(client); });
            }
        }

        private static void HandleClient(TcpClient client)
        {
            using (client)
            using (NetworkStream network = client.GetStream())
            {
                try
                {
                    string requestLine = ReadAsciiLine(network);
                    if (String.IsNullOrEmpty(requestLine)) return;

                    string[] requestParts = requestLine.Split(' ');
                    Dictionary<string, string> headers = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
                    string line;
                    while (!String.IsNullOrEmpty(line = ReadAsciiLine(network)))
                    {
                        int colon = line.IndexOf(':');
                        if (colon > 0) headers[line.Substring(0, colon).Trim()] = line.Substring(colon + 1).Trim();
                    }

                    if (headers.ContainsKey("Expect") &&
                        headers["Expect"].Equals("100-continue", StringComparison.OrdinalIgnoreCase))
                        WriteAscii(network, "HTTP/1.1 100 Continue\r\n\r\n");

                    if (requestParts.Length < 2 || requestParts[0] != "POST" ||
                        !requestParts[1].TrimEnd('/').EndsWith("/SelectDrive", StringComparison.OrdinalIgnoreCase))
                    {
                        WriteResponse(network, 404, "Not Found", Encoding.UTF8.GetBytes("Not Found"));
                        return;
                    }

                    int contentLength;
                    if (!headers.ContainsKey("Content-Length") ||
                        !Int32.TryParse(headers["Content-Length"], out contentLength) || contentLength < 0)
                    {
                        WriteResponse(network, 411, "Length Required", Encoding.UTF8.GetBytes("Content-Length required"));
                        return;
                    }

                    byte[] requestBody = ReadExactly(network, contentLength);
                    Stream result = (Stream)selectDrive.Invoke(service, new object[] { new MemoryStream(requestBody) });
                    byte[] responseBody;
                    using (result)
                    using (MemoryStream output = new MemoryStream())
                    {
                        result.CopyTo(output);
                        responseBody = output.ToArray();
                    }
                    WriteResponse(network, 200, "OK", responseBody);
                }
                catch (Exception ex)
                {
                    Exception actual = ex is TargetInvocationException && ex.InnerException != null ? ex.InnerException : ex;
                    try { WriteResponse(network, 500, "Internal Server Error", Encoding.UTF8.GetBytes(actual.ToString())); }
                    catch { }
                    Console.Error.WriteLine(actual);
                }
            }
        }

        private static string ReadAsciiLine(Stream stream)
        {
            MemoryStream line = new MemoryStream();
            int previous = -1;
            while (line.Length < 16384)
            {
                int current = stream.ReadByte();
                if (current < 0) break;
                if (previous == '\r' && current == '\n')
                {
                    line.SetLength(line.Length - 1);
                    break;
                }
                line.WriteByte((byte)current);
                previous = current;
            }
            return Encoding.ASCII.GetString(line.ToArray());
        }

        private static byte[] ReadExactly(Stream stream, int length)
        {
            byte[] data = new byte[length];
            int offset = 0;
            while (offset < length)
            {
                int read = stream.Read(data, offset, length - offset);
                if (read == 0) throw new EndOfStreamException();
                offset += read;
            }
            return data;
        }

        private static void WriteResponse(Stream stream, int status, string reason, byte[] body)
        {
            WriteAscii(stream, "HTTP/1.1 " + status + " " + reason + "\r\n" +
                "Content-Type: application/octet-stream\r\n" +
                "Content-Length: " + body.Length + "\r\n" +
                "Connection: close\r\n\r\n");
            stream.Write(body, 0, body.Length);
        }

        private static void WriteAscii(Stream stream, string text)
        {
            byte[] bytes = Encoding.ASCII.GetBytes(text);
            stream.Write(bytes, 0, bytes.Length);
        }
    }
}
