<script setup lang="ts">
import { ref, onMounted, onActivated, onDeactivated, onBeforeUnmount, computed, watch } from 'vue'
import {
  RefreshCw,
  Plus,
  Bell,
  AlertTriangle,
  AlertCircle,
  CheckCircle,
  XCircle,
  Trash2,
  Edit3,
  Play,
  Pause,
  Database,
  List,
  Filter,
  Clock,
  X,
  Search,
} from 'lucide-vue-next'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAlertStore } from '@/stores/alert'
import {
  getQueues,
  createAlertRule,
  updateAlertRule,
  deleteAlertRule,
  type QueueListItem,
  type AlertRule,
  type AlertRuleCreate,
  type AlertRuleUpdate,
  type AlertConditionType,
  type AlertLevel,
  type AlertStatus,
  type AlertRecord,
} from '@/api'

defineOptions({
  name: 'AlertCenter',
})

const alertStore = useAlertStore()
const activeTab = ref<'rules' | 'records'>('rules')
const queues = ref<QueueListItem[]>([])
let isActive = false
let refreshTimer: number | null = null

const filterStatus = ref<AlertStatus | ''>('')
const filterLevel = ref<AlertLevel | ''>('')
const searchKeyword = ref('')

const ruleDialogVisible = ref(false)
const isEditingRule = ref(false)
const editingRuleId = ref<number | null>(null)

const ruleForm = ref<AlertRuleCreate>({
  name: '',
  queue_name: '',
  condition_type: 'ready_gt',
  threshold: 100,
  level: 'warning',
  enabled: true,
  description: '',
})

const conditionOptions: { value: AlertConditionType; label: string; hasThreshold: boolean }[] = [
  { value: 'ready_gt', label: 'Ready消息数 > N', hasThreshold: true },
  { value: 'unacked_gt', label: 'Unacked消息数 > N', hasThreshold: true },
  { value: 'consumers_eq_0', label: '消费者数量 = 0', hasThreshold: false },
  { value: 'rate_gt', label: '消息速率 > N条/秒', hasThreshold: true },
]

const levelOptions: { value: AlertLevel; label: string }[] = [
  { value: 'warning', label: '警告' },
  { value: 'critical', label: '严重' },
]

const statusOptions: { value: AlertStatus | ''; label: string }[] = [
  { value: '', label: '全部' },
  { value: 'active', label: '活动中' },
  { value: 'acknowledged', label: '已确认' },
  { value: 'resolved', label: '已恢复' },
  { value: 'closed', label: '已关闭' },
]

const currentConditionHasThreshold = computed(() => {
  const opt = conditionOptions.find((o) => o.value === ruleForm.value.condition_type)
  return opt?.hasThreshold ?? true
})

const filteredRecords = computed(() => {
  let result = alertStore.records
  if (filterStatus.value) {
    result = result.filter((r) => r.status === filterStatus.value)
  }
  if (filterLevel.value) {
    result = result.filter((r) => r.level === filterLevel.value)
  }
  if (searchKeyword.value.trim()) {
    const kw = searchKeyword.value.trim().toLowerCase()
    result = result.filter(
      (r) =>
        r.rule_name.toLowerCase().includes(kw) ||
        r.queue_name.toLowerCase().includes(kw) ||
        (r.message?.toLowerCase().includes(kw) ?? false)
    )
  }
  return result
})

async function fetchQueues() {
  try {
    queues.value = await getQueues()
  } catch (err) {
    console.error('Failed to fetch queues:', err)
  }
}

async function refreshAll() {
  await Promise.all([fetchQueues(), alertStore.fetchRules(), alertStore.fetchRecords({ limit: 300 })])
}

async function handleEvaluate() {
  await alertStore.evaluate()
  ElMessage.success('告警评估完成')
}

function startRefreshTimer() {
  if (refreshTimer) return
  refreshTimer = window.setInterval(() => {
    if (isActive) {
      alertStore.fetchRecords({ limit: 300 })
    }
  }, 5000)
}

function stopRefreshTimer() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

function openCreateRule() {
  isEditingRule.value = false
  editingRuleId.value = null
  ruleForm.value = {
    name: '',
    queue_name: '',
    condition_type: 'ready_gt',
    threshold: 100,
    level: 'warning',
    enabled: true,
    description: '',
  }
  ruleDialogVisible.value = true
}

