<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  RefreshCw,
  Search,
  FileText,
  Send,
  Download,
  CheckCircle,
  XCircle,
  Clock,
  Calendar,
  Filter,
  ChevronLeft,
  ChevronRight,
  X,
  Hash,
  Mail,
  Tag,
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import {
  getAuditLogs,
  getAuditStats,
  getAuditLogDetail,
  type AuditLogItem,
  type AuditStats,
} from '@/api'

defineOptions({
  name: 'MessageAudit',
})

const loading = ref(false)
const auditLogs = ref<AuditLogItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const stats = ref<AuditStats>({
  publish: 0,
  consume: 0,
  ack: 0,
  reject: 0,
  total: 0,
})

const operationType = ref('')
const keyword = ref('')
const startTime = ref('')
const endTime = ref('')

const detailDialogVisible = ref(false)
const currentDetail = ref<AuditLogItem | null>(null)
const detailLoading = ref(false)

const operationTypes = [
  { value: '', label: '全部操作', icon: FileText },
  { value: 'publish', label: '发布消息', icon: Send },
  { value: 'consume', label: '消费消息', icon: Download },
  { value: 'ack', label: '确认消息', icon: CheckCircle },
  { value: 'reject', label: '拒绝消息', icon: XCircle },
]

const totalPages = computed(() => Math.ceil(total.value / pageSize.value) || 1)

function getOperationLabel(type: string): string {
  const found = operationTypes.find((t) => t.value === type)
  return found ? found.label : type
}

function getOperationClass(type: string): string {
  switch (type) {
    case 'publish':
      return 'bg-blue-500/15 text-blue-400 border-blue-500/30'
    case 'consume':
      return 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
    case 'ack':
      return 'bg-purple-500/15 text-purple-400 border-purple-500/30'
    case 'reject':
      return 'bg-red-500/15 text-red-400 border-red-500/30'
    default:
      return 'bg-slate-500/15 text-slate-400 border-slate-500/30'
  }
}

function getStatusClass(status: string): string {
  return status === 'success'
    ? 'bg-emerald-500/15 text-emerald-400'
    : 'bg-red-500/15 text-red-400'
}

function formatDateTime(dateStr: string): string {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', { hour12: false })
}

function formatTime(dateStr: string): string {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  return date.toLocaleDateString('zh-CN')
}

async function fetchStats() {
  try {
    const data = await getAuditStats(startTime.value || undefined, endTime.value || undefined)
    stats.value = data
  } catch (err) {
    console.error('Failed to fetch audit stats:', err)
  }
}

