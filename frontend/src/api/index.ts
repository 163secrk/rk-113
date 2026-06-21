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

export interface ExchangeListItem {
  name: string
  vhost: string
  type: 'direct' | 'topic' | 'fanout' | 'headers'
  durable: boolean
  auto_delete: boolean
  internal: boolean
}

export interface ExchangeBinding {
  source: string
  destination: string
  destination_type: string
  routing_key: string
  arguments: Record<string, unknown>
  properties_key?: string
}

export interface ExchangeDetail {
  name: string
  vhost: string
  type: 'direct' | 'topic' | 'fanout' | 'headers'
  durable: boolean
  auto_delete: boolean
  internal: boolean
  arguments: Record<string, unknown>
  bindings: ExchangeBinding[]
}

export interface CreateExchangeRequest {
  name: string
  type?: 'direct' | 'topic' | 'fanout' | 'headers'
  durable?: boolean
  auto_delete?: boolean
  internal?: boolean
  arguments?: Record<string, unknown>
}

export interface CreateBindingRequest {
  destination: string
  destination_type?: string
  routing_key?: string
  arguments?: Record<string, unknown>
}

export const getExchanges = () =>
  api.get<unknown, ExchangeListItem[]>('/rabbitmq/exchanges')

export const getExchangeDetail = (exchangeName: string) =>
  api.get<unknown, ExchangeDetail>(`/rabbitmq/exchanges/${encodeURIComponent(exchangeName)}`)

export const createExchange = (data: CreateExchangeRequest) =>
  api.post<unknown, OperationResponse>('/rabbitmq/exchanges', data)

export const deleteExchange = (exchangeName: string, ifUnused = false) => {
  const params = new URLSearchParams()
  if (ifUnused) params.append('if_unused', 'true')
  const query = params.toString()
  return api.delete<unknown, OperationResponse>(
    `/rabbitmq/exchanges/${encodeURIComponent(exchangeName)}${query ? `?${query}` : ''}`
  )
}

export const createBinding = (exchangeName: string, data: CreateBindingRequest) =>
  api.post<unknown, OperationResponse>(
    `/rabbitmq/exchanges/${encodeURIComponent(exchangeName)}/bindings`,
    data
  )

export const deleteBinding = (
  exchangeName: string,
  destination: string,
  destinationType = 'queue',
  propertiesKey = ''
) => {
  const params = new URLSearchParams()
  params.append('destination', destination)
  params.append('destination_type', destinationType)
  if (propertiesKey) params.append('properties_key', propertiesKey)
  return api.delete<unknown, OperationResponse>(
    `/rabbitmq/exchanges/${encodeURIComponent(exchangeName)}/bindings?${params.toString()}`
  )
}

export interface PublishMessageRequest {
  target_type: 'exchange' | 'queue'
  target_name: string
  routing_key: string
  payload: string
  headers?: Record<string, string>
  content_encoding?: string
  delivery_mode?: 1 | 2
  priority?: number
  content_type?: string
}

export interface PublishMessageResponse {
  success: boolean
  message: string
  published_count?: number
}

export interface DeadLetterInfo {
  reason?: string
  original_queue?: string
  original_routing_key?: string
  original_exchange?: string
  count?: number
  time?: string
}

export interface MessageItem {
  id: string
  index: number
  payload: string
  payload_bytes: number
  headers: Record<string, string>
  properties: {
    content_type?: string
    content_encoding?: string
    delivery_mode?: number
    priority?: number
    correlation_id?: string
    reply_to?: string
    expiration?: string
    message_id?: string
    timestamp?: number
    type?: string
    user_id?: string
    app_id?: string
    cluster_id?: string
  }
  exchange: string
  routing_key: string
  redelivered: boolean
  delivery_tag: number
  vhost: string
  dead_letter?: DeadLetterInfo
}

export interface RepublishRequest {
  delivery_tag: number
  original_queue?: string
  original_routing_key?: string
}

export interface RepublishAllResponse {
  success: boolean
  message: string
  total?: number
  success_count?: number
  failed_count?: number
  failed_details?: string[]
}

export interface CheckQueueExistsResponse {
  exists: boolean
  queue_name: string
}

export interface QueueMessageListResponse {
  success: boolean
  messages: MessageItem[]
  total: number
  queue: string
}

export interface MessageOperationResponse {
  success: boolean
  message: string
}

export const publishMessage = (data: PublishMessageRequest) =>
  api.post<unknown, PublishMessageResponse>('/rabbitmq/messages/publish', data)

