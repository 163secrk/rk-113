<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import {
  RefreshCw,
  Users,
  Eye,
  Shield,
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
  KeyRound,
  FileText,
  Lock,
  PencilLine,
  Download,
} from 'lucide-vue-next'
import { ElMessage } from 'element-plus'
import {
  getUsers,
  getUserDetail,
  type UserListItem,
  type UserDetail,
} from '@/api'

defineOptions({
  name: 'UserList',
})

const loading = ref(false)
const users = ref<UserListItem[]>([])
const lastUpdated = ref<Date | null>(null)
let refreshTimer: number | null = null
let isActive = false
let isFetching = false
let hasLoaded = false

const detailDrawerVisible = ref(false)
const detailLoading = ref(false)
const userDetail = ref<UserDetail | null>(null)

const tagConfig: Record<string, { class: string; label: string; icon: typeof Shield }> = {
  administrator: { class: 'bg-red-500/15 text-red-400', label: 'Administrator', icon: ShieldAlert },
  monitoring: { class: 'bg-blue-500/15 text-blue-400', label: 'Monitoring', icon: ShieldCheck },
  policymaker: { class: 'bg-purple-500/15 text-purple-400', label: 'Policymaker', icon: ShieldQuestion },
  management: { class: 'bg-amber-500/15 text-amber-400', label: 'Management', icon: Shield },
}

function getTagClass(tag: string): string {
  return tagConfig[tag]?.class || 'bg-slate-500/15 text-slate-400'
}

function getTagLabel(tag: string): string {
  return tagConfig[tag]?.label || tag
}

async function fetchData(forceRefresh: boolean | Event = false) {
  const isForce = typeof forceRefresh === 'boolean' ? forceRefresh : false
  if (isFetching && !isForce) return
  if (!isActive) return

  try {
    isFetching = true
    if (!hasLoaded || isForce) {
      loading.value = true
    }
    const data = await getUsers()
    users.value = data
    lastUpdated.value = new Date()
    hasLoaded = true
  } catch (err) {
    console.error('Failed to fetch users:', err)
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
  }, 15000)
}

function stopRefreshTimer() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

