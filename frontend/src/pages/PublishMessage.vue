<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import {
  Send,
  Target,
  KeyRound,
  FileJson,
  Hash,
  Plus,
  X,
  Wand2,
  AlertCircle,
  CheckCircle2,
  Database,
  Share2,
  Copy,
  RefreshCw,
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import {
  getQueues,
  getExchanges,
  publishMessage,
  type QueueListItem,
  type ExchangeListItem,
  type PublishMessageRequest,
} from '@/api'

defineOptions({
  name: 'PublishMessage',
})

const targetType = ref<'exchange' | 'queue'>('exchange')
const targetName = ref('')
const routingKey = ref('')
const payloadInput = ref('{\n  \n}')
const headers = ref<{ key: string; value: string }[]>([])
const deliveryMode = ref<1 | 2>(2)
const priority = ref(0)
const publishing = ref(false)

const queues = ref<QueueListItem[]>([])
const exchanges = ref<ExchangeListItem[]>([])
const loadingTargets = ref(false)

const payloadValidationError = ref('')
const headersValidationError = ref('')

const payloadIsValid = computed(() => {
  if (!payloadInput.value.trim()) {
    payloadValidationError.value = '消息体不能为空'
    return false
  }
  try {
    JSON.parse(payloadInput.value)
    payloadValidationError.value = ''
    return true
  } catch (e) {
    const err = e as Error
    payloadValidationError.value = `JSON 格式错误: ${err.message}`
    return false
  }
})

const headersIsValid = computed(() => {
  for (let i = 0; i < headers.value.length; i++) {
    const h = headers.value[i]
    if (!h.key.trim() && h.value.trim()) {
      headersValidationError.value = `第 ${i + 1} 行: Key 不能为空`
      return false
    }
    if (h.key.trim() && /\s/.test(h.key.trim())) {
      headersValidationError.value = `第 ${i + 1} 行: Key 不能包含空白字符`
      return false
    }
  }
  const keys = headers.value.filter((h) => h.key.trim()).map((h) => h.key.trim())
  const uniqueKeys = new Set(keys)
  if (keys.length !== uniqueKeys.size) {
    headersValidationError.value = '存在重复的 Header Key'
    return false
  }
  headersValidationError.value = ''
  return true
})

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

const payloadSize = computed(() => new Blob([payloadInput.value]).size)

const formattedPayload = computed(() => {
  try {
    const obj = JSON.parse(payloadInput.value)
    return JSON.stringify(obj, null, 2)
  } catch {
    return payloadInput.value
  }
})

watch(targetType, () => {
  targetName.value = ''
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

function addHeader() {
  headers.value.push({ key: '', value: '' })
}

function removeHeader(index: number) {
  headers.value.splice(index, 1)
}

function formatPayload() {
  try {
    const obj = JSON.parse(payloadInput.value)
    payloadInput.value = JSON.stringify(obj, null, 2)
    ElMessage.success('JSON 格式化成功')
  } catch {
    ElMessage.error('JSON 格式错误，无法格式化')
  }
}

function minifyPayload() {
  try {
    const obj = JSON.parse(payloadInput.value)
    payloadInput.value = JSON.stringify(obj)
    ElMessage.success('JSON 压缩成功')
  } catch {
    ElMessage.error('JSON 格式错误，无法压缩')
  }
}

function copyPayload() {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(payloadInput.value)
    ElMessage.success('已复制到剪贴板')
  }
}

function resetForm() {
  targetType.value = 'exchange'
  targetName.value = ''
  routingKey.value = ''
  payloadInput.value = '{\n  \n}'
  headers.value = []
  deliveryMode.value = 2
  priority.value = 0
  payloadValidationError.value = ''
  headersValidationError.value = ''
}

async function handlePublish() {
  if (!targetName.value.trim()) {
    ElMessage.warning('请选择目标')
    return
  }
  if (!payloadIsValid.value) {
    ElMessage.warning('请修正消息体中的 JSON 格式错误')
    return
  }
  if (!headersIsValid.value) {
    ElMessage.warning('请修正 Headers 中的错误')
    return
  }

  const headersObj: Record<string, string> = {}
  headers.value.forEach((h) => {
    if (h.key.trim()) {
      headersObj[h.key.trim()] = h.value
    }
  })

  const data: PublishMessageRequest = {
    target_type: targetType.value,
    target_name: targetName.value.trim(),
    routing_key: routingKey.value.trim(),
    payload: payloadInput.value,
    delivery_mode: deliveryMode.value,
    priority: priority.value,
    content_type: 'application/json',
    headers: Object.keys(headersObj).length > 0 ? headersObj : undefined,
  }

  publishing.value = true
  try {
    const result = await publishMessage(data)
    if (result.success) {
      const count = result.published_count ?? 1
      ElMessage.success(`消息发布成功 (${count} 条路由)`)
    } else {
      ElMessage.error(result.message || '消息发布失败')
    }
  } catch (err) {
    console.error('Publish failed:', err)
  } finally {
    publishing.value = false
  }
}

loadTargets()
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold text-ops-text mb-1">发布消息</h2>
        <p class="text-sm text-ops-muted">向指定交换机或队列发布 JSON 格式的消息</p>
      </div>
      <div class="flex items-center gap-3">
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 transition-all duration-200"
          @click="loadTargets"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loadingTargets }" />
          刷新目标
        </button>
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 transition-all duration-200"
          @click="resetForm"
        >
          重置表单
        </button>
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
                <input
                  v-model="targetType"
                  type="radio"
                  value="exchange"
                  class="w-4 h-4 text-ops-primary"
                />
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
                <input
                  v-model="targetType"
                  type="radio"
                  value="queue"
                  class="w-4 h-4 text-ops-primary"
                />
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
              <option
                v-for="opt in targetOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.displayLabel }}
              </option>
            </select>
          </div>

          <div v-if="targetType === 'exchange'">
            <label class="block text-sm font-medium text-ops-text mb-2">
              <div class="flex items-center gap-2">
                <KeyRound class="w-4 h-4 text-ops-muted" />
                Routing Key
              </div>
            </label>
            <input
              v-model="routingKey"
              type="text"
              placeholder="请输入路由键，例如：order.created"
              class="w-full px-4 py-2.5 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150 font-mono text-sm"
            />
            <p class="text-xs text-ops-muted mt-1">交换机类型为 fanout 时可留空</p>
          </div>
        </div>

        <div class="card-gradient rounded-2xl border border-ops-border p-6 space-y-5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 text-base font-semibold text-ops-text">
              <FileJson class="w-5 h-5 text-ops-primary" />
              消息体 (JSON)
              <span class="text-red-400">*</span>
            </div>
            <div class="flex items-center gap-2">
              <span
                class="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded"
                :class="payloadIsValid
                  ? 'bg-emerald-500/15 text-emerald-400'
                  : 'bg-red-500/15 text-red-400'"
              >
                <CheckCircle2 v-if="payloadIsValid" class="w-3 h-3" />
                <AlertCircle v-else class="w-3 h-3" />
                {{ payloadIsValid ? '格式正确' : '格式错误' }}
              </span>
              <span class="text-xs text-ops-muted font-mono">{{ payloadSize.toLocaleString() }} B</span>
            </div>
          </div>

          <div class="flex items-center gap-2 flex-wrap">
            <button
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-ops-card border border-ops-border text-xs text-ops-text hover:bg-ops-card/80 transition-all"
              @click="formatPayload"
            >
              <Wand2 class="w-3.5 h-3.5" />
              格式化
            </button>
            <button
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-ops-card border border-ops-border text-xs text-ops-text hover:bg-ops-card/80 transition-all"
              @click="minifyPayload"
            >
              压缩
            </button>
            <button
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-ops-card border border-ops-border text-xs text-ops-text hover:bg-ops-card/80 transition-all"
              @click="copyPayload"
            >
              <Copy class="w-3.5 h-3.5" />
              复制
            </button>
          </div>

          <div class="relative">
            <textarea
              v-model="payloadInput"
              rows="16"
              placeholder='{"key": "value", "nested": {"data": true}}'
              class="w-full px-4 py-3 rounded-lg bg-ops-bg border font-mono text-sm leading-relaxed placeholder:text-ops-muted/50 focus:outline-none transition-colors duration-150 resize-none"
              :class="payloadValidationError
                ? 'border-red-500/50 focus:border-red-500 text-ops-text'
                : 'border-ops-border focus:border-ops-primary text-ops-text'"
              spellcheck="false"
            />
          </div>

          <div v-if="payloadValidationError" class="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
            <AlertCircle class="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
            <span class="text-sm text-red-400">{{ payloadValidationError }}</span>
          </div>
        </div>
      </div>

      <div class="space-y-6">
        <div class="card-gradient rounded-2xl border border-ops-border p-6 space-y-5">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2 text-base font-semibold text-ops-text">
              <Hash class="w-5 h-5 text-ops-primary" />
              自定义 Headers
            </div>
            <button
              class="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-ops-primary/10 border border-ops-primary/30 text-xs text-ops-primary hover:bg-ops-primary/20 transition-all"
              @click="addHeader"
            >
              <Plus class="w-3.5 h-3.5" />
              添加
            </button>
          </div>

          <div v-if="headers.length === 0" class="flex flex-col items-center justify-center py-8 text-ops-muted/50">
            <Hash class="w-8 h-8 mb-2" />
            <span class="text-xs">暂无 Headers，点击上方按钮添加</span>
          </div>

          <div v-else class="space-y-2 max-h-72 overflow-y-auto pr-1">
            <div
              v-for="(h, idx) in headers"
              :key="idx"
              class="flex items-center gap-2 p-2 rounded-lg bg-ops-bg/50 border border-ops-border/50"
            >
              <span class="text-xs text-ops-muted w-5 text-center">{{ idx + 1 }}</span>
              <input
                v-model="h.key"
                type="text"
                placeholder="Key"
                class="flex-1 min-w-0 px-2 py-1.5 rounded-md bg-ops-bg border border-ops-border text-xs text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors font-mono"
              />
              <input
                v-model="h.value"
                type="text"
                placeholder="Value"
                class="flex-1 min-w-0 px-2 py-1.5 rounded-md bg-ops-bg border border-ops-border text-xs text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors font-mono"
              />
              <button
                class="p-1.5 rounded-md text-ops-muted hover:text-red-400 hover:bg-red-500/10 transition-all flex-shrink-0"
                @click="removeHeader(idx)"
              >
                <X class="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          <div v-if="headersValidationError" class="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
            <AlertCircle class="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
            <span class="text-xs text-red-400">{{ headersValidationError }}</span>
          </div>
        </div>

        <div class="card-gradient rounded-2xl border border-ops-border p-6 space-y-5">
          <div class="flex items-center gap-2 text-base font-semibold text-ops-text">
            <Send class="w-5 h-5 text-ops-primary" />
            发布属性
          </div>

          <div>
            <label class="block text-sm font-medium text-ops-text mb-2">投递模式 (Delivery Mode)</label>
            <div class="grid grid-cols-2 gap-3">
              <label
                class="flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-all duration-150"
                :class="deliveryMode === 1
                  ? 'bg-amber-500/10 border-amber-500/30'
                  : 'bg-ops-bg/50 border-ops-border hover:border-ops-primary/50'"
              >
                <input
                  v-model="deliveryMode"
                  type="radio"
                  :value="1"
                  class="w-3.5 h-3.5"
                />
                <div class="flex flex-col">
                  <span class="text-xs font-medium text-ops-text">非持久化</span>
                  <span class="text-[10px] text-ops-muted">重启后丢失</span>
                </div>
              </label>
              <label
                class="flex items-center gap-2 p-2.5 rounded-lg border cursor-pointer transition-all duration-150"
                :class="deliveryMode === 2
                  ? 'bg-emerald-500/10 border-emerald-500/30'
                  : 'bg-ops-bg/50 border-ops-border hover:border-ops-primary/50'"
              >
                <input
                  v-model="deliveryMode"
                  type="radio"
                  :value="2"
                  class="w-3.5 h-3.5"
                />
                <div class="flex flex-col">
                  <span class="text-xs font-medium text-ops-text">持久化</span>
                  <span class="text-[10px] text-ops-muted">写入磁盘 (推荐)</span>
                </div>
              </label>
            </div>
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
              class="w-full accent-ops-primary"
            />
            <div class="flex justify-between text-[10px] text-ops-muted mt-1">
              <span>0 (最低)</span>
              <span>9 (最高)</span>
            </div>
          </div>
        </div>

        <button
          class="w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-gradient-to-r from-ops-primary to-ops-accent text-white font-semibold shadow-glow-blue hover:shadow-glow-blue-lg transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          :disabled="publishing || !payloadIsValid || !headersIsValid || !targetName.trim()"
          @click="handlePublish"
        >
          <Send class="w-5 h-5" :class="{ 'animate-pulse': publishing }" />
          {{ publishing ? '发布中...' : '发布消息' }}
        </button>
      </div>
    </div>
  </div>
</template>
