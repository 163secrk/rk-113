<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  AlertTriangle,
  AlertCircle,
  X,
  CheckCircle,
  XCircle,
  Bell,
} from 'lucide-vue-next'
import { useAlertStore } from '@/stores/alert'
import type { AlertRecord } from '@/api'

const alertStore = useAlertStore()
const router = useRouter()

const hasAlerts = computed(() => alertStore.bannerAlerts.length > 0)

function getLevelClass(level: string) {
  return level === 'critical'
    ? 'bg-red-500/15 border-red-500/50 text-red-300'
    : 'bg-amber-500/15 border-amber-500/50 text-amber-300'
}

function getLevelIcon(level: string) {
  return level === 'critical' ? AlertCircle : AlertTriangle
}

function getLevelGlow(level: string) {
  return level === 'critical' ? 'shadow-glow-red' : 'shadow-glow-amber'
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', { hour12: false })
  } catch {
    return '--'
  }
}

function goToAlertCenter() {
  router.push('/alerts')
  alertStore.clearBanners()
}

async function handleAcknowledge(record: AlertRecord) {
  try {
    await alertStore.acknowledge(record.id)
  } catch {
    // error already logged in store
  }
}

async function handleClose(record: AlertRecord) {
  try {
    await alertStore.close(record.id)
  } catch {
    // error already logged in store
  }
}

function handleDismiss(recordId: number) {
  alertStore.dismissBanner(recordId)
}
</script>

<template>
  <div
    v-if="hasAlerts"
    class="w-full bg-ops-panel/95 backdrop-blur-md border-b border-ops-border animate-slide-up"
  >
    <div class="max-w-full mx-auto px-6 py-3">
      <div class="flex items-center justify-between mb-2">
        <div class="flex items-center gap-2">
          <Bell class="w-4 h-4 text-ops-warning animate-pulse" />
          <span class="text-sm font-semibold text-ops-text">
            告警通知（{{ alertStore.bannerAlerts.length }}）
          </span>
        </div>
        <div class="flex items-center gap-2">
          <button
            class="px-3 py-1 text-xs rounded-md bg-ops-primary/20 text-ops-primary hover:bg-ops-primary/30 transition-colors"
            @click="goToAlertCenter"
          >
            查看全部
          </button>
          <button
            class="p-1 rounded-md text-ops-muted hover:text-ops-text hover:bg-ops-card/50 transition-colors"
            title="关闭所有通知"
            @click="alertStore.clearBanners()"
          >
            <X class="w-4 h-4" />
          </button>
        </div>
      </div>

      <div class="flex flex-col gap-2 max-h-48 overflow-y-auto pr-1">
        <div
          v-for="record in alertStore.bannerAlerts"
          :key="record.id"
          class="flex items-center gap-3 px-3 py-2 rounded-lg border transition-all duration-200"
          :class="[getLevelClass(record.level), getLevelGlow(record.level)]"
        >
          <component
            :is="getLevelIcon(record.level)"
            class="w-5 h-5 flex-shrink-0"
          />

          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 text-sm font-medium">
              <span>[{{ alertStore.getLevelLabel(record.level) }}]</span>
              <span class="truncate">{{ record.rule_name }}</span>
              <span class="text-xs opacity-70 stat-number">· {{ formatTime(record.created_at) }}</span>
            </div>
            <div class="text-xs opacity-80 mt-0.5 truncate">
              队列: {{ record.queue_name }} | {{ alertStore.getConditionLabel(record.condition_type) }} |
              当前值: <span class="font-medium stat-number">{{ alertStore.formatValue(record.condition_type, record.current_value) }}</span>
              / 阈值: <span class="stat-number">{{ alertStore.formatValue(record.condition_type, record.threshold) }}</span>
            </div>
          </div>

          <div class="flex items-center gap-1 flex-shrink-0">
            <button
              class="p-1.5 rounded-md hover:bg-white/10 transition-colors"
              title="确认告警"
              @click="handleAcknowledge(record)"
            >
              <CheckCircle class="w-4 h-4" />
            </button>
            <button
              class="p-1.5 rounded-md hover:bg-white/10 transition-colors"
              title="关闭告警"
              @click="handleClose(record)"
            >
              <XCircle class="w-4 h-4" />
            </button>
            <button
              class="p-1.5 rounded-md hover:bg-white/10 transition-colors"
              title="忽略此条"
              @click="handleDismiss(record.id)"
            >
              <X class="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
