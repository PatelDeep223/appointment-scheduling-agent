'use client'

import { ChatMessage as ChatMessageType } from '@/lib/api'
import { User, Bot } from 'lucide-react'

interface ChatMessageProps {
  message: ChatMessageType
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}>
      {!isUser && (
        <div className="flex-shrink-0 w-8 h-8 bg-primary-100 rounded-full flex items-center justify-center">
          <Bot size={18} className="text-primary-600" />
        </div>
      )}

      <div
        className={`max-w-[80%] rounded-lg px-4 py-2 ${
          isUser
            ? 'bg-primary-600 text-white'
            : 'bg-white text-gray-800 border border-gray-200'
        }`}
      >
        <p className="text-sm whitespace-pre-wrap break-words">
          {message.content}
        </p>
        {message.timestamp && (
          <p
            className={`text-xs mt-1 ${
              isUser ? 'text-primary-100' : 'text-gray-500'
            }`}
          >
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </p>
        )}
      </div>

      {isUser && (
        <div className="flex-shrink-0 w-8 h-8 bg-primary-600 rounded-full flex items-center justify-center">
          <User size={18} className="text-white" />
        </div>
      )}
    </div>
  )
}

