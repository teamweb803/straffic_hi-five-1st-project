import axios from 'axios'

const chatbotClient = axios.create({
  baseURL: import.meta.env.VITE_CHATBOT_API_BASE_URL || '/chatbot-api',
  headers: { 'Content-Type': 'application/json' }
})

export async function askChatbot(question) {
  const { data } = await chatbotClient.post('/api/chatbot/ask', { question })
  return data
}
