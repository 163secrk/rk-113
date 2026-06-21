<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import {
  Database,
  RefreshCw,
  Eye,
  CheckCircle,
  XCircle,
  ChevronDown,
  FileJson,
  FileText,
  Copy,
  Hash,
  Clock,
  ListOrdered,
  Share2,
  KeyRound,
  AlertCircle,
  Filter,
  Download,
  Info,
  ArrowLeftRight,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getQueues,
  getQueueMessages,
  ackMessage,
  rejectMessage,
  bulkAckMessages,
  bulkRejectMessages,
  type QueueListItem,
  type MessageItem,
} from '@/api'

defineOptions({
  name: 'BrowseMessages',
})

const selectedQueue = ref('')
const queues = ref<QueueListItem[]>([])
const loadingQueues = ref(false)
const loadingMessages = ref(false)
const messages = ref<MessageItem[]>([])
const totalMessages = ref(0)
const fetchLimit = ref(50)
const lastUpdated = ref<Date | null>(null)

const isActive = false
let hasLoaded = false

const detailDialogVisible = ref(false)
const viewMode = ref<'formatted' | 'raw'>('formatted')
const selectedMessage = ref<MessageItem | null>(null)

const searchedPayload = ref('')
const filterMode = ref<'all' | 'with_headers' | 'redelivered'>('all')

const selectedDeliveryTags = ref<number[]>([])
const isAllSelected = computed(() => {
  return filteredMessages.value.length > 0 && filteredMessages.value.every((m) => selectedDeliveryTags.value.includes(m.delivery_tag))
})
const isIndeterminate = computed(() => {
  const selectedInFiltered = filteredMessages.value.filter((m) => selectedDeliveryTags.value.includes(m.delivery_tag)).length
  return selectedInFiltered > 0 && selectedInFiltered < filteredMessages.value.length
})

const filteredMessages = computed(() => {
  let result = messages.value
  if (filterMode.value === 'with_headers') {
    result = result.filter((m) => m.headers && Object.keys(m.headers).length > 0)
  } else if (filterMode.value === 'redelivered') {
    result = result.filter((m) => m.redelivered)
  }
  if (searchedPayload.value.trim()) {
    const kw = searchedPayload.value.trim().toLowerCase()
    result = result.filter((m) => m.payload.toLowerCase().includes(kw))
  }
  return result
})

function getPayloadSummary(payload: string, len = 80): string {
  const clean = payload.replace(/\s+/g, ' ').trim()
  if (clean.length <= len) return clean
  return clean.slice(0, len) + '...'
}

function formatTimestamp(ts?: number): string {
  if (!ts) return '--'
  try {
    return new Date(ts * 1000).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return '--'
  }
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
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

function isPayloadJson(msg: MessageItem): boolean {
  try {
    JSON.parse(msg.payload)
    return true
  } catch {
    return false
  }
}

function copyPayload(msg: MessageItem) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(msg.payload)
    ElMessage.success('消息体已复制')
  }
}

async function loadQueues() {
  loadingQueues.value = true
  try {
    queues.value = await getQueues()
  } catch (err) {
    console.error('Failed to load queues:', err)
    ElMessage.error('加载队列列表失败')
  } finally {
    loadingQueues.value = false
  }
}

