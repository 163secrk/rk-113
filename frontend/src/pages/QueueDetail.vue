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
  Skull,
  RotateCcw,
  Eye,
  CheckCircle,
  XCircle,
  FileJson,
  FileText,
  Copy,
  Hash,
  ListOrdered,
  Share2,
  KeyRound,
  Info,
  ChevronDown,
  Download,
  ArrowLeftRight,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getQueueDetail,
  purgeQueue,
  deleteQueue,
  getQueueMessages,
  ackMessage,
  rejectMessage,
  republishDeadLetter,
  republishAllDeadLetters,
  checkQueueExists,
  isDeadLetterQueue,
  type QueueDetail,
  type MessageItem,
  type DeadLetterInfo,
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

const loadingMessages = ref(false)
const messages = ref<MessageItem[]>([])
const totalMessages = ref(0)
const fetchLimit = ref(50)

const detailDialogVisible = ref(false)
const viewMode = ref<'formatted' | 'raw'>('formatted')
const selectedMessage = ref<MessageItem | null>(null)

const republishingAll = ref(false)

const queueName = computed(() => {
  const name = route.params.name as string
  return decodeURIComponent(name)
})

const isDLQ = computed(() => {
  return queueDetail.value ? isDeadLetterQueue(queueDetail.value.name) : isDeadLetterQueue(queueName.value)
})

function getDeadLetterReasonLabel(reason?: string): string {
  switch (reason) {
    case 'rejected':
      return '消息被拒绝'
    case 'expired':
      return '消息过期'
    case 'maxlen':
      return '队列长度超限'
    default:
      return reason || '未知'
  }
}

function getDeadLetterReasonClass(reason?: string): string {
  switch (reason) {
    case 'rejected':
      return 'bg-red-500/15 text-red-400'
    case 'expired':
      return 'bg-amber-500/15 text-amber-400'
    case 'maxlen':
      return 'bg-purple-500/15 text-purple-400'
    default:
      return 'bg-slate-500/15 text-slate-400'
  }
}

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
    messages.value = []
    totalMessages.value = 0
    fetchData()
  } catch {
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
  }
}

async function loadMessages(force = false) {
  loadingMessages.value = true
  try {
    const data = await getQueueMessages(queueName.value, fetchLimit.value, false)
    messages.value = data.messages
    totalMessages.value = data.total
    lastUpdated.value = new Date()
  } catch (err) {
    console.error('Failed to load messages:', err)
    messages.value = []
    totalMessages.value = 0
  } finally {
    loadingMessages.value = false
  }
}

function openDetail(msg: MessageItem) {
  selectedMessage.value = msg
  viewMode.value = isPayloadJson(msg) ? 'formatted' : 'raw'
  detailDialogVisible.value = true
}

function closeDetail() {
  detailDialogVisible.value = false
  selectedMessage.value = null
}

function isPayloadJson(msg: MessageItem): boolean {
  try {
    JSON.parse(msg.payload)
    return true
  } catch {
    return false
  }
}

function formatDisplayPayload(msg: MessageItem): string {
  if (viewMode.value === 'raw') {
    return msg.payload
  }
  try {
    const obj = JSON.parse(msg.payload)
    return JSON.stringify(obj, null, 2)
  } catch {
    return msg.payload
  }
}

function copyPayload(msg: MessageItem) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(msg.payload)
    ElMessage.success('消息体已复制')
  }
}

function downloadPayload(msg: MessageItem) {
  const blob = new Blob([msg.payload], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `message_${msg.delivery_tag}_${Date.now()}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success('已开始下载')
}

async function handleAck(msg: MessageItem) {
  try {
    await ElMessageBox.confirm(
      `确认 ACK 消息 #${msg.index}?\n\n此操作将从队列中永久移除此消息，且无法恢复！`,
      '确认消费 (ACK)',
      {
        confirmButtonText: '确认 ACK',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--primary',
      }
    )
    await ackMessage(queueName.value, msg.delivery_tag)
    ElMessage.success(`消息 #${msg.index} 已 ACK`)
    messages.value = messages.value.filter((m) => m.delivery_tag !== msg.delivery_tag)
    totalMessages.value = Math.max(0, totalMessages.value - 1)
    if (detailDialogVisible.value && selectedMessage.value?.delivery_tag === msg.delivery_tag) {
      closeDetail()
    }
  } catch {
  }
}

