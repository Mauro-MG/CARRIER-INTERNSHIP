''' <summary>
''' A drive solution interchange - a driver sheave, driver bushing, driven sheave and driven bushing.
''' </summary>
Public Class Interchange

    ''' <summary>
    ''' The driver sheave part number.
    ''' </summary>
    Public Property DriverSheave() As String
        Get
            Return m_DriverSheave
        End Get
        Set(ByVal value As String)
            m_DriverSheave = value
        End Set
    End Property
    Private m_DriverSheave As String

    ''' <summary>
    ''' The driver bushing part number, or the empty string if no bushing is required for the driver sheave.
    ''' </summary>
    Public Property DriverBushing() As String
        Get
            Return m_DriverBushing
        End Get
        Set(ByVal value As String)
            m_DriverBushing = value
        End Set
    End Property
    Private m_DriverBushing As String

    ''' <summary>
    ''' The driven sheave part number.
    ''' </summary>
    Public Property DrivenSheave() As String
        Get
            Return m_DrivenSheave
        End Get
        Set(ByVal value As String)
            m_DrivenSheave = value
        End Set
    End Property
    Private m_DrivenSheave As String

    ''' <summary>
    ''' The driven bushing part number, or the empty string if no bushing is required for the driven sheave.
    ''' </summary>
    Public Property DrivenBushing() As String
        Get
            Return m_DrivenBushing
        End Get
        Set(ByVal value As String)
            m_DrivenBushing = value
        End Set
    End Property
    Private m_DrivenBushing As String

    ''' <summary>
    ''' Creates a new Interchange object.
    ''' </summary>
    ''' <param name="DriverSheave">The driver sheave part number.</param>
    ''' <param name="DriverBushing">The driver bushing part number, or the empty string if no bushing is required for the driver sheave.</param>
    ''' <param name="DrivenSheave">The driven sheave part number.</param>
    ''' <param name="DrivenBushing">The driven bushing part number, or the empty string if no bushing is required for the driven sheave.</param>
    Public Sub New(ByVal DriverSheave As String, ByVal DriverBushing As String, ByVal DrivenSheave As String, ByVal DrivenBushing As String)

        Me.DriverSheave = DriverSheave
        Me.DriverBushing = DriverBushing
        Me.DrivenSheave = DrivenSheave
        Me.DrivenBushing = DrivenBushing

    End Sub

End Class