async function loadMessages(force = false) {
  if (!selectedQueue.value) {
    messages.value = []
    totalMessages.value = 0
    return
  }
  loadingMessages.value = true
  try {
    const data = await getQueueMessages(selectedQueue.value, fetchLimit.value, false)
    messages.value = data.messages
    totalMessages.value = data.total
    lastUpdated.value = new Date()
    hasLoaded = true
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
    await ackMessage(selectedQueue.value, msg.delivery_tag)
    ElMessage.success(`消息 #${msg.index} 已 ACK`)
    messages.value = messages.value.filter((m) => m.delivery_tag !== msg.delivery_tag)
    totalMessages.value = Math.max(0, totalMessages.value - 1)
    if (detailDialogVisible.value && selectedMessage.value?.delivery_tag === msg.delivery_tag) {
      closeDetail()
    }
  } catch {
    // user cancelled
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
    await rejectMessage(selectedQueue.value, msg.delivery_tag, requeue)
    ElMessage.success(`消息 #${msg.index} 已 Reject (${actionLabel})`)
    messages.value = messages.value.filter((m) => m.delivery_tag !== msg.delivery_tag)
    if (!requeue) {
      totalMessages.value = Math.max(0, totalMessages.value - 1)
    }
    if (detailDialogVisible.value && selectedMessage.value?.delivery_tag === msg.delivery_tag) {
      closeDetail()
    }
  } catch {
    // user cancelled
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

function toggleSelectAll() {
  if (isAllSelected.value) {
    selectedDeliveryTags.value = selectedDeliveryTags.value.filter(
      (tag) => !filteredMessages.value.some((m) => m.delivery_tag === tag)
    )
  } else {
    const filteredTags = filteredMessages.value.map((m) => m.delivery_tag)
    const newTags = [...new Set([...selectedDeliveryTags.value, ...filteredTags])]
    selectedDeliveryTags.value = newTags
  }
}

function toggleSelectOne(deliveryTag: number) {
  const idx = selectedDeliveryTags.value.indexOf(deliveryTag)
  if (idx >= 0) {
    selectedDeliveryTags.value.splice(idx, 1)
  } else {
    selectedDeliveryTags.value.push(deliveryTag)
  }
}

function clearSelection() {
  selectedDeliveryTags.value = []
}

async function handleBulkAck() {
  if (selectedDeliveryTags.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确认 ACK 选中的 ${selectedDeliveryTags.value.length} 条消息?\n\n此操作将从队列中永久移除这些消息，且无法恢复！`,
      '批量确认消费 (ACK)',
      {
        confirmButtonText: '确认 ACK',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--primary',
      }
    )
    const result = await bulkAckMessages(selectedQueue.value, selectedDeliveryTags.value)
    if (result.success) {
      ElMessage.success(`批量 ACK 完成：成功 ${result.success_count} 条，失败 ${result.failed_count} 条`)
    } else {
      ElMessage.error(result.message || '批量 ACK 失败')
    }
    messages.value = messages.value.filter((m) => !selectedDeliveryTags.value.includes(m.delivery_tag))
    totalMessages.value = Math.max(0, totalMessages.value - (result?.success_count ?? selectedDeliveryTags.value.length))
    clearSelection()
    if (detailDialogVisible.value && selectedMessage.value && selectedDeliveryTags.value.includes(selectedMessage.value.delivery_tag)) {
      closeDetail()
    }
  } catch {
  }
}

async function handleBulkReject(requeue = false) {
  if (selectedDeliveryTags.value.length === 0) return
  const actionLabel = requeue ? '重新入队' : '丢弃'
  try {
    await ElMessageBox.confirm(
      `确认 Reject 选中的 ${selectedDeliveryTags.value.length} 条消息 (${actionLabel})?\n\n${requeue
        ? '此操作会将消息重新放回队列头部。'
        : '此操作将从队列中永久丢弃这些消息，且无法恢复！'
      }`,
      `批量拒绝 (Reject - ${actionLabel})`,
      {
        confirmButtonText: `确认 Reject`,
        cancelButtonText: '取消',
        type: requeue ? 'info' : 'error',
        confirmButtonClass: requeue ? '' : 'el-button--danger',
      }
    )
    const result = await bulkRejectMessages(selectedQueue.value, selectedDeliveryTags.value, requeue)
    if (result.success) {
      ElMessage.success(`批量 Reject 完成：成功 ${result.success_count} 条，失败 ${result.failed_count} 条`)
    } else {
      ElMessage.error(result.message || '批量 Reject 失败')
    }
    messages.value = messages.value.filter((m) => !selectedDeliveryTags.value.includes(m.delivery_tag))
    if (!requeue) {
      totalMessages.value = Math.max(0, totalMessages.value - (result?.success_count ?? selectedDeliveryTags.value.length))
    }
    clearSelection()
    if (detailDialogVisible.value && selectedMessage.value && selectedDeliveryTags.value.includes(selectedMessage.value.delivery_tag)) {
      closeDetail()
    }
  } catch {
  }
}

function handleBulkExport() {
  if (selectedDeliveryTags.value.length === 0) return
  const selectedMsgs = messages.value.filter((m) => selectedDeliveryTags.value.includes(m.delivery_tag))
  if (selectedMsgs.length === 0) {
    ElMessage.warning('没有可导出的消息')
    return
  }
  const exportData = selectedMsgs.map((m) => ({
    index: m.index,
    delivery_tag: m.delivery_tag,
    payload: m.payload,
    exchange: m.exchange,
    routing_key: m.routing_key,
    headers: m.headers,
    properties: m.properties,
    redelivered: m.redelivered,
    vhost: m.vhost,
  }))
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `messages_${selectedQueue.value || 'export'}_${Date.now()}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出 ${selectedMsgs.length} 条消息`)
}

onMounted(() => {
  loadQueues()
})

onActivated(() => {
  if (queues.value.length === 0) {
    loadQueues()
  }
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div>
        <h2 class="text-xl font-bold text-ops-text mb-1">消息浏览</h2>
        <p class="text-sm text-ops-muted">
          查看队列中的消息，支持查看详情、ACK 确认和 Reject 拒绝
          <span v-if="lastUpdated" class="stat-number ml-2">
            · 最后更新: {{ lastUpdated.toLocaleTimeString('zh-CN', { hour12: false }) }}
          </span>
        </p>
      </div>
      <div class="flex items-center gap-3 flex-wrap">
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 hover:border-ops-primary/50 transition-all duration-200"
          :disabled="loadingMessages || !selectedQueue"
          @click="loadMessages(true)"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loadingMessages }" />
          刷新
        </button>
      </div>
    </div>

    <div class="card-gradient rounded-2xl border border-ops-border p-5 space-y-4">
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 items-end">
        <div class="lg:col-span-4">
          <label class="block text-sm font-medium text-ops-text mb-2">
            <div class="flex items-center gap-2">
              <Database class="w-4 h-4 text-ops-muted" />
              选择队列 <span class="text-red-400">*</span>
            </div>
          </label>
          <select
            v-model="selectedQueue"
            class="w-full px-4 py-2.5 rounded-lg bg-ops-bg border border-ops-border text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
            @change="loadMessages()"
          >
            <option value="" disabled>
              {{ loadingQueues ? '加载中...' : '请选择要查看的队列' }}
            </option>
            <option
              v-for="q in queues"
              :key="q.name"
              :value="q.name"
            >
              {{ q.name }} (Ready: {{ q.ready }} / Unacked: {{ q.unacked }} / Total: {{ q.total }})
            </option>
          </select>
        </div>

        <div class="lg:col-span-3">
          <label class="block text-sm font-medium text-ops-text mb-2">
            <div class="flex items-center gap-2">
              <ListOrdered class="w-4 h-4 text-ops-muted" />
              获取数量
            </div>
          </label>
          <select
            v-model.number="fetchLimit"
            class="w-full px-4 py-2.5 rounded-lg bg-ops-bg border border-ops-border text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
            @change="loadMessages()"
          >
            <option :value="10">最近 10 条</option>
            <option :value="50">最近 50 条</option>
            <option :value="100">最近 100 条</option>
            <option :value="200">最近 200 条</option>
            <option :value="500">最近 500 条</option>
          </select>
        </div>

        <div class="lg:col-span-3">
          <label class="block text-sm font-medium text-ops-text mb-2">
            <div class="flex items-center gap-2">
              <Filter class="w-4 h-4 text-ops-muted" />
              筛选条件
            </div>
          </label>
          <select
            v-model="filterMode"
            class="w-full px-4 py-2.5 rounded-lg bg-ops-bg border border-ops-border text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
          >
            <option value="all">全部消息</option>
            <option value="with_headers">含 Headers</option>
            <option value="redelivered">已重投 (Redelivered)</option>
          </select>
        </div>

        <div class="lg:col-span-2">
          <div
            v-if="selectedQueue"
            class="w-full px-4 py-2.5 rounded-lg bg-ops-bg border border-ops-border flex items-center justify-between"
          >
            <div class="flex flex-col">
              <span class="text-[10px] text-ops-muted">已获取</span>
              <span class="text-sm font-semibold text-ops-text stat-number">
                {{ messages.length }} / {{ totalMessages }}
              </span>
            </div>
            <ChevronDown class="w-4 h-4 text-ops-muted" />
          </div>
        </div>
      </div>

      <div v-if="selectedQueue">
        <label class="block text-sm font-medium text-ops-text mb-2">
          <div class="flex items-center gap-2">
            <FileJson class="w-4 h-4 text-ops-muted" />
            搜索消息体 (按内容过滤)
          </div>
        </label>
        <input
          v-model="searchedPayload"
          type="text"
          placeholder="输入关键词搜索消息体内容..."
          class="w-full px-4 py-2.5 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150 font-mono text-sm"
        />
      </div>
    </div>

    <div v-if="!selectedQueue" class="card-gradient rounded-2xl border border-ops-border p-16 text-center">
      <Database class="w-16 h-16 text-ops-muted/30 mx-auto mb-4" />
      <div class="text-lg font-semibold text-ops-text mb-2">请先选择一个队列</div>
      <div class="text-sm text-ops-muted">从上方下拉菜单中选择要浏览消息的队列</div>
    </div>

    <template v-else>
      <div v-if="loadingMessages && messages.length === 0">
        <div class="card-gradient rounded-2xl border border-ops-border p-12 text-center">
          <RefreshCw class="w-12 h-12 text-ops-muted/30 mx-auto mb-3 animate-spin" />
          <div class="text-ops-muted text-sm">加载消息中...</div>
        </div>
      </div>

      <div v-else-if="filteredMessages.length === 0" class="card-gradient rounded-2xl border border-ops-border p-16 text-center">
        <FileText class="w-16 h-16 text-ops-muted/30 mx-auto mb-4" />
        <div class="text-lg font-semibold text-ops-text mb-2">
          {{ messages.length === 0 ? '该队列暂无消息' : '没有符合筛选条件的消息' }}
        </div>
        <div class="text-sm text-ops-muted">
          {{ messages.length === 0 ? '队列中还没有待处理的消息' : '请尝试调整搜索关键词或筛选条件' }}
        </div>
      </div>

      <div v-else class="card-gradient rounded-2xl border border-ops-border overflow-hidden">
        <div v-if="selectedDeliveryTags.length > 0" class="px-5 py-3 border-b border-ops-border bg-ops-primary/5 flex items-center justify-between flex-wrap gap-3">
          <div class="flex items-center gap-2 text-sm">
            <span class="text-ops-muted">已选择</span>
            <span class="inline-flex items-center justify-center min-w-[2rem] h-7 px-2 rounded-md bg-ops-primary/15 text-ops-primary font-semibold stat-number">
              {{ selectedDeliveryTags.length }}
            </span>
            <span class="text-ops-muted">条消息</span>
            <button
              class="ml-2 text-xs text-ops-muted hover:text-ops-text underline underline-offset-2 transition-colors"
              @click="clearSelection"
            >
              清除选择
            </button>
          </div>
          <div class="flex items-center gap-2 flex-wrap">
            <button
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-xs text-emerald-400 hover:bg-emerald-500/25 transition-all duration-200"
              @click="handleBulkAck"
            >
              <CheckCircle class="w-3.5 h-3.5" />
              批量 ACK
            </button>
            <button
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/15 border border-red-500/30 text-xs text-red-400 hover:bg-red-500/25 transition-all duration-200"
              @click="handleBulkReject(false)"
            >
              <XCircle class="w-3.5 h-3.5" />
              批量丢弃
            </button>
            <button
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/15 border border-amber-500/30 text-xs text-amber-400 hover:bg-amber-500/25 transition-all duration-200"
              @click="handleBulkReject(true)"
            >
              <XCircle class="w-3.5 h-3.5" />
              批量重新入队
            </button>
            <button
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-500/15 border border-blue-500/30 text-xs text-blue-400 hover:bg-blue-500/25 transition-all duration-200"
              @click="handleBulkExport"
            >
              <Download class="w-3.5 h-3.5" />
              批量导出 JSON
            </button>
          </div>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-ops-border">
                <th class="text-left px-5 py-3.5 text-sm font-medium text-ops-muted w-12">
                  <input
                    type="checkbox"
                    :checked="isAllSelected"
                    :indeterminate="isIndeterminate"
                    class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary cursor-pointer"
                    @change="toggleSelectAll"
                  />
                </th>
                <th class="text-left px-5 py-3.5 text-sm font-medium text-ops-muted w-16">
                  <div class="flex items-center gap-1.5">
                    <ListOrdered class="w-3.5 h-3.5" />
                    序号
                  </div>
                </th>
                <th class="text-left px-5 py-3.5 text-sm font-medium text-ops-muted">
                  <div class="flex items-center gap-1.5">
                    <FileJson class="w-3.5 h-3.5" />
                    消息体摘要
                  </div>
                </th>
                <th class="text-left px-5 py-3.5 text-sm font-medium text-ops-muted w-36">
                  <div class="flex items-center gap-1.5">
                    <Hash class="w-3.5 h-3.5" />
                    Headers
                  </div>
                </th>
                <th class="text-left px-5 py-3.5 text-sm font-medium text-ops-muted w-52">
                  <div class="flex items-center gap-1.5">
                    <Clock class="w-3.5 h-3.5" />
                    发布时间
                  </div>
                </th>
                <th class="text-center px-5 py-3.5 text-sm font-medium text-ops-muted w-36">
                  <div class="flex items-center justify-center gap-1.5">
                    <ArrowLeftRight class="w-3.5 h-3.5" />
                    路由信息
                  </div>
                </th>
                <th class="text-center px-5 py-3.5 text-sm font-medium text-ops-muted w-24">
                  大小
                </th>
                <th class="text-right px-5 py-3.5 text-sm font-medium text-ops-muted w-40">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="msg in filteredMessages"
                :key="msg.id + '-' + msg.delivery_tag"
                class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
                :class="{ 'bg-ops-primary/5': selectedDeliveryTags.includes(msg.delivery_tag) }"
              >
                <td class="px-5 py-4">
                  <input
                    type="checkbox"
                    :value="msg.delivery_tag"
                    :checked="selectedDeliveryTags.includes(msg.delivery_tag)"
                    class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary cursor-pointer"
                    @change="toggleSelectOne(msg.delivery_tag)"
                  />
                </td>
                <td class="px-5 py-4">
                  <div class="flex flex-col items-start gap-1">
                    <span class="inline-flex items-center justify-center min-w-[2rem] h-7 px-2 rounded-md bg-ops-primary/10 text-ops-primary text-sm font-mono font-semibold stat-number">
                      #{{ msg.index }}
                    </span>
                    <span
                      v-if="msg.redelivered"
                      class="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded bg-amber-500/15 text-amber-400"
                    >
                      已重投
                    </span>
                  </div>
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
                  <div v-if="msg.headers && Object.keys(msg.headers).length > 0" class="flex flex-wrap gap-1.5 max-w-xs">
                    <span
                      v-for="(val, key) in msg.headers"
                      :key="String(key)"
                      class="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded bg-blue-500/15 text-blue-400 font-mono"
                      :title="`${key}: ${val}`"
                    >
                      {{ String(key) }}
                    </span>
                    <span
                      v-if="Object.keys(msg.headers).length > 3"
                      class="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded bg-slate-500/15 text-slate-400"
                    >
                      +{{ Object.keys(msg.headers).length - 3 }}
                    </span>
                  </div>
                  <span v-else class="text-xs text-ops-muted/50">—</span>
                </td>
                <td class="px-5 py-4">
                  <div class="flex flex-col gap-1">
                    <span class="text-xs text-ops-text stat-number">
                      {{ formatTimestamp(msg.properties.timestamp) }}
                    </span>
                    <span
                      v-if="msg.properties.message_id"
                      class="text-[10px] text-ops-muted font-mono truncate max-w-40"
                      :title="msg.properties.message_id"
                    >
                      ID: {{ msg.properties.message_id }}
                    </span>
                  </div>
                </td>
                <td class="px-5 py-4 text-center">
                  <div class="flex flex-col items-center gap-1">
                    <div class="flex items-center gap-1 text-xs text-ops-muted">
                      <Share2 class="w-3 h-3" />
                      <span class="font-mono truncate max-w-28" :title="msg.exchange">{{ msg.exchange || '(default)' }}</span>
                    </div>
                    <div v-if="msg.routing_key" class="flex items-center gap-1 text-[10px] text-ops-primary">
                      <KeyRound class="w-2.5 h-2.5" />
                      <span class="font-mono truncate max-w-28" :title="msg.routing_key">{{ msg.routing_key }}</span>
                    </div>
                  </div>
                </td>
                <td class="px-5 py-4 text-center text-xs text-ops-muted font-mono stat-number">
                  {{ formatBytes(msg.payload_bytes) }}
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
                      title="确认消费 (ACK)"
                      @click="handleAck(msg)"
                    >
                      <CheckCircle class="w-4 h-4" />
                    </button>
                    <button
                      class="p-2 rounded-lg text-ops-muted hover:text-red-400 hover:bg-red-500/10 transition-all duration-150"
                      title="拒绝并丢弃 (Reject)"
                      @click="handleReject(msg, false)"
                    >
                      <XCircle class="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="px-5 py-3 border-t border-ops-border bg-ops-bg/30 flex items-center justify-between text-xs text-ops-muted">
          <span>
            显示 <span class="text-ops-text font-semibold stat-number">{{ filteredMessages.length }}</span> 条消息
            <span v-if="searchedPayload || filterMode !== 'all'">
              （从 <span class="text-ops-text stat-number">{{ messages.length }}</span> 条中筛选）
            </span>
          </span>
          <span class="flex items-center gap-1">
            <Info class="w-3 h-3" />
            消息获取后处于未确认状态，刷新或切换队列将自动退回
          </span>
        </div>
      </div>
    </template>

    <el-dialog
      v-model="detailDialogVisible"
      title="消息详情"
      width="900px"
      :close-on-click-modal="false"
      class="message-detail-dialog"
      @closed="closeDetail"
    >
      <div v-if="selectedMessage" class="space-y-5">
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
              <div v-if="selectedMessage.properties.message_id" class="flex items-start gap-2">
                <span class="text-ops-muted w-28 flex-shrink-0">Message ID:</span>
                <code class="font-mono text-ops-text break-all">{{ selectedMessage.properties.message_id }}</code>
              </div>
              <div v-if="selectedMessage.properties.correlation_id" class="flex items-start gap-2">
                <span class="text-ops-muted w-28 flex-shrink-0">Correlation ID:</span>
                <code class="font-mono text-ops-text break-all">{{ selectedMessage.properties.correlation_id }}</code>
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
            ACK / Reject 操作将立即作用于队列中的实际消息
          </div>
          <div class="flex items-center gap-2">
            <button
              class="px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 transition-all duration-200"
              @click="detailDialogVisible = false"
            >
              关闭
            </button>
            <button
              v-if="selectedMessage"
              class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-500/15 border border-amber-500/30 text-sm text-amber-400 hover:bg-amber-500/25 transition-all duration-200"
              @click="handleReject(selectedMessage, true)"
            >
              <XCircle class="w-4 h-4" />
              Reject (重新入队)
            </button>
            <button
              v-if="selectedMessage"
              class="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-red-500/15 border border-red-500/30 text-sm text-red-400 hover:bg-red-500/25 transition-all duration-200"
              @click="handleReject(selectedMessage, false)"
            >
              <XCircle class="w-4 h-4" />
              Reject (丢弃)
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
