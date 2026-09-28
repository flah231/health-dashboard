const { app, BrowserWindow, dialog, shell, ipcMain } = require('electron')
const { spawn, spawnSync } = require('child_process')
const path = require('path')
const http = require('http')
const fs = require('fs')

// ==================== 统一用户数据目录 ====================
// 把 Electron 的 userData 也放到 %APPDATA%\HealthDashboard
// 这样 %APPDATA%\health-dashboard 就不会再被自动创建
const APP_DATA_DIR = path.join(app.getPath('appData'), 'HealthDashboard')
if (!fs.existsSync(APP_DATA_DIR)) fs.mkdirSync(APP_DATA_DIR, { recursive: true })
app.setPath('userData', APP_DATA_DIR)

// 数据目录结构
const LOG_DIR = path.join(APP_DATA_DIR, 'logs')
if (!fs.existsSync(LOG_DIR)) fs.mkdirSync(LOG_DIR, { recursive: true })
const DB_PATH = path.join(APP_DATA_DIR, 'health_dashboard.db')

// ==================== 全局变量 ====================
let mainWindow = null
let backendProcess = null

const BACKEND_PORT = 8000
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`

const isPackaged = app.isPackaged
const RESOURCES_DIR = isPackaged
  ? process.resourcesPath
  : path.resolve(__dirname, '..')

console.log(`[Electron] Packaged: ${isPackaged}`)
console.log(`[Electron] APP_DATA_DIR: ${APP_DATA_DIR}`)
console.log(`[Electron] DB: ${DB_PATH}`)

// ==================== 查找后端启动方式 ====================
function findBackendRunner() {
  // 1. 优先用 PyInstaller 打包好的 backend.exe
  const exeCandidates = isPackaged
    ? [
        path.join(RESOURCES_DIR, 'backend', 'backend.exe'),
        path.join(RESOURCES_DIR, 'backend.exe'),
      ]
    : [
        path.resolve(__dirname, '..', 'build', 'dist', 'backend.exe'),
      ]

  for (const p of exeCandidates) {
    if (fs.existsSync(p)) {
      console.log(`[Electron] 找到 backend.exe: ${p}`)
      return { type: 'exe', path: p }
    }
  }

  // 2. 回退到系统 Python（开发环境 / 未打包）
  const mainPy = isPackaged
    ? path.join(RESOURCES_DIR, 'backend', 'main.py')
    : path.resolve(__dirname, '..', 'backend', 'main.py')

  if (fs.existsSync(mainPy)) {
    console.log(`[Electron] 未找到 exe，回退到 python: ${mainPy}`)
    return { type: 'python', path: mainPy, python: 'python' }
  }

  return null
}

// ==================== 启动后端 ====================
function startBackend() {
  return new Promise((resolve, reject) => {
    const runner = findBackendRunner()
    if (!runner) {
      reject(new Error('找不到 backend.exe 或 main.py'))
      return
    }

    // 传给后端的环境变量
    const childEnv = {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      HEALTH_APP_DIR: APP_DATA_DIR,
      HEALTH_LOG_DIR: LOG_DIR,
      HEALTH_DB_PATH: DB_PATH,
    }

    let spawnCmd, spawnArgs, spawnCwd
    if (runner.type === 'exe') {
      spawnCmd = runner.path
      spawnArgs = []
      spawnCwd = path.dirname(runner.path)
    } else {
      spawnCmd = runner.python
      spawnArgs = [runner.path]
      spawnCwd = path.dirname(runner.path)
    }

    console.log(`[Electron] Spawn: ${spawnCmd} ${spawnArgs.join(' ')}`)

    backendProcess = spawn(spawnCmd, spawnArgs, {
      cwd: spawnCwd,
      env: childEnv,
      windowsHide: true,
    })

    // 日志写到 %APPDATA%\HealthDashboard\logs\
    const backendLog = fs.createWriteStream(
      path.join(LOG_DIR, 'electron_backend.log'),
      { flags: 'a' }
    )
    backendProcess.stdout.on('data', (d) => {
      backendLog.write(`[OUT] ${d}`)
      process.stdout.write(`[Backend] ${d}`)
    })
    backendProcess.stderr.on('data', (d) => {
      backendLog.write(`[ERR] ${d}`)
      process.stderr.write(`[Backend-ERR] ${d}`)
    })
    backendProcess.on('error', (err) => {
      backendLog.write(`[FATAL] ${err.message}\n`)
      reject(new Error(`无法启动后端: ${err.message}`))
    })
    backendProcess.on('exit', (code) => {
      backendLog.write(`[EXIT] code=${code}\n`)
      console.log(`[Electron] 后端退出，代码 ${code}`)
      backendProcess = null
    })

    // 轮询 /api/health 直到就绪（最多 60 秒）
    let attempts = 0
    const check = () => {
      attempts++
      if (attempts > 120) {
        reject(new Error('后端启动超时（60 秒）'))
        return
      }
      http.get(`${BACKEND_URL}/api/health`, (res) => {
        if (res.statusCode === 200) resolve()
        else setTimeout(check, 500)
      }).on('error', () => setTimeout(check, 500))
    }
    setTimeout(check, 1000)
  })
}

// ==================== 创建窗口 ====================
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: '医疗疾病信息数据分析看板',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),   // ← 新增
    },
  })

  mainWindow.loadURL(BACKEND_URL)

  mainWindow.on('closed', () => {
    mainWindow = null
  })
}

// ==================== IPC：打开数据目录 ====================
ipcMain.handle('open-data-dir', () => {
  shell.openPath(APP_DATA_DIR)
  return APP_DATA_DIR
})

// ==================== 生命周期 ====================
app.whenReady().then(async () => {
  try {
    await startBackend()
    createWindow()
  } catch (err) {
    dialog.showErrorBox('启动失败', `无法启动后端：\n${err.message}`)
    app.quit()
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

// 窗口全关时：杀掉后端进程
app.on('window-all-closed', () => {
  if (backendProcess) {
    console.log('[Electron] 关闭后端进程...')
    backendProcess.kill()
    backendProcess = null
  }
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// 应用退出前确保杀掉后端
app.on('before-quit', () => {
  if (backendProcess) {
    backendProcess.kill()
    backendProcess = null
  }
})