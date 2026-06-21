<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import {
  RefreshCw,
  Link2,
  XCircle,
  Globe,
  Network,
  UserCircle,
  Clock,
  Layers,
  Server,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getConnections,
  closeConnection,
  type ConnectionListItem,
} from '@/api'

defineOptions({
  name: 'ConnectionList',
})

const loading = ref(false)
const connections = ref<ConnectionListItem[]>([])
const lastUpdated = ref<Date | null>(null)
let refreshTimer: number | null = null
let isActive = false
let isFetching = false
let hasLoaded = false

async function fetchData(forceRefresh: boolean | Event = false) {
  const isForce = typeof forceRefresh === 'boolean' ? forceRefresh : false
  if (isFetching && !isForce) return
  if (!isActive) return

  try {
    isFetching = true
    if (!hasLoaded || isForce) {
      loading.value = true
    }
    const data = await getConnections()
    connections.value = data
    lastUpdated.value = new Date()
    hasLoaded = true
  } catch (err) {
    console.error('Failed to fetch connections:', err)
  } finally {
    loading.value = false
    isFetching = false
  }
}

function startRefreshTimer() {
  if (refreshTimer) return
  refreshTimer = window.setInterval(() => {
    if (isActive) {
      fetchData()
    }
  }, 10000)
}

function stopRefreshTimer() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

async function handleClose(connection: ConnectionListItem) {
  try {
    await ElMessageBox.confirm(
      `确定要强制关闭该连接吗？\n\n客户端: ${connection.client_ip}:${connection.client_port}\n用户: ${connection.username}\nVHost: ${connection.vhost}\n\n此操作将立即断开该客户端连接，可能影响正在进行的消息收发！`,
      '强制关闭连接',
      {
        confirmButtonText: '确认关闭',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await closeConnection(connection.name)
    ElMessage.success(`连接 "${connection.client_ip}:${connection.client_port}" 已关闭`)
    fetchData()
  } catch {
    // 用户取消操作
  }
}

function formatTime(timestamp: number): string {
  if (!timestamp) return '--'
  const date = new Date(timestamp)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatDuration(timestamp: number): string {
  if (!timestamp) return '--'
  const seconds = Math.floor((Date.now() - timestamp) / 1000)
  if (seconds < 0) return '--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

onMounted(() => {
  isActive = true
  fetchData()
  startRefreshTimer()
})

onActivated(() => {
  isActive = true
  if (!hasLoaded) {
    fetchData()
  }
  startRefreshTimer()
})

onDeactivated(() => {
  isActive = false
  stopRefreshTimer()
})

onBeforeUnmount(() => {
  isActive = false
  stopRefreshTimer()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold text-ops-text mb-1">连接管理</h2>
        <p class="text-sm text-ops-muted">
          查看 RabbitMQ 所有当前连接，支持强制关闭指定连接
          <span v-if="lastUpdated" class="stat-number ml-2">
            · 最后更新: {{ lastUpdated.toLocaleTimeString('zh-CN', { hour12: false }) }}
          </span>
        </p>
      </div>
      <div class="flex items-center gap-3">
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 hover:border-ops-primary/50 transition-all duration-200"
          :disabled="loading"
          @click="fetchData"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
      </div>
    </div>

    <div class="grid grid-cols-4 gap-4">
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <Link2 class="w-3.5 h-3.5" />
          连接总数
        </div>
        <div class="text-2xl font-bold text-ops-text stat-number">{{ connections.length }}</div>
      </div>
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <Layers class="w-3.5 h-3.5" />
          Channel 总数
        </div>
        <div class="text-2xl font-bold text-ops-text stat-number">
          {{ connections.reduce((sum, c) => sum + c.channels, 0) }}
        </div>
      </div>
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <UserCircle class="w-3.5 h-3.5" />
          活跃用户
        </div>
        <div class="text-2xl font-bold text-ops-text stat-number">
          {{ new Set(connections.map((c) => c.username)).size }}
        </div>
      </div>
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <Globe class="w-3.5 h-3.5" />
          客户端 IP
        </div>
        <div class="text-2xl font-bold text-ops-text stat-number">
          {{ new Set(connections.map((c) => c.client_ip)).size }}
        </div>
      </div>
    </div>

    <div class="card-gradient rounded-2xl border border-ops-border overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-ops-border">
              <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center gap-2">
                  <Globe class="w-4 h-4" />
                  客户端 IP
                </div>
              </th>
              <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">
                端口
              </th>
              <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center gap-2">
                  <UserCircle class="w-4 h-4" />
                  用户名
                </div>
              </th>
              <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">
                VHost
              </th>
              <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center gap-2">
                  <Clock class="w-4 h-4" />
                  连接时间
                </div>
              </th>
              <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center justify-end gap-2">
                  <Layers class="w-4 h-4" />
                  Channels
                </div>
              </th>
              <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center gap-2">
                  <Server class="w-4 h-4" />
                  服务端
                </div>
              </th>
              <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="conn in connections"
              :key="conn.name"
              class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
            >
              <td class="px-6 py-4">
                <div class="flex items-center gap-2">
                  <Network class="w-4 h-4 text-ops-muted" />
                  <span class="font-medium text-ops-text stat-number">{{ conn.client_ip }}</span>
                </div>
              </td>
              <td class="px-6 py-4 text-ops-text stat-number">
                {{ conn.client_port }}
              </td>
              <td class="px-6 py-4">
                <span class="inline-flex items-center px-2.5 py-1 text-xs rounded-full font-medium bg-blue-500/15 text-blue-400">
                  {{ conn.username }}
                </span>
              </td>
              <td class="px-6 py-4 text-ops-text stat-number">
                {{ conn.vhost }}
              </td>
              <td class="px-6 py-4">
                <div class="text-sm text-ops-text">{{ formatTime(conn.connected_at) }}</div>
                <div class="text-xs text-ops-muted mt-0.5">已连接 {{ formatDuration(conn.connected_at) }}</div>
              </td>
              <td class="px-6 py-4 text-right">
                <span
                  class="inline-flex items-center px-2.5 py-1 text-xs rounded-full font-medium"
                  :class="conn.channels > 0 ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-500/15 text-slate-400'"
                >
                  {{ conn.channels }}
                </span>
              </td>
              <td class="px-6 py-4 text-ops-muted text-sm stat-number">
                {{ conn.server_ip }}:{{ conn.server_port }}
              </td>
              <td class="px-6 py-4 text-right">
                <button
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-red-400 hover:text-white hover:bg-red-500/80 border border-red-500/30 transition-all duration-150 text-xs font-medium"
                  title="强制关闭连接"
                  @click.stop="handleClose(conn)"
                >
                  <XCircle class="w-3.5 h-3.5" />
                  强制关闭
                </button>
              </td>
            </tr>
            <tr v-if="connections.length === 0 && !loading">
              <td colspan="8" class="px-6 py-12 text-center">
                <div class="flex flex-col items-center gap-3">
                  <Link2 class="w-12 h-12 text-ops-muted/30" />
                  <div class="text-ops-muted text-sm">暂无连接数据</div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="loading && connections.length === 0">
      <div class="card-gradient rounded-2xl border border-ops-border p-12 text-center">
        <RefreshCw class="w-12 h-12 text-ops-muted/30 mx-auto mb-3 animate-spin" />
        <div class="text-ops-muted text-sm">加载中...</div>
      </div>
    </div>
  </div>
</template>
