import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import Dashboard from '@/pages/Dashboard.vue'
import Placeholder from '@/pages/Placeholder.vue'
import QueueList from '@/pages/QueueList.vue'
import QueueDetail from '@/pages/QueueDetail.vue'
import ExchangeList from '@/pages/ExchangeList.vue'
import ExchangeDetail from '@/pages/ExchangeDetail.vue'

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
    component: QueueList,
    meta: { title: '队列管理', icon: 'List', featureName: '队列管理' },
  },
  {
    path: '/queues/:name',
    name: 'QueueDetail',
    component: QueueDetail,
    meta: { title: '队列详情', icon: 'List', featureName: '队列管理', hideInMenu: true },
  },
  {
    path: '/exchanges',
    name: 'Exchanges',
    component: ExchangeList,
    meta: { title: '交换机管理', icon: 'Share2', featureName: '交换机管理' },
  },
  {
    path: '/exchanges/:name',
    name: 'ExchangeDetail',
    component: ExchangeDetail,
    meta: { title: '交换机详情', icon: 'Share2', featureName: '交换机管理', hideInMenu: true },
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
