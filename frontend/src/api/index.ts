import axios, { type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

const errorMessageCache = new Map<string, number>()
const ERROR_DEBOUNCE_MS = 10000

function showErrorDebounced(message: string) {
  const now = Date.now()
  const lastShown = errorMessageCache.get(message) || 0
  if (now - lastShown < ERROR_DEBOUNCE_MS) {
    return
  }
  errorMessageCache.set(message, now)
  ElMessage.error({
    message,
    duration: 3000,
    showClose: true,
  })
}

async function requestWithRetry<T>(
  config: AxiosRequestConfig,
  retries: number = 1,
  retryDelay: number = 500
): Promise<T> {
  let lastError: unknown
  for (let i = 0; i <= retries; i++) {
    try {
      const response = await api.request<T>(config)
      return response.data as T
    } catch (err) {
      lastError = err
      if (i < retries) {
        await new Promise((resolve) => setTimeout(resolve, retryDelay * (i + 1)))
        continue
      }
    }
  }
  throw lastError
}

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    console.error('API Error:', err)
    const url = err.config?.url || ''
    const status = err.response?.status
    let errorMsg = '请求失败，请稍后重试'
    if (status === 404) {
      errorMsg = '请求的资源不存在'
    } else if (status === 500) {
      errorMsg = '服务器内部错误'
    } else if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
      errorMsg = '请求超时，请检查网络连接'
    } else if (err.message?.includes('Network Error')) {
      errorMsg = '网络连接失败，请检查后端服务'
    }
    if (!url.includes('/health') && !url.includes('/connection/status')) {
      showErrorDebounced(errorMsg)
    }
    return Promise.reject(err)
  }
)

export interface MessageRate {
  publish: number
  deliver: number
  ack: number
}

export interface ConnectionInfo {
  status: 'connected' | 'disconnected' | 'connecting'
  host: string
  port: number
  uptime?: number
}

export interface RabbitMQOverview {
  connection: ConnectionInfo
  channels: number
  queues: number
  messageRate: MessageRate
  timestamp: number
}

export interface ConnectionStatus {
  status: 'connected' | 'disconnected' | 'connecting'
  host: string
  port: number
  error?: string
}

export const getHealth = () => api.get<unknown, { status: string; timestamp: number }>('/health')

export const getRabbitMQOverview = () =>
  api.get<unknown, RabbitMQOverview>('/rabbitmq/overview')

export const getConnectionStatus = () =>
  api.get<unknown, ConnectionStatus>('/rabbitmq/connection/status')

export interface QueueListItem {
  name: string
  ready: number
  unacked: number
  total: number
  consumers: number
  status: 'running' | 'idle'
  vhost: string
  durable: boolean
  auto_delete: boolean
  exclusive: boolean
  node: string
}

export interface QueueBinding {
  exchange: string
  routing_key: string
  destination: string
  destination_type: string
  arguments: Record<string, unknown>
}

export interface QueueConsumer {
  consumer_tag: string
  channel_details: Record<string, unknown>
  ack_required: boolean
  exclusive: boolean
  arguments: Record<string, unknown>
}

export interface QueueDetail {
  name: string
  vhost: string
  durable: boolean
  auto_delete: boolean
  exclusive: boolean
  arguments: Record<string, unknown>
  ready: number
  unacked: number
  total: number
  consumers: number
  status: 'running' | 'idle'
  node?: string
  state?: string
  bindings: QueueBinding[]
  consumer_list: QueueConsumer[]
  message_stats?: Record<string, unknown>
  memory: number
  policy?: string
}

export interface CreateQueueRequest {
  name: string
  durable?: boolean
  auto_delete?: boolean
  exclusive?: boolean
  arguments?: Record<string, unknown>
}

export interface OperationResponse {
  success: boolean
  message: string
}

export const getQueues = () =>
  api.get<unknown, QueueListItem[]>('/rabbitmq/queues')

export const getQueueDetail = (queueName: string) =>
  api.get<unknown, QueueDetail>(`/rabbitmq/queues/${encodeURIComponent(queueName)}`)

export const createQueue = (data: CreateQueueRequest) =>
  api.post<unknown, OperationResponse>('/rabbitmq/queues', data)

export const purgeQueue = (queueName: string) =>
  api.post<unknown, OperationResponse>(`/rabbitmq/queues/${encodeURIComponent(queueName)}/purge`)

export const deleteQueue = (queueName: string, ifUnused = false, ifEmpty = false) => {
  const params = new URLSearchParams()
  if (ifUnused) params.append('if_unused', 'true')
  if (ifEmpty) params.append('if_empty', 'true')
  const query = params.toString()
  return api.delete<unknown, OperationResponse>(
    `/rabbitmq/queues/${encodeURIComponent(queueName)}${query ? `?${query}` : ''}`
  )
}

export default api
