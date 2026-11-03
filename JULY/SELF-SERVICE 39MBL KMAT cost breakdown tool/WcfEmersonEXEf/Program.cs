// Decompiled with JetBrains decompiler
// Type: WcfEmersonEXE.Program
// Assembly: WcfEmersonEXE, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null
// MVID: 262039AD-1FF5-45A1-9262-B39C78D2708F
// Assembly location: C:\Users\montelma1\Desktop\JULY\SELF-SERVICE 39MBL KMAT cost breakdown tool\WcfEmersonEXE.exe

using System;
using System.ServiceModel;
using System.ServiceModel.Channels;
using System.ServiceModel.Web;
using System.Threading;

#nullable disable
namespace WcfEmersonEXE;

internal class Program
{
  public static void Main(string[] args)
  {
    // Supply safe local defaults so the program can also be started directly.
    Service1.configDirectory = args.Length > 0
      ? args[0]
      : AppDomain.CurrentDomain.BaseDirectory;

    Uri baseAddress = new Uri(args.Length > 1
      ? args[1]
      : "http://127.0.0.1:8020/");

    if (!baseAddress.IsLoopback)
      throw new InvalidOperationException("The service may only bind to a loopback address.");

    string endpointAddress = args.Length > 2
      ? args[2]
      : "SelectDrive";

    WebServiceHost webServiceHost = new WebServiceHost(typeof (Service1), new Uri[1]
    {
      baseAddress
    });

    WebHttpBinding binding = new WebHttpBinding();
    // StrongWildcard registers http://+:port/ and requires an administrator
    // URL ACL. Exact binds only the loopback host supplied above.
    binding.HostNameComparisonMode = HostNameComparisonMode.Exact;

    webServiceHost.AddServiceEndpoint(typeof (IEmersonRest), (Binding) binding, endpointAddress);
    webServiceHost.Open();
    Console.WriteLine("WcfEmersonEXE listening at " + baseAddress);
    Thread.Sleep(-1);
    webServiceHost.Close();
  }
}