async function viewDetail(user: UserListItem) {
  detailDrawerVisible.value = true
  detailLoading.value = true
  userDetail.value = null
  try {
    const detail = await getUserDetail(user.name)
    userDetail.value = detail
  } catch (err) {
    console.error('Failed to fetch user detail:', err)
    ElMessage.error('获取用户详情失败')
  } finally {
    detailLoading.value = false
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
        <h2 class="text-xl font-bold text-ops-text mb-1">用户管理</h2>
        <p class="text-sm text-ops-muted">
          查看 RabbitMQ 所有用户及其权限，支持查看各 VHost 的 configure/write/read 权限与 Topic 权限
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
      </div>
    </div>

    <div class="grid grid-cols-4 gap-4">
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <Users class="w-3.5 h-3.5" />
          用户总数
        </div>
        <div class="text-2xl font-bold text-ops-text stat-number">{{ users.length }}</div>
      </div>
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <ShieldAlert class="w-3.5 h-3.5" />
          管理员
        </div>
        <div class="text-2xl font-bold text-red-400 stat-number">
          {{ users.filter((u) => u.tags.includes('administrator')).length }}
        </div>
      </div>
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <ShieldCheck class="w-3.5 h-3.5" />
          监控者
        </div>
        <div class="text-2xl font-bold text-blue-400 stat-number">
          {{ users.filter((u) => u.tags.includes('monitoring')).length }}
        </div>
      </div>
      <div class="card-gradient rounded-xl border border-ops-border p-4">
        <div class="flex items-center gap-2 text-ops-muted text-xs mb-1">
          <Shield class="w-3.5 h-3.5" />
          管理者
        </div>
        <div class="text-2xl font-bold text-amber-400 stat-number">
          {{ users.filter((u) => u.tags.includes('management')).length }}
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
                  <Users class="w-4 h-4" />
                  用户名
                </div>
              </th>
              <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">
                <div class="flex items-center gap-2">
                  <Shield class="w-4 h-4" />
                  角色标签
                </div>
              </th>
              <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="user in users"
              :key="user.name"
              class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
            >
              <td class="px-6 py-4">
                <div class="flex items-center gap-2">
                  <div class="w-8 h-8 rounded-full bg-ops-primary/15 flex items-center justify-center">
                    <KeyRound class="w-4 h-4 text-ops-primary" />
                  </div>
                  <span class="font-medium text-ops-text">{{ user.name }}</span>
                </div>
              </td>
              <td class="px-6 py-4">
                <div class="flex items-center gap-1.5 flex-wrap">
                  <span
                    v-if="user.tags.length === 0"
                    class="inline-flex items-center px-2 py-0.5 text-xs rounded bg-slate-500/15 text-slate-400"
                  >
                    无标签
                  </span>
                  <span
                    v-for="tag in user.tags"
                    :key="tag"
                    class="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded font-medium"
                    :class="getTagClass(tag)"
                  >
                    <component :is="tagConfig[tag]?.icon || Shield" class="w-3 h-3" />
                    {{ getTagLabel(tag) }}
                  </span>
                </div>
              </td>
              <td class="px-6 py-4 text-right">
                <button
                  class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-ops-primary hover:text-white hover:bg-ops-primary/80 border border-ops-primary/30 transition-all duration-150 text-xs font-medium"
                  @click.stop="viewDetail(user)"
                >
                  <Eye class="w-3.5 h-3.5" />
                  查看详情
                </button>
              </td>
            </tr>
            <tr v-if="users.length === 0 && !loading">
              <td colspan="3" class="px-6 py-12 text-center">
                <div class="flex flex-col items-center gap-3">
                  <Users class="w-12 h-12 text-ops-muted/30" />
                  <div class="text-ops-muted text-sm">暂无用户数据</div>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="loading && users.length === 0">
      <div class="card-gradient rounded-2xl border border-ops-border p-12 text-center">
        <RefreshCw class="w-12 h-12 text-ops-muted/30 mx-auto mb-3 animate-spin" />
        <div class="text-ops-muted text-sm">加载中...</div>
      </div>
    </div>

    <el-drawer
      v-model="detailDrawerVisible"
      title="用户权限详情"
      direction="rtl"
      size="55%"
      class="user-detail-drawer"
    >
      <div v-loading="detailLoading" class="space-y-6">
        <div v-if="userDetail" class="space-y-6">
          <div class="card-gradient rounded-xl border border-ops-border p-5">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-12 h-12 rounded-full bg-ops-primary/15 flex items-center justify-center">
                <KeyRound class="w-6 h-6 text-ops-primary" />
              </div>
              <div>
                <div class="text-lg font-bold text-ops-text">{{ userDetail.name }}</div>
                <div class="text-xs text-ops-muted mt-0.5">RabbitMQ 用户</div>
              </div>
            </div>
            <div class="flex items-center gap-1.5 flex-wrap">
              <span
                v-if="userDetail.tags.length === 0"
                class="inline-flex items-center px-2 py-0.5 text-xs rounded bg-slate-500/15 text-slate-400"
              >
                无标签
              </span>
              <span
                v-for="tag in userDetail.tags"
                :key="tag"
                class="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-full font-medium"
                :class="getTagClass(tag)"
              >
                <component :is="tagConfig[tag]?.icon || Shield" class="w-3 h-3" />
                {{ getTagLabel(tag) }}
              </span>
            </div>
          </div>

          <div>
            <div class="flex items-center gap-2 mb-3">
              <Lock class="w-4 h-4 text-ops-primary" />
              <h3 class="text-sm font-semibold text-ops-text">VHost 权限</h3>
              <span class="text-xs text-ops-muted">（configure / write / read）</span>
            </div>
            <div class="card-gradient rounded-xl border border-ops-border overflow-hidden">
              <div class="overflow-x-auto">
                <table class="w-full">
                  <thead>
                    <tr class="border-b border-ops-border">
                      <th class="text-left px-4 py-3 text-xs font-medium text-ops-muted">VHost</th>
                      <th class="text-left px-4 py-3 text-xs font-medium text-ops-muted">
                        <div class="flex items-center gap-1">
                          <PencilLine class="w-3 h-3" />
                          Configure
                        </div>
                      </th>
                      <th class="text-left px-4 py-3 text-xs font-medium text-ops-muted">
                        <div class="flex items-center gap-1">
                          <Download class="w-3 h-3" />
                          Write
                        </div>
                      </th>
                      <th class="text-left px-4 py-3 text-xs font-medium text-ops-muted">
                        <div class="flex items-center gap-1">
                          <FileText class="w-3 h-3" />
                          Read
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(perm, idx) in userDetail.permissions"
                      :key="idx"
                      class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
                    >
                      <td class="px-4 py-3 text-ops-text font-medium stat-number">{{ perm.vhost }}</td>
                      <td class="px-4 py-3 stat-number font-mono text-xs" :class="getPermissionClass(perm.configure)">
                        {{ formatPermission(perm.configure) }}
                      </td>
                      <td class="px-4 py-3 stat-number font-mono text-xs" :class="getPermissionClass(perm.write)">
                        {{ formatPermission(perm.write) }}
                      </td>
                      <td class="px-4 py-3 stat-number font-mono text-xs" :class="getPermissionClass(perm.read)">
                        {{ formatPermission(perm.read) }}
                      </td>
                    </tr>
                    <tr v-if="userDetail.permissions.length === 0">
                      <td colspan="4" class="px-4 py-8 text-center text-ops-muted text-sm">
                        该用户暂无 VHost 权限
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div>
            <div class="flex items-center gap-2 mb-3">
              <FileText class="w-4 h-4 text-ops-accent" />
              <h3 class="text-sm font-semibold text-ops-text">Topic 权限</h3>
              <span class="text-xs text-ops-muted">（基于交换机的读写权限）</span>
            </div>
            <div class="card-gradient rounded-xl border border-ops-border overflow-hidden">
              <div class="overflow-x-auto">
                <table class="w-full">
                  <thead>
                    <tr class="border-b border-ops-border">
                      <th class="text-left px-4 py-3 text-xs font-medium text-ops-muted">VHost</th>
                      <th class="text-left px-4 py-3 text-xs font-medium text-ops-muted">Exchange</th>
                      <th class="text-left px-4 py-3 text-xs font-medium text-ops-muted">
                        <div class="flex items-center gap-1">
                          <Download class="w-3 h-3" />
                          Write
                        </div>
                      </th>
                      <th class="text-left px-4 py-3 text-xs font-medium text-ops-muted">
                        <div class="flex items-center gap-1">
                          <FileText class="w-3 h-3" />
                          Read
                        </div>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr
                      v-for="(tp, idx) in userDetail.topic_permissions"
                      :key="idx"
                      class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
                    >
                      <td class="px-4 py-3 text-ops-text font-medium stat-number">{{ tp.vhost }}</td>
                      <td class="px-4 py-3 text-ops-text stat-number">{{ tp.exchange }}</td>
                      <td class="px-4 py-3 stat-number font-mono text-xs" :class="getPermissionClass(tp.write)">
                        {{ formatPermission(tp.write) }}
                      </td>
                      <td class="px-4 py-3 stat-number font-mono text-xs" :class="getPermissionClass(tp.read)">
                        {{ formatPermission(tp.read) }}
                      </td>
                    </tr>
                    <tr v-if="userDetail.topic_permissions.length === 0">
                      <td colspan="4" class="px-4 py-8 text-center text-ops-muted text-sm">
                        该用户暂无 Topic 权限
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>

        <div v-else-if="!detailLoading" class="text-center py-12 text-ops-muted text-sm">
          无法加载用户详情
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
.user-detail-drawer :deep(.el-drawer) {
  background: #0F172A;
  border-left: 1px solid #334155;
}

.user-detail-drawer :deep(.el-drawer__header) {
  color: #E2E8F0;
  font-size: 18px;
  font-weight: 600;
  border-bottom: 1px solid #334155;
  margin-bottom: 0;
  padding: 20px 24px;
}

.user-detail-drawer :deep(.el-drawer__body) {
  padding: 24px;
}

.user-detail-drawer :deep(.el-drawer__close-btn) {
  color: #94A3B8;
}
</style>
