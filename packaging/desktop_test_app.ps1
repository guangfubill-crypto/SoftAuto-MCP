param([Parameter(Mandatory = $true)][string]$StatePath)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$form = New-Object System.Windows.Forms.Form
$form.Text = 'SoftAuto Desktop Release Gate'
$form.Size = New-Object System.Drawing.Size(440, 260)
$form.StartPosition = 'Manual'
$form.Location = New-Object System.Drawing.Point(120, 120)

$title = New-Object System.Windows.Forms.Label
$title.Text = 'Desktop UIA Release Test'
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(130, 25)
$form.Controls.Add($title)

$textBox = New-Object System.Windows.Forms.TextBox
$textBox.Name = 'releaseGateInput'
$textBox.AccessibleName = 'Release Gate Input'
$textBox.Size = New-Object System.Drawing.Size(280, 28)
$textBox.Location = New-Object System.Drawing.Point(70, 75)
$form.Controls.Add($textBox)

$button = New-Object System.Windows.Forms.Button
$button.Name = 'releaseGateButton'
$button.Text = 'Execute Gate'
$button.AccessibleName = 'Execute Gate'
$button.Size = New-Object System.Drawing.Size(120, 36)
$button.Location = New-Object System.Drawing.Point(150, 120)
$form.Controls.Add($button)

$result = New-Object System.Windows.Forms.Label
$result.Text = 'WAITING'
$result.AutoSize = $true
$result.Location = New-Object System.Drawing.Point(165, 175)
$form.Controls.Add($result)

$button.Add_Click({
    [System.IO.File]::WriteAllText($StatePath, $textBox.Text)
    $result.Text = 'DESKTOP_CLICK_OK'
})

[void]$form.ShowDialog()
