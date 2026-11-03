// Decompiled with JetBrains decompiler
// Type: WcfEmersonEXE.IEmersonRest
// Assembly: WcfEmersonEXE, Version=1.0.0.0, Culture=neutral, PublicKeyToken=null
// MVID: 262039AD-1FF5-45A1-9262-B39C78D2708F
// Assembly location: C:\Users\montelma1\Desktop\JULY\SELF-SERVICE 39MBL KMAT cost breakdown tool\WcfEmersonEXE.exe

using System.IO;
using System.ServiceModel;
using System.ServiceModel.Web;

#nullable disable
namespace WcfEmersonEXE;

[ServiceContract]
public interface IEmersonRest
{
  [WebInvoke(BodyStyle = WebMessageBodyStyle.Bare)]
  [OperationContract]
  Stream selectDrive(Stream s);
}
