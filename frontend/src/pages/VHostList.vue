<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import { useRouter } from 'vue-router'
import {
  RefreshCw,
  Plus,
  Trash2,
  Layers,
  ArrowRight,
  List,
  Share2,
  Link2,
  MessageSquare,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getVHosts,
  createVHost,
  deleteVHost,
  type VHostListItem,
  type CreateVHostRequest,
} from '@/api'

defineOptions({
  name: 'VHostList',
})

const router = useRouter()
const loading = ref(false)
const vhosts = ref<VHostListItem[]>([])
const lastUpdated = ref<Date | null>(null)
let refreshTimer: number | null = null
let isActive = false
let isFetching = false
let hasLoaded = false

const createDialogVisible = ref(false)
const createForm = ref<CreateVHostRequest>({
  name: '',
})

async function fetchData(forceRefresh: boolean | Event = false) {
  const isForce = typeof forceRefresh === 'boolean' ? forceRefresh : false
  if (isFetching && !isForce) return
  if (!isActive) return

  try {
    isFetching = true
    if (!hasLoaded || isForce) {
      loading.value = true
    }
    const data = await getVHosts()
    vhosts.value = data
    lastUpdated.value = new Date()
    hasLoaded = true
  } catch (err) {
    console.error('Failed to fetch vhosts:', err)
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

function goToDetail(vhostName: string) {
  router.push(`/vhosts/${encodeURIComponent(vhostName)}`)
}

function handleCreate() {
  createForm.value = {
    name: '',
  }
  createDialogVisible.value = true
}

async function confirmCreate() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('请输入 VHost 名称')
    return
  }

  const data: CreateVHostRequest = {
    name: createForm.value.name.trim(),
  }

  try {
    await createVHost(data)
    ElMessage.success(`VHost "${data.name}" 创建成功`)
    createDialogVisible.value = false
    fetchData()
  } catch (err) {
    console.error('Failed to create vhost:', err)
    ElMessage.error('创建 VHost 失败')
  }
}