function openEditRule(rule: AlertRule) {
  isEditingRule.value = true
  editingRuleId.value = rule.id
  ruleForm.value = {
    name: rule.name,
    queue_name: rule.queue_name,
    condition_type: rule.condition_type,
    threshold: rule.threshold,
    level: rule.level,
    enabled: rule.enabled,
    description: rule.description || '',
  }
  ruleDialogVisible.value = true
}

async function confirmRule() {
  if (!ruleForm.value.name.trim()) {
    ElMessage.warning('请输入规则名称')
    return
  }
  if (!ruleForm.value.queue_name) {
    ElMessage.warning('请选择监控队列')
    return
  }
  if (currentConditionHasThreshold.value && ruleForm.value.threshold < 0) {
    ElMessage.warning('阈值必须大于等于 0')
    return
  }

  try {
    if (isEditingRule.value && editingRuleId.value !== null) {
      const updateData: AlertRuleUpdate = { ...ruleForm.value }
      if (!currentConditionHasThreshold.value) {
        updateData.threshold = 0
      }
      await updateAlertRule(editingRuleId.value, updateData)
      ElMessage.success('规则更新成功')
    } else {
      const createData: AlertRuleCreate = { ...ruleForm.value }
      if (!currentConditionHasThreshold.value) {
        createData.threshold = 0
      }
      await createAlertRule(createData)
      ElMessage.success('规则创建成功')
    }
    ruleDialogVisible.value = false
    await alertStore.fetchRules()
  } catch (err) {
    console.error('Failed to save rule:', err)
    ElMessage.error('保存规则失败')
  }
}

async function handleToggleRule(rule: AlertRule) {
  try {
    await updateAlertRule(rule.id, { enabled: !rule.enabled })
    ElMessage.success(`规则已${rule.enabled ? '停用' : '启用'}`)
    await alertStore.fetchRules()
  } catch (err) {
    console.error('Failed to toggle rule:', err)
    ElMessage.error('操作失败')
  }
}

async function handleDeleteRule(rule: AlertRule) {
  try {
    await ElMessageBox.confirm(
      `确定要删除告警规则 "${rule.name}" 吗？`,
      '删除规则',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger',
      }
    )
    await deleteAlertRule(rule.id)
    ElMessage.success('规则已删除')
    await alertStore.fetchRules()
  } catch {
    // user cancelled
  }
}

async function handleAcknowledge(record: AlertRecord) {
  try {
    await alertStore.acknowledge(record.id)
    ElMessage.success('告警已确认')
  } catch {
    ElMessage.error('操作失败')
  }
}

async function handleClose(record: AlertRecord) {
  try {
    await ElMessageBox.confirm(
      `确定要关闭此告警吗？关闭后将不再显示在活动列表中。`,
      '关闭告警',
      {
        confirmButtonText: '确认关闭',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    await alertStore.close(record.id)
    ElMessage.success('告警已关闭')
  } catch {
    // user cancelled
  }
}

function getLevelClass(level: string) {
  switch (level) {
    case 'critical':
      return 'bg-red-500/15 text-red-400 border-red-500/30'
    case 'warning':
      return 'bg-amber-500/15 text-amber-400 border-amber-500/30'
    default:
      return 'bg-slate-500/15 text-slate-400 border-slate-500/30'
  }
}

function getStatusClass(status: string) {
  switch (status) {
    case 'active':
      return 'bg-red-500/15 text-red-400'
    case 'acknowledged':
      return 'bg-blue-500/15 text-blue-400'
    case 'resolved':
      return 'bg-emerald-500/15 text-emerald-400'
    case 'closed':
      return 'bg-slate-500/15 text-slate-400'
    default:
      return 'bg-slate-500/15 text-slate-400'
  }
}

function formatDateTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return '--'
  }
}

watch(currentConditionHasThreshold, (hasThreshold) => {
  if (!hasThreshold) {
    ruleForm.value.threshold = 0
  }
})

onMounted(() => {
  isActive = true
  refreshAll()
  startRefreshTimer()
})

