import axios from 'axios'

const http = axios.create({ baseURL: '/api', timeout: 15000 })

export const getFilters    = ()            => http.get('/stats/filters').then(r => r.data)
export const getOverview   = (params = {}) => http.get('/stats/overview',   { params }).then(r => r.data)
export const getTrend      = (params = {}) => http.get('/stats/trend',      { params }).then(r => r.data)
export const getMonthly    = (params = {}) => http.get('/stats/monthly',    { params }).then(r => r.data)
export const getYearly     = (params = {}) => http.get('/stats/yearly',     { params }).then(r => r.data)
export const getRanking    = (params = {}) => http.get('/stats/ranking',    { params }).then(r => r.data)
export const getRegions    = (params = {}) => http.get('/stats/regions',    { params }).then(r => r.data)
export const getCategories = (params = {}) => http.get('/stats/categories', { params }).then(r => r.data)
export const getDetail     = (params = {}) => http.get('/stats/detail',     { params }).then(r => r.data)

export const getSyncStatus = ()            => http.get('/sync/status').then(r => r.data)
export const triggerSync   = ()            => http.post('/sync/smart').then(r => r.data)