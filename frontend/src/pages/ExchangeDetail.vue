<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, onActivated, onDeactivated, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  RefreshCw,
  ArrowLeft,
  Share2,
  Plus,
  Trash2,
  Settings,
  Link2,
  ArrowRight,
  Database,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getExchangeDetail,
  deleteExchange,
  createBinding,
  deleteBinding,
  getQueues,
  type ExchangeDetail,
  type ExchangeBinding,
  type CreateBindingRequest,
  type QueueListItem,
} from '@/api'

defineOptions({
  name: 'ExchangeDetail',
})

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const exchangeDetail = ref<ExchangeDetail | null>(null)
const lastUpdated = ref<Date | null>(null)
const queues = ref<QueueListItem[]>([])
let refreshTimer: number | null = null
let isActive = false
let isFetching = false
let hasLoaded = false
let currentExchangeName = ''

const bindingDialogVisible = ref(false)
const bindingForm = ref<CreateBindingRequest>({
  destination: '',
  destination_type: 'queue',
  routing_key: '',
  arguments: undefined,
})
const bindingArgumentsInput = ref('')

const exchangeName = computed(() => {
  const name = route.params.name as string
  return decodeURIComponent(name)
})

const exchangeTypes = [
  { value: 'direct', label: 'Direct' },
  { value: 'topic', label: 'Topic' },
  { value: 'fanout', label: 'Fanout' },
  { value: 'headers', label: 'Headers' },
]

function getTypeLabel(type: string): string {
  const found = exchangeTypes.find((t) => t.value === type)
  return found ? found.label : type
}

function getTypeClass(type: string): string {
  switch (type) {
    case 'direct':
      return 'bg-blue-500/15 text-blue-400'
    case 'topic':
      return 'bg-emerald-500/15 text-emerald-400'
    case 'fanout':
      return 'bg-purple-500/15 text-purple-400'
    case 'headers':
      return 'bg-amber-500/15 text-amber-400'
    default:
      return 'bg-slate-500/15 text-slate-400'
  }
}

async function fetchData(forceRefresh: boolean | Event = false) {
  const isForce = typeof forceRefresh === 'boolean' ? forceRefresh : false
  if (isFetching && !isForce) return
  if (!isActive) return

  const name = exchangeName.value
  currentExchangeName = name

  try {
    isFetching = true
    if (!hasLoaded || isForce) {
      loading.value = true
    }
    const data = await getExchangeDetail(name)
    if (currentExchangeName !== name) return
    exchangeDetail.value = data
    lastUpdated.value = new Date()
    hasLoaded = true
  } catch (err: any) {
    if (currentExchangeName !== name) return
    console.error('Failed to fetch exchange detail:', err)
    if (err.response?.status === 404) {
      ElMessage.error(`交换机 "${name}" 不存在`)
      router.push('/exchanges')
    }
  } finally {
    if (currentExchangeName === name) {
      loading.value = false
      isFetching = false
    }
  }
}

