'use client'

import { useState, useRef, useEffect, forwardRef, useImperativeHandle } from 'react'
import { MessageCircle, X, Send, Minimize2 } from 'lucide-react'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
// SuggestionButtons removed - using natural LLM conversation instead
import AppointmentConfirmation from './AppointmentConfirmation'
import TimeSlotButtons from './TimeSlotButtons'
import { apiService, ChatMessage as ChatMessageType, TimeSlot } from '@/lib/api'

export interface FloatingChatWidgetRef {
  sendMessage: (message: string) => void
}

const FloatingChatWidget = forwardRef<FloatingChatWidgetRef>((props, ref) => {
  const [isOpen, setIsOpen] = useState(false)
  const [isMinimized, setIsMinimized] = useState(false)
  const [messages, setMessages] = useState<ChatMessageType[]>([])
  const [isLoading, setIsLoading] = useState(false)
  // Suggestions removed - using natural LLM conversation
  const [appointmentDetails, setAppointmentDetails] = useState<any>(null)
  const [availableSlots, setAvailableSlots] = useState<TimeSlot[]>([])
  const [sessionId] = useState(() => `session-${Date.now()}`)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const chatContainerRef = useRef<HTMLDivElement>(null)
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const [isWaitingForConfirmation, setIsWaitingForConfirmation] = useState(false)

  // Poll for booking status updates if there's a pending booking
  useEffect(() => {
    const checkBookingStatus = async () => {
      if (!appointmentDetails?.booking_id) return
      
      const isPending = appointmentDetails.status === 'pending' || 
                       appointmentDetails.status === 'ready' ||
                       appointmentDetails.booking_id?.startsWith('TEMP-')
      
      if (!isPending && !isWaitingForConfirmation) {
        // Booking is confirmed, stop polling
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current)
          pollingIntervalRef.current = null
        }
        return
      }

      try {
        console.log(`[Polling] Checking status for booking: ${appointmentDetails.booking_id}`)
        const updatedBooking = await apiService.getAppointmentStatus(appointmentDetails.booking_id)
        
        if (!updatedBooking) {
          console.warn('[Polling] No booking data returned')
          return
        }
        
        // Update if status changed from pending to confirmed
        const wasPending = appointmentDetails.status === 'pending' || 
                          appointmentDetails.status === 'ready' ||
                          appointmentDetails.booking_id?.startsWith('TEMP-')
        const isNowConfirmed = updatedBooking && 
                               updatedBooking.status === 'confirmed' && 
                               !updatedBooking.booking_id?.startsWith('TEMP-')
        
        // Check if this is a direct booking (immediately confirmed, no scheduling_link)
        const isDirectBooking = isNowConfirmed && !updatedBooking.scheduling_link
        
        if (wasPending && isNowConfirmed) {
          // Booking just got confirmed!
          setAppointmentDetails(updatedBooking)
          setIsWaitingForConfirmation(false)
          console.log('✅ Booking confirmed!', updatedBooking)
          
          // Show success message
          const bookingMethod = isDirectBooking 
            ? 'Your appointment was booked directly and is confirmed!'
            : 'Your appointment has been confirmed!'
          
          const successMessage: ChatMessageType = {
            role: 'assistant',
            content: `🎉 Great news! ${bookingMethod}\n\nYour booking details:\n• Date: ${updatedBooking.date || appointmentDetails.date}\n• Time: ${updatedBooking.time || appointmentDetails.time}\n• Confirmation Code: ${updatedBooking.confirmation_code || appointmentDetails.confirmation_code}\n\nYou should receive a confirmation email shortly.${isDirectBooking && (updatedBooking.cancel_url || updatedBooking.reschedule_url) ? '\n\nYou can reschedule or cancel your appointment using the buttons below.' : ''}`,
            timestamp: new Date().toISOString(),
          }
          setMessages((prev) => [...prev, successMessage])
          
          // Stop polling
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current)
            pollingIntervalRef.current = null
          }
        } else if (updatedBooking && updatedBooking.status !== appointmentDetails.status) {
          // Status changed (e.g., pending -> confirmed)
          console.log(`📊 Booking status changed: ${appointmentDetails.status} → ${updatedBooking.status}`)
          setAppointmentDetails(updatedBooking)
          
          // If it became confirmed, show success message
          if (updatedBooking.status === 'confirmed' && appointmentDetails.status === 'pending') {
            const successMessage: ChatMessageType = {
              role: 'assistant',
              content: `🎉 Great news! Your appointment has been confirmed!\n\nYour booking details:\n• Date: ${updatedBooking.date || appointmentDetails.date}\n• Time: ${updatedBooking.time || appointmentDetails.time}\n• Confirmation Code: ${updatedBooking.confirmation_code || appointmentDetails.confirmation_code}\n\nYou should receive a confirmation email shortly.`,
              timestamp: new Date().toISOString(),
            }
            setMessages((prev) => [...prev, successMessage])
            setIsWaitingForConfirmation(false)
            
            // Stop polling
            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current)
              pollingIntervalRef.current = null
            }
          }
        } else {
          // Status hasn't changed, just log for debugging
          console.log(`📊 Booking status unchanged: ${updatedBooking.status} (still ${appointmentDetails.status === 'pending' ? 'waiting for confirmation' : 'confirmed'})`)
        }
      } catch (error) {
        // Silently fail - booking might not exist yet or webhook hasn't arrived
        console.debug('Polling booking status:', error)
      }
    }

    // Determine polling interval based on whether user is actively completing booking
    const pollInterval = isWaitingForConfirmation ? 3000 : 5000 // Poll every 3s if waiting, 5s otherwise

    // Poll for pending bookings
    if (appointmentDetails?.booking_id) {
      const isPending = appointmentDetails.status === 'pending' || 
                       appointmentDetails.status === 'ready' ||
                       appointmentDetails.booking_id?.startsWith('TEMP-')
      
      if (isPending || isWaitingForConfirmation) {
        // Initial check after 2 seconds (faster if waiting)
        const initialDelay = isWaitingForConfirmation ? 2000 : 3000
        const initialTimeout = setTimeout(checkBookingStatus, initialDelay)
        
        // Then poll at appropriate interval
        pollingIntervalRef.current = setInterval(checkBookingStatus, pollInterval)
        
        return () => {
          clearTimeout(initialTimeout)
          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current)
            pollingIntervalRef.current = null
          }
        }
      }
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [appointmentDetails?.booking_id, appointmentDetails?.status, isWaitingForConfirmation])

  const handleSendMessage = async (message: string) => {
    if (!message.trim() || isLoading) return

    // Ensure chat is open when sending message
    if (!isOpen) {
      setIsOpen(true)
      setIsMinimized(false)
    }

    // Add user message
    const userMessage: ChatMessageType = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMessage])
    setIsLoading(true)

    try {
      // Get user timezone and send with message
      const userTimezone = apiService.getUserTimezone()
      const response = await apiService.sendMessage(message, sessionId, userTimezone)

      // Add assistant message
      const assistantMessage: ChatMessageType = {
        role: 'assistant',
        content: response.message,
        timestamp: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, assistantMessage])

      // Update appointment details and available slots (suggestions removed)
      setAppointmentDetails(response.appointment_details || null)
      setAvailableSlots(response.available_slots || [])
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

  // Expose sendMessage method via ref
  useImperativeHandle(ref, () => ({
    sendMessage: handleSendMessage,
  }))

  // Suggestion click handler removed - using natural conversation

  const handleSlotClick = (slot: TimeSlot) => {
    // Send the slot's display text as the selection
    handleSendMessage(slot.display_text)
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
              <AppointmentConfirmation 
                appointmentDetails={appointmentDetails}
                onBookingComplete={() => {
                  // Start aggressive polling when user opens booking page
                  setIsWaitingForConfirmation(true)
                  
                  // Also refresh booking status immediately
                  if (appointmentDetails.booking_id) {
                    apiService.getAppointmentStatus(appointmentDetails.booking_id)
                      .then(updated => {
                        if (updated) {
                          setAppointmentDetails(updated)
                        }
                      })
                      .catch(err => console.debug('Error refreshing booking:', err))
                  }
                }}
              />
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

          {/* Time Slot Buttons - Show clickable slots when available */}
          {availableSlots.length > 0 && !isLoading && (
            <TimeSlotButtons
              slots={availableSlots}
              onSlotClick={handleSlotClick}
            />
          )}

          {/* Suggestions removed - using natural LLM conversation */}

          {/* Input */}
          <ChatInput onSendMessage={handleSendMessage} disabled={isLoading} />
        </>
      )}
    </div>
  )
})

FloatingChatWidget.displayName = 'FloatingChatWidget'

export default FloatingChatWidget

