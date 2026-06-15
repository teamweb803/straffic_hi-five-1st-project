import apiClient from './client'

export const pdmApi = {
  getDashboardSummary() {
    return apiClient.get('/api/v1/pdm/dashboard/summary')
  },
  getCameras() {
    return apiClient.get('/api/v1/pdm/cameras')
  },
  getCameraDetail(cameraId) {
    return apiClient.get(`/api/v1/pdm/cameras/${cameraId}`)
  },
  getQualityMetrics(cameraId, params = {}) {
    return apiClient.get(`/api/v1/pdm/cameras/${cameraId}/quality-metrics`, { params })
  },
  getAlerts(params = {}) {
    return apiClient.get('/api/v1/pdm/alerts', { params })
  },
  updateAlertStatus(alertId, status) {
    return apiClient.patch(`/api/v1/pdm/alerts/${alertId}/status`, { status })
  },
  getCompareResults(params = {}) {
    return apiClient.get('/api/v1/pdm/compare-results', { params })
  },
}
