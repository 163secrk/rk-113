<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import { useRouter } from 'vue-router'
import {
  RefreshCw,
  Plus,
  Trash2,
  Share2,
  ArrowRight,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getExchanges,
  createExchange,
  deleteExchange,
  type ExchangeListItem,
  type CreateExchangeRequest,
} from '@/api'

defineOptions({
  name: 'ExchangeList',
})

const router = useRouter()
const loading = ref(false)
const exchanges = ref<ExchangeListItem[]>([])
const lastUpdated = ref<Date | null>(null)
let refreshTimer: number | null = null
let isActive = false
let isFetching = false
let hasLoaded = false

const createDialogVisible = ref(false)
const createForm = ref<CreateExchangeRequest>({
  name: '',
  type: 'direct',
  durable: true,
  auto_delete: false,
  internal: false,
  arguments: undefined,
})

const argumentsInput = ref('')

const exchangeTypes = [
  { value: 'direct', label: 'Direct', desc: '精确匹配路由键' },
  { value: 'topic', label: 'Topic', desc: '通配符匹配路由键' },
  { value: 'fanout', label: 'Fanout', desc: '广播到所有绑定队列' },
  { value: 'headers', label: 'Headers', desc: '基于消息头匹配' },
]

async function fetchData(forceRefresh: boolean | Event = false) {
  const isForce = typeof forceRefresh === 'boolean' ? forceRefresh : false
  if (isFetching && !isForce) return
  if (!isActive) return

  try {
    isFetching = true
    if (!hasLoaded || isForce) {
      loading.value = true
    }
    const data = await getExchanges()
    exchanges.value = data
    lastUpdated.value = new Date()
    hasLoaded = true
  } catch (err) {
    console.error('Failed to fetch exchanges:', err)
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

function goToDetail(exchangeName: string) {
  router.push(`/exchanges/${encodeURIComponent(exchangeName)}`)
}

function handleCreate() {
  createForm.value = {
    name: '',
    type: 'direct',
    durable: true,
    auto_delete: false,
    internal: false,
    arguments: undefined,
  }
  argumentsInput.value = ''
  createDialogVisible.value = true
}

async function confirmCreate() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入交换机名称')
    return
  }

  const data: CreateExchangeRequest = {
    name: createForm.value.name.trim(),
    type: createForm.value.type,
    durable: createForm.value.durable,
    auto_delete: createForm.value.auto_delete,
    internal: createForm.value.internal,
  }

  if (argumentsInput.value.trim()) {
    try {
      data.arguments = JSON.parse(argumentsInput.value.trim())
    } catch {
      ElMessage.error('Arguments 必须是有效的 JSON 格式')
      return
    }
  }

  try {
    await createExchange(data)
    ElMessage.success(`交换机 "${data.name}" 创建成功`)
    createDialogVisible.value = false
    fetchData()
  } catch (err) {
    console.error('Failed to create exchange:', err)
    ElMessage.error('创建交换机失败')
  }
}

