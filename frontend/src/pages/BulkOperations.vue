<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  Upload,
  Target,
  KeyRound,
  FileJson,
  FileSpreadsheet,
  Send,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Database,
  Share2,
  RefreshCw,
  Trash2,
  Play,
  Loader2,
  Info,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getQueues,
  getExchanges,
  bulkPublishMessages,
  type QueueListItem,
  type ExchangeListItem,
  type BulkPublishItem,
} from '@/api'

defineOptions({
  name: 'BulkOperations',
})

const targetType = ref<'exchange' | 'queue'>('exchange')
const targetName = ref('')
const routingKey = ref('')
const deliveryMode = ref<1 | 2>(2)
const priority = ref(0)

const queues = ref<QueueListItem[]>([])
const exchanges = ref<ExchangeListItem[]>([])
const loadingTargets = ref(false)

const uploadedFile = ref<File | null>(null)
const fileContent = ref<string>('')
const fileFormat = ref<'json' | 'csv' | ''>('')
const parsedMessages = ref<BulkPublishItem[]>([])
const parseError = ref('')
const isParsing = ref(false)

const isPublishing = ref(false)
const publishProgress = ref(0)
const publishResult = ref<{
  total: number
  success: number
  failed: number
  failedDetails: string[]
} | null>(null)

const BATCH_SIZE = 100

interface TargetOption {
  value: string
  label: string
  displayLabel: string
}

const targetOptions = computed<TargetOption[]>(() => {
  if (targetType.value === 'queue') {
    return queues.value.map((q) => ({
      value: q.name,
      label: q.name,
      displayLabel: `${q.name} (Ready: ${q.ready} / Total: ${q.total})`,
    }))
  }
  return exchanges.value.map((e) => ({
    value: e.name,
    label: e.name,
    displayLabel: `${e.name} [${e.type}]`,
  }))
})

const fileSizeStr = computed(() => {
  if (!uploadedFile.value) return ''
  const bytes = uploadedFile.value.size
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
})

const canPublish = computed(() => {
  return (
    !isPublishing.value &&
    targetName.value.trim() !== '' &&
    parsedMessages.value.length > 0
  )
})

async function loadTargets() {
  loadingTargets.value = true
  try {
    const [queuesData, exchangesData] = await Promise.all([getQueues(), getExchanges()])
    queues.value = queuesData
    exchanges.value = exchangesData
  } catch (err) {
    console.error('Failed to load targets:', err)
    ElMessage.error('加载目标列表失败')
  } finally {
    loadingTargets.value = false
  }
}

function parseCsv(text: string): BulkPublishItem[] {
  const lines = text.trim().split(/\r?\n/)
  if (lines.length < 2) {
    throw new Error('CSV 文件至少需要包含表头和一行数据')
  }

  const headers = parseCsvLine(lines[0])
  const payloadIdx = headers.findIndex((h) => h.toLowerCase() === 'payload')
  const routingKeyIdx = headers.findIndex((h) => h.toLowerCase() === 'routing_key' || h.toLowerCase() === 'routingkey')

  if (payloadIdx === -1) {
    throw new Error('CSV 必须包含 "payload" 列')
  }

  const headerColumns: { name: string; idx: number }[] = []
  headers.forEach((h, idx) => {
    const lower = h.toLowerCase()
    if (lower.startsWith('header:') || lower.startsWith('headers:')) {
      const headerName = h.split(':').slice(1).join(':').trim()
      if (headerName) {
        headerColumns.push({ name: headerName, idx })
      }
    }
  })

  const result: BulkPublishItem[] = []
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line) continue

    const fields = parseCsvLine(line)
    const payload = fields[payloadIdx] || ''
    if (!payload) continue

    const item: BulkPublishItem = { payload }

    if (routingKeyIdx >= 0 && fields[routingKeyIdx]) {
      item.routing_key = fields[routingKeyIdx]
    }

    if (headerColumns.length > 0) {
      const headersObj: Record<string, string> = {}
      headerColumns.forEach((hc) => {
        if (fields[hc.idx] !== undefined && fields[hc.idx] !== '') {
          headersObj[hc.name] = fields[hc.idx]
        }
      })
      if (Object.keys(headersObj).length > 0) {
        item.headers = headersObj
      }
    }

    result.push(item)
  }

  return result
}

