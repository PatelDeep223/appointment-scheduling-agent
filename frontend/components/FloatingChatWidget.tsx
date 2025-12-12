'use client'

import { useState, useRef, useEffect } from 'react'
import { MessageCircle, X, Send, Minimize2 } from 'lucide-react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import SuggestionButtons from './SuggestionButtons'
import AppointmentConfirmation from './AppointmentConfirmation'
import { apiService, ChatMessage as ChatMessageType } from '@/lib/api'

export default function FloatingChatWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [messages, setMessages] = useState<ChatMessageType[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [currentSuggestions, setCurrentSuggestions] = useState<string[]>([])
  const [appointmentDetails, setAppointmentDetails] = useState<any>(null)
  const [sessionId] = useState(() => `session-${Date.now()}`)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async (message: string) => {
    if (!message.trim() || isLoading) return

    // Add user message
    const userMessage: ChatMessageType = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      const response = await apiService.sendMessage(message, sessionId)

      // Add assistant message
      const assistantMessage: ChatMessageType = {
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMessage])

      // Update suggestions and appointment details
      setCurrentSuggestions(response.suggestions || [])
      setAppointmentDetails(response.appointment_details || null)
    } catch (error: any) {
      const errorMessage: ChatMessageType = {
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error.message}. Please try again.`,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSuggestionClick = (suggestion: string) => {
    handleSendMessage(suggestion)
  }

  const getLastResponse = () => {
    const lastAssistantMessage = [...messages]
      .reverse()
      .find((msg) => msg.role === 'assistant')
    return lastAssistantMessage?.content || ''
  }

  const toggleChat = () => {
    if (isOpen && !isMinimized) {
      setIsMinimized(true)
    } else {
      setIsOpen(true)
      setIsMinimized(false)
    }
  }

  const closeChat = () => {
    setIsOpen(false)
    setIsMinimized(false)
  }

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-16 h-16 bg-primary-600 hover:bg-primary-700 text-white rounded-full shadow-lg flex items-center justify-center transition-all duration-300 hover:scale-110 z-50"
        aria-label="Open chat"
      >
        <MessageCircle size={28} />
      </button>
    )
  }

  return (
    <div
      ref={chatContainerRef}
      className={`fixed bottom-6 right-6 w-96 bg-white rounded-lg shadow-2xl flex flex-col transition-all duration-300 z-50 ${
        isMinimized ? 'h-16' : 'h-[600px]'
      }`}
    >
      {/* Header */}
      <div className="bg-primary-600 text-white p-4 rounded-t-lg flex items-center justify-between">
        <div className="flex items-center gap-2">
          <MessageCircle size={20} />
          <h3 className="font-semibold">Appointment Assistant</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleChat}
            className="hover:bg-primary-700 p-1 rounded transition-colors"
            aria-label="Minimize chat"
          >
            <Minimize2 size={18} />
          </button>
          <button
            onClick={closeChat}
            className="hover:bg-primary-700 p-1 rounded transition-colors"
            aria-label="Close chat"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Messages Container */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 chat-scrollbar bg-gray-50">
            {messages.length === 0 && (
              <div className="text-center text-gray-500 py-8">
                <MessageCircle size={48} className="mx-auto mb-4 text-gray-300" />
                <p className="text-sm">
                  Hi! I'm your appointment scheduling assistant. How can I help you today?
                </p>
              </div>
            )}

            {messages.map((message, index) => (
              <ChatMessage key={index} message={message} />
            ))}

            {appointmentDetails && (
              <AppointmentConfirmation appointmentDetails={appointmentDetails} />
            )}

            {isLoading && (
              <div className="flex items-center gap-2 text-gray-500">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
                <span className="text-sm">Assistant is typing...</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Suggestions */}
          {messages.length > 0 && !isLoading && (
            <SuggestionButtons
              onSuggestionClick={handleSuggestionClick}
              lastMessage={getLastResponse()}
              apiSuggestions={currentSuggestions}
            />
          )}

          {/* Input */}
          <ChatInput onSendMessage={handleSendMessage} disabled={isLoading} />
        </>
      )}
    </div>
  )
}

