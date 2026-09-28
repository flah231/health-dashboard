import { ref, onMounted, onBeforeUnmount } from 'vue'

/**
 * WebSocket 连接管理。
 * @param {Function} onDataUpdated - 收到 data_updated 消息时回调
 */
export function useWebSocket(onDataUpdated) {
  const connected = ref(false)
  let ws = null
  let heartbeatTimer = null
  let reconnectTimer = null
  let manualClose = false

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    // 开发时走 Vite 代理，或直连后端
    const url = `${proto}//${location.host}/api/ws`

    try {
      ws = new WebSocket(url)
    } catch (e) {
      console.error('[WS] 创建失败', e)
      scheduleReconnect()
      return
    }

    ws.onopen = () => {
      connected.value = true
      console.log('[WS] 已连接')
      // 心跳：每 25 秒发一次
      heartbeatTimer = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping')
      }, 25000)
    }

    ws.onmessage = (ev) => {
      if (ev.data === 'pong') return
      try {
        const msg = JSON.parse(ev.data)
        if (msg.type === 'data_updated') {
          console.log('[WS] 数据更新通知', msg)
          onDataUpdated && onDataUpdated(msg)
        }
      } catch (e) {
        // 非 JSON 消息（例如 pong）忽略
      }
    }

    ws.onclose = () => {
      connected.value = false
      clearInterval(heartbeatTimer)
      if (!manualClose) {
        console.log('[WS] 断开，5 秒后重连')
        scheduleReconnect()
      }
    }

    ws.onerror = (e) => {
      console.warn('[WS] 错误', e)
    }
  }

  function scheduleReconnect() {
    clearTimeout(reconnectTimer)
    reconnectTimer = setTimeout(connect, 5000)
  }

  onMounted(() => connect())

  onBeforeUnmount(() => {
    manualClose = true
    clearInterval(heartbeatTimer)
    clearTimeout(reconnectTimer)
    if (ws) ws.close()
  })

  return { connected }
}