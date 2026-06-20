<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'

interface Props {
  title: string
  value: string | number
  icon: Component
  accent?: 'blue' | 'green' | 'amber' | 'red' | 'purple'
  trend?: number
  trendLabel?: string
  subtitle?: string
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  accent: 'blue',
  loading: false,
})

const accentClasses = computed(() => {
  const map: Record<string, { icon: string; glow: string; bar: string; text: string }> = {
    blue: {
      icon: 'from-blue-500/20 to-blue-600/20 text-blue-400',
      glow: 'shadow-glow-blue',
      bar: 'bg-gradient-to-r from-blue-500 to-cyan-400',
      text: 'text-blue-400',
    },
    green: {
      icon: 'from-emerald-500/20 to-emerald-600/20 text-emerald-400',
      glow: 'shadow-glow-green',
      bar: 'bg-gradient-to-r from-emerald-500 to-teal-400',
      text: 'text-emerald-400',
    },
    amber: {
      icon: 'from-amber-500/20 to-amber-600/20 text-amber-400',
      glow: 'shadow-glow-amber',
      bar: 'bg-gradient-to-r from-amber-500 to-orange-400',
      text: 'text-amber-400',
    },
    red: {
      icon: 'from-red-500/20 to-red-600/20 text-red-400',
      glow: 'shadow-glow-red',
      bar: 'bg-gradient-to-r from-red-500 to-rose-400',
      text: 'text-red-400',
    },
    purple: {
      icon: 'from-purple-500/20 to-purple-600/20 text-purple-400',
      glow: 'shadow-glow-blue',
      bar: 'bg-gradient-to-r from-purple-500 to-fuchsia-400',
      text: 'text-purple-400',
    },
  }
  return map[props.accent] || map.blue
})
</script>

<template>
  <div
    class="card-gradient rounded-2xl border border-ops-border p-6 transition-all duration-300 hover:border-ops-primary/40 hover:shadow-glow-blue relative overflow-hidden group"
  >
    <div
      class="absolute top-0 left-0 right-0 h-0.5 transition-all duration-500 group-hover:h-1"
      :class="accentClasses.bar"
    />

    <div class="flex items-start justify-between mb-4">
      <div>
        <div class="text-sm text-ops-muted mb-1">{{ title }}</div>
        <div
          v-if="loading"
          class="h-9 w-24 rounded bg-ops-card animate-pulse"
        />
        <div v-else class="text-3xl font-bold text-ops-text stat-number">
          {{ value }}
        </div>
      </div>
      <div
        class="w-12 h-12 rounded-xl bg-gradient-to-br flex items-center justify-center transition-transform duration-300 group-hover:scale-110"
        :class="[accentClasses.icon, accentClasses.glow]"
      >
        <component :is="icon" class="w-6 h-6" />
      </div>
    </div>

    <div v-if="subtitle" class="text-xs text-ops-muted mb-3">
      {{ subtitle }}
    </div>

    <div v-if="trend !== undefined" class="flex items-center gap-1 text-xs">
      <span :class="trend >= 0 ? 'text-emerald-400' : 'text-red-400'" class="font-medium">
        {{ trend >= 0 ? '+' : '' }}{{ trend }}%
      </span>
      <span class="text-ops-muted">{{ trendLabel || '较上次' }}</span>
    </div>
  </div>
</template>
