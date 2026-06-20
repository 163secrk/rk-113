<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
import {
  Activity,
  ListTodo,
  Layers,
  Zap,
  ArrowUpRight,
  ArrowDownRight,
  RefreshCw,
  Server,
  Clock,
  HardDrive,
} from 'lucide-vue-next'
import StatCard from '@/components/StatCard.vue'
import { getRabbitMQOverview, type RabbitMQOverview } from '@/api'

const loading = ref(true)
const data = ref<RabbitMQOverview | null>(null)
const lastUpdated = ref<Date | null>(null)
let refreshTimer: number | null = null

async function fetchData() {
  try {
    const overview = await getRabbitMQOverview()
    data.value = overview
    lastUpdated.value = new Date()
  } catch (err) {
    console.error('Failed to fetch overview:', err)
  } finally {
    loading.value = false
  }
}

function formatRate(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k/s'
  return n.toFixed(2) + '/s'
}

function formatUptime(seconds?: number): string {
  if (!seconds) return '--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

const connectionSubtitle = computed(() => {
  if (!data.value) return ''
  const { status, host, port } = data.value.connection
  const statusText = status === 'connected' ? '正常运行中' : '连接异常'
  return `${statusText} · ${host}:${port}`
})

onMounted(() => {
  fetchData()
  refreshTimer = window.setInterval(fetchData, 5000)
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold text-ops-text mb-1">集群总览</h2>
        <p class="text-sm text-ops-muted">
          实时监控 RabbitMQ 运行状态，每 5 秒自动刷新
          <span v-if="lastUpdated" class="stat-number ml-2">
            · 最后更新: {{ lastUpdated.toLocaleTimeString('zh-CN', { hour12: false }) }}
          </span>
        </p>
      </div>
      <button
        class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 hover:border-ops-primary/50 transition-all duration-200"
        :disabled="loading"
        @click="fetchData"
      >
        <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" />
        刷新数据
      </button>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
      <StatCard
        title="连接状态"
        :value="data?.connection.status === 'connected' ? '在线' : '离线'"
        :icon="Activity"
        :accent="data?.connection.status === 'connected' ? 'green' : 'red'"
        :subtitle="connectionSubtitle"
        :loading="loading"
      />

      <StatCard
        title="Channel 数量"
        :value="data?.channels ?? 0"
        :icon="Layers"
        accent="blue"
        subtitle="当前活跃的通道数"
        :loading="loading"
      />

      <StatCard
        title="队列总数"
        :value="data?.queues ?? 0"
        :icon="ListTodo"
        accent="purple"
        subtitle="VHost 内声明队列"
        :loading="loading"
      />

      <StatCard
        title="消息发布速率"
        :value="data ? formatRate(data.messageRate.publish) : '--'"
        :icon="Zap"
        accent="amber"
        subtitle="每秒发布消息数"
        :loading="loading"
      />
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-3 gap-5">
      <div class="xl:col-span-2 card-gradient rounded-2xl border border-ops-border p-6">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h3 class="text-base font-semibold text-ops-text">消息流量</h3>
            <p class="text-xs text-ops-muted mt-0.5">实时消息吞吐指标</p>
          </div>
          <div class="flex gap-1 p-1 rounded-lg bg-ops-bg border border-ops-border">
            <button class="px-3 py-1 text-xs rounded-md bg-ops-primary text-white">实时</button>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div class="p-4 rounded-xl bg-ops-bg/60 border border-ops-border">
            <div class="flex items-center gap-2 mb-2">
              <div class="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                <ArrowUpRight class="w-4 h-4 text-emerald-400" />
              </div>
              <span class="text-sm text-ops-muted">Publish 速率</span>
            </div>
            <div class="text-2xl font-bold text-ops-text stat-number">
              {{ data ? formatRate(data.messageRate.publish) : '--' }}
            </div>
          </div>

          <div class="p-4 rounded-xl bg-ops-bg/60 border border-ops-border">
            <div class="flex items-center gap-2 mb-2">
              <div class="w-8 h-8 rounded-lg bg-blue-500/15 flex items-center justify-center">
                <ArrowDownRight class="w-4 h-4 text-blue-400" />
              </div>
              <span class="text-sm text-ops-muted">Deliver 速率</span>
            </div>
            <div class="text-2xl font-bold text-ops-text stat-number">
              {{ data ? formatRate(data.messageRate.deliver) : '--' }}
            </div>
          </div>

          <div class="p-4 rounded-xl bg-ops-bg/60 border border-ops-border">
            <div class="flex items-center gap-2 mb-2">
              <div class="w-8 h-8 rounded-lg bg-purple-500/15 flex items-center justify-center">
                <Zap class="w-4 h-4 text-purple-400" />
              </div>
              <span class="text-sm text-ops-muted">Ack 速率</span>
            </div>
            <div class="text-2xl font-bold text-ops-text stat-number">
              {{ data ? formatRate(data.messageRate.ack) : '--' }}
            </div>
          </div>
        </div>
      </div>

      <div class="card-gradient rounded-2xl border border-ops-border p-6">
        <div class="flex items-center justify-between mb-6">
          <div>
            <h3 class="text-base font-semibold text-ops-text">节点信息</h3>
            <p class="text-xs text-ops-muted mt-0.5">连接详情</p>
          </div>
          <Server class="w-5 h-5 text-ops-muted" />
        </div>

        <div class="space-y-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-lg bg-ops-card flex items-center justify-center">
                <HardDrive class="w-4 h-4 text-ops-muted" />
              </div>
              <span class="text-sm text-ops-muted">主机地址</span>
            </div>
            <span class="text-sm font-medium text-ops-text stat-number">
              {{ data?.connection.host ?? '--' }}:{{ data?.connection.port ?? '--' }}
            </span>
          </div>

          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-lg bg-ops-card flex items-center justify-center">
                <Clock class="w-4 h-4 text-ops-muted" />
              </div>
              <span class="text-sm text-ops-muted">运行时长</span>
            </div>
            <span class="text-sm font-medium text-ops-text stat-number">
              {{ data ? formatUptime(data.connection.uptime) : '--' }}
            </span>
          </div>

          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="w-8 h-8 rounded-lg bg-ops-card flex items-center justify-center">
                <span
                  class="status-dot"
                  :class="data?.connection.status === 'connected' ? 'status-connected' : 'status-disconnected'"
                />
              </div>
              <span class="text-sm text-ops-muted">连接状态</span>
            </div>
            <span
              class="text-sm font-medium"
              :class="data?.connection.status === 'connected' ? 'text-emerald-400' : 'text-red-400'"
            >
              {{ data?.connection.status === 'connected' ? '正常' : '异常' }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div class="card-gradient rounded-2xl border border-ops-border p-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h3 class="text-base font-semibold text-ops-text">监控说明</h3>
          <p class="text-xs text-ops-muted mt-0.5">Dashboard 指标含义</p>
        </div>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-sm">
        <div class="p-3 rounded-lg bg-ops-bg/50 border border-ops-border">
          <div class="text-ops-text font-medium mb-1">连接状态</div>
          <div class="text-ops-muted text-xs">检测 AMQP 和 Management API 双路连通性</div>
        </div>
        <div class="p-3 rounded-lg bg-ops-bg/50 border border-ops-border">
          <div class="text-ops-text font-medium mb-1">Channel 数</div>
          <div class="text-ops-muted text-xs">当前所有活跃连接上的 Channel 总数</div>
        </div>
        <div class="p-3 rounded-lg bg-ops-bg/50 border border-ops-border">
          <div class="text-ops-text font-medium mb-1">队列总数</div>
          <div class="text-ops-muted text-xs">默认 Virtual Host 下已声明的队列数量</div>
        </div>
        <div class="p-3 rounded-lg bg-ops-bg/50 border border-ops-border">
          <div class="text-ops-text font-medium mb-1">消息速率</div>
          <div class="text-ops-muted text-xs">Publish / Deliver / Ack 每秒吞吐统计</div>
        </div>
      </div>
    </div>
  </div>
</template>
