<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import { useRouter } from 'vue-router'
import {
  RefreshCw,
  Plus,
  Trash2,
  Database,
  Activity,
  Clock,
  Users,
  AlertCircle,
  ArrowRight,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getQueues,
  createQueue,
  purgeQueue,
  deleteQueue,
  type QueueListItem,
  type CreateQueueRequest,
} from '@/api'

defineOptions({
  name: 'QueueList',
})

const router = useRouter()
const loading = ref(false)
const queues = ref<QueueListItem[]>([])
const lastUpdated = ref<Date | null>(null)
let refreshTimer: number | null = null
let isActive = false
let isFetching = false
let hasLoaded = false

const createDialogVisible = ref(false)
const createForm = ref<CreateQueueRequest>({
  name: '',
  durable: true,
  auto_delete: false,
  exclusive: false,
  arguments: undefined,
})

const argumentsInput = ref('')

async function fetchData(forceRefresh: boolean | Event = false) {
  const isForce = typeof forceRefresh === 'boolean' ? forceRefresh : false
  if (isFetching && !isForce) return
  if (!isActive) return

  try {
    isFetching = true
    if (!hasLoaded || isForce) {
      loading.value = true
    }
    const data = await getQueues()
    queues.value = data
    lastUpdated.value = new Date()
    hasLoaded = true
  } catch (err) {
    console.error('Failed to fetch queues:', err)
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

function goToDetail(queueName: string) {
  router.push(`/queues/${encodeURIComponent(queueName)}`)
}

function handleCreate() {
  createForm.value = {
    name: '',
    durable: true,
    auto_delete: false,
    exclusive: false,
    arguments: undefined,
  }
  argumentsInput.value = ''
  createDialogVisible.value = true
}

async function confirmCreate() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入队列名称')
    return
  }

  const data: CreateQueueRequest = {
    name: createForm.value.name.trim(),
    durable: createForm.value.durable,
    auto_delete: createForm.value.auto_delete,
    exclusive: createForm.value.exclusive,
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
    await createQueue(data)
    ElMessage.success(`队列 "${data.name}" 创建成功`)
    createDialogVisible.value = false
    fetchData()
  } catch (err) {
    console.error('Failed to create queue:', err)
    ElMessage.error('创建队列失败')
  }
}

