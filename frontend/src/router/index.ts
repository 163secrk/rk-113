import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import Dashboard from '@/pages/Dashboard.vue'
import Placeholder from '@/pages/Placeholder.vue'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: Dashboard,
    meta: { title: 'Dashboard', icon: 'Gauge' },
  },
  {
    path: '/queues',
    name: 'Queues',
    component: Placeholder,
    meta: { title: '队列管理', icon: 'List', featureName: '队列管理' },
  },
  {
    path: '/exchanges',
    name: 'Exchanges',
    component: Placeholder,
    meta: { title: '交换机管理', icon: 'Share2', featureName: '交换机管理' },
  },
  {
    path: '/messages',
    name: 'Messages',
    component: Placeholder,
    meta: { title: '消息中心', icon: 'MessageSquare', featureName: '消息中心' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
