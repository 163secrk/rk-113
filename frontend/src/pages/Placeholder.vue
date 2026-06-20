<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Construction, Sparkles } from 'lucide-vue-next'

const route = useRoute()
const featureName = computed(() => (route.meta.featureName as string) || '该功能')
</script>

<template>
  <div class="h-full flex items-center justify-center">
    <div class="text-center animate-slide-up">
      <div class="relative inline-flex mb-8">
        <div class="w-28 h-28 rounded-3xl bg-gradient-to-br from-ops-primary/20 to-ops-accent/20 border border-ops-border flex items-center justify-center">
          <Construction class="w-14 h-14 text-ops-primary" />
        </div>
        <div class="absolute -top-2 -right-2 w-10 h-10 rounded-full bg-gradient-to-br from-ops-warning to-ops-danger flex items-center justify-center shadow-glow-amber animate-pulse-slow">
          <Sparkles class="w-5 h-5 text-white" />
        </div>
      </div>

      <h2 class="text-2xl font-bold text-ops-text mb-3">功能开发中</h2>
      <p class="text-ops-muted mb-8 max-w-md">
        <span class="text-ops-primary font-medium">{{ featureName }}</span>
        模块正在紧张开发中，敬请期待。我们将为您提供更强大的 RabbitMQ 运维能力。
      </p>

      <div class="flex items-center justify-center gap-2">
        <div class="flex gap-1">
          <span class="w-2 h-2 rounded-full bg-ops-primary animate-bounce" style="animation-delay: 0ms" />
          <span class="w-2 h-2 rounded-full bg-ops-primary animate-bounce" style="animation-delay: 150ms" />
          <span class="w-2 h-2 rounded-full bg-ops-primary animate-bounce" style="animation-delay: 300ms" />
        </div>
        <span class="text-sm text-ops-muted ml-2">Coming Soon</span>
      </div>
    </div>
  </div>
</template>