export const getQueueMessages = (queueName: string, limit = 50, requeue = true) => {
  const params = new URLSearchParams()
  params.append('limit', String(limit))
  params.append('requeue', String(requeue))
  return api.get<unknown, QueueMessageListResponse>(
    `/rabbitmq/queues/${encodeURIComponent(queueName)}/messages?${params.toString()}`
  )
}

export const ackMessage = (queueName: string, deliveryTag: number) =>
  api.post<unknown, MessageOperationResponse>(
    `/rabbitmq/queues/${encodeURIComponent(queueName)}/messages/ack`,
    { delivery_tag: deliveryTag }
  )

export const rejectMessage = (queueName: string, deliveryTag: number, requeue = false) =>
  api.post<unknown, MessageOperationResponse>(
    `/rabbitmq/queues/${encodeURIComponent(queueName)}/messages/reject`,
    { delivery_tag: deliveryTag, requeue }
  )

export const checkQueueExists = (queueName: string) =>
  api.get<unknown, CheckQueueExistsResponse>(
    `/rabbitmq/queues/${encodeURIComponent(queueName)}/exists`
  )

export const republishDeadLetter = (queueName: string, data: RepublishRequest) =>
  api.post<unknown, OperationResponse>(
    `/rabbitmq/queues/${encodeURIComponent(queueName)}/messages/republish`,
    data
  )

export const republishAllDeadLetters = (queueName: string) =>
  api.post<unknown, RepublishAllResponse>(
    `/rabbitmq/queues/${encodeURIComponent(queueName)}/messages/republish-all`
  )

export function isDeadLetterQueue(queueName: string): boolean {
  const nameLower = queueName.toLowerCase()
  return nameLower.includes('dlq') || nameLower.includes('dead-letter') || nameLower.includes('dead_letter')
}

export interface AuditLogItem {
  id: number
  operation_type: string
  operator: string
  target_exchange: string | null
  routing_key: string | null
  queue_name: string | null
  message_id: string | null
  message_summary: string | null
  message_body: string | null
  headers: Record<string, unknown> | null
  properties: Record<string, unknown> | null
  delivery_tag: number | null
  status: string
  error_message: string | null
  created_at: string
}

export interface AuditLogListResponse {
  items: AuditLogItem[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface AuditStats {
  publish: number
  consume: number
  ack: number
  reject: number
  total: number
}

export interface AuditLogQueryParams {
  operation_type?: string
  start_time?: string
  end_time?: string
  keyword?: string
  page?: number
  page_size?: number
}

export const getAuditLogs = (params: AuditLogQueryParams) => {
  const queryParams = new URLSearchParams()
  if (params.operation_type) queryParams.append('operation_type', params.operation_type)
  if (params.start_time) queryParams.append('start_time', params.start_time)
  if (params.end_time) queryParams.append('end_time', params.end_time)
  if (params.keyword) queryParams.append('keyword', params.keyword)
  if (params.page) queryParams.append('page', String(params.page))
  if (params.page_size) queryParams.append('page_size', String(params.page_size))
  const query = queryParams.toString()
  return api.get<unknown, AuditLogListResponse>(`/audit/logs${query ? `?${query}` : ''}`)
}

export const getAuditLogDetail = (logId: number) =>
  api.get<unknown, AuditLogItem>(`/audit/logs/${logId}`)

export const getAuditStats = (startTime?: string, endTime?: string) => {
  const params = new URLSearchParams()
  if (startTime) params.append('start_time', startTime)
  if (endTime) params.append('end_time', endTime)
  const query = params.toString()
  return api.get<unknown, AuditStats>(`/audit/stats${query ? `?${query}` : ''}`)
}

export interface ConnectionListItem {
  name: string
  client_ip: string
  client_port: number
  username: string
  vhost: string
  connected_at: number
  channels: number
  server_ip: string
  server_port: number
  protocol?: string
  type?: string
}

export interface UserListItem {
  name: string
  tags: string[]
}

export interface UserPermission {
  vhost: string
  configure: string
  write: string
  read: string
}

export interface UserTopicPermission {
  vhost: string
  exchange: string
  write: string
  read: string
}

export interface UserDetail {
  name: string
  tags: string[]
  permissions: UserPermission[]
  topic_permissions: UserTopicPermission[]
}

export const getConnections = () =>
  api.get<unknown, ConnectionListItem[]>('/rabbitmq/connections')

export const closeConnection = (connectionName: string) =>
  api.delete<unknown, OperationResponse>(
    `/rabbitmq/connections/${encodeURIComponent(connectionName)}`
  )

export const getUsers = () =>
  api.get<unknown, UserListItem[]>('/rabbitmq/users')

export const getUserDetail = (username: string) =>
  api.get<unknown, UserDetail>(`/rabbitmq/users/${encodeURIComponent(username)}`)

export default api
