<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, onActivated, onDeactivated, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  RefreshCw,
  ArrowLeft,
  Layers,
  List,
  Share2,
  Shield,
  Plus,
  Trash2,
  ArrowRight,
  Database,
  Users,
  PencilLine,
  Download,
  FileText,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getVHostDetail,
  deleteVHost,
  getUsers,
  setVHostPermission,
  deleteVHostPermission,
  type VHostDetail,
  type VHostPermission,
  type UserListItem,
  type SetVHostPermissionRequest,
} from '@/api'

defineOptions({
  name: 'VHostDetail',
})

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const vhostDetail = ref<VHostDetail | null>(null)
const lastUpdated = ref<Date | null>(null)
let refreshTimer: number | null = null
let isActive = false
let isFetching = false
let hasLoaded = false
let currentVHostName = ''

const activeTab = ref<'queues' | 'exchanges' | 'permissions'>('queues')
const users = ref<UserListItem[]>([])

const permissionDialogVisible = ref(false)
const permissionForm = ref<SetVHostPermissionRequest>({
  username: '',
  configure: '.*',
  write: '.*',
  read: '.*',
})

const vhostName = computed(() => {
  const name = route.params.name as string
  return decodeURIComponent(name)
})

function formatNumber(n: number): string {
  return n.toLocaleString('zh-CN')
}

async function fetchData(forceRefresh: boolean | Event = false) {
  const isForce = typeof forceRefresh === 'boolean' ? forceRefresh : false
  if (isFetching && !isForce) return
  if (!isActive) return

  const name = vhostName.value
  currentVHostName = name

  try {
    isFetching = true
    if (!hasLoaded || isForce) {
      loading.value = true
    }
    const data = await getVHostDetail(name)
    if (currentVHostName !== name) return
    vhostDetail.value = data
    lastUpdated.value = new Date()
    hasLoaded = true
  } catch (err: any) {
    if (currentVHostName !== name) return
    console.error('Failed to fetch vhost detail:', err)
    if (err.response?.status === 404) {
      ElMessage.error(`VHost "${name}" 不存在`)
      router.push('/vhosts')
    }
  } finally {
    if (currentVHostName === name) {
      loading.value = false
      isFetching = false
    }
  }
}

async function fetchUsers() {
  try {
    const data = await getUsers()
    users.value = data
  } catch (err) {
    console.error('Failed to fetch users:', err)
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
  router.push('/vhosts')
}

async function handleDelete() {
  if (!vhostDetail.value) return
  if (vhostDetail.value.name === '/') {
    ElMessage.warning('无法删除默认 VHost "/"')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除 VHost "${vhostDetail.value.name}" 吗？\n\n该VHost下所有队列/交换机/消息将永久删除，且无法恢复！`,
      '删除 VHost',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'error',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await deleteVHost(vhostDetail.value.name)
    ElMessage.success(`VHost "${vhostDetail.value.name}" 已删除`)
    router.push('/vhosts')
  } catch {
  }
}

function goToQueueDetail(queueName: string) {
  router.push(`/queues/${encodeURIComponent(queueName)}`)
}

function goToExchangeDetail(exchangeName: string) {
  router.push(`/exchanges/${encodeURIComponent(exchangeName)}`)
}

function openPermissionDialog() {
  permissionForm.value = {
    username: '',
    configure: '.*',
    write: '.*',
    read: '.*',
  }
  fetchUsers()
  permissionDialogVisible.value = true
}

async function confirmSetPermission() {
  if (!permissionForm.value.username.trim()) {
    ElMessage.warning('请选择用户')
    return
  }

  try {
    await setVHostPermission(vhostName.value, {
      username: permissionForm.value.username.trim(),
      configure: permissionForm.value.configure || '.*',
      write: permissionForm.value.write || '.*',
      read: permissionForm.value.read || '.*',
    })
    ElMessage.success('权限设置成功')
    permissionDialogVisible.value = false
    fetchData(true)
  } catch (err) {
    console.error('Failed to set permission:', err)
    ElMessage.error('权限设置失败')
  }
}

async function handleDeletePermission(perm: VHostPermission) {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${perm.user}" 在 VHost "${perm.vhost}" 的权限吗？`,
      '删除用户权限',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await deleteVHostPermission(vhostName.value, perm.user)
    ElMessage.success(`用户 "${perm.user}" 的权限已删除`)
    fetchData(true)
  } catch {
  }
}

function formatPermission(pattern: string): string {
  if (!pattern || pattern === '') return '无权限'
  if (pattern === '.*') return '.* (全部)'
  return pattern
}

function getPermissionClass(pattern: string): string {
  if (!pattern || pattern === '') return 'text-slate-500'
  if (pattern === '.*') return 'text-emerald-400'
  return 'text-blue-400'
}

function getTypeLabel(type: string): string {
  const exchangeTypes: Record<string, string> = {
    direct: 'Direct',
    topic: 'Topic',
    fanout: 'Fanout',
    headers: 'Headers',
  }
  return exchangeTypes[type] || type
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
  currentVHostName = vhostName.value
  fetchData()
  startRefreshTimer()
})

