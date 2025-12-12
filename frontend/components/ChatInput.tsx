'use client'

import { useState, KeyboardEvent, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'

interface ChatInputProps {
  onSendMessage: (message: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSendMessage, disabled }: ChatInputProps) {
  const [message, setMessage] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = '44px'
      const scrollHeight = textareaRef.current.scrollHeight
      if (scrollHeight > 44) {
        textareaRef.current.style.height = `${Math.min(scrollHeight, 120)}px`
      }
    }
  }, [message])

  const handleSend = () => {
    if (message.trim() && !disabled) {
      onSendMessage(message.trim())
      setMessage('')
      if (textareaRef.current) {
        textareaRef.current.style.height = '44px'
      }
    }
  }

  const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="border-t border-gray-200 p-4 bg-white">
      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type your message..."
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none border text-black border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed overflow-y-auto"
          style={{ minHeight: '44px', maxHeight: '120px' }}
        />
        <button
          onClick={handleSend}
          disabled={disabled || !message.trim()}
          className="bg-primary-600 hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white p-3 rounded-lg transition-colors flex items-center justify-center"
          aria-label="Send message"
        >
          <Send size={20} />
        </button>
      </div>
      <p className="text-xs text-gray-500 mt-2">
        Press Enter to send, Shift+Enter for new line
      </p>
    </div>
  )
}

