<Global.Microsoft.VisualBasic.CompilerServices.DesignerGenerated()> _
Partial Class Form1
    Inherits System.Windows.Forms.Form

    'Form overrides dispose to clean up the component list.
    <System.Diagnostics.DebuggerNonUserCode()> _
    Protected Overrides Sub Dispose(ByVal disposing As Boolean)
        Try
            If disposing AndAlso components IsNot Nothing Then
                components.Dispose()
            End If
        Finally
            MyBase.Dispose(disposing)
        End Try
    End Sub

    'Required by the Windows Form Designer
    Private components As System.ComponentModel.IContainer

    'NOTE: The following procedure is required by the Windows Form Designer
    'It can be modified using the Windows Form Designer.  
    'Do not modify it using the code editor.
    <System.Diagnostics.DebuggerStepThrough()> _
    Private Sub InitializeComponent()
        Me.Button1 = New System.Windows.Forms.Button
        Me.txtInputXml = New System.Windows.Forms.TextBox
        Me.webResults = New System.Windows.Forms.WebBrowser
        Me.txtResultsXml = New System.Windows.Forms.TextBox
        Me.Label1 = New System.Windows.Forms.Label
        Me.Label2 = New System.Windows.Forms.Label
        Me.Label3 = New System.Windows.Forms.Label
        Me.SuspendLayout()
        '
        'Button1
        '
        Me.Button1.Location = New System.Drawing.Point(12, 547)
        Me.Button1.Name = "Button1"
        Me.Button1.Size = New System.Drawing.Size(75, 23)
        Me.Button1.TabIndex = 0
        Me.Button1.Text = "Solve"
        Me.Button1.UseVisualStyleBackColor = True
        '
        'txtInputXml
        '
        Me.txtInputXml.Font = New System.Drawing.Font("Verdana", 8.25!, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, CType(0, Byte))
        Me.txtInputXml.Location = New System.Drawing.Point(12, 45)
        Me.txtInputXml.Multiline = True
        Me.txtInputXml.Name = "txtInputXml"
        Me.txtInputXml.ScrollBars = System.Windows.Forms.ScrollBars.Both
        Me.txtInputXml.Size = New System.Drawing.Size(312, 485)
        Me.txtInputXml.TabIndex = 2
        '
        'webResults
        '
        Me.webResults.Location = New System.Drawing.Point(340, 45)
        Me.webResults.MinimumSize = New System.Drawing.Size(20, 20)
        Me.webResults.Name = "webResults"
        Me.webResults.Size = New System.Drawing.Size(548, 485)
        Me.webResults.TabIndex = 4
        '
        'txtResultsXml
        '
        Me.txtResultsXml.Font = New System.Drawing.Font("Verdana", 8.25!, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, CType(0, Byte))
        Me.txtResultsXml.Location = New System.Drawing.Point(906, 45)
        Me.txtResultsXml.Multiline = True
        Me.txtResultsXml.Name = "txtResultsXml"
        Me.txtResultsXml.ReadOnly = True
        Me.txtResultsXml.ScrollBars = System.Windows.Forms.ScrollBars.Both
        Me.txtResultsXml.Size = New System.Drawing.Size(312, 485)
        Me.txtResultsXml.TabIndex = 5
        '
        'Label1
        '
        Me.Label1.AutoSize = True
        Me.Label1.Location = New System.Drawing.Point(136, 29)
        Me.Label1.Name = "Label1"
        Me.Label1.Size = New System.Drawing.Size(56, 13)
        Me.Label1.TabIndex = 6
        Me.Label1.Text = "Input XML"
        '
        'Label2
        '
        Me.Label2.AutoSize = True
        Me.Label2.Location = New System.Drawing.Point(1013, 29)
        Me.Label2.Name = "Label2"
        Me.Label2.Size = New System.Drawing.Size(67, 13)
        Me.Label2.TabIndex = 7
        Me.Label2.Text = "Results XML"
        '
        'Label3
        '
        Me.Label3.AutoSize = True
        Me.Label3.Location = New System.Drawing.Point(545, 29)
        Me.Label3.Name = "Label3"
        Me.Label3.Size = New System.Drawing.Size(92, 13)
        Me.Label3.TabIndex = 8
        Me.Label3.Text = "Formatted Results"
        '
        'Form1
        '
        Me.AutoScaleDimensions = New System.Drawing.SizeF(6.0!, 13.0!)
        Me.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font
        Me.ClientSize = New System.Drawing.Size(1227, 587)
        Me.Controls.Add(Me.Label3)
        Me.Controls.Add(Me.Label2)
        Me.Controls.Add(Me.Label1)
        Me.Controls.Add(Me.txtResultsXml)
        Me.Controls.Add(Me.webResults)
        Me.Controls.Add(Me.txtInputXml)
        Me.Controls.Add(Me.Button1)
        Me.FormBorderStyle = System.Windows.Forms.FormBorderStyle.FixedSingle
        Me.Name = "Form1"
        Me.Text = "PTS V-Belt Drive Configurator"
        Me.ResumeLayout(False)
        Me.PerformLayout()

    End Sub
    Friend WithEvents Button1 As System.Windows.Forms.Button
    Friend WithEvents txtInputXml As System.Windows.Forms.TextBox
    Friend WithEvents webResults As System.Windows.Forms.WebBrowser
    Friend WithEvents txtResultsXml As System.Windows.Forms.TextBox
    Friend WithEvents Label1 As System.Windows.Forms.Label
    Friend WithEvents Label2 As System.Windows.Forms.Label
    Friend WithEvents Label3 As System.Windows.Forms.Label

End Class
