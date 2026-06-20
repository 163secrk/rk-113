<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, onActivated, onDeactivated, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  RefreshCw,
  ArrowLeft,
  Database,
  Clock,
  Activity,
  AlertCircle,
  Users,
  HardDrive,
  Link2,
  UserCircle,
  Settings,
  Trash2,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getQueueDetail,
  purgeQueue,
  deleteQueue,
  type QueueDetail,
} from '@/api'

defineOptions({
  name: 'QueueDetail',
})

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const queueDetail = ref<QueueDetail | null>(null)
const lastUpdated = ref<Date | null>(null)
let refreshTimer: number | null = null
let isActive = false
let isFetching = false
let hasLoaded = false
let currentQueueName = ''

const queueName = computed(() => {
  const name = route.params.name as string
  return decodeURIComponent(name)
})



async function fetchData(forceRefresh: boolean | Event = false) {
  const isForce = typeof forceRefresh === 'boolean' ? forceRefresh : false
  if (isFetching && !isForce) return
  if (!isActive) return

  const name = queueName.value
  currentQueueName = name

  try {
    isFetching = true
    if (!hasLoaded || isForce) {
      loading.value = true
    }
    const data = await getQueueDetail(name)
    if (currentQueueName !== name) return
    queueDetail.value = data
    lastUpdated.value = new Date()
    hasLoaded = true
  } catch (err: any) {
    if (currentQueueName !== name) return
    console.error('Failed to fetch queue detail:', err)
    if (err.response?.status === 404) {
      ElMessage.error(`队列 "${name}" 不存在`)
      router.push('/queues')
    }
  } finally {
    if (currentQueueName === name) {
      loading.value = false
      isFetching = false
    }
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

function goBack() {
  router.push('/queues')
}

async function handlePurge() {
  if (!queueDetail.value) return
  try {
    await ElMessageBox.confirm(
      `确定要清空队列 "${queueDetail.value.name}" 吗？\n\n此操作将删除队列中所有消息，且无法恢复！`,
      '清空队列',
      {
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await purgeQueue(queueDetail.value.name)
    ElMessage.success(`队列 "${queueDetail.value.name}" 已清空`)
    fetchData()
  } catch {
    // 用户取消操作
  }
}

async function handleDelete() {
  if (!queueDetail.value) return
  try {
    await ElMessageBox.confirm(
      `确定要删除队列 "${queueDetail.value.name}" 吗？\n\n此操作将永久删除队列及其所有消息，且无法恢复！`,
      '删除队列',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await deleteQueue(queueDetail.value.name)
    ElMessage.success(`队列 "${queueDetail.value.name}" 已删除`)
    router.push('/queues')
  } catch {
    // 用户取消操作
  }
}

function formatNumber(n: number): string {
  return n.toLocaleString('zh-CN')
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

function formatJson(obj: Record<string, unknown>): string {
  if (!obj || Object.keys(obj).length === 0) return '{}'
  return JSON.stringify(obj, null, 2)
}

function getStatusText(status: string): string {
  return status === 'running' ? '运行中' : '空闲'
}

function getStatusClass(status: string): string {
  return status === 'running'
    ? 'bg-emerald-500/15 text-emerald-400'
    : 'bg-slate-500/15 text-slate-400'
}

onMounted(() => {
  isActive = true
  currentQueueName = queueName.value
  fetchData()
  startRefreshTimer()
})

onActivated(() => {
  isActive = true
  if (currentQueueName !== queueName.value || !hasLoaded) {
    currentQueueName = queueName.value
    hasLoaded = false
    queueDetail.value = null
    fetchData(true)
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
      <div class="flex items-center gap-4">
        <button
          class="p-2 rounded-lg bg-ops-card border border-ops-border text-ops-muted hover:text-ops-text hover:border-ops-primary/50 transition-all duration-200"
          @click="goBack"
        >
          <ArrowLeft class="w-5 h-5" />
        </button>
        <div>
          <h2 class="text-xl font-bold text-ops-text mb-1">
            <span v-if="queueDetail">{{ queueDetail.name }}</span>
            <span v-else>队列详情</span>
          </h2>
          <p class="text-sm text-ops-muted">
            队列详细信息
            <span v-if="lastUpdated" class="stat-number ml-2">
              · 最后更新: {{ lastUpdated.toLocaleTimeString('zh-CN', { hour12: false }) }}
            </span>
          </p>
        </div>
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
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/15 border border-amber-500/30 text-amber-400 text-sm font-medium hover:bg-amber-500/25 transition-all duration-200"
          @click="handlePurge"
        >
          <Trash2 class="w-4 h-4" />
          清空队列
        </button>
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/15 border border-red-500/30 text-red-400 text-sm font-medium hover:bg-red-500/25 transition-all duration-200"
          @click="handleDelete"
        >
          <Trash2 class="w-4 h-4" />
          删除队列
        </button>
      </div>
    </div>

    <div v-if="!loading && queueDetail">
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
        <div class="card-gradient rounded-2xl border border-ops-border p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-xl bg-blue-500/15 flex items-center justify-center">
              <Clock class="w-5 h-5 text-blue-400" />
            </div>
            <div class="text-sm text-ops-muted">Ready 消息</div>
          </div>
          <div class="text-2xl font-bold text-ops-text stat-number">
            {{ formatNumber(queueDetail.ready) }}
          </div>
        </div>

        <div class="card-gradient rounded-2xl border border-ops-border p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-xl bg-amber-500/15 flex items-center justify-center">
              <Activity class="w-5 h-5 text-amber-400" />
            </div>
            <div class="text-sm text-ops-muted">Unacked 消息</div>
          </div>
          <div class="text-2xl font-bold text-amber-400 stat-number">
            {{ formatNumber(queueDetail.unacked) }}
          </div>
        </div>

        <div class="card-gradient rounded-2xl border border-ops-border p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-xl bg-purple-500/15 flex items-center justify-center">
              <AlertCircle class="w-5 h-5 text-purple-400" />
            </div>
            <div class="text-sm text-ops-muted">消息总数</div>
          </div>
          <div class="text-2xl font-bold text-ops-text stat-number">
            {{ formatNumber(queueDetail.total) }}
          </div>
        </div>

        <div class="card-gradient rounded-2xl border border-ops-border p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center">
              <Users class="w-5 h-5 text-emerald-400" />
            </div>
            <div class="text-sm text-ops-muted">消费者数量</div>
          </div>
          <div class="text-2xl font-bold text-ops-text stat-number">
            {{ formatNumber(queueDetail.consumers) }}
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 xl:grid-cols-3 gap-5 mt-5">
        <div class="card-gradient rounded-2xl border border-ops-border p-6">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-base font-semibold text-ops-text flex items-center gap-2">
                <Settings class="w-5 h-5 text-ops-muted" />
                队列属性
              </h3>
              <p class="text-xs text-ops-muted mt-0.5">队列配置信息</p>
            </div>
          </div>

          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-sm text-ops-muted">Virtual Host</span>
              </div>
              <span class="text-sm font-medium text-ops-text stat-number">
                {{ queueDetail.vhost }}
              </span>
            </div>

            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-sm text-ops-muted">所在节点</span>
              </div>
              <span class="text-sm font-medium text-ops-text stat-number">
                {{ queueDetail.node || '--' }}
              </span>
            </div>

            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-sm text-ops-muted">状态</span>
              </div>
              <div class="flex items-center gap-2">
                <span
                  class="status-dot"
                  :class="queueDetail.status === 'running' ? 'status-connected' : 'bg-slate-500'"
                />
                <span
                  class="inline-flex items-center px-2 py-1 text-xs rounded-full"
                  :class="getStatusClass(queueDetail.status)"
                >
                  {{ getStatusText(queueDetail.status) }}
                </span>
              </div>
            </div>

            <div class="pt-3 border-t border-ops-border">
              <div class="grid grid-cols-3 gap-3">
                <label class="flex flex-col items-center gap-2 p-3 rounded-xl bg-ops-bg/50 border border-ops-border">
                  <input
                    v-model="queueDetail.durable"
                    type="checkbox"
                    disabled
                    class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary"
                  />
                  <span class="text-xs text-ops-text">Durable</span>
                </label>
                <label class="flex flex-col items-center gap-2 p-3 rounded-xl bg-ops-bg/50 border border-ops-border">
                  <input
                    v-model="queueDetail.auto_delete"
                    type="checkbox"
                    disabled
                    class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary"
                  />
                  <span class="text-xs text-ops-text">Auto-delete</span>
                </label>
                <label class="flex flex-col items-center gap-2 p-3 rounded-xl bg-ops-bg/50 border border-ops-border">
                  <input
                    v-model="queueDetail.exclusive"
                    type="checkbox"
                    disabled
                    class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary"
                  />
                  <span class="text-xs text-ops-text">Exclusive</span>
                </label>
              </div>
            </div>

            <div class="pt-3 border-t border-ops-border">
              <div class="flex items-center gap-2 mb-2">
                <span class="text-sm text-ops-muted">Arguments</span>
              </div>
              <pre class="p-3 rounded-xl bg-ops-bg/50 border border-ops-border text-xs text-ops-text font-mono overflow-x-auto">
{{ formatJson(queueDetail.arguments) }}</pre
              >
            </div>

            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <HardDrive class="w-4 h-4 text-ops-muted" />
                <span class="text-sm text-ops-muted">内存占用</span>
              </div>
              <span class="text-sm font-medium text-ops-text stat-number">
                {{ formatBytes(queueDetail.memory) }}
              </span>
            </div>

            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-sm text-ops-muted">Policy</span>
              </div>
              <span class="text-sm font-medium text-ops-text">
                {{ queueDetail.policy || '--' }}
              </span>
            </div>
          </div>
        </div>

        <div class="xl:col-span-2 space-y-5">
          <div class="card-gradient rounded-2xl border border-ops-border p-6">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="text-base font-semibold text-ops-text flex items-center gap-2">
                  <Link2 class="w-5 h-5 text-ops-muted" />
                  绑定信息
                </h3>
                <p class="text-xs text-ops-muted mt-0.5">队列绑定的交换机和路由键</p>
              </div>
              <span class="px-2 py-1 text-xs rounded-full bg-ops-bg text-ops-muted">
                {{ queueDetail.bindings.length }} 个绑定
              </span>
            </div>

            <div v-if="queueDetail.bindings.length > 0" class="space-y-3">
              <div
                v-for="(binding, index) in queueDetail.bindings"
                :key="index"
                class="p-4 rounded-xl bg-ops-bg/50 border border-ops-border"
              >
                <div class="flex items-center gap-3 flex-wrap">
                  <div class="flex items-center gap-2">
                    <span class="text-xs text-ops-muted">Exchange:</span>
                    <code class="px-2 py-0.5 text-xs rounded bg-blue-500/15 text-blue-400 font-mono">
                      {{ binding.exchange || '(default)' }}
                    </code>
                  </div>
                  <div class="flex items-center gap-2">
                    <span class="text-xs text-ops-muted">Routing Key:</span>
                    <code class="px-2 py-0.5 text-xs rounded bg-emerald-500/15 text-emerald-400 font-mono">
                      {{ binding.routing_key || '(empty)' }}
                    </code>
                  </div>
                </div>
                <div v-if="binding.arguments && Object.keys(binding.arguments).length > 0" class="mt-2">
                  <span class="text-xs text-ops-muted">Arguments:</span>
                  <pre class="mt-1 p-2 rounded-lg bg-ops-card/50 text-xs text-ops-text font-mono overflow-x-auto">
{{ formatJson(binding.arguments) }}</pre
                  >
                </div>
              </div>
            </div>

            <div v-else class="py-8 text-center">
              <Link2 class="w-12 h-12 text-ops-muted/30 mx-auto mb-3" />
              <div class="text-ops-muted text-sm">暂无绑定信息</div>
            </div>
          </div>

          <div class="card-gradient rounded-2xl border border-ops-border p-6">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="text-base font-semibold text-ops-text flex items-center gap-2">
                  <UserCircle class="w-5 h-5 text-ops-muted" />
                  消费者列表
                </h3>
                <p class="text-xs text-ops-muted mt-0.5">当前活跃的消费者</p>
              </div>
              <span class="px-2 py-1 text-xs rounded-full bg-ops-bg text-ops-muted">
                {{ queueDetail.consumer_list.length }} 个消费者
              </span>
            </div>

            <div v-if="queueDetail.consumer_list.length > 0" class="space-y-3">
              <div
                v-for="(consumer, index) in queueDetail.consumer_list"
                :key="index"
                class="p-4 rounded-xl bg-ops-bg/50 border border-ops-border"
              >
                <div class="flex items-center justify-between mb-2">
                  <div class="flex items-center gap-2">
                    <UserCircle class="w-4 h-4 text-ops-muted" />
                    <code class="text-xs text-ops-text font-mono">
                      {{ consumer.consumer_tag || '(anonymous)' }}
                    </code>
                  </div>
                  <div class="flex items-center gap-2">
                    <span
                      v-if="consumer.ack_required"
                      class="px-2 py-0.5 text-xs rounded bg-amber-500/15 text-amber-400"
                    >
                      Ack Required
                    </span>
                    <span
                      v-if="consumer.exclusive"
                      class="px-2 py-0.5 text-xs rounded bg-purple-500/15 text-purple-400"
                    >
                      Exclusive
                    </span>
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span class="text-ops-muted">Channel:</span>
                    <span class="ml-2 text-ops-text stat-number">
                      {{ consumer.channel_details?.name || '--' }}
                    </span>
                  </div>
                  <div>
                    <span class="text-ops-muted">User:</span>
                    <span class="ml-2 text-ops-text">
                      {{ consumer.channel_details?.user || '--' }}
                    </span>
                  </div>
                  <div>
                    <span class="text-ops-muted">Connection:</span>
                    <span class="ml-2 text-ops-text stat-number">
                      {{ consumer.channel_details?.connection_name || '--' }}
                    </span>
                  </div>
                  <div>
                    <span class="text-ops-muted">Node:</span>
                    <span class="ml-2 text-ops-text stat-number">
                      {{ consumer.channel_details?.node || '--' }}
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="py-8 text-center">
              <UserCircle class="w-12 h-12 text-ops-muted/30 mx-auto mb-3" />
              <div class="text-ops-muted text-sm">暂无活跃消费者</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading && !queueDetail">
      <div class="card-gradient rounded-2xl border border-ops-border p-12 text-center">
        <RefreshCw class="w-12 h-12 text-ops-muted/30 mx-auto mb-3 animate-spin" />
        <div class="text-ops-muted text-sm">加载中...</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
