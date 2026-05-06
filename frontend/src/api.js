import axios from 'axios';

const api = axios.create({
  baseURL: 'https://simulation-api-seven.vercel.app'
});

export const runSimulation = async (params) => {
  const response = await api.post('/run-simulation', params);
  return response.data;
};

export const runStressTest = async (params) => {
  const response = await api.post('/stress-test', params);
  return response.data;
};

export const runProfitVsQ = async (params) => {
  const response = await api.post('/profit-vs-q', params);
  return response.data;
};

export const runSensitivityRQ = async (params) => {
  const response = await api.post('/sensitivity-rq', params);
  return response.data;
};

export const suggestR = async (params) => {
  const response = await api.post('/suggest-r', params);
  return response.data;
};

export const generateInsights = async (data) => {
  const response = await api.post('/generate-insights', data);
  return response.data;
};
