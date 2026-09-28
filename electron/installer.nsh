; ==================== 卸载时的清理逻辑 ====================

!macro customUnInstall
  ; 1. 杀掉所有相关进程（否则 backend.exe 被锁，删不掉）
  nsExec::ExecToLog 'taskkill /F /IM backend.exe /T'
  nsExec::ExecToLog 'taskkill /F /IM run_sync.exe /T'
  nsExec::ExecToLog 'taskkill /F /IM HealthDashboard.exe /T'
  Sleep 500

  ; 2. 删除用户数据目录
  RMDir /r "$APPDATA\HealthDashboard"
  RMDir /r "$APPDATA\health-dashboard"

  ; 3. 删除桌面快捷方式（NSIS 默认已经删，但保险起见再删一次）
  Delete "$DESKTOP\医疗疾病信息看板.lnk"

  ; 4. 删除开始菜单快捷方式
  Delete "$SMPROGRAMS\医疗疾病信息看板.lnk"
  RMDir "$SMPROGRAMS\医疗疾病信息看板"

  ; 5. 删除安装目录里可能的残留文件
  ; （NSIS 会自动清理 $INSTDIR，但 backend.exe 可能因为被锁没删干净）
  Delete "$INSTDIR\resources\backend\backend.exe"
  Delete "$INSTDIR\resources\collector\run_sync.exe"
!macroend