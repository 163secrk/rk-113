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

export default api