async function fetchQueues() {
  try {
    const data = await getQueues()
    queues.value = data
  } catch (err) {
    console.error('Failed to fetch queues:', err)
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
  router.push('/exchanges')
}

async function handleDelete() {
  if (!exchangeDetail.value) return
  try {
    await ElMessageBox.confirm(
      `确定要删除交换机 "${exchangeDetail.value.name}" 吗？\n\n此操作将永久删除交换机及其所有绑定关系，且无法恢复！`,
      '删除交换机',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await deleteExchange(exchangeDetail.value.name)
    ElMessage.success(`交换机 "${exchangeDetail.value.name}" 已删除`)
    router.push('/exchanges')
  } catch {
  }
}

function openBindingDialog() {
  bindingForm.value = {
    destination: '',
    destination_type: 'queue',
    routing_key: '',
    arguments: undefined,
  }
  bindingArgumentsInput.value = ''
  fetchQueues()
  bindingDialogVisible.value = true
}

async function confirmCreateBinding() {
  if (!bindingForm.value.destination.trim()) {
    ElMessage.warning('请选择目标队列')
    return
  }

  const data: CreateBindingRequest = {
    destination: bindingForm.value.destination.trim(),
    destination_type: bindingForm.value.destination_type,
    routing_key: bindingForm.value.routing_key || '',
  }

  if (bindingArgumentsInput.value.trim()) {
    try {
      data.arguments = JSON.parse(bindingArgumentsInput.value.trim())
    } catch {
      ElMessage.error('Arguments 必须是有效的 JSON 格式')
      return
    }
  }

  try {
    await createBinding(exchangeName.value, data)
    ElMessage.success('绑定创建成功')
    bindingDialogVisible.value = false
    fetchData(true)
  } catch (err) {
    console.error('Failed to create binding:', err)
    ElMessage.error('创建绑定失败')
  }
}

async function handleDeleteBinding(binding: ExchangeBinding) {
  try {
    await ElMessageBox.confirm(
      `确定要解除绑定吗？\n\n目标: ${binding.destination}\n路由键: ${binding.routing_key || '(empty)'}`,
      '解除绑定',
      {
        confirmButtonText: '确认解绑',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await deleteBinding(
      exchangeName.value,
      binding.destination,
      binding.destination_type,
      binding.properties_key || binding.routing_key
    )
    ElMessage.success('绑定已解除')
    fetchData(true)
  } catch {
  }
}

function formatJson(obj: Record<string, unknown>): string {
  if (!obj || Object.keys(obj).length === 0) return '{}'
  return JSON.stringify(obj, null, 2)
}

function goToQueueDetail(queueName: string) {
  router.push(`/queues/${encodeURIComponent(queueName)}`)
}

onMounted(() => {
  isActive = true
  currentExchangeName = exchangeName.value
  fetchData()
  startRefreshTimer()
})

onActivated(() => {
  isActive = true
  if (currentExchangeName !== exchangeName.value || !hasLoaded) {
    currentExchangeName = exchangeName.value
    hasLoaded = false
    exchangeDetail.value = null
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
            <span v-if="exchangeDetail">{{ exchangeDetail.name }}</span>
            <span v-else>交换机详情</span>
          </h2>
          <p class="text-sm text-ops-muted">
            交换机详细信息
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
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/15 border border-red-500/30 text-red-400 text-sm font-medium hover:bg-red-500/25 transition-all duration-200"
          @click="handleDelete"
        >
          <Trash2 class="w-4 h-4" />
          删除交换机
        </button>
      </div>
    </div>

    <div v-if="!loading && exchangeDetail">
      <div class="grid grid-cols-1 xl:grid-cols-3 gap-5">
        <div class="card-gradient rounded-2xl border border-ops-border p-6">
          <div class="flex items-center justify-between mb-4">
            <div>
              <h3 class="text-base font-semibold text-ops-text flex items-center gap-2">
                <Settings class="w-5 h-5 text-ops-muted" />
                交换机属性
              </h3>
              <p class="text-xs text-ops-muted mt-0.5">交换机配置信息</p>
            </div>
          </div>

          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-sm text-ops-muted">Virtual Host</span>
              </div>
              <span class="text-sm font-medium text-ops-text stat-number">
                {{ exchangeDetail.vhost }}
              </span>
            </div>

            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <span class="text-sm text-ops-muted">类型</span>
              </div>
              <span
                class="inline-flex items-center px-2.5 py-1 text-xs rounded-full font-medium"
                :class="getTypeClass(exchangeDetail.type)"
              >
                {{ getTypeLabel(exchangeDetail.type) }}
              </span>
            </div>

            <div class="pt-3 border-t border-ops-border">
              <div class="grid grid-cols-3 gap-3">
                <label class="flex flex-col items-center gap-2 p-3 rounded-xl bg-ops-bg/50 border border-ops-border">
                  <input
                    v-model="exchangeDetail.durable"
                    type="checkbox"
                    disabled
                    class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary"
                  />
                  <span class="text-xs text-ops-text">Durable</span>
                </label>
                <label class="flex flex-col items-center gap-2 p-3 rounded-xl bg-ops-bg/50 border border-ops-border">
                  <input
                    v-model="exchangeDetail.auto_delete"
                    type="checkbox"
                    disabled
                    class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary"
                  />
                  <span class="text-xs text-ops-text">Auto-delete</span>
                </label>
                <label class="flex flex-col items-center gap-2 p-3 rounded-xl bg-ops-bg/50 border border-ops-border">
                  <input
                    v-model="exchangeDetail.internal"
                    type="checkbox"
                    disabled
                    class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary"
                  />
                  <span class="text-xs text-ops-text">Internal</span>
                </label>
              </div>
            </div>

            <div class="pt-3 border-t border-ops-border">
              <div class="flex items-center gap-2 mb-2">
                <span class="text-sm text-ops-muted">Arguments</span>
              </div>
              <pre class="p-3 rounded-xl bg-ops-bg/50 border border-ops-border text-xs text-ops-text font-mono overflow-x-auto">
{{ formatJson(exchangeDetail.arguments) }}</pre
              >
            </div>
          </div>
        </div>

        <div class="xl:col-span-2 space-y-5">
          <div class="card-gradient rounded-2xl border border-ops-border p-6">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="text-base font-semibold text-ops-text flex items-center gap-2">
                  <Link2 class="w-5 h-5 text-ops-muted" />
                  绑定关系图
                </h3>
                <p class="text-xs text-ops-muted mt-0.5">交换机到队列的可视化绑定</p>
              </div>
              <button
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ops-primary/15 border border-ops-primary/30 text-ops-primary text-xs font-medium hover:bg-ops-primary/25 transition-all duration-200"
                @click="openBindingDialog"
              >
                <Plus class="w-3.5 h-3.5" />
                新建绑定
              </button>
            </div>

            <div v-if="exchangeDetail.bindings.length > 0" class="py-4">
              <div class="flex flex-col items-center gap-6">
                <div class="flex items-center gap-3 px-5 py-3 rounded-xl bg-gradient-to-r from-ops-primary/20 to-ops-accent/20 border border-ops-primary/30">
                  <Share2 class="w-5 h-5 text-ops-primary" />
                  <span class="font-semibold text-ops-text">{{ exchangeDetail.name }}</span>
                  <span
                    class="inline-flex items-center px-2 py-0.5 text-xs rounded-full"
                    :class="getTypeClass(exchangeDetail.type)"
                  >
                    {{ getTypeLabel(exchangeDetail.type) }}
                  </span>
                </div>

                <div class="flex flex-col gap-4 w-full max-w-xl">
                  <div
                    v-for="binding in exchangeDetail.bindings"
                    :key="binding.properties_key || binding.routing_key + binding.destination"
                    class="relative flex items-center gap-4 px-4"
                  >
                    <div class="flex-1 flex items-center justify-end">
                      <div class="w-10" />
                    </div>

                    <div class="flex flex-col items-center gap-1">
                      <div class="w-6 h-6 rounded-full border-2 border-dashed border-ops-muted/30 flex items-center justify-center">
                        <ArrowRight class="w-3 h-3 text-ops-muted/50" />
                      </div>
                      <code
                        v-if="binding.routing_key"
                        class="px-2 py-0.5 text-xs rounded bg-emerald-500/15 text-emerald-400 font-mono whitespace-nowrap"
                      >
                        {{ binding.routing_key }}
                      </code>
                      <code
                        v-else
                        class="px-2 py-0.5 text-xs rounded bg-slate-500/15 text-slate-400 font-mono whitespace-nowrap"
                      >
                        (empty)
                      </code>
                    </div>

                    <div class="flex-1 flex items-center gap-2">
                      <button
                        v-if="binding.destination_type === 'queue'"
                        class="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-ops-bg/50 border border-ops-border hover:border-ops-primary/50 hover:bg-ops-card/30 transition-all duration-150 group"
                        @click="goToQueueDetail(binding.destination)"
                      >
                        <Database class="w-4 h-4 text-ops-muted group-hover:text-ops-primary transition-colors" />
                        <span class="text-sm font-medium text-ops-text group-hover:text-ops-primary transition-colors">
                          {{ binding.destination }}
                        </span>
                        <ArrowRight class="w-3.5 h-3.5 text-ops-muted/50 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </button>
                      <div
                        v-else
                        class="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-ops-bg/50 border border-ops-border"
                      >
                        <Share2 class="w-4 h-4 text-ops-muted" />
                        <span class="text-sm font-medium text-ops-text">{{ binding.destination }}</span>
                        <span class="px-1.5 py-0.5 text-xs rounded bg-purple-500/15 text-purple-400">
                          {{ binding.destination_type }}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="py-12 text-center">
              <Link2 class="w-12 h-12 text-ops-muted/30 mx-auto mb-3" />
              <div class="text-ops-muted text-sm mb-4">暂无绑定关系</div>
              <button
                class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-ops-primary/15 border border-ops-primary/30 text-ops-primary text-sm font-medium hover:bg-ops-primary/25 transition-all duration-200"
                @click="openBindingDialog"
              >
                <Plus class="w-4 h-4" />
                创建第一个绑定
              </button>
            </div>
          </div>

          <div class="card-gradient rounded-2xl border border-ops-border p-6">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="text-base font-semibold text-ops-text flex items-center gap-2">
                  <Link2 class="w-5 h-5 text-ops-muted" />
                  绑定列表
                </h3>
                <p class="text-xs text-ops-muted mt-0.5">所有绑定关系详情</p>
              </div>
              <div class="flex items-center gap-3">
                <span class="px-2 py-1 text-xs rounded-full bg-ops-bg text-ops-muted">
                  {{ exchangeDetail.bindings.length }} 个绑定
                </span>
                <button
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ops-primary/15 border border-ops-primary/30 text-ops-primary text-xs font-medium hover:bg-ops-primary/25 transition-all duration-200"
                  @click="openBindingDialog"
                >
                  <Plus class="w-3.5 h-3.5" />
                  新建绑定
                </button>
              </div>
            </div>

            <div v-if="exchangeDetail.bindings.length > 0" class="overflow-x-auto">
              <table class="w-full">
                <thead>
                  <tr class="border-b border-ops-border">
                    <th class="text-left px-4 py-3 text-sm font-medium text-ops-muted">
                      目标
                    </th>
                    <th class="text-left px-4 py-3 text-sm font-medium text-ops-muted">
                      类型
                    </th>
                    <th class="text-left px-4 py-3 text-sm font-medium text-ops-muted">
                      Routing Key
                    </th>
                    <th class="text-left px-4 py-3 text-sm font-medium text-ops-muted">
                      Arguments
                    </th>
                    <th class="text-right px-4 py-3 text-sm font-medium text-ops-muted">
                      操作
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="binding in exchangeDetail.bindings"
                    :key="binding.properties_key || binding.routing_key + binding.destination"
                    class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
                  >
                    <td class="px-4 py-3">
                      <a
                        v-if="binding.destination_type === 'queue'"
                        href="javascript:void(0)"
                        class="flex items-center gap-2 text-ops-text hover:text-ops-primary transition-colors"
                        @click="goToQueueDetail(binding.destination)"
                      >
                        <Database class="w-4 h-4 text-ops-muted" />
                        <span class="font-medium">{{ binding.destination }}</span>
                      </a>
                      <div v-else class="flex items-center gap-2 text-ops-text">
                        <Share2 class="w-4 h-4 text-ops-muted" />
                        <span class="font-medium">{{ binding.destination }}</span>
                      </div>
                    </td>
                    <td class="px-4 py-3">
                      <span
                        v-if="binding.destination_type === 'queue'"
                        class="inline-flex items-center px-2 py-0.5 text-xs rounded bg-blue-500/15 text-blue-400"
                      >
                        Queue
                      </span>
                      <span
                        v-else
                        class="inline-flex items-center px-2 py-0.5 text-xs rounded bg-purple-500/15 text-purple-400"
                      >
                        Exchange
                      </span>
                    </td>
                    <td class="px-4 py-3">
                      <code
                        v-if="binding.routing_key"
                        class="px-2 py-0.5 text-xs rounded bg-emerald-500/15 text-emerald-400 font-mono"
                      >
                        {{ binding.routing_key }}
                      </code>
                      <span v-else class="text-ops-muted text-xs">(empty)</span>
                    </td>
                    <td class="px-4 py-3">
                      <code
                        v-if="binding.arguments && Object.keys(binding.arguments).length > 0"
                        class="px-2 py-0.5 text-xs rounded bg-ops-bg text-ops-text font-mono"
                      >
                        {{ formatJson(binding.arguments) }}
                      </code>
                      <span v-else class="text-ops-muted text-xs">-</span>
                    </td>
                    <td class="px-4 py-3 text-right">
                      <button
                        class="p-1.5 rounded-lg text-ops-muted hover:text-red-400 hover:bg-red-500/10 transition-all duration-150"
                        title="解除绑定"
                        @click="handleDeleteBinding(binding)"
                      >
                        <Trash2 class="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-else class="py-8 text-center">
              <Link2 class="w-10 h-10 text-ops-muted/30 mx-auto mb-3" />
              <div class="text-ops-muted text-sm">暂无绑定信息</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading && !exchangeDetail">
      <div class="card-gradient rounded-2xl border border-ops-border p-12 text-center">
        <RefreshCw class="w-12 h-12 text-ops-muted/30 mx-auto mb-3 animate-spin" />
        <div class="text-ops-muted text-sm">加载中...</div>
      </div>
    </div>

    <el-dialog
      v-model="bindingDialogVisible"
      title="新建绑定"
      width="500px"
      :close-on-click-modal="false"
      class="binding-create-dialog"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">交换机</label>
          <div class="px-4 py-2.5 rounded-lg bg-ops-bg/50 border border-ops-border">
            <div class="flex items-center gap-2">
              <Share2 class="w-4 h-4 text-ops-muted" />
              <span class="text-sm font-medium text-ops-text">{{ exchangeName }}</span>
            </div>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">目标队列 <span class="text-red-400">*</span></label>
          <el-select
            v-model="bindingForm.destination"
            placeholder="请选择目标队列"
            class="w-full"
            filterable
          >
            <el-option
              v-for="queue in queues"
              :key="queue.name"
              :label="queue.name"
              :value="queue.name"
            />
          </el-select>
          <p class="text-xs text-ops-muted mt-1">选择要绑定到此交换机的队列</p>
        </div>

        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">Routing Key</label>
          <input
            v-model="bindingForm.routing_key"
            type="text"
            placeholder="请输入 routing key，例如：order.created"
            class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150"
          />
          <p class="text-xs text-ops-muted mt-1">
            Fanout 类型交换机不需要 routing key，可留空；Topic 类型支持通配符 * 和 #
          </p>
        </div>

        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">Arguments (JSON)</label>
          <textarea
            v-model="bindingArgumentsInput"
            rows="2"
            placeholder='例如: {"x-match": "all"}'
            class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150 font-mono text-sm"
          />
          <p class="text-xs text-ops-muted mt-1">可选，绑定的额外参数，必须为有效 JSON 格式</p>
        </div>
      </div>

      <template #footer>
        <div class="flex items-center justify-end gap-3">
          <button
            class="px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 transition-all duration-200"
            @click="bindingDialogVisible = false"
          >
            取消
          </button>
          <button
            class="px-4 py-2 rounded-lg bg-ops-primary text-white text-sm font-medium hover:bg-ops-primary/90 transition-all duration-200"
            @click="confirmCreateBinding"
          >
            创建绑定
          </button>
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

.binding-create-dialog :deep(.el-dialog) {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 16px;
}

.binding-create-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #334155;
  padding: 20px 24px;
}

.binding-create-dialog :deep(.el-dialog__title) {
  color: #E2E8F0;
  font-size: 18px;
  font-weight: 600;
}

.binding-create-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.binding-create-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #334155;
  padding: 16px 24px;
}

.binding-create-dialog :deep(.el-select) {
  --el-select-border-color: #334155;
  --el-select-input-background-color: #0F172A;
  --el-select-text-color: #E2E8F0;
  --el-select-placeholder-text-color: #64748B;
}

.binding-create-dialog :deep(.el-select .el-input__wrapper) {
  background: #0F172A;
  border: 1px solid #334155;
  border-radius: 8px;
  box-shadow: none;
}

.binding-create-dialog :deep(.el-select .el-input__wrapper:hover) {
  border-color: #6366F1;
}

.binding-create-dialog :deep(.el-select .el-input__wrapper.is-focus) {
  border-color: #6366F1;
  box-shadow: none;
}

.binding-create-dialog :deep(.el-select-dropdown) {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 12px;
}

.binding-create-dialog :deep(.el-select-dropdown__item) {
  color: #E2E8F0;
}

.binding-create-dialog :deep(.el-select-dropdown__item.hover),
.binding-create-dialog :deep(.el-select-dropdown__item:hover) {
  background: rgba(99, 102, 241, 0.1);
}

.binding-create-dialog :deep(.el-select-dropdown__item.selected) {
  background: rgba(99, 102, 241, 0.15);
  color: #6366F1;
  font-weight: 600;
}

.binding-create-dialog :deep(.el-message-box) {
  background: #1E293B;
  border: 1px solid #334155;
}

.binding-create-dialog :deep(.el-message-box__title) {
  color: #E2E8F0;
}

.binding-create-dialog :deep(.el-message-box__message) {
  color: #94A3B8;
}

.binding-create-dialog :deep(.el-message-box__content) {
  color: #94A3B8;
}
</style>