async function handlePurge(queue: QueueListItem) {
  try {
    await ElMessageBox.confirm(
      `确定要清空队列 "${queue.name}" 吗？\n\n此操作将删除队列中所有消息，且无法恢复！`,
      '清空队列',
      {
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await purgeQueue(queue.name)
    ElMessage.success(`队列 "${queue.name}" 已清空`)
    fetchData()
  } catch {
    // 用户取消操作
  }
}

async function handleDelete(queue: QueueListItem) {
  try {
    await ElMessageBox.confirm(
      `确定要删除队列 "${queue.name}" 吗？\n\n此操作将永久删除队列及其所有消息，且无法恢复！`,
      '删除队列',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await deleteQueue(queue.name)
    ElMessage.success(`队列 "${queue.name}" 已删除`)
    fetchData()
  } catch {
    // 用户取消操作
  }
}

function formatNumber(n: number): string {
  return n.toLocaleString('zh-CN')
}

function getStatusText(status: string): string {
  return status === 'running' ? '运行中' : '空闲'
}

function getStatusClass(status: string): string {
  return status === 'running'
    ? 'bg-emerald-500/15 text-emerald-400'
    : 'bg-slate-500/15 text-slate-400'
}

function getStatusDotClass(status: string): string {
  return status === 'running' ? 'status-connected' : ''
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
        <h2 class="text-xl font-bold text-ops-text mb-1">队列管理</h2>
        <p class="text-sm text-ops-muted">
          管理 RabbitMQ 中的所有队列，支持查看、创建、清空和删除操作
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
          创建队列
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
                  <Database class="w-4 h-4" />
                  队列名称
                </div>
              </th>
              <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center justify-end gap-2">
                  <Clock class="w-4 h-4" />
                  Ready
                </div>
              </th>
              <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center justify-end gap-2">
                  <Activity class="w-4 h-4" />
                  Unacked
                </div>
              </th>
              <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center justify-end gap-2">
                  <AlertCircle class="w-4 h-4" />
                  Total
                </div>
              </th>
              <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center justify-end gap-2">
                  <Users class="w-4 h-4" />
                  消费者
                </div>
              </th>
              <th class="text-center px-6 py-4 text-sm font-medium text-ops-muted">
                状态
              </th>
              <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="queue in queues"
              :key="queue.name"
              class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
            >
              <td class="px-6 py-4">
                <a
                  href="javascript:void(0)"
                  class="flex items-center gap-2 text-ops-text hover:text-ops-primary transition-colors duration-150 group"
                  @click="goToDetail(queue.name)"
                >
                  <span class="font-medium">{{ queue.name }}</span>
                  <ArrowRight class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity duration-150" />
                </a>
                <div class="flex items-center gap-2 mt-1">
                  <span
                    v-if="queue.durable"
                    class="inline-flex items-center px-1.5 py-0.5 text-xs rounded bg-blue-500/15 text-blue-400"
                  >
                    Durable
                  </span>
                  <span
                    v-if="queue.auto_delete"
                    class="inline-flex items-center px-1.5 py-0.5 text-xs rounded bg-amber-500/15 text-amber-400"
                  >
                    Auto-delete
                  </span>
                  <span
                    v-if="queue.exclusive"
                    class="inline-flex items-center px-1.5 py-0.5 text-xs rounded bg-purple-500/15 text-purple-400"
                  >
                    Exclusive
                  </span>
                </div>
              </td>
              <td class="px-6 py-4 text-right text-ops-text font-medium stat-number">
                {{ formatNumber(queue.ready) }}
              </td>
              <td class="px-6 py-4 text-right text-amber-400 font-medium stat-number">
                {{ formatNumber(queue.unacked) }}
              </td>
              <td class="px-6 py-4 text-right text-ops-text font-medium stat-number">
                {{ formatNumber(queue.total) }}
              </td>
              <td class="px-6 py-4 text-right text-ops-text font-medium stat-number">
                {{ formatNumber(queue.consumers) }}
              </td>
              <td class="px-6 py-4 text-center">
                <div class="flex items-center justify-center gap-2">
                  <span
                    class="status-dot"
                    :class="queue.status === 'running' ? 'status-connected' : 'bg-slate-500'"
                  />
                  <span
                    class="inline-flex items-center px-2 py-1 text-xs rounded-full"
                    :class="getStatusClass(queue.status)"
                  >
                    {{ getStatusText(queue.status) }}
                  </span>
                </div>
              </td>
              <td class="px-6 py-4 text-right">
                <div class="flex items-center justify-end gap-2">
                  <button
                    class="p-2 rounded-lg text-ops-muted hover:text-amber-400 hover:bg-amber-500/10 transition-all duration-150"
                    title="清空队列"
                    @click.stop="handlePurge(queue)"
                  >
                    <Trash2 class="w-4 h-4" />
                  </button>
                  <button
                    class="p-2 rounded-lg text-ops-muted hover:text-red-400 hover:bg-red-500/10 transition-all duration-150"
                    title="删除队列"
                    @click.stop="handleDelete(queue)"
                  >
                    <Trash2 class="w-4 h-4" />
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="queues.length === 0 && !loading">
              <td colspan="7" class="px-6 py-12 text-center">
                <div class="flex flex-col items-center gap-3">
                  <Database class="w-12 h-12 text-ops-muted/30" />
                  <div class="text-ops-muted text-sm">暂无队列数据</div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="loading && queues.length === 0">
      <div class="card-gradient rounded-2xl border border-ops-border p-12 text-center">
        <RefreshCw class="w-12 h-12 text-ops-muted/30 mx-auto mb-3 animate-spin" />
        <div class="text-ops-muted text-sm">加载中...</div>
      </div>
    </div>

    <el-dialog
      v-model="createDialogVisible"
      title="创建队列"
      width="500px"
      :close-on-click-modal="false"
      class="queue-create-dialog"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">队列名称 <span class="text-red-400">*</span></label>
          <input
            v-model="createForm.name"
            type="text"
            placeholder="请输入队列名称，例如：order.notification"
            class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150"
          />
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
              v-model="createForm.exclusive"
              type="checkbox"
              class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary"
            />
            <span class="text-sm text-ops-text">Exclusive</span>
          </label>
        </div>

        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">Arguments (JSON)</label>
          <textarea
            v-model="argumentsInput"
            rows="3"
            placeholder='例如: {"x-message-ttl": 60000, "x-dead-letter-exchange": "dlx"}'
            class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150 font-mono text-sm"
          />
          <p class="text-xs text-ops-muted mt-1">可选，队列的额外参数，必须为有效 JSON 格式</p>
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
.queue-create-dialog :deep(.el-dialog) {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 16px;
}

.queue-create-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #334155;
  padding: 20px 24px;
}

.queue-create-dialog :deep(.el-dialog__title) {
  color: #E2E8F0;
  font-size: 18px;
  font-weight: 600;
}

.queue-create-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.queue-create-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #334155;
  padding: 16px 24px;
}

.queue-create-dialog :deep(.el-message-box) {
  background: #1E293B;
  border: 1px solid #334155;
}

.queue-create-dialog :deep(.el-message-box__title) {
  color: #E2E8F0;
}

.queue-create-dialog :deep(.el-message-box__message) {
  color: #94A3B8;
}

.queue-create-dialog :deep(.el-message-box__content) {
  color: #94A3B8;
}
</style>