async function handleReject(msg: MessageItem, requeue = false) {
  const actionLabel = requeue ? '重新入队' : '丢弃'
  try {
    await ElMessageBox.confirm(
      `确认 Reject 消息 #${msg.index} (${actionLabel})?\n\n${requeue
        ? '此操作会将消息重新放回队列头部。'
        : '此操作将从队列中永久丢弃此消息，且无法恢复！'
      }`,
      `确认拒绝 (Reject - ${actionLabel})`,
      {
        confirmButtonText: `确认 Reject`,
        cancelButtonText: '取消',
        type: requeue ? 'info' : 'error',
        confirmButtonClass: requeue ? '' : 'el-button--danger',
      }
    )
    await rejectMessage(queueName.value, msg.delivery_tag, requeue)
    ElMessage.success(`消息 #${msg.index} 已 Reject (${actionLabel})`)
    messages.value = messages.value.filter((m) => m.delivery_tag !== msg.delivery_tag)
    if (!requeue) {
      totalMessages.value = Math.max(0, totalMessages.value - 1)
    }
    if (detailDialogVisible.value && selectedMessage.value?.delivery_tag === msg.delivery_tag) {
      closeDetail()
    }
  } catch {
  }
}

async function handleRepublish(msg: MessageItem) {
  const dlInfo: DeadLetterInfo | undefined = msg.dead_letter
  const originalQueue = dlInfo?.original_queue
  const originalRoutingKey = dlInfo?.original_routing_key

  try {
    const queueLabel = originalQueue ? `队列 "${originalQueue}"` : '原始队列（未识别）'
    await ElMessageBox.confirm(
      `确认将消息 #${msg.index} 重新投递到${queueLabel}？\n\n此操作会将消息从死信队列移除并发布到原始队列。`,
      '确认重新投递',
      {
        confirmButtonText: '确认投递',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    if (!originalQueue) {
      ElMessage.error('无法识别原始队列，无法自动投递')
      return
    }

    const existsCheck = await checkQueueExists(originalQueue)
    if (!existsCheck.exists) {
      ElMessage.error(`原始队列 "${originalQueue}" 不存在，无法投递`)
      return
    }

    const result = await republishDeadLetter(queueName.value, {
      delivery_tag: msg.delivery_tag,
      original_queue: originalQueue,
      original_routing_key: originalRoutingKey,
    })

    if (result.success) {
      ElMessage.success(result.message)
      messages.value = messages.value.filter((m) => m.delivery_tag !== msg.delivery_tag)
      totalMessages.value = Math.max(0, totalMessages.value - 1)
      if (detailDialogVisible.value && selectedMessage.value?.delivery_tag === msg.delivery_tag) {
        closeDetail()
      }
      fetchData()
    } else {
      ElMessage.error(result.message || '重新投递失败')
    }
  } catch (err: any) {
    if (err !== 'cancel') {
      console.error('Republish error:', err)
    }
  }
}

async function handleRepublishAll() {
  if (totalMessages.value === 0) {
    ElMessage.warning('死信队列为空，无需投递')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确认将死信队列中全部 ${totalMessages.value} 条消息重新投递到各自的原始队列？\n\n注意：如果原始队列不存在，对应消息会保留在死信队列中。`,
      '批量重新投递',
      {
        confirmButtonText: '确认全部投递',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--primary',
      }
    )

    republishingAll.value = true
    try {
      const result = await republishAllDeadLetters(queueName.value)
      if (result.success) {
        ElMessage.success(result.message)
        if (result.failed_count && result.failed_count > 0 && result.failed_details && result.failed_details.length > 0) {
          ElMessage.warning(`部分消息投递失败：${result.failed_details.slice(0, 3).join('；')}`)
        }
        await loadMessages(true)
        fetchData()
      } else {
        ElMessage.error(result.message || '批量重新投递失败')
      }
    } finally {
      republishingAll.value = false
    }
  } catch (err) {
    if (err !== 'cancel') {
      console.error('Republish all error:', err)
    }
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

function formatTimestamp(ts?: number): string {
  if (!ts) return '--'
  try {
    return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return '--'
  }
}

function getPayloadSummary(payload: string, len = 80): string {
  const clean = payload.replace(/\s+/g, ' ').trim()
  if (clean.length <= len) return clean
  return clean.slice(0, len) + '...'
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
          <h2 class="text-xl font-bold text-ops-text mb-1 flex items-center gap-2">
            <Skull v-if="isDLQ" class="w-5 h-5 text-red-400" />
            <span v-if="queueDetail" :class="{ 'text-red-400': isDLQ }">{{ queueDetail.name }}</span>
            <span v-else>队列详情</span>
            <span
              v-if="isDLQ"
              class="inline-flex items-center px-2 py-0.5 text-xs rounded-full bg-red-500/15 text-red-400 font-medium"
            >
              死信队列
            </span>
          </h2>
          <p class="text-sm text-ops-muted">
            {{ isDLQ ? '死信队列 - 查看死信消息并支持重新投递' : '队列详细信息' }}
            <span v-if="lastUpdated" class="stat-number ml-2">
              · 最后更新: {{ lastUpdated.toLocaleTimeString('zh-CN', { hour12: false }) }}
            </span>
          </p>
        </div>
      </div>
      <div class="flex items-center gap-3 flex-wrap">
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 hover:border-ops-primary/50 transition-all duration-200"
          :disabled="loading"
          @click="fetchData"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
        <button
          v-if="isDLQ"
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-sm font-medium hover:bg-emerald-500/25 transition-all duration-200"
          :disabled="republishingAll || totalMessages === 0"
          @click="handleRepublishAll"
        >
          <RotateCcw class="w-4 h-4" :class="{ 'animate-spin': republishingAll }" />
          {{ republishingAll ? '投递中...' : '全部重新投递' }}
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
            <div class="w-10 h-10 rounded-xl" :class="isDLQ ? 'bg-red-500/15' : 'bg-purple-500/15'">
              <AlertCircle class="w-5 h-5" :class="isDLQ ? 'text-red-400' : 'text-purple-400'" />
            </div>
            <div class="text-sm text-ops-muted">{{ isDLQ ? '死信消息总数' : '消息总数' }}</div>
          </div>
          <div class="text-2xl font-bold" :class="isDLQ ? 'text-red-400' : 'text-ops-text'" >
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

      <div v-if="isDLQ" class="mt-5">
        <div class="card-gradient rounded-2xl border border-ops-border overflow-hidden">
          <div class="px-6 py-5 border-b border-ops-border flex items-center justify-between flex-wrap gap-3">
            <div>
              <h3 class="text-base font-semibold text-ops-text flex items-center gap-2">
                <Skull class="w-5 h-5 text-red-400" />
                死信消息列表
              </h3>
              <p class="text-xs text-ops-muted mt-0.5">查看死信消息详情，支持逐条或批量重新投递</p>
            </div>
            <div class="flex items-center gap-3 flex-wrap">
              <select
                v-model.number="fetchLimit"
                class="px-3 py-2 rounded-lg bg-ops-bg border border-ops-border text-sm text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
                @change="loadMessages()"
              >
                <option :value="10">最近 10 条</option>
                <option :value="50">最近 50 条</option>
                <option :value="100">最近 100 条</option>
                <option :value="200">最近 200 条</option>
              </select>
              <button
                class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 hover:border-ops-primary/50 transition-all duration-200"
                :disabled="loadingMessages"
                @click="loadMessages(true)"
              >
                <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loadingMessages }" />
                加载消息
              </button>
              <div
                class="px-4 py-2 rounded-lg bg-ops-bg/50 border border-ops-border flex items-center gap-2"
              >
                <span class="text-xs text-ops-muted">已获取</span>
                <span class="text-sm font-semibold text-ops-text stat-number">
                  {{ messages.length }} / {{ totalMessages }}
                </span>
              </div>
            </div>
          </div>

          <div v-if="loadingMessages && messages.length === 0" class="p-12 text-center">
            <RefreshCw class="w-12 h-12 text-ops-muted/30 mx-auto mb-3 animate-spin" />
            <div class="text-ops-muted text-sm">加载死信消息中...</div>
          </div>

          <div v-else-if="messages.length === 0 && !loadingMessages" class="p-16 text-center">
            <Skull class="w-16 h-16 text-ops-muted/30 mx-auto mb-4" />
            <div class="text-lg font-semibold text-ops-text mb-2">暂无死信消息</div>
            <div class="text-sm text-ops-muted">点击上方"加载消息"按钮获取死信消息</div>
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full">
              <thead>
                <tr class="border-b border-ops-border">
                  <th class="text-left px-5 py-3.5 text-sm font-medium text-ops-muted w-16">
                    <div class="flex items-center gap-1.5">
                      <ListOrdered class="w-3.5 h-3.5" />
                      序号
                    </div>
                  </th>
                  <th class="text-left px-5 py-3.5 text-sm font-medium text-ops-muted w-32">
                    <div class="flex items-center gap-1.5">
                      <AlertCircle class="w-3.5 h-3.5" />
                      死信原因
                    </div>
                  </th>
                  <th class="text-left px-5 py-3.5 text-sm font-medium text-ops-muted">
                    <div class="flex items-center gap-1.5">
                      <FileJson class="w-3.5 h-3.5" />
                      消息体摘要
                    </div>
                  </th>
                  <th class="text-left px-5 py-3.5 text-sm font-medium text-ops-muted w-44">
                    <div class="flex items-center gap-1.5">
                      <Database class="w-3.5 h-3.5" />
                      原始队列
                    </div>
                  </th>
                  <th class="text-left px-5 py-3.5 text-sm font-medium text-ops-muted w-36">
                    <div class="flex items-center gap-1.5">
                      <KeyRound class="w-3.5 h-3.5" />
                      原始 Routing Key
                    </div>
                  </th>
                  <th class="text-right px-5 py-3.5 text-sm font-medium text-ops-muted w-56">
                    操作
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="msg in messages"
                  :key="msg.id + '-' + msg.delivery_tag"
                  class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
                >
                  <td class="px-5 py-4">
                    <div class="flex flex-col items-start gap-1">
                      <span class="inline-flex items-center justify-center min-w-[2rem] h-7 px-2 rounded-md bg-ops-primary/10 text-ops-primary text-sm font-mono font-semibold stat-number">
                        #{{ msg.index }}
                      </span>
                    </div>
                  </td>
                  <td class="px-5 py-4">
                    <span
                      v-if="msg.dead_letter?.reason"
                      class="inline-flex items-center px-2 py-1 text-xs rounded-full font-medium"
                      :class="getDeadLetterReasonClass(msg.dead_letter.reason)"
                    >
                      {{ getDeadLetterReasonLabel(msg.dead_letter.reason) }}
                    </span>
                    <span v-else class="inline-flex items-center px-2 py-1 text-xs rounded-full bg-slate-500/15 text-slate-400">
                      未知
                    </span>
                  </td>
                  <td class="px-5 py-4">
                    <div class="flex flex-col gap-1.5 max-w-xl">
                      <code class="font-mono text-xs leading-relaxed text-ops-text break-all">
                        {{ getPayloadSummary(msg.payload) }}
                      </code>
                      <div class="flex items-center gap-2">
                        <span
                          v-if="isPayloadJson(msg)"
                          class="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded bg-emerald-500/15 text-emerald-400"
                        >
                          JSON
                        </span>
                        <span
                          v-else
                          class="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded bg-slate-500/15 text-slate-400"
                        >
                          文本
                        </span>
                      </div>
                    </div>
                  </td>
                  <td class="px-5 py-4">
                    <code
                      v-if="msg.dead_letter?.original_queue"
                      class="font-mono text-xs text-blue-400 break-all"
                      :title="msg.dead_letter.original_queue"
                    >
                      {{ msg.dead_letter.original_queue }}
                    </code>
                    <span v-else class="text-xs text-ops-muted/50">—</span>
                  </td>
                  <td class="px-5 py-4">
                    <code
                      v-if="msg.dead_letter?.original_routing_key"
                      class="font-mono text-xs text-emerald-400 break-all"
                      :title="msg.dead_letter.original_routing_key"
                    >
                      {{ msg.dead_letter.original_routing_key }}
                    </code>
                    <span v-else class="text-xs text-ops-muted/50">—</span>
                  </td>
                  <td class="px-5 py-4 text-right">
                    <div class="flex items-center justify-end gap-1">
                      <button
                        class="p-2 rounded-lg text-ops-muted hover:text-ops-primary hover:bg-ops-primary/10 transition-all duration-150"
                        title="查看完整消息"
                        @click="openDetail(msg)"
                      >
                        <Eye class="w-4 h-4" />
                      </button>
                      <button
                        class="p-2 rounded-lg text-ops-muted hover:text-emerald-400 hover:bg-emerald-500/10 transition-all duration-150"
                        title="重新投递到原始队列"
                        :disabled="!msg.dead_letter?.original_queue"
                        @click="handleRepublish(msg)"
                      >
                        <RotateCcw class="w-4 h-4" />
                      </button>
                      <button
                        class="p-2 rounded-lg text-ops-muted hover:text-emerald-400 hover:bg-emerald-500/10 transition-all duration-150"
                        title="确认消费 (ACK)"
                        @click="handleAck(msg)"
                      >
                        <CheckCircle class="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div v-if="messages.length > 0" class="px-5 py-3 border-t border-ops-border bg-ops-bg/30 flex items-center justify-between text-xs text-ops-muted">
            <span>
              显示 <span class="text-ops-text font-semibold stat-number">{{ messages.length }}</span> 条死信消息
            </span>
            <span class="flex items-center gap-1">
              <Info class="w-3 h-3" />
              消息获取后处于未确认状态，刷新或切换页面将自动退回
            </span>
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

    <el-dialog
      v-model="detailDialogVisible"
      title="死信消息详情"
      width="900px"
      :close-on-click-modal="false"
      class="message-detail-dialog"
      @closed="closeDetail"
    >
      <div v-if="selectedMessage" class="space-y-5">
        <div v-if="selectedMessage.dead_letter" class="p-4 rounded-xl bg-red-500/10 border border-red-500/30 space-y-3">
          <div class="flex items-center gap-2 text-sm font-semibold text-red-400">
            <Skull class="w-4 h-4" />
            死信信息
          </div>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div class="p-3 rounded-lg bg-ops-bg/50 border border-ops-border/50">
              <div class="text-[10px] text-ops-muted mb-1">死信原因</div>
              <span
                class="inline-flex items-center px-2 py-1 text-xs rounded-full font-medium"
                :class="getDeadLetterReasonClass(selectedMessage.dead_letter.reason)"
              >
                {{ getDeadLetterReasonLabel(selectedMessage.dead_letter.reason) }}
              </span>
            </div>
            <div class="p-3 rounded-lg bg-ops-bg/50 border border-ops-border/50">
              <div class="text-[10px] text-ops-muted mb-1">原始队列</div>
              <code v-if="selectedMessage.dead_letter.original_queue" class="font-mono text-xs text-blue-400 break-all">
                {{ selectedMessage.dead_letter.original_queue }}
              </code>
              <span v-else class="text-xs text-ops-muted/50">—</span>
            </div>
            <div class="p-3 rounded-lg bg-ops-bg/50 border border-ops-border/50">
              <div class="text-[10px] text-ops-muted mb-1">原始 Routing Key</div>
              <code v-if="selectedMessage.dead_letter.original_routing_key" class="font-mono text-xs text-emerald-400 break-all">
                {{ selectedMessage.dead_letter.original_routing_key }}
              </code>
              <span v-else class="text-xs text-ops-muted/50">—</span>
            </div>
            <div class="p-3 rounded-lg bg-ops-bg/50 border border-ops-border/50">
              <div class="text-[10px] text-ops-muted mb-1">死信次数</div>
              <div class="text-base font-semibold text-ops-text stat-number">
                {{ selectedMessage.dead_letter.count ?? 1 }}
              </div>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div class="p-3 rounded-xl bg-ops-bg/50 border border-ops-border/50">
            <div class="text-[10px] text-ops-muted mb-1">消息序号</div>
            <div class="text-base font-bold text-ops-primary font-mono stat-number">#{{ selectedMessage.index }}</div>
          </div>
          <div class="p-3 rounded-xl bg-ops-bg/50 border border-ops-border/50">
            <div class="text-[10px] text-ops-muted mb-1">大小</div>
            <div class="text-base font-semibold text-ops-text font-mono stat-number">{{ formatBytes(selectedMessage.payload_bytes) }}</div>
          </div>
          <div class="p-3 rounded-xl bg-ops-bg/50 border border-ops-border/50">
            <div class="text-[10px] text-ops-muted mb-1">Delivery Tag</div>
            <div class="text-base font-semibold text-ops-text font-mono stat-number">{{ selectedMessage.delivery_tag }}</div>
          </div>
          <div class="p-3 rounded-xl bg-ops-bg/50 border border-ops-border/50">
            <div class="text-[10px] text-ops-muted mb-1">重投状态</div>
            <div class="text-base font-semibold">
              <span
                v-if="selectedMessage.redelivered"
                class="text-amber-400"
              >是 (Redelivered)</span>
              <span v-else class="text-emerald-400">否</span>
            </div>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="p-4 rounded-xl bg-ops-bg/50 border border-ops-border/50 space-y-2.5">
            <div class="flex items-center gap-2 text-sm font-semibold text-ops-text">
              <Share2 class="w-4 h-4 text-ops-primary" />
              路由信息
            </div>
            <div class="space-y-2 text-xs">
              <div class="flex items-start gap-2">
                <span class="text-ops-muted w-20 flex-shrink-0">Exchange:</span>
                <code class="font-mono text-ops-text break-all">{{ selectedMessage.exchange || '(default exchange)' }}</code>
              </div>
              <div class="flex items-start gap-2">
                <span class="text-ops-muted w-20 flex-shrink-0">Routing Key:</span>
                <code class="font-mono text-ops-text break-all">{{ selectedMessage.routing_key || '(empty)' }}</code>
              </div>
              <div class="flex items-start gap-2">
                <span class="text-ops-muted w-20 flex-shrink-0">Virtual Host:</span>
                <code class="font-mono text-ops-text">{{ selectedMessage.vhost }}</code>
              </div>
            </div>
          </div>

          <div class="p-4 rounded-xl bg-ops-bg/50 border border-ops-border/50 space-y-2.5">
            <div class="flex items-center gap-2 text-sm font-semibold text-ops-text">
              <Info class="w-4 h-4 text-ops-primary" />
              消息属性 (Properties)
            </div>
            <div class="space-y-2 text-xs">
              <div class="flex items-start gap-2">
                <span class="text-ops-muted w-28 flex-shrink-0">发布时间:</span>
                <code class="font-mono text-ops-text">{{ formatTimestamp(selectedMessage.properties.timestamp) }}</code>
              </div>
              <div class="flex items-start gap-2">
                <span class="text-ops-muted w-28 flex-shrink-0">Content Type:</span>
                <code class="font-mono text-ops-text">{{ selectedMessage.properties.content_type || '(not set)' }}</code>
              </div>
              <div class="flex items-start gap-2">
                <span class="text-ops-muted w-28 flex-shrink-0">Delivery Mode:</span>
                <code class="font-mono text-ops-text">
                  {{ selectedMessage.properties.delivery_mode === 2 ? '2 (持久化)' : selectedMessage.properties.delivery_mode === 1 ? '1 (非持久化)' : '(not set)' }}
                </code>
              </div>
              <div class="flex items-start gap-2">
                <span class="text-ops-muted w-28 flex-shrink-0">Priority:</span>
                <code class="font-mono text-ops-text">{{ selectedMessage.properties.priority ?? '(not set)' }}</code>
              </div>
            </div>
          </div>
        </div>

        <div class="p-4 rounded-xl bg-ops-bg/50 border border-ops-border/50 space-y-3">
          <div class="flex items-center justify-between gap-3 flex-wrap">
            <div class="flex items-center gap-2 text-sm font-semibold text-ops-text">
              <Hash class="w-4 h-4 text-ops-primary" />
              自定义 Headers
            </div>
            <span
              v-if="selectedMessage.headers && Object.keys(selectedMessage.headers).length > 0"
              class="inline-flex items-center px-2 py-0.5 text-[10px] rounded bg-blue-500/15 text-blue-400"
            >
              {{ Object.keys(selectedMessage.headers).length }} 项
            </span>
            <span v-else class="inline-flex items-center px-2 py-0.5 text-[10px] rounded bg-slate-500/15 text-slate-400">
              无 Headers
            </span>
          </div>
          <div
            v-if="selectedMessage.headers && Object.keys(selectedMessage.headers).length > 0"
            class="grid grid-cols-1 md:grid-cols-2 gap-2"
          >
            <div
              v-for="(val, key) in selectedMessage.headers"
              :key="String(key)"
              class="flex items-center gap-2 p-2 rounded-lg bg-ops-card/50 border border-ops-border/50"
            >
              <code class="font-mono text-xs text-blue-400 flex-shrink-0 w-1/3 truncate" :title="String(key)">{{ String(key) }}</code>
              <span class="text-ops-muted text-xs">=</span>
              <code class="font-mono text-xs text-ops-text break-all" :title="String(val)">{{ String(val) }}</code>
            </div>
          </div>
        </div>

        <div class="p-4 rounded-xl bg-ops-bg/50 border border-ops-border/50 space-y-3">
          <div class="flex items-center justify-between gap-3 flex-wrap">
            <div class="flex items-center gap-2 text-sm font-semibold text-ops-text">
              <FileJson class="w-4 h-4 text-ops-primary" />
              消息体 (Payload)
            </div>
            <div class="flex items-center gap-2 flex-wrap">
              <div class="flex rounded-md border border-ops-border overflow-hidden">
                <button
                  class="px-3 py-1 text-xs transition-all"
                  :class="viewMode === 'formatted'
                    ? 'bg-ops-primary/20 text-ops-primary border-r border-ops-border'
                    : 'bg-ops-card/50 text-ops-muted border-r border-ops-border hover:text-ops-text'"
                  @click="viewMode = 'formatted'"
                >
                  <span class="flex items-center gap-1.5">
                    <FileJson class="w-3 h-3" />
                    JSON 格式化
                  </span>
                </button>
                <button
                  class="px-3 py-1 text-xs transition-all"
                  :class="viewMode === 'raw'
                    ? 'bg-ops-primary/20 text-ops-primary'
                    : 'bg-ops-card/50 text-ops-muted hover:text-ops-text'"
                  @click="viewMode = 'raw'"
                >
                  <span class="flex items-center gap-1.5">
                    <FileText class="w-3 h-3" />
                    原始文本
                  </span>
                </button>
              </div>
              <button
                class="flex items-center gap-1.5 px-3 py-1 rounded-md bg-ops-card/50 border border-ops-border text-xs text-ops-muted hover:text-ops-text transition-all"
                @click="copyPayload(selectedMessage)"
              >
                <Copy class="w-3 h-3" />
                复制
              </button>
              <button
                class="flex items-center gap-1.5 px-3 py-1 rounded-md bg-ops-card/50 border border-ops-border text-xs text-ops-muted hover:text-ops-text transition-all"
                @click="downloadPayload(selectedMessage)"
              >
                <Download class="w-3 h-3" />
                下载
              </button>
            </div>
          </div>

          <div class="relative rounded-lg bg-ops-bg border border-ops-border overflow-hidden">
            <pre
              class="p-4 text-xs leading-relaxed font-mono text-ops-text overflow-x-auto max-h-96 whitespace-pre-wrap break-all"
            ><code>{{ formatDisplayPayload(selectedMessage) }}</code></pre>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-1 text-xs text-ops-muted">
            <AlertCircle class="w-3.5 h-3.5" />
            ACK / Reject / 重新投递 操作将立即作用于队列中的实际消息
          </div>
          <div class="flex items-center gap-2 flex-wrap">
            <button
              class="px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 transition-all duration-200"
              @click="detailDialogVisible = false"
            >
              关闭
            </button>
            <button
              v-if="selectedMessage && isDLQ && selectedMessage.dead_letter?.original_queue"
              class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-sm text-emerald-400 hover:bg-emerald-500/25 transition-all duration-200"
              @click="handleRepublish(selectedMessage)"
            >
              <RotateCcw class="w-4 h-4" />
              重新投递
            </button>
            <button
              v-if="selectedMessage"
              class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-sm text-emerald-400 hover:bg-emerald-500/25 transition-all duration-200"
              @click="handleAck(selectedMessage)"
            >
              <CheckCircle class="w-4 h-4" />
              ACK (确认消费)
            </button>
          </div>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
}

.message-detail-dialog :deep(.el-dialog) {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 16px;
}

.message-detail-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #334155;
  padding: 20px 24px;
}

.message-detail-dialog :deep(.el-dialog__title) {
  color: #E2E8F0;
  font-size: 18px;
  font-weight: 600;
}

.message-detail-dialog :deep(.el-dialog__body) {
  padding: 24px;
  max-height: 70vh;
  overflow-y: auto;
}

.message-detail-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #334155;
  padding: 16px 24px;
}

.message-detail-dialog :deep(.el-message-box) {
  background: #1E293B;
  border: 1px solid #334155;
}

.message-detail-dialog :deep(.el-message-box__title) {
  color: #E2E8F0;
}

.message-detail-dialog :deep(.el-message-box__message) {
  color: #94A3B8;
}

.message-detail-dialog :deep(.el-message-box__content) {
  color: #94A3B8;
}
</style>