async function fetchLogs(forceRefresh = false) {
  if (loading.value && !forceRefresh) return

  try {
    loading.value = true
    const params: Record<string, string | number> = {
      page: page.value,
      page_size: pageSize.value,
    }
    if (operationType.value) params.operation_type = operationType.value
    if (keyword.value) params.keyword = keyword.value
    if (startTime.value) params.start_time = startTime.value
    if (endTime.value) params.end_time = endTime.value

    const data = await getAuditLogs(params)
    auditLogs.value = data.items
    total.value = data.total
  } catch (err) {
    console.error('Failed to fetch audit logs:', err)
    ElMessage.error('获取审计日志失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  fetchLogs(true)
  fetchStats()
}

function handleReset() {
  operationType.value = ''
  keyword.value = ''
  startTime.value = ''
  endTime.value = ''
  page.value = 1
  fetchLogs(true)
  fetchStats()
}

function handlePageChange(newPage: number) {
  if (newPage < 1 || newPage > totalPages.value) return
  page.value = newPage
  fetchLogs()
}

async function handleViewDetail(log: AuditLogItem) {
  try {
    detailLoading.value = true
    detailDialogVisible.value = true
    const data = await getAuditLogDetail(log.id)
    currentDetail.value = data
  } catch (err) {
    console.error('Failed to fetch audit log detail:', err)
    ElMessage.error('获取审计详情失败')
  } finally {
    detailLoading.value = false
  }
}

function formatJson(data: unknown): string {
  if (!data) return ''
  try {
    return JSON.stringify(data, null, 2)
  } catch {
    return String(data)
  }
}

onMounted(() => {
  fetchLogs()
  fetchStats()
})
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl font-bold text-ops-text mb-1">消息审计</h2>
        <p class="text-sm text-ops-muted">
          记录所有消息操作的审计日志，支持按时间、类型、关键字筛选
        </p>
      </div>
      <button
        class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 hover:border-ops-primary/50 transition-all duration-200"
        :disabled="loading"
        @click="handleSearch"
      >
        <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" />
        刷新
      </button>
    </div>

    <div class="grid grid-cols-5 gap-4">
      <div class="stat-card card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-blue-500/15 flex items-center justify-center">
            <FileText class="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <div class="text-2xl font-bold text-ops-text stat-number">{{ stats.total }}</div>
            <div class="text-xs text-ops-muted">总操作数</div>
          </div>
        </div>
      </div>
      <div class="stat-card card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-blue-500/15 flex items-center justify-center">
            <Send class="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <div class="text-2xl font-bold text-ops-text stat-number">{{ stats.publish }}</div>
            <div class="text-xs text-ops-muted">发布消息</div>
          </div>
        </div>
      </div>
      <div class="stat-card card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-emerald-500/15 flex items-center justify-center">
            <Download class="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <div class="text-2xl font-bold text-ops-text stat-number">{{ stats.consume }}</div>
            <div class="text-xs text-ops-muted">消费消息</div>
          </div>
        </div>
      </div>
      <div class="stat-card card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-purple-500/15 flex items-center justify-center">
            <CheckCircle class="w-5 h-5 text-purple-400" />
          </div>
          <div>
            <div class="text-2xl font-bold text-ops-text stat-number">{{ stats.ack }}</div>
            <div class="text-xs text-ops-muted">确认消息</div>
          </div>
        </div>
      </div>
      <div class="stat-card card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-lg bg-red-500/15 flex items-center justify-center">
            <XCircle class="w-5 h-5 text-red-400" />
          </div>
          <div>
            <div class="text-2xl font-bold text-ops-text stat-number">{{ stats.reject }}</div>
            <div class="text-xs text-ops-muted">拒绝消息</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card-gradient rounded-2xl border border-ops-border p-5">
      <div class="flex items-center gap-2 mb-4">
        <Filter class="w-4 h-4 text-ops-muted" />
        <span class="text-sm font-medium text-ops-text">筛选条件</span>
      </div>
      <div class="grid grid-cols-12 gap-4">
        <div class="col-span-3">
          <label class="block text-xs font-medium text-ops-muted mb-2">操作类型</label>
          <select
            v-model="operationType"
            class="w-full px-3 py-2 rounded-lg bg-ops-bg border border-ops-border text-sm text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
          >
            <option v-for="type in operationTypes" :key="type.value" :value="type.value">
              {{ type.label }}
            </option>
          </select>
        </div>
        <div class="col-span-3">
          <label class="block text-xs font-medium text-ops-muted mb-2">开始时间</label>
          <input
            v-model="startTime"
            type="datetime-local"
            class="w-full px-3 py-2 rounded-lg bg-ops-bg border border-ops-border text-sm text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
          />
        </div>
        <div class="col-span-3">
          <label class="block text-xs font-medium text-ops-muted mb-2">结束时间</label>
          <input
            v-model="endTime"
            type="datetime-local"
            class="w-full px-3 py-2 rounded-lg bg-ops-bg border border-ops-border text-sm text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
          />
        </div>
        <div class="col-span-3">
          <label class="block text-xs font-medium text-ops-muted mb-2">关键字搜索</label>
          <div class="relative">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-ops-muted" />
            <input
              v-model="keyword"
              type="text"
              placeholder="搜索消息ID、交换机、路由键等"
              class="w-full pl-9 pr-3 py-2 rounded-lg bg-ops-bg border border-ops-border text-sm text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150"
              @keyup.enter="handleSearch"
            />
          </div>
        </div>
      </div>
      <div class="flex items-center justify-end gap-3 mt-4">
        <button
          class="px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 transition-all duration-200"
          @click="handleReset"
        >
          重置
        </button>
        <button
          class="px-4 py-2 rounded-lg bg-ops-primary text-white text-sm font-medium hover:bg-ops-primary/90 transition-all duration-200"
          @click="handleSearch"
        >
          查询
        </button>
      </div>
    </div>

    <div class="card-gradient rounded-2xl border border-ops-border overflow-hidden">
      <div class="px-6 py-4 border-b border-ops-border flex items-center justify-between">
        <div class="flex items-center gap-2">
          <Clock class="w-4 h-4 text-ops-muted" />
          <span class="text-sm font-medium text-ops-text">操作时间轴</span>
          <span class="text-xs text-ops-muted">共 {{ total }} 条记录</span>
        </div>
      </div>

      <div v-if="loading && auditLogs.length === 0" class="p-12 text-center">
        <RefreshCw class="w-12 h-12 text-ops-muted/30 mx-auto mb-3 animate-spin" />
        <div class="text-ops-muted text-sm">加载中...</div>
      </div>

      <div v-else-if="auditLogs.length === 0" class="p-12 text-center">
        <FileText class="w-12 h-12 text-ops-muted/30 mx-auto mb-3" />
        <div class="text-ops-muted text-sm">暂无审计记录</div>
      </div>

      <div v-else class="relative">
        <div class="absolute left-8 top-0 bottom-0 w-px bg-ops-border/50"></div>

        <div class="divide-y divide-ops-border/30">
          <div
            v-for="log in auditLogs"
            :key="log.id"
            class="relative pl-16 pr-6 py-4 hover:bg-ops-card/30 transition-colors duration-150 cursor-pointer group"
            @click="handleViewDetail(log)"
          >
            <div
              class="absolute left-6 top-5 w-4 h-4 rounded-full border-2 z-10 bg-ops-bg"
              :class="getOperationClass(log.operation_type)"
            ></div>

            <div class="flex items-start justify-between gap-4">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-3 mb-2">
                  <span
                    class="inline-flex items-center px-2.5 py-1 text-xs rounded-full font-medium border"
                    :class="getOperationClass(log.operation_type)"
                  >
                    {{ getOperationLabel(log.operation_type) }}
                  </span>
                  <span
                    class="inline-flex items-center px-2 py-0.5 text-xs rounded font-medium"
                    :class="getStatusClass(log.status)"
                  >
                    {{ log.status === 'success' ? '成功' : '失败' }}
                  </span>
                  <span class="text-xs text-ops-muted stat-number">
                    {{ formatDateTime(log.created_at) }}
                  </span>
                </div>

                <div class="flex items-center gap-4 text-sm text-ops-text mb-2">
                  <div v-if="log.target_exchange" class="flex items-center gap-1.5">
                    <Tag class="w-3.5 h-3.5 text-ops-muted" />
                    <span class="text-ops-muted">交换机:</span>
                    <span class="font-mono text-ops-text">{{ log.target_exchange }}</span>
                  </div>
                  <div v-if="log.routing_key" class="flex items-center gap-1.5">
                    <Hash class="w-3.5 h-3.5 text-ops-muted" />
                    <span class="text-ops-muted">路由键:</span>
                    <span class="font-mono text-ops-text">{{ log.routing_key }}</span>
                  </div>
                  <div v-if="log.queue_name" class="flex items-center gap-1.5">
                    <Mail class="w-3.5 h-3.5 text-ops-muted" />
                    <span class="text-ops-muted">队列:</span>
                    <span class="font-mono text-ops-text">{{ log.queue_name }}</span>
                  </div>
                </div>

                <div v-if="log.message_summary" class="text-sm text-ops-muted line-clamp-2">
                  {{ log.message_summary }}
                </div>

                <div class="flex items-center gap-4 mt-2 text-xs text-ops-muted">
                  <span v-if="log.message_id">消息ID: {{ log.message_id }}</span>
                  <span>操作人: {{ log.operator }}</span>
                </div>
              </div>

              <div class="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity duration-150">
                <span class="text-xs text-ops-primary">查看详情 →</span>
              </div>
            </div>
          </div>
        </div>

        <div v-if="totalPages > 1" class="px-6 py-4 border-t border-ops-border flex items-center justify-between">
          <div class="text-sm text-ops-muted">
            第 {{ page }} / {{ totalPages }} 页，共 {{ total }} 条记录
          </div>
          <div class="flex items-center gap-2">
            <button
              class="p-2 rounded-lg border border-ops-border text-ops-text hover:bg-ops-card/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150"
              :disabled="page <= 1"
              @click="handlePageChange(page - 1)"
            >
              <ChevronLeft class="w-4 h-4" />
            </button>
            <button
              v-for="p in Math.min(5, totalPages)"
              :key="p"
              class="min-w-[36px] h-9 px-3 rounded-lg text-sm font-medium transition-all duration-150"
              :class="page === p
                ? 'bg-ops-primary text-white'
                : 'border border-ops-border text-ops-text hover:bg-ops-card/50'"
              @click="handlePageChange(p)"
            >
              {{ p }}
            </button>
            <button
              class="p-2 rounded-lg border border-ops-border text-ops-text hover:bg-ops-card/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150"
              :disabled="page >= totalPages"
              @click="handlePageChange(page + 1)"
            >
              <ChevronRight class="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="detailDialogVisible"
      title="审计详情"
      width="700px"
      :close-on-click-modal="false"
      class="audit-detail-dialog"
    >
      <div v-if="detailLoading" class="py-12 text-center">
        <RefreshCw class="w-8 h-8 text-ops-muted/30 mx-auto mb-3 animate-spin" />
        <div class="text-ops-muted text-sm">加载中...</div>
      </div>

      <div v-else-if="currentDetail" class="space-y-5">
        <div class="flex items-center gap-3">
          <span
            class="inline-flex items-center px-3 py-1.5 text-sm rounded-full font-medium border"
            :class="getOperationClass(currentDetail.operation_type)"
          >
            {{ getOperationLabel(currentDetail.operation_type) }}
          </span>
          <span
            class="inline-flex items-center px-2.5 py-1 text-xs rounded font-medium"
            :class="getStatusClass(currentDetail.status)"
          >
            {{ currentDetail.status === 'success' ? '成功' : '失败' }}
          </span>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div class="space-y-1">
            <div class="text-xs text-ops-muted">操作时间</div>
            <div class="text-sm text-ops-text font-mono">
              {{ formatDateTime(currentDetail.created_at) }}
            </div>
          </div>
          <div class="space-y-1">
            <div class="text-xs text-ops-muted">操作人</div>
            <div class="text-sm text-ops-text">{{ currentDetail.operator }}</div>
          </div>
          <div v-if="currentDetail.target_exchange" class="space-y-1">
            <div class="text-xs text-ops-muted">目标交换机</div>
            <div class="text-sm text-ops-text font-mono">{{ currentDetail.target_exchange }}</div>
          </div>
          <div v-if="currentDetail.routing_key" class="space-y-1">
            <div class="text-xs text-ops-muted">路由键</div>
            <div class="text-sm text-ops-text font-mono">{{ currentDetail.routing_key }}</div>
          </div>
          <div v-if="currentDetail.queue_name" class="space-y-1">
            <div class="text-xs text-ops-muted">队列名称</div>
            <div class="text-sm text-ops-text font-mono">{{ currentDetail.queue_name }}</div>
          </div>
          <div v-if="currentDetail.delivery_tag" class="space-y-1">
            <div class="text-xs text-ops-muted">Delivery Tag</div>
            <div class="text-sm text-ops-text font-mono">{{ currentDetail.delivery_tag }}</div>
          </div>
          <div v-if="currentDetail.message_id" class="space-y-1 col-span-2">
            <div class="text-xs text-ops-muted">消息ID</div>
            <div class="text-sm text-ops-text font-mono break-all">{{ currentDetail.message_id }}</div>
          </div>
        </div>

        <div v-if="currentDetail.error_message" class="space-y-2">
          <div class="text-xs font-medium text-red-400">错误信息</div>
          <div class="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-300">
            {{ currentDetail.error_message }}
          </div>
        </div>

        <div v-if="currentDetail.message_body" class="space-y-2">
          <div class="text-xs font-medium text-ops-text">消息体</div>
          <div class="p-4 rounded-lg bg-ops-bg border border-ops-border overflow-auto max-h-64">
            <pre class="text-xs text-ops-text font-mono whitespace-pre-wrap break-all">{{ currentDetail.message_body }}</pre>
          </div>
        </div>

        <div v-if="currentDetail.headers && Object.keys(currentDetail.headers).length > 0" class="space-y-2">
          <div class="text-xs font-medium text-ops-text">Headers</div>
          <div class="p-4 rounded-lg bg-ops-bg border border-ops-border overflow-auto max-h-48">
            <pre class="text-xs text-ops-text font-mono whitespace-pre-wrap">{{ formatJson(currentDetail.headers) }}</pre>
          </div>
        </div>

        <div v-if="currentDetail.properties && Object.keys(currentDetail.properties).length > 0" class="space-y-2">
          <div class="text-xs font-medium text-ops-text">Properties</div>
          <div class="p-4 rounded-lg bg-ops-bg border border-ops-border overflow-auto max-h-48">
            <pre class="text-xs text-ops-text font-mono whitespace-pre-wrap">{{ formatJson(currentDetail.properties) }}</pre>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex items-center justify-end">
          <button
            class="px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 transition-all duration-200"
            @click="detailDialogVisible = false"
          >
            关闭
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.audit-detail-dialog :deep(.el-dialog) {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 16px;
}

.audit-detail-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #334155;
  padding: 20px 24px;
}

.audit-detail-dialog :deep(.el-dialog__title) {
  color: #e2e8f0;
  font-size: 18px;
  font-weight: 600;
}

.audit-detail-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.audit-detail-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #334155;
  padding: 16px 24px;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
