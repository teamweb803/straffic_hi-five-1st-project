import apiClient from './client'

/**
 * 백엔드 API
 *  GET  /api/board
 *  POST /api/board  { title, content, plateNumber, vehicleCount, recognitionConfidence }
 */
export const boardApi = {
  list() {
    return apiClient.get('/api/board')
  },
  create(payload) {
    return apiClient.post('/api/board', payload)
  }
}
