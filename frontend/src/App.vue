<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Gauge,
  List,
  Share2,
  MessageSquare,
  Rabbit,
  RefreshCw,
  Clock,
} from 'lucide-vue-next'
import { getConnectionStatus, type ConnectionStatus } from '@/api'

const route = useRoute()
const router = useRouter()

const menuItems = [
  { path: '/dashboard', title: 'Dashboard', icon: Gauge },
  { path: '/queues', title: '队列管理', icon: List },
  { path: '/exchanges', title: '交换机管理', icon: Share2 },
  { path: '/messages', title: '消息中心', icon: MessageSquare },
]

const connStatus = ref<ConnectionStatus>({
  status: 'connecting',
  host: 'localhost',
  port: 5672,
})

const currentTime = ref(new Date())
let timer: number

function formatUptime(seconds?: number): string {
  if (!seconds) return '--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

async function fetchStatus() {
  try {
    const data = await getConnectionStatus()
    connStatus.value = data
  } catch {
    connStatus.value = {
      status: 'disconnected',
      host: 'localhost',
      port: 5672,
      error: '无法连接到后端服务',
    }
  }
}

const statusText = computed(() => {
  switch (connStatus.value.status) {
    case 'connected':
      return '已连接'
    case 'connecting':
      return '连接中...'
    default:
      return '未连接'
  }
})

function navigate(path: string) {
  router.push(path)
}

onMounted(() => {
  fetchStatus()
  setInterval(fetchStatus, 5000)
  timer = window.setInterval(() => {
    currentTime.value = new Date()
  }, 1000)
})
</script>

<template>
  <div class="flex h-screen bg-ops-bg text-ops-text overflow-hidden">
    <aside class="w-60 flex-shrink-0 bg-ops-panel border-r border-ops-border flex flex-col">
      <div class="h-16 flex items-center gap-3 px-5 border-b border-ops-border">
        <div class="w-10 h-10 rounded-lg bg-gradient-to-br from-ops-primary to-ops-accent flex items-center justify-center shadow-glow-blue">
          <Rabbit class="w-5 h-5 text-white" />
        </div>
        <div>
          <div class="text-base font-semibold text-ops-text">MQ Ops Center</div>
          <div class="text-xs text-ops-muted">RabbitMQ Management</div>
        </div>
      </div>

      <nav class="flex-1 py-4 overflow-y-auto">
        <div class="px-4 mb-2 text-xs font-medium text-ops-muted uppercase tracking-wider">主导航</div>
        <div
          v-for="item in menuItems"
          :key="item.path"
          class="menu-item"
          :class="{ active: route.path === item.path }"
          @click="navigate(item.path)"
        >
          <component :is="item.icon" class="w-5 h-5" />
          <span class="text-sm">{{ item.title }}</span>
        </div>
      </nav>

      <div class="p-4 border-t border-ops-border">
        <div class="flex items-center gap-2 text-xs text-ops-muted">
          <RefreshCw class="w-3.5 h-3.5" />
          <span>v1.0.0</span>
        </div>
      </div>
    </aside>

    <div class="flex-1 flex flex-col overflow-hidden">
      <header class="h-16 flex-shrink-0 bg-ops-panel border-b border-ops-border flex items-center justify-between px-6">
        <div class="flex items-center gap-4">
          <h1 class="text-lg font-semibold">{{ (route.meta.title as string) || 'MQ Ops Center' }}</h1>
        </div>

        <div class="flex items-center gap-6">
          <div class="flex items-center gap-2 text-sm text-ops-muted">
            <Clock class="w-4 h-4" />
            <span class="stat-number">{{ currentTime.toLocaleString('zh-CN', { hour12: false }) }}</span>
          </div>

          <div class="flex items-center gap-3 px-4 py-2 rounded-lg bg-ops-card border border-ops-border">
            <span
              class="status-dot"
              :class="connStatus.status === 'connected' ? 'status-connected' : 'status-disconnected'"
            />
            <div class="text-sm">
              <div class="font-medium text-ops-text">{{ statusText }}</div>
              <div class="text-xs text-ops-muted stat-number">
                {{ connStatus.host }}:{{ connStatus.port }}
              </div>
            </div>
          </div>
        </div>
      </header>

      <main class="flex-1 overflow-auto bg-grid p-6 animate-fade-in">
        <router-view v-slot="{ Component }">
          <keep-alive :include="['QueueList', 'QueueDetail']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>
    </div>
  </div>
</template>
