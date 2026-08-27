import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://tender-backend-pi.vercel.app';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchTenders = async (params = {}) => {
  const res = await api.get('/api/tenders', { params });
  return res.data;
};

export const fetchTenderById = async (id) => {
  const res = await api.get(`/api/tenders/${id}`);
  return res.data;
};

export const fetchScreening = async (id) => {
  const res = await api.get(`/api/tenders/${id}/screening`);
  return res.data;
};

export const rescreenTender = async (id) => {
  const res = await api.post(`/api/tenders/${id}/screen`);
  return res.data;
};

export const fetchProfile = async () => {
  const res = await api.get('/api/profile');
  return res.data;
};

export const updateProfile = async (data) => {
  const res = await api.put('/api/profile', data);
  return res.data;
};

export const sendChatQuestion = async (question, tenderId = null) => {
  const res = await api.post('/api/chat', { question, tender_id: tenderId });
  return res.data;
};

export const triggerIngestion = async () => {
  const res = await api.post('/api/ingestion/run');
  return res.data;
};

export const triggerDiscovery = async () => {
  const res = await api.post('/api/discover');
  return res.data;
};

export const fetchIngestionStatus = async (jobId) => {
  const res = await api.get(`/api/ingestion/${jobId}`);
  return res.data;
};

export default api;
