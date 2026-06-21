<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Send, Eye, MessageSquare } from 'lucide-vue-next'
import PublishMessage from './PublishMessage.vue'
import BrowseMessages from './BrowseMessages.vue'

defineOptions({
  name: 'MessageCenter',
})

const route = useRoute()
const router = useRouter()

const tabs = [
  { name: 'publish', title: '发布消息', icon: Send },
  { name: 'browse', title: '消息浏览', icon: Eye },
] as const

type TabName = (typeof tabs)[number]['name']

const activeTab = ref<TabName>('publish')

function syncFromRoute() {
  const hash = route.hash.replace('#', '')
  if (hash === 'browse' || hash === 'publish') {
    activeTab.value = hash as TabName
  }
}

function switchTab(tabName: TabName) {
  activeTab.value = tabName
  router.replace({ hash: tabName })
}

watch(
  () => route.hash,
  () => syncFromRoute()
)

onMounted(() => {
  syncFromRoute()
})
</script>

<template>
  <div class="space-y-5">
    <div class="card-gradient rounded-2xl border border-ops-border p-4">
      <div class="flex items-center justify-between flex-wrap gap-4">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-ops-primary/20 to-ops-accent/20 border border-ops-primary/30 flex items-center justify-center">
            <MessageSquare class="w-5 h-5 text-ops-primary" />
          </div>
          <div>
            <h2 class="text-lg font-bold text-ops-text">消息中心</h2>
            <p class="text-xs text-ops-muted">消息的发布、浏览和管理中心</p>
          </div>
        </div>

        <div class="flex rounded-xl bg-ops-bg border border-ops-border p-1">
          <button
            v-for="tab in tabs"
            :key="tab.name"
            class="flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all duration-200"
            :class="activeTab === tab.name
              ? 'bg-ops-primary/15 text-ops-primary shadow-sm'
              : 'text-ops-muted hover:text-ops-text hover:bg-ops-card/50'"
            @click="switchTab(tab.name)"
          >
            <component :is="tab.icon" class="w-4 h-4" />
            {{ tab.title }}
          </button>
        </div>
      </div>
    </div>

    <transition name="fade-slide" mode="out-in">
      <PublishMessage v-if="activeTab === 'publish'" />
      <BrowseMessages v-else />
    </transition>
  </div>
</template>

<style scoped>
.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.25s ease;
}

.fade-slide-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
