import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    console.error('API Error:', err)
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