onActivated(() => {
  isActive = true
  refreshAll()
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
        <h2 class="text-xl font-bold text-ops-text mb-1">告警中心</h2>
        <p class="text-sm text-ops-muted">
          管理告警规则与查看告警记录，每 5 秒自动刷新告警状态
          <span v-if="alertStore.lastEvaluatedAt" class="stat-number ml-2">
            · 最后评估: {{ alertStore.lastEvaluatedAt.toLocaleTimeString('zh-CN', { hour12: false }) }}
          </span>
        </p>
      </div>
      <div class="flex items-center gap-3">
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 hover:border-ops-primary/50 transition-all duration-200"
          :disabled="alertStore.evaluating || alertStore.loadingRecords || alertStore.loadingRules"
          @click="refreshAll"
        >
          <RefreshCw
            class="w-4 h-4"
            :class="{ 'animate-spin': alertStore.evaluating || alertStore.loadingRecords || alertStore.loadingRules }"
          />
          刷新
        </button>
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-accent/20 border border-ops-accent/40 text-sm text-ops-accent hover:bg-ops-accent/30 transition-all duration-200"
          :disabled="alertStore.evaluating"
          @click="handleEvaluate"
        >
          <Bell class="w-4 h-4" :class="{ 'animate-pulse': alertStore.evaluating }" />
          立即评估
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="card-gradient rounded-2xl border border-ops-border p-5">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-ops-muted">告警规则</span>
          <List class="w-4 h-4 text-ops-muted" />
        </div>
        <div class="text-2xl font-bold text-ops-text stat-number">{{ alertStore.rules.length }}</div>
        <div class="text-xs text-ops-muted mt-1">
          已启用: {{ alertStore.rules.filter((r) => r.enabled).length }}
        </div>
      </div>
      <div class="card-gradient rounded-2xl border border-red-500/30 p-5">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-red-400">严重告警</span>
          <AlertCircle class="w-4 h-4 text-red-400" />
        </div>
        <div class="text-2xl font-bold text-red-400 stat-number">{{ alertStore.activeCriticalCount }}</div>
        <div class="text-xs text-ops-muted mt-1">活动状态</div>
      </div>
      <div class="card-gradient rounded-2xl border border-amber-500/30 p-5">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-amber-400">警告</span>
          <AlertTriangle class="w-4 h-4 text-amber-400" />
        </div>
        <div class="text-2xl font-bold text-amber-400 stat-number">{{ alertStore.activeWarningCount }}</div>
        <div class="text-xs text-ops-muted mt-1">活动状态</div>
      </div>
      <div class="card-gradient rounded-2xl border border-ops-border p-5">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm text-ops-muted">告警记录总数</span>
          <Bell class="w-4 h-4 text-ops-muted" />
        </div>
        <div class="text-2xl font-bold text-ops-text stat-number">{{ alertStore.totalRecords }}</div>
        <div class="text-xs text-ops-muted mt-1">历史所有记录</div>
      </div>
    </div>

    <div class="flex gap-1 p-1 rounded-lg bg-ops-card border border-ops-border w-fit">
      <button
        class="px-5 py-2 text-sm rounded-md transition-all duration-200"
        :class="activeTab === 'rules' ? 'bg-ops-primary text-white' : 'text-ops-muted hover:text-ops-text'"
        @click="activeTab = 'rules'"
      >
        <span class="flex items-center gap-2">
          <List class="w-4 h-4" />
          告警规则
        </span>
      </button>
      <button
        class="px-5 py-2 text-sm rounded-md transition-all duration-200"
        :class="activeTab === 'records' ? 'bg-ops-primary text-white' : 'text-ops-muted hover:text-ops-text'"
        @click="activeTab = 'records'"
      >
        <span class="flex items-center gap-2">
          <Bell class="w-4 h-4" />
          告警记录
          <span
            v-if="alertStore.activeRecords.length > 0"
            class="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 text-xs rounded-full bg-red-500 text-white"
          >
            {{ alertStore.activeRecords.length }}
          </span>
        </span>
      </button>
    </div>

    <div v-show="activeTab === 'rules'" class="space-y-4">
      <div class="flex items-center justify-between">
        <div class="text-sm text-ops-muted">
          共 {{ alertStore.rules.length }} 条规则
        </div>
        <button
          class="flex items-center gap-2 px-4 py-2 rounded-lg bg-ops-primary text-white text-sm font-medium hover:bg-ops-primary/90 transition-all duration-200"
          @click="openCreateRule"
        >
          <Plus class="w-4 h-4" />
          创建规则
        </button>
      </div>

      <div class="card-gradient rounded-2xl border border-ops-border overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-ops-border">
                <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">规则名称</th>
                <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">监控队列</th>
                <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">告警条件</th>
                <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">级别</th>
                <th class="text-center px-6 py-4 text-sm font-medium text-ops-muted">状态</th>
                <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="rule in alertStore.rules"
                :key="rule.id"
                class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
              >
                <td class="px-6 py-4">
                  <div class="font-medium text-ops-text">{{ rule.name }}</div>
                  <div v-if="rule.description" class="text-xs text-ops-muted mt-1">
                    {{ rule.description }}
                  </div>
                </td>
                <td class="px-6 py-4">
                  <div class="flex items-center gap-2">
                    <Database class="w-4 h-4 text-ops-muted" />
                    <span class="text-ops-text">{{ rule.queue_name }}</span>
                  </div>
                </td>
                <td class="px-6 py-4">
                  <div class="text-ops-text">
                    {{ alertStore.getConditionLabel(rule.condition_type) }}
                    <span v-if="rule.condition_type !== 'consumers_eq_0'" class="text-ops-primary font-medium stat-number ml-1">
                      (阈值: {{ alertStore.formatValue(rule.condition_type, rule.threshold) }})
                    </span>
                  </div>
                </td>
                <td class="px-6 py-4">
                  <span
                    class="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-full border"
                    :class="getLevelClass(rule.level)"
                  >
                    <AlertCircle v-if="rule.level === 'critical'" class="w-3 h-3" />
                    <AlertTriangle v-else class="w-3 h-3" />
                    {{ alertStore.getLevelLabel(rule.level) }}
                  </span>
                </td>
                <td class="px-6 py-4 text-center">
                  <span
                    class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full"
                    :class="rule.enabled ? 'bg-emerald-500/15 text-emerald-400' : 'bg-slate-500/15 text-slate-400'"
                  >
                    <span
                      class="w-1.5 h-1.5 rounded-full"
                      :class="rule.enabled ? 'bg-emerald-400' : 'bg-slate-400'"
                    />
                    {{ rule.enabled ? '已启用' : '已停用' }}
                  </span>
                </td>
                <td class="px-6 py-4 text-right">
                  <div class="flex items-center justify-end gap-1">
                    <button
                      class="p-2 rounded-lg text-ops-muted hover:text-emerald-400 hover:bg-emerald-500/10 transition-all duration-150"
                      :title="rule.enabled ? '停用' : '启用'"
                      @click="handleToggleRule(rule)"
                    >
                      <Pause v-if="rule.enabled" class="w-4 h-4" />
                      <Play v-else class="w-4 h-4" />
                    </button>
                    <button
                      class="p-2 rounded-lg text-ops-muted hover:text-ops-primary hover:bg-ops-primary/10 transition-all duration-150"
                      title="编辑"
                      @click="openEditRule(rule)"
                    >
                      <Edit3 class="w-4 h-4" />
                    </button>
                    <button
                      class="p-2 rounded-lg text-ops-muted hover:text-red-400 hover:bg-red-500/10 transition-all duration-150"
                      title="删除"
                      @click="handleDeleteRule(rule)"
                    >
                      <Trash2 class="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="alertStore.rules.length === 0 && !alertStore.loadingRules">
                <td colspan="6" class="px-6 py-12 text-center">
                  <div class="flex flex-col items-center gap-3">
                    <Bell class="w-12 h-12 text-ops-muted/30" />
                    <div class="text-ops-muted text-sm">暂无告警规则，点击"创建规则"开始配置</div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div v-show="activeTab === 'records'" class="space-y-4">
      <div class="flex flex-wrap items-center gap-3">
        <div class="relative">
          <Search class="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ops-muted" />
          <input
            v-model="searchKeyword"
            type="text"
            placeholder="搜索规则名、队列名..."
            class="w-64 pl-9 pr-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150"
          />
        </div>
        <div class="flex items-center gap-2">
          <Filter class="w-4 h-4 text-ops-muted" />
          <select
            v-model="filterStatus"
            class="px-3 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
          >
            <option v-for="opt in statusOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
        <div class="flex items-center gap-2">
          <select
            v-model="filterLevel"
            class="px-3 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
          >
            <option value="">全部级别</option>
            <option v-for="opt in levelOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
        <div class="text-sm text-ops-muted ml-auto">
          共 {{ filteredRecords.length }} 条记录
        </div>
      </div>

      <div class="card-gradient rounded-2xl border border-ops-border overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full">
            <thead>
              <tr class="border-b border-ops-border">
                <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">级别</th>
                <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">规则</th>
                <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">队列</th>
                <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">条件</th>
                <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">当前值 / 阈值</th>
                <th class="text-left px-6 py-4 text-sm font-medium text-ops-muted">
                  <div class="flex items-center gap-1">
                    <Clock class="w-4 h-4" />
                    触发时间
                  </div>
                </th>
                <th class="text-center px-6 py-4 text-sm font-medium text-ops-muted">状态</th>
                <th class="text-right px-6 py-4 text-sm font-medium text-ops-muted">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="record in filteredRecords"
                :key="record.id"
                class="border-b border-ops-border/50 hover:bg-ops-card/30 transition-colors duration-150"
              >
                <td class="px-6 py-4">
                  <span
                    class="inline-flex items-center gap-1 px-2.5 py-1 text-xs rounded-full border"
                    :class="getLevelClass(record.level)"
                  >
                    <AlertCircle v-if="record.level === 'critical'" class="w-3 h-3" />
                    <AlertTriangle v-else class="w-3 h-3" />
                    {{ alertStore.getLevelLabel(record.level) }}
                  </span>
                </td>
                <td class="px-6 py-4 font-medium text-ops-text">{{ record.rule_name }}</td>
                <td class="px-6 py-4">
                  <div class="flex items-center gap-2">
                    <Database class="w-4 h-4 text-ops-muted" />
                    <span class="text-ops-text">{{ record.queue_name }}</span>
                  </div>
                </td>
                <td class="px-6 py-4 text-ops-text">
                  {{ alertStore.getConditionLabel(record.condition_type) }}
                </td>
                <td class="px-6 py-4">
                  <div class="text-sm">
                    <span class="font-medium text-ops-text stat-number">
                      {{ alertStore.formatValue(record.condition_type, record.current_value) }}
                    </span>
                    <span class="text-ops-muted mx-1">/</span>
                    <span class="text-ops-muted stat-number">
                      {{ alertStore.formatValue(record.condition_type, record.threshold) }}
                    </span>
                  </div>
                </td>
                <td class="px-6 py-4 text-ops-text text-sm stat-number">
                  {{ formatDateTime(record.created_at) }}
                </td>
                <td class="px-6 py-4 text-center">
                  <span
                    class="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-full"
                    :class="getStatusClass(record.status)"
                  >
                    <span
                      class="w-1.5 h-1.5 rounded-full"
                      :class="{
                        'bg-red-400 animate-pulse': record.status === 'active',
                        'bg-blue-400': record.status === 'acknowledged',
                        'bg-emerald-400': record.status === 'resolved',
                        'bg-slate-400': record.status === 'closed',
                      }"
                    />
                    {{ alertStore.getStatusLabel(record.status) }}
                  </span>
                </td>
                <td class="px-6 py-4 text-right">
                  <div class="flex items-center justify-end gap-1">
                    <button
                      v-if="record.status === 'active'"
                      class="p-2 rounded-lg text-ops-muted hover:text-emerald-400 hover:bg-emerald-500/10 transition-all duration-150"
                      title="确认告警"
                      @click="handleAcknowledge(record)"
                    >
                      <CheckCircle class="w-4 h-4" />
                    </button>
                    <button
                      v-if="record.status === 'active' || record.status === 'acknowledged'"
                      class="p-2 rounded-lg text-ops-muted hover:text-red-400 hover:bg-red-500/10 transition-all duration-150"
                      title="关闭告警"
                      @click="handleClose(record)"
                    >
                      <XCircle class="w-4 h-4" />
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="filteredRecords.length === 0 && !alertStore.loadingRecords">
                <td colspan="8" class="px-6 py-12 text-center">
                  <div class="flex flex-col items-center gap-3">
                    <Bell class="w-12 h-12 text-ops-muted/30" />
                    <div class="text-ops-muted text-sm">暂无告警记录</div>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="ruleDialogVisible"
      :title="isEditingRule ? '编辑告警规则' : '创建告警规则'"
      width="560px"
      :close-on-click-modal="false"
      class="alert-rule-dialog"
    >
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">规则名称 <span class="text-red-400">*</span></label>
          <input
            v-model="ruleForm.name"
            type="text"
            placeholder="例如：订单队列堆积告警"
            class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150"
          />
        </div>

        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">监控队列 <span class="text-red-400">*</span></label>
          <select
            v-model="ruleForm.queue_name"
            class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
          >
            <option value="">请选择队列</option>
            <option v-for="q in queues" :key="q.name" :value="q.name">
              {{ q.name }} (Ready: {{ q.ready }}, Unacked: {{ q.unacked }}, Consumers: {{ q.consumers }})
            </option>
          </select>
        </div>

        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-sm font-medium text-ops-text mb-2">告警条件 <span class="text-red-400">*</span></label>
            <select
              v-model="ruleForm.condition_type"
              class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text focus:outline-none focus:border-ops-primary transition-colors duration-150"
            >
              <option v-for="opt in conditionOptions" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </div>
          <div v-if="currentConditionHasThreshold">
            <label class="block text-sm font-medium text-ops-text mb-2">阈值 <span class="text-red-400">*</span></label>
            <input
              v-model.number="ruleForm.threshold"
              type="number"
              min="0"
              step="any"
              placeholder="请输入阈值"
              class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150"
            />
          </div>
          <div v-else>
            <label class="block text-sm font-medium text-ops-text mb-2">阈值</label>
            <div class="w-full px-4 py-2 rounded-lg bg-ops-bg/50 border border-ops-border text-ops-muted text-sm">
              此条件无需阈值
            </div>
          </div>
        </div>

        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">告警级别</label>
          <div class="flex gap-3">
            <label
              v-for="opt in levelOptions"
              :key="opt.value"
              class="flex items-center gap-2 cursor-pointer flex-1"
            >
              <input
                v-model="ruleForm.level"
                type="radio"
                :value="opt.value"
                class="w-4 h-4 accent-ops-primary"
              />
              <span
                class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-sm"
                :class="ruleForm.level === opt.value ? getLevelClass(opt.value) : 'bg-ops-bg border-ops-border text-ops-muted'"
              >
                <AlertCircle v-if="opt.value === 'critical'" class="w-3.5 h-3.5" />
                <AlertTriangle v-else class="w-3.5 h-3.5" />
                {{ opt.label }}
              </span>
            </label>
          </div>
        </div>

        <div>
          <label class="flex items-center gap-2 cursor-pointer">
            <input
              v-model="ruleForm.enabled"
              type="checkbox"
              class="w-4 h-4 rounded border-ops-border bg-ops-bg text-ops-primary"
            />
            <span class="text-sm text-ops-text">启用此规则</span>
          </label>
        </div>

        <div>
          <label class="block text-sm font-medium text-ops-text mb-2">描述（可选）</label>
          <textarea
            v-model="ruleForm.description"
            rows="2"
            placeholder="规则的详细说明"
            class="w-full px-4 py-2 rounded-lg bg-ops-bg border border-ops-border text-ops-text placeholder:text-ops-muted/50 focus:outline-none focus:border-ops-primary transition-colors duration-150 resize-none"
          />
        </div>
      </div>

      <template #footer>
        <div class="flex items-center justify-end gap-3">
          <button
            class="px-4 py-2 rounded-lg bg-ops-card border border-ops-border text-sm text-ops-text hover:bg-ops-card/80 transition-all duration-200"
            @click="ruleDialogVisible = false"
          >
            取消
          </button>
          <button
            class="px-4 py-2 rounded-lg bg-ops-primary text-white text-sm font-medium hover:bg-ops-primary/90 transition-all duration-200"
            @click="confirmRule"
          >
            {{ isEditingRule ? '保存' : '创建' }}
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.alert-rule-dialog :deep(.el-dialog) {
  background: #1E293B;
  border: 1px solid #334155;
  border-radius: 16px;
}

.alert-rule-dialog :deep(.el-dialog__header) {
  border-bottom: 1px solid #334155;
  padding: 20px 24px;
}

.alert-rule-dialog :deep(.el-dialog__title) {
  color: #E2E8F0;
  font-size: 18px;
  font-weight: 600;
}

.alert-rule-dialog :deep(.el-dialog__body) {
  padding: 24px;
}

.alert-rule-dialog :deep(.el-dialog__footer) {
  border-top: 1px solid #334155;
  padding: 16px 24px;
}
</style>