function parseCsvLine(line: string): string[] {
  const result: string[] = []
  let current = ''
  let inQuotes = false

  for (let i = 0; i < line.length; i++) {
    const ch = line[i]

    if (inQuotes) {
      if (ch === '"') {
        if (i + 1 < line.length && line[i + 1] === '"') {
          current += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        current += ch
      }
    } else {
      if (ch === '"') {
        inQuotes = true
      } else if (ch === ',') {
        result.push(current)
        current = ''
      } else {
        current += ch
      }
    }
  }
  result.push(current)

  return result
}

function parseJson(text: string): BulkPublishItem[] {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch (e) {
    const err = e as Error
    throw new Error(`JSON 解析失败: ${err.message}`)
  }

  if (!Array.isArray(data)) {
    throw new Error('JSON 根节点必须是数组')
  }

  const result: BulkPublishItem[] = []

  data.forEach((item, idx) => {
    if (typeof item === 'string') {
      if (item.trim()) {
        result.push({ payload: item })
      }
    } else if (item && typeof item === 'object') {
      const obj = item as Record<string, unknown>
      const payload = typeof obj.payload === 'string' ? obj.payload : JSON.stringify(obj)
      const resultItem: BulkPublishItem = { payload }

      if (typeof obj.routing_key === 'string' && obj.routing_key.trim()) {
        resultItem.routing_key = obj.routing_key
      } else if (typeof obj.routingKey === 'string' && obj.routingKey.trim()) {
        resultItem.routing_key = obj.routingKey
      }

      if (obj.headers && typeof obj.headers === 'object') {
        const headersObj: Record<string, string> = {}
        Object.entries(obj.headers as Record<string, unknown>).forEach(([k, v]) => {
          if (v !== null && v !== undefined) {
            headersObj[k] = String(v)
          }
        })
        if (Object.keys(headersObj).length > 0) {
          resultItem.headers = headersObj
        }
      }

      result.push(resultItem)
    } else {
      console.warn(`跳过第 ${idx + 1} 项: 不支持的类型`)
    }
  })

  return result
}

async function handleFileUpload(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  const name = file.name.toLowerCase()
  if (name.endsWith('.json')) {
    fileFormat.value = 'json'
  } else if (name.endsWith('.csv')) {
    fileFormat.value = 'csv'
  } else {
    ElMessage.error('只支持 .json 或 .csv 文件')
    input.value = ''
    return
  }

  uploadedFile.value = file
  parseError.value = ''
  parsedMessages.value = []
  publishResult.value = null
  isParsing.value = true

  try {
    const text = await file.text()
    fileContent.value = text

    let messages: BulkPublishItem[]
    if (fileFormat.value === 'json') {
      messages = parseJson(text)
    } else {
      messages = parseCsv(text)
    }

    if (messages.length === 0) {
      throw new Error('文件中没有解析到有效消息')
    }

    if (messages.length > 5000) {
      await ElMessageBox.confirm(
        `文件包含 ${messages.length} 条消息，超过推荐上限 5000 条。是否继续加载前 5000 条？`,
        '消息数量过多',
        {
          confirmButtonText: '加载前 5000 条',
          cancelButtonText: '取消',
          type: 'warning',
        }
      )
      messages = messages.slice(0, 5000)
    }

    parsedMessages.value = messages
    ElMessage.success(`成功解析 ${messages.length} 条消息`)
  } catch (e) {
    const err = e as Error
    if (err.message !== 'cancel') {
      parseError.value = err.message
      ElMessage.error(err.message)
    }
  } finally {
    isParsing.value = false
    input.value = ''
  }
}

function clearFile() {
  uploadedFile.value = null
  fileContent.value = ''
  fileFormat.value = ''
  parsedMessages.value = []
  parseError.value = ''
  publishResult.value = null
}

async function handleBulkPublish() {
  if (!canPublish.value) return

  try {
    await ElMessageBox.confirm(
      `确认向 ${targetType.value === 'exchange' ? '交换机' : '队列'} "${targetName.value}" 批量发布 ${parsedMessages.value.length} 条消息？`,
      '确认批量发布',
      {
        confirmButtonText: '确认发布',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }

  isPublishing.value = true
  publishProgress.value = 0
  publishResult.value = null

  const allMessages = parsedMessages.value
  const total = allMessages.length
  let successCount = 0
  let failedCount = 0
  const failedDetails: string[] = []

  try {
    for (let i = 0; i < total; i += BATCH_SIZE) {
      const batch = allMessages.slice(i, i + BATCH_SIZE)
      try {
        const result = await bulkPublishMessages({
          target_type: targetType.value,
          target_name: targetName.value.trim(),
          routing_key: routingKey.value.trim(),
          messages: batch,
          delivery_mode: deliveryMode.value,
          priority: priority.value,
          content_type: 'application/json',
        })
        successCount += result.success_count
        failedCount += result.failed_count
        if (result.failed_details) {
          failedDetails.push(...result.failed_details)
        }
      } catch (e) {
        const err = e as Error
        failedCount += batch.length
        failedDetails.push(`批次 ${Math.floor(i / BATCH_SIZE) + 1}: ${err.message || '未知错误'}`)
      }
      publishProgress.value = Math.min(100, Math.round(((i + batch.length) / total) * 100))
      await new Promise((resolve) => setTimeout(resolve, 50))
    }

    publishProgress.value = 100
    publishResult.value = {
      total,
      success: successCount,
      failed: failedCount,
      failedDetails: failedDetails.slice(0, 20),
    }

    if (failedCount === 0) {
      ElMessage.success(`批量发布完成，成功 ${successCount} 条`)
    } else {
      ElMessage.warning(`批量发布完成，成功 ${successCount} 条，失败 ${failedCount} 条`)
    }
  } finally {
    isPublishing.value = false
  }
}

function downloadTemplate(format: 'json' | 'csv') {
  let content = ''
  let filename = ''

  if (format === 'json') {
    content = JSON.stringify(
      [
        {
          payload: '{"orderId": "1001", "status": "created"}',
          routing_key: 'order.created',
          headers: {
            'x-custom-header': 'value',
          },
        },
        {
          payload: '{"orderId": "1002", "status": "paid"}',
          routing_key: 'order.paid',
        },
        '简单字符串作为消息体',
      ],
      null,
      2
    )
    filename = 'bulk_messages_template.json'
  } else {
    content =
      'payload,routing_key,header:x-custom-header\n' +
      '"{\"orderId\": \"1001\"}",order.created,custom_value\n' +
      '"{\"orderId\": \"1002\"}",order.paid,\n'
    filename = 'bulk_messages_template.csv'
  }

  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

onMounted(() => {
  loadTargets()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold text-ops-text mb-1">批量操作</h2>
        <p class="text-sm text-ops-muted">批量发送消息，支持上传 CSV 或 JSON 文件</p>
      </div>
      <div class="flex items-center gap-3">
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 transition-all duration-200"
          @click="loadTargets"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loadingTargets }" />
          刷新目标
        </button>
        <div class="flex rounded-lg border border-ops-border overflow-hidden">
          <button
            class="flex items-center gap-1.5 px-3 py-2 text-xs bg-ops-card hover:bg-ops-card/80 transition-all text-ops-text border-r border-ops-border"
            @click="downloadTemplate('json')"
          >
            <FileJson class="w-3.5 h-3.5" />
            JSON 模板
          </button>
          <button
            class="flex items-center gap-1.5 px-3 py-2 text-xs bg-ops-card hover:bg-ops-card/80 transition-all text-ops-text"
            @click="downloadTemplate('csv')"
          >
            <FileSpreadsheet class="w-3.5 h-3.5" />
            CSV 模板
          </button>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <div class="xl:col-span-2 space-y-6">
        <div class="card-gradient rounded-2xl border border-ops-border p-6 space-y-5">
          <div class="flex items-center gap-2 text-base font-semibold text-ops-text">
            <Target class="w-5 h-5 text-ops-primary" />
            发布目标
          </div>

          <div>
            <label class="block text-sm font-medium text-ops-text mb-2">目标类型 <span class="text-red-400">*</span></label>
            <div class="grid grid-cols-2 gap-3 max-w-md">
              <label
                class="flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all duration-150"
                :class="targetType === 'exchange'
                  ? 'bg-ops-primary/10 border-ops-primary'
                  : 'bg-ops-bg/50 border-ops-border hover:border-ops-primary/50'"
              >
                <input v-model="targetType" type="radio" value="exchange" class="w-4 h-4 text-ops-primary" />
                <Share2 class="w-4 h-4" :class="targetType === 'exchange' ? 'text-ops-primary' : 'text-ops-muted'" />
                <div class="flex flex-col">
                  <span class="text-sm font-medium text-ops-text">交换机</span>
                  <span class="text-xs text-ops-muted">通过路由键路由到队列</span>
                </div>
              </label>
              <label
                class="flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all duration-150"
                :class="targetType === 'queue'
                  ? 'bg-ops-primary/10 border-ops-primary'
                  : 'bg-ops-bg/50 border-ops-border hover:border-ops-primary/50'"
              >
                <input v-model="targetType" type="radio" value="queue" class="w-4 h-4 text-ops-primary" />
                <Database class="w-4 h-4" :class="targetType === 'queue' ? 'text-ops-primary' : 'text-ops-muted'" />
                <div class="flex flex-col">
                  <span class="text-sm font-medium text-ops-text">队列</span>
                  <span class="text-xs text-ops-muted">直接投递到指定队列</span>
                </div>
              </label>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-ops-text mb-2">
              {{ targetType === 'exchange' ? '交换机名称' : '队列名称' }}
              <span class="text-red-400">*</span>
            </label>
            <select
              v-model="targetName"
              class="w-full px-4 py-2.5 rounded-lg bg-ops-bg border border-ops-border text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
            >
              <option value="" disabled>
                {{ loadingTargets ? '加载中...' : `请选择${targetType === 'exchange' ? '交换机' : '队列'}` }}
              </option>
              <option v-for="opt in targetOptions" :key="opt.value" :value="opt.value">
                {{ opt.displayLabel }}
              </option>
            </select>
          </div>

          <div v-if="targetType === 'exchange'">
            <label class="block text-sm font-medium text-ops-text mb-2">
              <div class="flex items-center gap-2">
                <KeyRound class="w-4 h-4 text-ops-muted" />
                默认 Routing Key
              </div>
            </label>
            <input
              v-model="routingKey"
              type="text"
              placeholder="文件中未指定 routing_key 时使用此默认值"
              class="w-full px-4 py-2.5 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150 font-mono text-sm"
            />
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-sm font-medium text-ops-text mb-2">投递模式 (Delivery Mode)</label>
              <select
                v-model.number="deliveryMode"
                class="w-full px-4 py-2.5 rounded-lg bg-ops-bg border border-ops-border text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
              >
                <option :value="2">持久化 (写入磁盘)</option>
                <option :value="1">非持久化 (重启后丢失)</option>
              </select>
            </div>
            <div>
              <label class="block text-sm font-medium text-ops-text mb-2">
                优先级 (Priority): <span class="text-ops-primary font-mono">{{ priority }}</span>
              </label>
              <input
                v-model.number="priority"
                type="range"
                min="0"
                max="9"
                step="1"
                class="w-full accent-ops-primary mt-2.5"
              />
            </div>
          </div>
        </div>

        <div class="card-gradient rounded-2xl border border-ops-border p-6 space-y-5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 text-base font-semibold text-ops-text">
              <Upload class="w-5 h-5 text-ops-primary" />
              上传消息文件
            </div>
            <div
              v-if="parsedMessages.length > 0"
              class="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded bg-emerald-500/15 text-emerald-400"
            >
              <CheckCircle2 class="w-3 h-3" />
              已解析 {{ parsedMessages.length }} 条
            </div>
          </div>

          <div v-if="!uploadedFile" class="space-y-4">
            <label
              class="flex flex-col items-center justify-center w-full h-40 border-2 border-dashed rounded-xl cursor-pointer transition-all duration-150 border-ops-border hover:border-ops-primary/50 hover:bg-ops-bg/30"
            >
              <Upload class="w-10 h-10 text-ops-muted/50 mb-3" />
              <span class="text-sm text-ops-text mb-1">点击或拖拽文件到此处</span>
              <span class="text-xs text-ops-muted">支持 .json 或 .csv 格式，最多 5000 条消息</span>
              <input type="file" accept=".json,.csv" class="hidden" @change="handleFileUpload" />
            </label>
          </div>

          <div v-else class="space-y-4">
            <div class="flex items-center justify-between p-4 rounded-xl bg-ops-bg/50 border border-ops-border/50">
              <div class="flex items-center gap-3">
                <div
                  class="w-10 h-10 rounded-lg flex items-center justify-center"
                  :class="fileFormat === 'json' ? 'bg-emerald-500/15' : 'bg-blue-500/15'"
                >
                  <FileJson v-if="fileFormat === 'json'" class="w-5 h-5 text-emerald-400" />
                  <FileSpreadsheet v-else class="w-5 h-5 text-blue-400" />
                </div>
                <div class="flex flex-col">
                  <span class="text-sm font-medium text-ops-text">{{ uploadedFile.name }}</span>
                  <span class="text-xs text-ops-muted">{{ fileSizeStr }} · {{ parsedMessages.length }} 条消息</span>
                </div>
              </div>
              <div class="flex items-center gap-2">
                <Loader2 v-if="isParsing" class="w-4 h-4 text-ops-muted animate-spin" />
                <button
                  class="p-2 rounded-lg text-ops-muted hover:text-red-400 hover:bg-red-500/10 transition-all"
                  :disabled="isPublishing"
                  @click="clearFile"
                >
                  <Trash2 class="w-4 h-4" />
                </button>
              </div>
            </div>

            <div v-if="parseError" class="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
              <AlertCircle class="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
              <span class="text-sm text-red-400">{{ parseError }}</span>
            </div>

            <div v-if="parsedMessages.length > 0">
              <label class="block text-sm font-medium text-ops-text mb-2">消息预览 (前 5 条)</label>
              <div class="space-y-2 max-h-64 overflow-y-auto pr-1">
                <div
                  v-for="(msg, idx) in parsedMessages.slice(0, 5)"
                  :key="idx"
                  class="p-3 rounded-lg bg-ops-bg/50 border border-ops-border/50"
                >
                  <div class="flex items-center justify-between mb-2">
                    <span class="text-xs font-medium text-ops-primary">#{{ idx + 1 }}</span>
                    <div class="flex items-center gap-2">
                      <span
                        v-if="msg.routing_key"
                        class="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded bg-emerald-500/15 text-emerald-400 font-mono"
                      >
                        RK: {{ msg.routing_key }}
                      </span>
                      <span
                        v-if="msg.headers && Object.keys(msg.headers).length > 0"
                        class="inline-flex items-center px-1.5 py-0.5 text-[10px] rounded bg-blue-500/15 text-blue-400"
                      >
                        Headers: {{ Object.keys(msg.headers).length }}
                      </span>
                    </div>
                  </div>
                  <code class="font-mono text-xs text-ops-text break-all line-clamp-2">
                    {{ msg.payload.slice(0, 200) }}{{ msg.payload.length > 200 ? '...' : '' }}
                  </code>
                </div>
                <div
                  v-if="parsedMessages.length > 5"
                  class="text-center text-xs text-ops-muted py-1"
                >
                  ... 还有 {{ parsedMessages.length - 5 }} 条消息
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="space-y-6">
        <div class="card-gradient rounded-2xl border border-ops-border p-6 space-y-5">
          <div class="flex items-center gap-2 text-base font-semibold text-ops-text">
            <Info class="w-5 h-5 text-ops-primary" />
            文件格式说明
          </div>
          <div class="space-y-4 text-xs">
            <div class="space-y-2">
              <div class="flex items-center gap-2 text-sm font-medium text-ops-text">
                <FileJson class="w-4 h-4 text-emerald-400" />
                JSON 格式
              </div>
              <p class="text-ops-muted leading-relaxed">
                JSON 数组，每个元素可以是字符串（作为消息体）或对象：
              </p>
              <pre class="p-3 rounded-lg bg-ops-bg/50 border border-ops-border/50 font-mono text-[10px] text-ops-text overflow-x-auto">
[
  {
    "payload": "消息内容",
    "routing_key": "order.created",
    "headers": { "key": "value" }
  },
  "简单字符串消息"
]</pre>
            </div>
            <div class="space-y-2">
              <div class="flex items-center gap-2 text-sm font-medium text-ops-text">
                <FileSpreadsheet class="w-4 h-4 text-blue-400" />
                CSV 格式
              </div>
              <p class="text-ops-muted leading-relaxed">
                第一行为表头，必须包含 <code class="px-1 rounded bg-ops-bg text-ops-primary">payload</code> 列：
              </p>
              <pre class="p-3 rounded-lg bg-ops-bg/50 border border-ops-border/50 font-mono text-[10px] text-ops-text overflow-x-auto">
payload,routing_key,header:自定义头
{"id":1},order.key,header值</pre>
            </div>
          </div>
        </div>

        <div
          v-if="isPublishing || publishResult"
          class="card-gradient rounded-2xl border border-ops-border p-6 space-y-5"
        >
          <div class="flex items-center gap-2 text-base font-semibold text-ops-text">
            <Play class="w-5 h-5 text-ops-primary" />
            发布状态
          </div>

          <div class="space-y-3">
            <div class="flex items-center justify-between text-sm">
              <span class="text-ops-muted">进度</span>
              <span class="text-ops-text font-medium">{{ publishProgress }}%</span>
            </div>
            <div class="h-2 rounded-full bg-ops-bg overflow-hidden">
              <div
                class="h-full bg-gradient-to-r from-ops-primary to-ops-accent transition-all duration-300"
                :style="{ width: `${publishProgress}%` }"
              />
            </div>
          </div>

          <div v-if="publishResult" class="grid grid-cols-3 gap-3">
            <div class="p-3 rounded-xl bg-ops-bg/50 border border-ops-border/50 text-center">
              <div class="text-[10px] text-ops-muted mb-1">总数</div>
              <div class="text-lg font-bold text-ops-text stat-number">{{ publishResult.total }}</div>
            </div>
            <div class="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-center">
              <div class="text-[10px] text-emerald-400 mb-1">成功</div>
              <div class="text-lg font-bold text-emerald-400 stat-number">{{ publishResult.success }}</div>
            </div>
            <div class="p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-center">
              <div class="text-[10px] text-red-400 mb-1">失败</div>
              <div class="text-lg font-bold text-red-400 stat-number">{{ publishResult.failed }}</div>
            </div>
          </div>

          <div
            v-if="publishResult?.failedDetails && publishResult.failedDetails.length > 0"
            class="space-y-1.5 max-h-40 overflow-y-auto pr-1"
          >
            <div class="text-xs font-medium text-ops-text">失败详情：</div>
            <div
              v-for="(detail, idx) in publishResult.failedDetails"
              :key="idx"
              class="flex items-start gap-1.5 p-2 rounded-lg bg-red-500/5 border border-red-500/10"
            >
              <XCircle class="w-3 h-3 text-red-400 mt-0.5 flex-shrink-0" />
              <span class="text-[11px] text-red-400 break-all">{{ detail }}</span>
            </div>
          </div>
        </div>

        <button
          class="w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-gradient-to-r from-ops-primary to-ops-accent text-white font-semibold shadow-glow-blue hover:shadow-glow-blue-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="!canPublish"
          @click="handleBulkPublish"
        >
          <Send v-if="!isPublishing" class="w-5 h-5" />
          <Loader2 v-else class="w-5 h-5 animate-spin" />
          {{ isPublishing ? `发布中 ${publishProgress}%` : `批量发布 (${parsedMessages.length} 条)` }}
        </button>
      </div>
    </div>
  </div>
</template>
