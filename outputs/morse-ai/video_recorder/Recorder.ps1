param([switch]$SmokeTest,[string]$SmokeRecordSource)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
$script:base = Split-Path -Parent $PSScriptRoot
$script:python = Join-Path $script:base '.venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $script:python)) {
 $script:python = Join-Path (Split-Path -Parent $script:base) 'runtime\python.exe'
}
$script:state='Idle';$script:worker=$null;$script:overlays=@();$script:directory=$null;$script:clock=[Diagnostics.Stopwatch]::StartNew();$script:cursorHidden=$false
$form=New-Object Windows.Forms.Form
$form.Text='光モールス動画 記録アプリ';$form.ClientSize=New-Object Drawing.Size(680,660);$form.StartPosition='CenterScreen';$form.FormBorderStyle='FixedDialog';$form.MaximizeBox=$false
$form.Font=New-Object Drawing.Font('Yu Gothic UI',10)
function Label($text,$x,$y,$w=620){$c=New-Object Windows.Forms.Label;$c.Text=$text;$c.SetBounds($x,$y,$w,28);$form.Controls.Add($c);return $c}
$null=Label 'テストNo.' 20 22 100
$test=New-Object Windows.Forms.TextBox;$test.SetBounds(130,20,210,28);$form.Controls.Add($test)
$null=Label 'USBカメラ番号' 355 22 130
$camera=New-Object Windows.Forms.NumericUpDown;$camera.SetBounds(495,20,75,28);$camera.Minimum=0;$camera.Maximum=10;$form.Controls.Add($camera)
$null=Label '保存先' 20 68 100
$folder=New-Object Windows.Forms.TextBox;$folder.SetBounds(130,65,435,28);$folder.Text=Join-Path $script:base 'recordings_video';$form.Controls.Add($folder)
$browse=New-Object Windows.Forms.Button;$browse.Text='参照';$browse.SetBounds(575,63,80,32);$form.Controls.Add($browse)
$null=Label '録画開始 → 全画面を黒く表示 → 任意のキーで停止・画面復帰' 20 113
$null=Label '映像のみ録画（音声なし）。640×480・30fpsを要求します。' 20 143
$null=Label 'カメラ番号0で映らない場合は1、2…を試してください。' 20 173
$start=New-Object Windows.Forms.Button;$start.Text='録画開始';$start.SetBounds(20,220,180,45);$form.Controls.Add($start)
$open=New-Object Windows.Forms.Button;$open.Text='保存先を開く';$open.SetBounds(220,220,180,45);$form.Controls.Add($open)
$preview=New-Object Windows.Forms.Button;$preview.Text='プレビュー開始';$preview.SetBounds(430,220,225,45);$form.Controls.Add($preview)
$picture=New-Object Windows.Forms.PictureBox;$picture.SetBounds(130,325,420,315);$picture.SizeMode='Zoom';$picture.BackColor=[Drawing.Color]::Black;$form.Controls.Add($picture)
$play=New-Object Windows.Forms.Button;$play.Text='保存動画を再生';$play.SetBounds(20,325,100,65);$play.Enabled=$false;$form.Controls.Add($play)
$play.Add_Click({try{Start-Process -FilePath $script:lastVideo}catch{[Windows.Forms.MessageBox]::Show('AVI対応の動画プレーヤーで保存先のvideo.aviを開いてください。')}})
$script:previewPath=Join-Path ([IO.Path]::GetTempPath()) ('morse_preview_'+[guid]::NewGuid().ToString('N')+'.jpg')
$script:startAfterPreview=$false;$script:closeAfterPreview=$false
$status=Label '待機中：テストNo.を入力してください。' 20 285 640
function Restore-Screen {
 $script:restoring=$true
 foreach($o in $script:overlays){$o.Close();$o.Dispose()};$script:overlays=@()
 if($script:cursorHidden){[Windows.Forms.Cursor]::Show();$script:cursorHidden=$false}
 if(!$form.IsDisposed){$form.Show();$form.Activate()};$script:restoring=$false
}
function Stop-Recording {
 if($script:state -ne 'Recording'){return}
 $script:state='Stopping';Restore-Screen;$status.Text='保存を完了しています…';$script:clock.Restart()
 try{$script:worker.StandardInput.WriteLine('STOP');$script:worker.StandardInput.Flush()}catch{$status.Text='停止要求を送れませんでした。終了を待っています。'}
}
function Black-Screen {
 $script:state='Recording';$form.Hide()
 foreach($screen in [Windows.Forms.Screen]::AllScreens){
  $o=New-Object Windows.Forms.Form;$o.FormBorderStyle='None';$o.StartPosition='Manual';$o.Bounds=$screen.Bounds;$o.BackColor=[Drawing.Color]::Black;$o.TopMost=$true;$o.ShowInTaskbar=$false;$o.KeyPreview=$true
  $o.Add_KeyDown({param($sender,$e) $e.SuppressKeyPress=$true;if($script:clock.ElapsedMilliseconds -ge 250){Stop-Recording}})
  $o.Add_FormClosing({param($sender,$e) if(!$script:restoring -and $script:state -eq 'Recording'){$e.Cancel=$true;Stop-Recording}})
  $script:overlays+=$o;$o.Show()
 }
 [Windows.Forms.Cursor]::Hide();$script:cursorHidden=$true
 $script:overlays[0].Activate();[Windows.Forms.Application]::DoEvents();$script:clock.Restart()
 $script:worker.StandardInput.WriteLine('START');$script:worker.StandardInput.Flush()
}
function Idle-Controls {$preview.Enabled=$true;$preview.Text='プレビュー開始';$start.Enabled=$true;$browse.Enabled=$true;$test.Enabled=$true;$camera.Enabled=$true;$folder.Enabled=$true;$open.Enabled=$true;$script:state='Idle'}
$browse.Add_Click({$d=New-Object Windows.Forms.FolderBrowserDialog;$d.Description='動画の保存先';if($d.ShowDialog() -eq 'OK'){$folder.Text=$d.SelectedPath};$d.Dispose()})
$open.Add_Click({if(Test-Path -LiteralPath $folder.Text){Start-Process explorer.exe -ArgumentList ('"'+$folder.Text+'"')}})
function Launch-Worker($arguments) {
 $psi=New-Object Diagnostics.ProcessStartInfo;$psi.FileName=$script:python
 $psi.Arguments='-B -X utf8 "'+(Join-Path $PSScriptRoot 'capture_worker.py')+'" '+$arguments
 if($SmokeRecordSource){$psi.Arguments+=' --source "'+$SmokeRecordSource+'"'}
 $psi.UseShellExecute=$false;$psi.CreateNoWindow=$true;$psi.RedirectStandardInput=$true;$psi.RedirectStandardOutput=$true;$psi.RedirectStandardError=$true;$psi.StandardOutputEncoding=[Text.Encoding]::UTF8
 $script:worker=New-Object Diagnostics.Process;$script:worker.StartInfo=$psi;$null=$script:worker.Start();$script:rxTask=$script:worker.StandardOutput.ReadLineAsync();$script:errors=$script:worker.StandardError.ReadToEndAsync()
}
function Stop-Preview {
 $script:state='PreviewStopping';$script:clock.Restart();$preview.Enabled=$false;$start.Enabled=$false
 $script:worker.StandardInput.WriteLine('STOP');$script:worker.StandardInput.Flush()
}
$preview.Add_Click({
 if($script:state -eq 'Preview' -or $script:state -eq 'PreviewPreparing'){Stop-Preview;return}
 if($script:state -ne 'Idle'){return}
 try {
  $script:state='PreviewPreparing';$script:clock.Restart();$camera.Enabled=$false;$preview.Text='プレビュー停止';$status.Text='プレビュー準備中…'
  Launch-Worker ('--camera '+$camera.Value+' --preview-path "'+$script:previewPath+'"')
 }catch{$status.Text=$_.Exception.Message;Idle-Controls}
})
$start.Add_Click({
 if($test.Text -notmatch '^[\w-]{1,40}$'){[Windows.Forms.MessageBox]::Show('テストNo.を文字・数字・ハイフン・下線で入力してください。');return}
 if(!(Test-Path -LiteralPath $script:python)){[Windows.Forms.MessageBox]::Show('実行用Pythonが見つかりません。');return}
 if($folder.Text.Contains('"') -or !$folder.Text.Trim()){[Windows.Forms.MessageBox]::Show('保存先を確認してください。');return}
 if($script:state -eq 'Preview' -or $script:state -eq 'PreviewPreparing'){$script:startAfterPreview=$true;Stop-Preview;return}
 if($script:state -ne 'Idle'){return}
 try {
  $preview.Enabled=$false;$script:directory=$null;$script:state='Preparing';$script:clock.Restart();$status.Text='カメラを準備中…';$start.Enabled=$false;$browse.Enabled=$false;$test.Enabled=$false;$camera.Enabled=$false;$folder.Enabled=$false;$open.Enabled=$false
  Launch-Worker ('--test-no "'+$test.Text+'" --camera '+$camera.Value+' --output "'+$folder.Text.TrimEnd('\')+'"')
 }catch{Restore-Screen;Idle-Controls;$status.Text='起動失敗：'+$_.Exception.Message}
})
function Poll-Worker {
 if($null -eq $script:worker){return}
 try {
  while($null -ne $script:rxTask -and $script:rxTask.IsCompleted){
   $message=$script:rxTask.Result;$script:rxTask=$null
   if($null -eq $message){break}
   $payload=$message|ConvertFrom-Json
   switch($payload.event){
    'preview_frame' {
     if($script:state -ne 'PreviewStopping'){
      $script:state='Preview';$status.Text='プレビュー中：位置を確認して録画開始を押してください。'
      $bytes=[IO.File]::ReadAllBytes($script:previewPath);$ms=New-Object IO.MemoryStream(,$bytes)
      $img=[Drawing.Image]::FromStream($ms);$copy=New-Object Drawing.Bitmap($img);$img.Dispose();$ms.Dispose()
      $old=$picture.Image;$picture.Image=$copy;if($old){$old.Dispose()}
     }
    }
    'preparing' {$script:directory=$payload.directory}
    'ready' {$script:directory=$payload.directory;Black-Screen}
    'done' {$script:lastVideo=Join-Path $payload.directory 'video.avi';$play.Enabled=$true;Restore-Screen;$script:state='Finishing';$status.Text='保存完了：'+$payload.frames+'フレーム';if($payload.timing_warning){$status.Text+='（FPS差あり・記録情報を確認）'}}
    'error' {Restore-Screen;$script:state='Finishing';$status.Text='エラー：'+$payload.message;$script:startAfterPreview=$false}
   }
   $script:rxTask=$script:worker.StandardOutput.ReadLineAsync()
  }
  if(($script:state -in @('Preparing','PreviewPreparing') -and $script:clock.Elapsed.TotalSeconds -gt 30) -or ($script:state -in @('Stopping','PreviewStopping') -and $script:clock.Elapsed.TotalSeconds -gt 10)){
   Restore-Screen;$script:worker.Kill();$status.Text='応答がないため停止しました。記録情報を確認してください。';$script:startAfterPreview=$false
  }
  if($script:worker.HasExited -and ($null -eq $script:rxTask)){
   if($script:state -eq 'Recording' -or $script:state -eq 'Preparing'){Restore-Screen;$status.Text='録画プロセスが終了しました。記録情報を確認してください。'}
   $script:worker.Dispose();$script:worker=$null
   if(Test-Path -LiteralPath $script:previewPath){Remove-Item -LiteralPath $script:previewPath}
   if($picture.Image){$picture.Image.Dispose();$picture.Image=$null}
   if($script:state -eq 'PreviewStopping'){$status.Text='プレビューを停止しました。'}
   Idle-Controls
   if($script:closeAfterPreview){$form.Close();return}
   if($script:startAfterPreview){$script:startAfterPreview=$false;$start.PerformClick()}
  }
 }catch{
  Restore-Screen;$status.Text='処理エラー：'+$_.Exception.Message;$script:startAfterPreview=$false
  if($script:worker){if(!$script:worker.HasExited){$script:worker.Kill()};$script:worker.Dispose()};$script:worker=$null;Idle-Controls
 }
}
$form.Add_FormClosing({param($sender,$e)
 if($script:state -ne 'Idle'){
  $e.Cancel=$true
  if($script:state -eq 'Recording'){Stop-Recording}
  elseif($script:state -in @('Preview','PreviewPreparing')){$script:closeAfterPreview=$true;Stop-Preview}
  else{$status.Text='保存または準備の完了を待ってください。'}
 }
})
$script:smokeStage=0;$overall=[Diagnostics.Stopwatch]::StartNew()
try {
 $form.Show()
 if($SmokeRecordSource){$test.Text='SELFTEST';$folder.Text=Join-Path $PSScriptRoot 'test_outputs';$preview.PerformClick()}
 while(!$form.IsDisposed){
  [Windows.Forms.Application]::DoEvents();Poll-Worker
  if($SmokeRecordSource){
   if($script:smokeStage -eq 0 -and $script:state -eq 'Preview' -and $picture.Image){$script:smokeStage=1;$start.PerformClick()}
   if($script:smokeStage -eq 1 -and $script:state -eq 'Recording' -and $script:clock.ElapsedMilliseconds -gt 700){
    if($script:overlays.Count -ne [Windows.Forms.Screen]::AllScreens.Count){throw 'Blackout count mismatch'}
    $key=New-Object Windows.Forms.KeyEventArgs([Windows.Forms.Keys]::Escape)
    $script:overlays[0].GetType().GetMethod('OnKeyDown',[Reflection.BindingFlags]'Instance,NonPublic').Invoke($script:overlays[0],@($key.PSObject.BaseObject))
    if($script:state -ne 'Stopping' -or $script:overlays.Count -ne 0){throw 'Key stop failed'}
    $script:smokeStage=2
   }
   if($script:smokeStage -eq 2 -and $script:state -eq 'Idle'){
    $meta=Get-Content -LiteralPath (Join-Path $script:directory 'recording.json') -Raw|ConvertFrom-Json
    if($meta.status -ne 'COMPLETE'){throw 'Save failed'}
    Write-Output ('PASS preview, blackout, key stop, restoration, saved '+$meta.frames+' frames');$form.Close()
   }
   if($overall.Elapsed.TotalSeconds -gt 15){throw ('Smoke timeout: '+$script:state+' '+$status.Text)}
  }
  if($SmokeTest -and $overall.ElapsedMilliseconds -gt 500){$form.Close()}
  Start-Sleep -Milliseconds 20
 }
}finally{
 Restore-Screen
 if($script:worker){if(!$script:worker.HasExited){$script:worker.Kill()};$script:worker.Dispose()}
 if($picture.Image){$picture.Image.Dispose()}
 if(Test-Path -LiteralPath $script:previewPath){Remove-Item -LiteralPath $script:previewPath}
 $form.Dispose()
}
