''' <summary>
''' This class encapsulates the components of a drive solution, as well as other information about the solution (center distance, actual service factor, etc.)
''' </summary>
Public Class DriveSolution

    ''' <summary>
    ''' The solution ID (a number from one to ten if this one of the main solutions, or "EPTSolution" if this is the best solution disregarding options.
    ''' </summary>
    Public Property SolutionId() As String
        Get
            Return m_SolutionId
        End Get
        Set(ByVal value As String)
            m_SolutionId = value
        End Set

    End Property
    Private m_SolutionId As String

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
    ''' The belt part number.
    ''' </summary>
    Public Property Belt() As String
        Get
            Return m_Belt
        End Get
        Set(ByVal value As String)
            m_Belt = value
        End Set
    End Property
    Private m_Belt As String

    ''' <summary>
    ''' The number of belts required (which is the same as the number of grooves in the driver and driven sheaves.)
    ''' </summary>
    Public Property BeltQuantity() As Integer
        Get
            Return m_BeltQuantity
        End Get
        Set(ByVal value As Integer)
            m_BeltQuantity = value
        End Set
    End Property
    Private m_BeltQuantity As Integer

    ''' <summary>
    ''' The actual center distance of the drive.
    ''' </summary>
    Public Property ActualCenterDistance() As Double
        Get
            Return m_ActualCenterDistance
        End Get
        Set(ByVal value As Double)
            m_ActualCenterDistance = value
        End Set
    End Property
    Private m_ActualCenterDistance As Double

    ''' <summary>
    ''' The actual service factor of the drive.
    ''' </summary>
    Public Property ActualServiceFactor() As Double
        Get
            Return m_ActualServiceFactor
        End Get
        Set(ByVal value As Double)
            m_ActualServiceFactor = value
        End Set
    End Property
    Private m_ActualServiceFactor As Double

    ''' <summary>
    ''' The actual driven speed. For variable speed drives, this is the driven sped at the sheave fully opened.
    ''' </summary>
    Public Property ActualDrivenSpeedAtSheaveFullyOpened() As Integer
        Get
            Return m_ActualDrivenSpeedAtSheaveFullyOpened
        End Get
        Set(ByVal value As Integer)
            m_ActualDrivenSpeedAtSheaveFullyOpened = value
        End Set
    End Property
    Private m_ActualDrivenSpeedAtSheaveFullyOpened As Integer

    ''' <summary>
    ''' The actual driven speed. For variable speed drives, this is the driven speed at the sheave fully closed.
    ''' </summary>
    Public Property ActualDrivenSpeedAtSheaveFullyClosed() As Integer
        Get
            Return m_ActualDrivenSpeedAtSheaveFullyClosed
        End Get
        Set(ByVal value As Integer)
            m_ActualDrivenSpeedAtSheaveFullyClosed = value
        End Set
    End Property
    Private m_ActualDrivenSpeedAtSheaveFullyClosed As Integer

    ''' <summary>
    ''' The total cost of the drive.
    ''' </summary>
    Public Property Cost() As Decimal
        Get
            Return m_Cost
        End Get
        Set(ByVal value As Decimal)
            m_Cost = value
        End Set
    End Property
    Private m_Cost As Decimal

    ''' <summary>
    ''' For variable speed drives, this is the comment that lists the turns of the driver sheave and the corresponding driven speeds and center distances.
    ''' </summary>
    Public Property VariableSpeedDriveAdjustmentComment() As String
        Get
            Return m_VariableSpeedDriveAdjustmentComment
        End Get
        Set(ByVal value As String)
            m_VariableSpeedDriveAdjustmentComment = value
        End Set
    End Property
    Private m_VariableSpeedDriveAdjustmentComment As String

    ''' <summary>
    ''' The tensioning instructions.
    ''' </summary>
    Public Property TensioningInstructionsComment() As String
        Get
            Return m_TensioningInstructionsComment
        End Get
        Set(ByVal value As String)
            m_TensioningInstructionsComment = value
        End Set
    End Property
    Private m_TensioningInstructionsComment As String

    ''' <summary>
    ''' The interchanges.
    ''' </summary>
    Public Property Interchanges() As List(Of Interchange)
        Get
            Return m_Interchanges
        End Get
        Set(ByVal value As List(Of Interchange))
            m_Interchanges = value
        End Set
    End Property
    Private m_Interchanges As List(Of Interchange)

    ''' <summary>
    ''' Creates a new DriveSolution object.
    ''' </summary>
    ''' <param name="SolutionId">The solution ID (a number from one to ten if this one of the main solutions, or "EPTSolution" if this is the best solution disregarding options.</param>
    ''' <param name="DriverSheave">The driver sheave part number.</param>
    ''' <param name="DriverBushing">The driver bushing part number, or the empty string if no bushing is required for the driver sheave.</param>
    ''' <param name="DrivenSheave">The driven sheave part number.</param>
    ''' <param name="DrivenBushing">The driven bushing part number, or the empty string if no bushing is required for the driven sheave.</param>
    ''' <param name="Belt">The belt part number.</param>
    ''' <param name="BeltQuantity">The number of belts required (which is the same as the number of grooves in the driver and driven sheaves.)</param>
    ''' <param name="ActualCenterDistance">The actual center distance of the drive.</param>
    ''' <param name="ActualServiceFactor">The actual service factor of the drive.</param>
    ''' <param name="ActualDrivenSpeedAtSheaveFullyOpened">The actual driven speed. For variable speed drives, this is the driven sped at the sheave fully opened.</param>
    ''' <param name="ActualDrivenSpeedAtSheaveFullyClosed">The actual driven speed. For variable speed drives, this is the driven speed at the sheave fully closed.</param>
    ''' <param name="Cost">The total cost of the drive.</param>
    ''' <param name="VariableSpeedDriveAdjustmentComment">For variable speed drives, this is the comment that lists the turns of the driver sheave and the corresponding driven speeds and center distances.</param>
    ''' <param name="TensioningInstructionsComment">The tensioning instructions.</param>
    ''' <param name="Interchanges">The interchanges.</param>
    Public Sub New(ByVal SolutionId As String, ByVal DriverSheave As String, ByVal DriverBushing As String, ByVal DrivenSheave As String, ByVal DrivenBushing As String, ByVal Belt As String, ByVal BeltQuantity As Integer, ByVal ActualCenterDistance As Double, ByVal ActualServiceFactor As Double, ByVal ActualDrivenSpeedAtSheaveFullyOpened As Integer, ByVal ActualDrivenSpeedAtSheaveFullyClosed As Integer, ByVal Cost As Decimal, ByVal VariableSpeedDriveAdjustmentComment As String, ByVal TensioningInstructionsComment As String, ByVal Interchanges As List(Of Interchange))

        Me.SolutionId = SolutionId
        Me.DriverSheave = DriverSheave
        Me.DriverBushing = DriverBushing
        Me.DrivenSheave = DrivenSheave
        Me.DrivenBushing = DrivenBushing
        Me.Belt = Belt
        Me.BeltQuantity = BeltQuantity
        Me.ActualCenterDistance = ActualCenterDistance
        Me.ActualServiceFactor = ActualServiceFactor
        Me.ActualDrivenSpeedAtSheaveFullyOpened = ActualDrivenSpeedAtSheaveFullyOpened
        Me.ActualDrivenSpeedAtSheaveFullyClosed = ActualDrivenSpeedAtSheaveFullyClosed
        Me.Cost = Cost
        Me.VariableSpeedDriveAdjustmentComment = VariableSpeedDriveAdjustmentComment
        Me.TensioningInstructionsComment = TensioningInstructionsComment
        Me.Interchanges = Interchanges

    End Sub

End Class
