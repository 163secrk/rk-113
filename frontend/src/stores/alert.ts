import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import {
  getAlertRules,
  getAlertRecords,
  evaluateAlertsNow,
  acknowledgeAlertRecord,
  closeAlertRecord,
  type AlertRule,
  type AlertRecord,
  type AlertStatus,
  type AlertLevel,
} from '@/api'

const CONDITION_LABELS: Record<string, string> = {
  ready_gt: 'Ready消息数 > N',
  unacked_gt: 'Unacked消息数 > N',
  consumers_eq_0: '消费者数量 = 0',
  rate_gt: '消息速率 > N条/秒',
}

const LEVEL_LABELS: Record<string, string> = {
  warning: '警告',
  critical: '严重',
}

const STATUS_LABELS: Record<string, string> = {
  active: '活动中',
  acknowledged: '已确认',
  resolved: '已恢复',
  closed: '已关闭',
}

export const useAlertStore = defineStore('alert', () => {
  const rules = ref<AlertRule[]>([])
  const records = ref<AlertRecord[]>([])
  const totalRecords = ref(0)
  const loadingRules = ref(false)
  const loadingRecords = ref(false)
  const evaluating = ref(false)
  const lastEvaluatedAt = ref<Date | null>(null)
  const bannerAlerts = ref<AlertRecord[]>([])
  const seenRecordIds = ref<Set<number>>(new Set())

  const activeRecords = computed(() =>
    records.value.filter((r) => r.status === 'active')
  )

  const activeCriticalCount = computed(() =>
    activeRecords.value.filter((r) => r.level === 'critical').length
  )

  const activeWarningCount = computed(() =>
    activeRecords.value.filter((r) => r.level === 'warning').length
  )

  function getConditionLabel(type: string): string {
    return CONDITION_LABELS[type] || type
  }

  function getLevelLabel(level: string): string {
    return LEVEL_LABELS[level] || level
  }

  function getStatusLabel(status: string): string {
    return STATUS_LABELS[status] || status
  }

  async function fetchRules() {
    loadingRules.value = true
    try {
      rules.value = await getAlertRules()
    } catch (err) {
      console.error('Failed to fetch alert rules:', err)
    } finally {
      loadingRules.value = false
    }
  }

  async function fetchRecords(params?: { status?: AlertStatus; level?: AlertLevel; limit?: number }) {
    loadingRecords.value = true
    try {
      const response = await getAlertRecords(params)
      records.value = response.items
      totalRecords.value = response.total
    } catch (err) {
      console.error('Failed to fetch alert records:', err)
    } finally {
      loadingRecords.value = false
    }
  }

  async function evaluate() {
    if (evaluating.value) return
    evaluating.value = true
    try {
      const triggered = await evaluateAlertsNow()
      const newActive = triggered.filter((r) => {
        if (seenRecordIds.value.has(r.id)) return false
        seenRecordIds.value.add(r.id)
        return true
      })
      if (newActive.length > 0) {
        bannerAlerts.value = [...newActive, ...bannerAlerts.value].slice(0, 10)
      }
      lastEvaluatedAt.value = new Date()
      await fetchRecords({ limit: 200 })
    } catch (err) {
      console.error('Failed to evaluate alerts:', err)
    } finally {
      evaluating.value = false
    }
  }

  function dismissBanner(recordId: number) {
    bannerAlerts.value = bannerAlerts.value.filter((r) => r.id !== recordId)
  }

  function clearBanners() {
    bannerAlerts.value = []
  }

  async function acknowledge(recordId: number) {
    try {
      const updated = await acknowledgeAlertRecord(recordId)
      const idx = records.value.findIndex((r) => r.id === recordId)
      if (idx >= 0) {
        records.value[idx] = updated
      }
      bannerAlerts.value = bannerAlerts.value.filter((r) => r.id !== recordId)
      return updated
    } catch (err) {
      console.error('Failed to acknowledge alert:', err)
      throw err
    }
  }

  async function close(recordId: number) {
    try {
      const updated = await closeAlertRecord(recordId)
      const idx = records.value.findIndex((r) => r.id === recordId)
      if (idx >= 0) {
        records.value[idx] = updated
      }
      bannerAlerts.value = bannerAlerts.value.filter((r) => r.id !== recordId)
      return updated
    } catch (err) {
      console.error('Failed to close alert:', err)
      throw err
    }
  }

  function formatValue(conditionType: string, value: number): string {
    if (conditionType === 'rate_gt') {
      return value >= 1000 ? (value / 1000).toFixed(1) + 'k/s' : value.toFixed(2) + '/s'
    }
    return value.toLocaleString('zh-CN')
  }

  return {
    rules,
    records,
    totalRecords,
    loadingRules,
    loadingRecords,
    evaluating,
    lastEvaluatedAt,
    bannerAlerts,
    activeRecords,
    activeCriticalCount,
    activeWarningCount,
    getConditionLabel,
    getLevelLabel,
    getStatusLabel,
    fetchRules,
    fetchRecords,
    evaluate,
    dismissBanner,
    clearBanners,
    acknowledge,
    close,
    formatValue,
  }
})
