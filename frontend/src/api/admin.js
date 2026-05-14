import apiClient from './client'

export const adminApi = {
  members() {
    return apiClient.get('/api/admin/members')
  },
  assignDashboard(email, dashboardId) {
    return apiClient.patch(`/api/admin/members/${encodeURIComponent(email)}/dashboard`, { dashboardId })
  }
}