async function handleDelete(exchange: ExchangeListItem) {
  try {
    await ElMessageBox.confirm(
      `确定要删除交换机 "${exchange.name}" 吗？\n\n此操作将永久删除交换机及其所有绑定关系，且无法恢复！`,
      '删除交换机',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await deleteExchange(exchange.name)
    ElMessage.success(`交换机 "${exchange.name}" 已删除`)
    fetchData()
  } catch {
  }
}

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
        <h2 class="text-xl font-bold text-ops-text mb-1">交换机管理</h2>
        <p class="text-sm text-ops-muted">
          管理 RabbitMQ 中的所有交换机，支持查看、创建和删除操作
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
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-primary text-white text-sm font-medium hover:bg-ops-primary/90 transition-all duration-200"
          @click="handleCreate"
        >
          <Plus class="w-4 h-4" />
          创建交换机
        </button>
      </div>
    </div>

    <div class="card-gradient rounded-2xl border border-ops-border overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-ops-border">
              <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center gap-2">
                  <Share2 class="w-4 h-4" />
                  交换机名称
                </div>
              </th>
              <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">
                类型
              </th>
              <th class="text-center px-6 py-4 text-sm font-medium text-ops-muted">
                Virtual Host
              </th>
              <th class="text-center px-6 py-4 text-sm font-medium text-ops-muted">
                Durable
              </th>
              <th class="text-center px-6 py-4 text-sm font-medium text-ops-muted">
                Auto-delete
              </th>
              <th class="text-center px-6 py-4 text-sm font-medium text-ops-muted">
                Internal
              </th>
              <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="exchange in exchanges"
              :key="exchange.name"
              class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
            >
              <td class="px-6 py-4">
                <a
                  href="javascript:void(0)"
                  class="flex items-center gap-2 text-ops-text hover:text-ops-primary transition-colors duration-150 group"
                  @click="goToDetail(exchange.name)"
                >
                  <span class="font-medium">{{ exchange.name }}</span>
                  <ArrowRight class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity duration-150" />
                </a>
              </td>
              <td class="px-6 py-4">
                <span
                  class="inline-flex items-center px-2.5 py-1 text-xs rounded-full font-medium"
                  :class="getTypeClass(exchange.type)"
                >
                  {{ getTypeLabel(exchange.type) }}
                </span>
              </td>
              <td class="px-6 py-4 text-center text-ops-text stat-number">
                {{ exchange.vhost }}
              </td>
              <td class="px-6 py-4 text-center">
                <span
                  v-if="exchange.durable"
                  class="inline-flex items-center px-2 py-0.5 text-xs rounded bg-emerald-500/15 text-emerald-400"
                >
                  是
                </span>
                <span
                  v-else
                  class="inline-flex items-center px-2 py-0.5 text-xs rounded bg-slate-500/15 text-slate-400"
                >
                  否
                </span>
              </td>
              <td class="px-6 py-4 text-center">
                <span
                  v-if="exchange.auto_delete"
                  class="inline-flex items-center px-2 py-0.5 text-xs rounded bg-amber-500/15 text-amber-400"
                >
                  是
                </span>
                <span
                  v-else
                  class="inline-flex items-center px-2 py-0.5 text-xs rounded bg-slate-500/15 text-slate-400"
                >
                  否
                </span>
              </td>
              <td class="px-6 py-4 text-center">
                <span
                  v-if="exchange.internal"
                  class="inline-flex items-center px-2 py-0.5 text-xs rounded bg-purple-500/15 text-purple-400"
                >
                  是
                </span>
                <span
                  v-else
                  class="inline-flex items-center px-2 py-0.5 text-xs rounded bg-slate-500/15 text-slate-400"
                >
                  否
                </span>
              </td>
              <td class="px-6 py-4 text-right">
                <button
                  class="p-2 rounded-lg text-ops-muted hover:text-red-400 hover:bg-red-500/10 transition-all duration-150"
                  title="删除交换机"
                  @click.stop="handleDelete(exchange)"
                >
                  <Trash2 class="w-4 h-4" />
                </button>
              </td>
            </tr>
            <tr v-if="exchanges.length === 0 && !loading">
              <td colspan="7" class="px-6 py-12 text-center">
                <div class="flex flex-col items-center gap-3">
                  <Share2 class="w-12 h-12 text-ops-muted/30" />
                  <div class="text-ops-muted text-sm">暂无交换机数据</div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="loading && exchanges.length === 0">
      <div class="card-gradient rounded-2xl border border-ops-border p-12 text-center">
        <RefreshCw class="w-12 h-12 text-ops-muted/30 mx-auto mb-3 animate-spin" />
        <div class="text-ops-muted text-sm">加载中...</div>
      </div>
    </div>

    <el-dialog
      v-model="createDialogVisible"
      title="创建交换机"
      width="500px"
      :close-on-click-modal="false"
      class="exchange-create-dialog"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">交换机名称 <span class="text-red-400">*</span></label>
          <input
            v-model="createForm.name"
            type="text"
            placeholder="请输入交换机名称，例如：order.exchange"
            class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">交换机类型 <span class="text-red-400">*</span></label>
          <div class="grid grid-cols-2 gap-3">
            <label
              v-for="t in exchangeTypes"
              :key="t.value"
              class="flex flex-col gap-1 p-3 rounded-xl border cursor-pointer transition-all duration-150"
              :class="createForm.type === t.value
                ? 'bg-ops-primary/10 border-ops-primary'
                : 'bg-ops-bg/50 border-ops-border hover:border-ops-primary/50'"
            >
              <div class="flex items-center gap-2">
                <input
                  v-model="createForm.type"
                  type="radio"
                  :value="t.value"
                  class="w-4 h-4 text-ops-primary"
                />
                <span class="text-sm font-medium text-ops-text">{{ t.label }}</span>
              </div>
              <span class="text-xs text-ops-muted ml-6">{{ t.desc }}</span>
            </label>
          </div>
        </div>

        <div class="grid grid-cols-3 gap-4">
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              v-model="createForm.durable"
              type="checkbox"
              class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary"
            />
            <span class="text-sm text-ops-text">Durable</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              v-model="createForm.auto_delete"
              type="checkbox"
              class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary"
            />
            <span class="text-sm text-ops-text">Auto-delete</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              v-model="createForm.internal"
              type="checkbox"
              class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary"
            />
            <span class="text-sm text-ops-text">Internal</span>
          </label>
        </div>

        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">Arguments (JSON)</label>
          <textarea
            v-model="argumentsInput"
            rows="3"
            placeholder='例如: {"alternate-exchange": "backup"}'
            class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150 font-mono text-sm"
          />
          <p class="text-xs text-ops-muted mt-1">可选，交换机的额外参数，必须为有效 JSON 格式</p>
        </div>
      </div>

      <template #footer>
        <div class="flex items-center justify-end gap-3">
          <button
            class="px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 transition-all duration-200"
            @click="createDialogVisible = false"
          >
            取消
          </button>
          <button
            class="px-4 py-2 rounded-lg bg-ops-primary text-white text-sm font-medium hover:bg-ops-primary/90 transition-all duration-200"
            @click="confirmCreate"
          >
            创建
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.exchange-create-dialog :deep(.el-dialog) {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 16px;
}

.exchange-create-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #334155;
  padding: 20px 24px;
}

.exchange-create-dialog :deep(.el-dialog__title) {
  color: #E2E8F0;
  font-size: 18px;
  font-weight: 600;
}

.exchange-create-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.exchange-create-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #334155;
  padding: 16px 24px;
}

.exchange-create-dialog :deep(.el-message-box) {
  background: #1E293B;
  border: 1px solid #334155;
}

.exchange-create-dialog :deep(.el-message-box__title) {
  color: #E2E8F0;
}

.exchange-create-dialog :deep(.el-message-box__message) {
  color: #94A3B8;
}

.exchange-create-dialog :deep(.el-message-box__content) {
  color: #94A3B8;
}
</style>