onActivated(() => {
  isActive = true
  if (currentVHostName !== vhostName.value || !hasLoaded) {
    currentVHostName = vhostName.value
    hasLoaded = false
    vhostDetail.value = null
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
            <Layers class="w-5 h-5 text-ops-primary" />
            <span v-if="vhostDetail">{{ vhostDetail.name }}</span>
            <span v-else>VHost 详情</span>
          </h2>
          <p class="text-sm text-ops-muted">
            VHost 详细信息，包含队列、交换机和用户权限
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
          v-if="vhostDetail && vhostDetail.name !== '/'"
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-500/15 border border-red-500/30 text-red-400 text-sm font-medium hover:bg-red-500/25 transition-all duration-200"
          @click="handleDelete"
        >
          <Trash2 class="w-4 h-4" />
          删除 VHost
        </button>
      </div>
    </div>

    <div v-if="!loading && vhostDetail">
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-5">
        <div class="card-gradient rounded-2xl border border-ops-border p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-xl bg-blue-500/15 flex items-center justify-center">
              <List class="w-5 h-5 text-blue-400" />
            </div>
            <div class="text-sm text-ops-muted">队列数量</div>
          </div>
          <div class="text-2xl font-bold text-ops-text stat-number">
            {{ formatNumber(vhostDetail.queues.length) }}
          </div>
        </div>

        <div class="card-gradient rounded-2xl border border-ops-border p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center">
              <Share2 class="w-5 h-5 text-emerald-400" />
            </div>
            <div class="text-sm text-ops-muted">交换机数量</div>
          </div>
          <div class="text-2xl font-bold text-ops-text stat-number">
            {{ formatNumber(vhostDetail.exchanges.length) }}
          </div>
        </div>

        <div class="card-gradient rounded-2xl border border-ops-border p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-xl bg-purple-500/15 flex items-center justify-center">
              <Users class="w-5 h-5 text-purple-400" />
            </div>
            <div class="text-sm text-ops-muted">授权用户</div>
          </div>
          <div class="text-2xl font-bold text-ops-text stat-number">
            {{ formatNumber(vhostDetail.permissions.length) }}
          </div>
        </div>

        <div class="card-gradient rounded-2xl border border-ops-border p-5">
          <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 rounded-xl bg-amber-500/15 flex items-center justify-center">
              <Database class="w-5 h-5 text-amber-400" />
            </div>
            <div class="text-sm text-ops-muted">消息总数</div>
          </div>
          <div class="text-2xl font-bold text-amber-400 stat-number">
            {{ formatNumber(vhostDetail.queues.reduce((sum, q) => sum + q.total, 0)) }}
          </div>
        </div>
      </div>

      <div class="card-gradient rounded-2xl border border-ops-border mt-5 overflow-hidden">
        <div class="flex border-b border-ops-border">
          <button
            class="flex-1 flex items-center justify-center gap-2 px-6 py-4 text-sm font-medium transition-all duration-200"
            :class="activeTab === 'queues'
              ? 'text-ops-primary border-b-2 border-ops-primary bg-ops-primary/5'
              : 'text-ops-muted hover:text-ops-text hover:bg-ops-card/30'"
            @click="activeTab = 'queues'"
          >
            <List class="w-4 h-4" />
            队列列表
            <span class="px-2 py-0.5 text-xs rounded-full bg-ops-bg text-ops-muted">
              {{ vhostDetail.queues.length }}
            </span>
          </button>
          <button
            class="flex-1 flex items-center justify-center gap-2 px-6 py-4 text-sm font-medium transition-all duration-200"
            :class="activeTab === 'exchanges'
              ? 'text-ops-primary border-b-2 border-ops-primary bg-ops-primary/5'
              : 'text-ops-muted hover:text-ops-text hover:bg-ops-card/30'"
            @click="activeTab = 'exchanges'"
          >
            <Share2 class="w-4 h-4" />
            交换机列表
            <span class="px-2 py-0.5 text-xs rounded-full bg-ops-bg text-ops-muted">
              {{ vhostDetail.exchanges.length }}
            </span>
          </button>
          <button
            class="flex-1 flex items-center justify-center gap-2 px-6 py-4 text-sm font-medium transition-all duration-200"
            :class="activeTab === 'permissions'
              ? 'text-ops-primary border-b-2 border-ops-primary bg-ops-primary/5'
              : 'text-ops-muted hover:text-ops-text hover:bg-ops-card/30'"
            @click="activeTab = 'permissions'"
          >
            <Shield class="w-4 h-4" />
            用户权限汇总
            <span class="px-2 py-0.5 text-xs rounded-full bg-ops-bg text-ops-muted">
              {{ vhostDetail.permissions.length }}
            </span>
          </button>
        </div>

        <div class="p-6">
          <div v-if="activeTab === 'queues'">
            <div v-if="vhostDetail.queues.length > 0" class="overflow-x-auto">
              <table class="w-full">
                <thead>
                  <tr class="border-b border-ops-border">
                    <th class="text-left px-4 py-3 text-sm font-medium text-ops-muted">队列名称</th>
                    <th class="text-center px-4 py-3 text-sm font-medium text-ops-muted">状态</th>
                    <th class="text-center px-4 py-3 text-sm font-medium text-ops-muted">Ready</th>
                    <th class="text-center px-4 py-3 text-sm font-medium text-ops-muted">Unacked</th>
                    <th class="text-center px-4 py-3 text-sm font-medium text-ops-muted">总数</th>
                    <th class="text-center px-4 py-3 text-sm font-medium text-ops-muted">消费者</th>
                    <th class="text-center px-4 py-3 text-sm font-medium text-ops-muted">Durable</th>
                    <th class="text-right px-4 py-3 text-sm font-medium text-ops-muted">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="queue in vhostDetail.queues"
                    :key="queue.name"
                    class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
                  >
                    <td class="px-4 py-3">
                      <a
                        href="javascript:void(0)"
                        class="flex items-center gap-2 text-ops-text hover:text-ops-primary transition-colors group"
                        @click="goToQueueDetail(queue.name)"
                      >
                        <Database class="w-4 h-4 text-ops-muted" />
                        <span class="font-medium">{{ queue.name }}</span>
                        <ArrowRight class="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </a>
                    </td>
                    <td class="px-4 py-3 text-center">
                      <span
                        class="inline-flex items-center px-2 py-0.5 text-xs rounded-full"
                        :class="getStatusClass(queue.status)"
                      >
                        {{ getStatusText(queue.status) }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-center text-ops-text stat-number">{{ formatNumber(queue.ready) }}</td>
                    <td class="px-4 py-3 text-center text-amber-400 stat-number">{{ formatNumber(queue.unacked) }}</td>
                    <td class="px-4 py-3 text-center text-ops-text stat-number font-semibold">{{ formatNumber(queue.total) }}</td>
                    <td class="px-4 py-3 text-center text-emerald-400 stat-number">{{ formatNumber(queue.consumers) }}</td>
                    <td class="px-4 py-3 text-center">
                      <span
                        v-if="queue.durable"
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
                    <td class="px-4 py-3 text-right">
                      <button
                        class="p-1.5 rounded-lg text-ops-muted hover:text-ops-primary hover:bg-ops-primary/10 transition-all duration-150"
                        title="查看详情"
                        @click="goToQueueDetail(queue.name)"
                      >
                        <ArrowRight class="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="py-12 text-center">
              <List class="w-12 h-12 text-ops-muted/30 mx-auto mb-3" />
              <div class="text-ops-muted text-sm">暂无队列数据</div>
            </div>
          </div>

          <div v-else-if="activeTab === 'exchanges'">
            <div v-if="vhostDetail.exchanges.length > 0" class="overflow-x-auto">
              <table class="w-full">
                <thead>
                  <tr class="border-b border-ops-border">
                    <th class="text-left px-4 py-3 text-sm font-medium text-ops-muted">交换机名称</th>
                    <th class="text-left px-4 py-3 text-sm font-medium text-ops-muted">类型</th>
                    <th class="text-center px-4 py-3 text-sm font-medium text-ops-muted">Durable</th>
                    <th class="text-center px-4 py-3 text-sm font-medium text-ops-muted">Auto-delete</th>
                    <th class="text-center px-4 py-3 text-sm font-medium text-ops-muted">Internal</th>
                    <th class="text-right px-4 py-3 text-sm font-medium text-ops-muted">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="exchange in vhostDetail.exchanges"
                    :key="exchange.name"
                    class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
                  >
                    <td class="px-4 py-3">
                      <a
                        href="javascript:void(0)"
                        class="flex items-center gap-2 text-ops-text hover:text-ops-primary transition-colors group"
                        @click="goToExchangeDetail(exchange.name)"
                      >
                        <Share2 class="w-4 h-4 text-ops-muted" />
                        <span class="font-medium">{{ exchange.name }}</span>
                        <ArrowRight class="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                      </a>
                    </td>
                    <td class="px-4 py-3">
                      <span
                        class="inline-flex items-center px-2.5 py-1 text-xs rounded-full font-medium"
                        :class="getTypeClass(exchange.type)"
                      >
                        {{ getTypeLabel(exchange.type) }}
                      </span>
                    </td>
                    <td class="px-4 py-3 text-center">
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
                    <td class="px-4 py-3 text-center">
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
                    <td class="px-4 py-3 text-center">
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
                    <td class="px-4 py-3 text-right">
                      <button
                        class="p-1.5 rounded-lg text-ops-muted hover:text-ops-primary hover:bg-ops-primary/10 transition-all duration-150"
                        title="查看详情"
                        @click="goToExchangeDetail(exchange.name)"
                      >
                        <ArrowRight class="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="py-12 text-center">
              <Share2 class="w-12 h-12 text-ops-muted/30 mx-auto mb-3" />
              <div class="text-ops-muted text-sm">暂无交换机数据</div>
            </div>
          </div>

          <div v-else-if="activeTab === 'permissions'">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="text-sm font-semibold text-ops-text">用户权限列表</h3>
                <p class="text-xs text-ops-muted mt-0.5">管理该 VHost 下所有用户的访问权限</p>
              </div>
              <button
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-ops-primary/15 border border-ops-primary/30 text-ops-primary text-xs font-medium hover:bg-ops-primary/25 transition-all duration-200"
                @click="openPermissionDialog"
              >
                <Plus class="w-3.5 h-3.5" />
                添加用户授权
              </button>
            </div>

            <div v-if="vhostDetail.permissions.length > 0" class="overflow-x-auto">
              <table class="w-full">
                <thead>
                  <tr class="border-b border-ops-border">
                    <th class="text-left px-4 py-3 text-sm font-medium text-ops-muted">
                      <div class="flex items-center gap-2">
                        <Users class="w-4 h-4" />
                        用户名
                      </div>
                    </th>
                    <th class="text-left px-4 py-3 text-sm font-medium text-ops-muted">
                      <div class="flex items-center gap-1">
                        <PencilLine class="w-3 h-3" />
                        Configure
                      </div>
                    </th>
                    <th class="text-left px-4 py-3 text-sm font-medium text-ops-muted">
                      <div class="flex items-center gap-1">
                        <Download class="w-3 h-3" />
                        Write
                      </div>
                    </th>
                    <th class="text-left px-4 py-3 text-sm font-medium text-ops-muted">
                      <div class="flex items-center gap-1">
                        <FileText class="w-3 h-3" />
                        Read
                      </div>
                    </th>
                    <th class="text-right px-4 py-3 text-sm font-medium text-ops-muted">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="perm in vhostDetail.permissions"
                    :key="perm.user"
                    class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
                  >
                    <td class="px-4 py-3">
                      <div class="flex items-center gap-2">
                        <div class="w-8 h-8 rounded-full bg-ops-primary/15 flex items-center justify-center">
                          <Users class="w-4 h-4 text-ops-primary" />
                        </div>
                        <span class="font-medium text-ops-text">{{ perm.user }}</span>
                      </div>
                    </td>
                    <td class="px-4 py-3 stat-number font-mono text-xs" :class="getPermissionClass(perm.configure)">
                      {{ formatPermission(perm.configure) }}
                    </td>
                    <td class="px-4 py-3 stat-number font-mono text-xs" :class="getPermissionClass(perm.write)">
                      {{ formatPermission(perm.write) }}
                    </td>
                    <td class="px-4 py-3 stat-number font-mono text-xs" :class="getPermissionClass(perm.read)">
                      {{ formatPermission(perm.read) }}
                    </td>
                    <td class="px-4 py-3 text-right">
                      <button
                        class="p-1.5 rounded-lg text-ops-muted hover:text-red-400 hover:bg-red-500/10 transition-all duration-150"
                        title="删除权限"
                        @click="handleDeletePermission(perm)"
                      >
                        <Trash2 class="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="py-12 text-center">
              <Shield class="w-12 h-12 text-ops-muted/30 mx-auto mb-3" />
              <div class="text-ops-muted text-sm">暂无用户权限数据</div>
              <p class="text-xs text-ops-muted mt-1">点击上方"添加用户授权"按钮为用户分配权限</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="loading && !vhostDetail">
      <div class="card-gradient rounded-2xl border border-ops-border p-12 text-center">
        <RefreshCw class="w-12 h-12 text-ops-muted/30 mx-auto mb-3 animate-spin" />
        <div class="text-ops-muted text-sm">加载中...</div>
      </div>
    </div>

    <el-dialog
      v-model="permissionDialogVisible"
      title="添加用户授权"
      width="550px"
      :close-on-click-modal="false"
      class="permission-dialog"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">VHost</label>
          <div class="px-4 py-2.5 rounded-lg bg-ops-bg/50 border border-ops-border">
            <div class="flex items-center gap-2">
              <Layers class="w-4 h-4 text-ops-muted" />
              <span class="text-sm font-medium text-ops-text">{{ vhostName }}</span>
            </div>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">选择用户 <span class="text-red-400">*</span></label>
          <el-select
            v-model="permissionForm.username"
            placeholder="请选择要授权的用户"
            class="w-full"
            filterable
          >
            <el-option
              v-for="user in users"
              :key="user.name"
              :label="user.name"
              :value="user.name"
            />
          </el-select>
          <p class="text-xs text-ops-muted mt-1">选择要授权到此 VHost 的用户</p>
        </div>

        <div>
          <label class="block text-sm font-medium text-ops-text mb-3">权限配置</label>
          <div class="grid grid-cols-3 gap-4">
            <div>
              <label class="block text-xs font-medium text-ops-muted mb-2 flex items-center gap-1">
                <PencilLine class="w-3 h-3" />
                Configure
              </label>
              <input
                v-model="permissionForm.configure"
                type="text"
                placeholder=".*"
                class="w-full px-3 py-2 rounded-lg bg-ops-bg border border-ops-border text-sm text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150 font-mono"
              />
              <p class="text-xs text-ops-muted mt-1">队列/交换机创建/删除</p>
            </div>
            <div>
              <label class="block text-xs font-medium text-ops-muted mb-2 flex items-center gap-1">
                <Download class="w-3 h-3" />
                Write
              </label>
              <input
                v-model="permissionForm.write"
                type="text"
                placeholder=".*"
                class="w-full px-3 py-2 rounded-lg bg-ops-bg border border-ops-border text-sm text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150 font-mono"
              />
              <p class="text-xs text-ops-muted mt-1">发布消息</p>
            </div>
            <div>
              <label class="block text-xs font-medium text-ops-muted mb-2 flex items-center gap-1">
                <FileText class="w-3 h-3" />
                Read
              </label>
              <input
                v-model="permissionForm.read"
                type="text"
                placeholder=".*"
                class="w-full px-3 py-2 rounded-lg bg-ops-bg border border-ops-border text-sm text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150 font-mono"
              />
              <p class="text-xs text-ops-muted mt-1">消费消息</p>
            </div>
          </div>
          <p class="text-xs text-ops-muted mt-2">
            使用正则表达式匹配资源，<code class="text-ops-primary">.*</code> 表示全部权限，
            <code class="text-ops-primary">^queue\..*</code> 表示匹配以 queue. 开头的资源
          </p>
        </div>
      </div>

      <template #footer>
        <div class="flex items-center justify-end gap-3">
          <button
            class="px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 transition-all duration-200"
            @click="permissionDialogVisible = false"
          >
            取消
          </button>
          <button
            class="px-4 py-2 rounded-lg bg-ops-primary text-white text-sm font-medium hover:bg-ops-primary/90 transition-all duration-200"
            @click="confirmSetPermission"
          >
            确认授权
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.permission-dialog :deep(.el-dialog) {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 16px;
}

.permission-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #334155;
  padding: 20px 24px;
}

.permission-dialog :deep(.el-dialog__title) {
  color: #E2E8F0;
  font-size: 18px;
  font-weight: 600;
}

.permission-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.permission-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #334155;
  padding: 16px 24px;
}

.permission-dialog :deep(.el-select) {
  --el-select-border-color: #334155;
  --el-select-input-background-color: #0F172A;
  --el-select-text-color: #E2E8F0;
  --el-select-placeholder-text-color: #64748B;
}

.permission-dialog :deep(.el-select .el-input__wrapper) {
  background: #0F172A;
  border: 1px solid #334155;
  border-radius: 8px;
  box-shadow: none;
}

.permission-dialog :deep(.el-select .el-input__wrapper:hover) {
  border-color: #6366F1;
}

.permission-dialog :deep(.el-select .el-input__wrapper.is-focus) {
  border-color: #6366F1;
  box-shadow: none;
}

.permission-dialog :deep(.el-select-dropdown) {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 12px;
}

.permission-dialog :deep(.el-select-dropdown__item) {
  color: #E2E8F0;
}

.permission-dialog :deep(.el-select-dropdown__item.hover),
.permission-dialog :deep(.el-select-dropdown__item:hover) {
  background: rgba(99, 102, 241, 0.1);
}

.permission-dialog :deep(.el-select-dropdown__item.selected) {
  background: rgba(99, 102, 241, 0.15);
  color: #6366F1;
  font-weight: 600;
}

.permission-dialog :deep(.el-message-box) {
  background: #1E293B;
  border: 1px solid #334155;
}

.permission-dialog :deep(.el-message-box__title) {
  color: #E2E8F0;
}

.permission-dialog :deep(.el-message-box__message) {
  color: #94A3B8;
}

.permission-dialog :deep(.el-message-box__content) {
  color: #94A3B8;
}

code {
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.1);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}
</style>