async function handleDelete(vhost: VHostListItem) {
  if (vhost.name === '/') {
    ElMessage.warning('无法删除默认 VHost "/"')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除 VHost "${vhost.name}" 吗？\n\n该VHost下所有队列/交换机/消息将永久删除，且无法恢复！`,
      '删除 VHost',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await deleteVHost(vhost.name)
    ElMessage.success(`VHost "${vhost.name}" 已删除`)
    fetchData()
  } catch {
  }
}

function formatNumber(n: number): string {
  return n.toLocaleString('zh-CN')
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
        <h2 class="text-xl font-bold text-ops-text mb-1">虚拟主机管理</h2>
        <p class="text-sm text-ops-muted">
          管理 RabbitMQ 中的所有虚拟主机，支持查看、创建和删除操作
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
          创建 VHost
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <Layers class="w-3.5 h-3.5" />
          VHost 总数
        </div>
        <div class="text-2xl font-bold text-ops-text stat-number">{{ vhosts.length }}</div>
      </div>
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <List class="w-3.5 h-3.5" />
          队列总数
        </div>
        <div class="text-2xl font-bold text-blue-400 stat-number">
          {{ formatNumber(vhosts.reduce((sum, v) => sum + v.queues, 0)) }}
        </div>
      </div>
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <Share2 class="w-3.5 h-3.5" />
          交换机总数
        </div>
        <div class="text-2xl font-bold text-emerald-400 stat-number">
          {{ formatNumber(vhosts.reduce((sum, v) => sum + v.exchanges, 0)) }}
        </div>
      </div>
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <MessageSquare class="w-3.5 h-3.5" />
          消息总数
        </div>
        <div class="text-2xl font-bold text-amber-400 stat-number">
          {{ formatNumber(vhosts.reduce((sum, v) => sum + v.messages, 0)) }}
        </div>
      </div>
    </div>

    <div class="card-gradient rounded-2xl border border-ops-border overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full">
          <thead>
            <tr class="border-b border-ops-border">
              <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center gap-2">
                  <Layers class="w-4 h-4" />
                  VHost 名称
                </div>
              </th>
              <th class="text-center px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center justify-center gap-2">
                  <List class="w-4 h-4" />
                  队列数
                </div>
              </th>
              <th class="text-center px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center justify-center gap-2">
                  <Share2 class="w-4 h-4" />
                  交换机数
                </div>
              </th>
              <th class="text-center px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center justify-center gap-2">
                  <Link2 class="w-4 h-4" />
                  连接数
                </div>
              </th>
              <th class="text-center px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center justify-center gap-2">
                  <MessageSquare class="w-4 h-4" />
                  消息总数
                </div>
              </th>
              <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="vhost in vhosts"
              :key="vhost.name"
              class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
            >
              <td class="px-6 py-4">
                <a
                  href="javascript:void(0)"
                  class="flex items-center gap-2 text-ops-text hover:text-ops-primary transition-colors duration-150 group"
                  @click="goToDetail(vhost.name)"
                >
                  <span class="font-medium">{{ vhost.name }}</span>
                  <ArrowRight class="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity duration-150" />
                </a>
              </td>
              <td class="px-6 py-4 text-center text-ops-text stat-number">
                {{ formatNumber(vhost.queues) }}
              </td>
              <td class="px-6 py-4 text-center text-ops-text stat-number">
                {{ formatNumber(vhost.exchanges) }}
              </td>
              <td class="px-6 py-4 text-center text-ops-text stat-number">
                {{ formatNumber(vhost.connections) }}
              </td>
              <td class="px-6 py-4 text-center text-ops-text stat-number">
                {{ formatNumber(vhost.messages) }}
              </td>
              <td class="px-6 py-4 text-right">
                <button
                  class="p-2 rounded-lg text-ops-muted hover:text-red-400 hover:bg-red-500/10 transition-all duration-150"
                  :disabled="vhost.name === '/'"
                  :class="{ 'opacity-30 cursor-not-allowed': vhost.name === '/' }"
                  title="删除 VHost"
                  @click.stop="handleDelete(vhost)"
                >
                  <Trash2 class="w-4 h-4" />
                </button>
              </td>
            </tr>
            <tr v-if="vhosts.length === 0 && !loading">
              <td colspan="6" class="px-6 py-12 text-center">
                <div class="flex flex-col items-center gap-3">
                  <Layers class="w-12 h-12 text-ops-muted/30" />
                  <div class="text-ops-muted text-sm">暂无 VHost 数据</div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="loading && vhosts.length === 0">
      <div class="card-gradient rounded-2xl border border-ops-border p-12 text-center">
        <RefreshCw class="w-12 h-12 text-ops-muted/30 mx-auto mb-3 animate-spin" />
        <div class="text-ops-muted text-sm">加载中...</div>
      </div>
    </div>

    <el-dialog
      v-model="createDialogVisible"
      title="创建 VHost"
      width="500px"
      :close-on-click-modal="false"
      class="vhost-create-dialog"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">VHost 名称 <span class="text-red-400">*</span></label>
          <input
            v-model="createForm.name"
            type="text"
            placeholder="请输入 VHost 名称，例如：production"
            class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150"
          />
          <p class="text-xs text-ops-muted mt-1">VHost 用于隔离不同的业务环境，不能与现有 VHost 重名</p>
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
.vhost-create-dialog :deep(.el-dialog) {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 16px;
}

.vhost-create-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #334155;
  padding: 20px 24px;
}

.vhost-create-dialog :deep(.el-dialog__title) {
  color: #E2E8F0;
  font-size: 18px;
  font-weight: 600;
}

.vhost-create-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.vhost-create-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #334155;
  padding: 16px 24px;
}

.vhost-create-dialog :deep(.el-message-box) {
  background: #1E293B;
  border: 1px solid #334155;
}

.vhost-create-dialog :deep(.el-message-box__title) {
  color: #E2E8F0;
}

.vhost-create-dialog :deep(.el-message-box__message) {
  color: #94A3B8;
}

.vhost-create-dialog :deep(.el-message-box__content) {
  color: #94A3B8;
}
</style>
