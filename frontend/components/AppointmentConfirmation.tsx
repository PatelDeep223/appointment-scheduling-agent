'use client'

import { useState, useEffect } from 'react'
import { CheckCircle, ExternalLink, Loader2, Sparkles } from 'lucide-react'

interface AppointmentConfirmationProps {
  appointmentDetails: {
    booking_id?: string
    confirmation_code?: string
    date?: string
    time?: string
    appointment_type?: string
    scheduling_link?: string
    cancel_url?: string
    reschedule_url?: string
    status?: string
    patient_name?: string
    patient_email?: string
    patient_phone?: string
    duration_minutes?: number
    [key: string]: any
  }
  onBookingComplete?: () => void
}

export default function AppointmentConfirmation({
  appointmentDetails,
  onBookingComplete,
}: AppointmentConfirmationProps) {
  const [autoOpened, setAutoOpened] = useState(false)
  const [isCompleting, setIsCompleting] = useState(false)

  if (!appointmentDetails || (!appointmentDetails.booking_id && !appointmentDetails.confirmation_code)) {
    return null
  }

  const isPending = appointmentDetails.status === 'pending' || 
                   appointmentDetails.status === 'ready' ||
                   appointmentDetails.booking_id?.startsWith('TEMP-')
  const isConfirmed = appointmentDetails.status === 'confirmed' && 
                      !appointmentDetails.booking_id?.startsWith('TEMP-')
  
  const title = isPending 
    ? 'Appointment Ready to Book!' 
    : isConfirmed 
    ? 'Appointment Confirmed! 🎉' 
    : 'Appointment Confirmed!'
  
  const bgColor = isPending 
    ? 'bg-blue-50 border-blue-200' 
    : 'bg-green-50 border-green-200'
  const textColor = isPending 
    ? 'text-blue-900' 
    : 'text-green-900'
  const iconColor = isPending 
    ? 'text-blue-600' 
    : 'text-green-600'

  // Auto-open scheduling link when booking is ready (only once, optional)
  // Commented out by default - uncomment if you want auto-open
  // useEffect(() => {
  //   if (isPending && 
  //       appointmentDetails.scheduling_link && 
  //       !autoOpened && 
  //       !isCompleting) {
  //     // Small delay to let user see the message
  //     const timer = setTimeout(() => {
  //       if (window.confirm('Your appointment is ready! Would you like to open the booking page now? Your information is already pre-filled.')) {
  //         window.open(appointmentDetails.scheduling_link, '_blank', 'noopener,noreferrer')
  //         setAutoOpened(true)
  //         setIsCompleting(true)
  //       }
  //     }, 2000)
  //     
  //     return () => clearTimeout(timer)
  //   }
  // }, [isPending, appointmentDetails.scheduling_link, autoOpened, isCompleting])

  return (
    <div className={`${bgColor} border rounded-lg p-4 my-4`}>
      <div className="flex items-start gap-3">
        <CheckCircle className={`${iconColor} flex-shrink-0 mt-0.5`} size={20} />
        <div className="flex-1">
          <h4 className={`font-semibold ${textColor} mb-3`}>
            {title}
          </h4>
          <div className="space-y-2 text-sm">
            {appointmentDetails.patient_name && (
              <p className={isPending ? 'text-blue-800' : 'text-green-800'}>
                <strong>Patient:</strong> {appointmentDetails.patient_name}
              </p>
            )}
            {appointmentDetails.patient_email && (
              <p className={isPending ? 'text-blue-800' : 'text-green-800'}>
                <strong>Email:</strong> {appointmentDetails.patient_email}
              </p>
            )}
            {appointmentDetails.patient_phone && (
              <p className={isPending ? 'text-blue-800' : 'text-green-800'}>
                <strong>Phone:</strong> {appointmentDetails.patient_phone}
              </p>
            )}
            {appointmentDetails.appointment_type && (
              <p className={isPending ? 'text-blue-800' : 'text-green-800'}>
                <strong>Type:</strong> {appointmentDetails.appointment_type}
              </p>
            )}
            {appointmentDetails.date && (
              <p className={isPending ? 'text-blue-800' : 'text-green-800'}>
                <strong>Date:</strong> {appointmentDetails.date}
              </p>
            )}
            {appointmentDetails.time && (
              <p className={isPending ? 'text-blue-800' : 'text-green-800'}>
                <strong>Time:</strong> {appointmentDetails.time}
              </p>
            )}
            {appointmentDetails.duration_minutes && (
              <p className={isPending ? 'text-blue-800' : 'text-green-800'}>
                <strong>Duration:</strong> {appointmentDetails.duration_minutes} minutes
              </p>
            )}
            {appointmentDetails.confirmation_code && (
              <p className={isPending ? 'text-blue-800' : 'text-green-800'}>
                <strong>Confirmation Code:</strong> {appointmentDetails.confirmation_code}
              </p>
            )}
            {/* Action buttons section */}
            {(appointmentDetails.scheduling_link || appointmentDetails.cancel_url || appointmentDetails.reschedule_url) && (
              <div className="mt-3 pt-3 border-t border-gray-300 space-y-2">
                {isPending && appointmentDetails.scheduling_link ? (
                  <>
                    <button
                      onClick={() => {
                        if (appointmentDetails.scheduling_link) {
                          setIsCompleting(true)
                          // Open in new window
                          const bookingWindow = window.open(
                            appointmentDetails.scheduling_link, 
                            '_blank', 
                            'noopener,noreferrer'
                          )
                          
                          // Notify parent component to start aggressive polling
                          if (onBookingComplete) {
                            onBookingComplete()
                          }
                          
                          // Optional: Check if window was closed (user might have completed booking)
                          if (bookingWindow) {
                            const checkClosed = setInterval(() => {
                              if (bookingWindow.closed) {
                                clearInterval(checkClosed)
                                // Window closed - user might have completed booking
                                // Polling will handle the confirmation
                              }
                            }, 1000)
                            
                            // Clean up after 5 minutes
                            setTimeout(() => clearInterval(checkClosed), 300000)
                          }
                        }
                      }}
                      disabled={isCompleting}
                      className={`inline-flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors ${
                        isCompleting
                          ? 'bg-blue-400 cursor-not-allowed text-white'
                          : 'bg-blue-600 hover:bg-blue-700 text-white'
                      }`}
                    >
                      {isCompleting ? (
                        <>
                          <Loader2 className="animate-spin" size={16} />
                          <span>Opening Booking Page...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles size={16} />
                          <span>Complete Your Booking</span>
                          <ExternalLink size={16} />
                        </>
                      )}
                    </button>
                    <p className="text-xs mt-2 text-gray-600">
                      {isCompleting 
                        ? 'Complete your booking in the new window. We\'ll automatically confirm it here once you\'re done!'
                        : 'Your information is already pre-filled. Click the button above to finalize your appointment in Calendly.'}
                    </p>
                    {isCompleting && (
                      <div className="mt-2 flex items-center gap-2 text-xs text-blue-700">
                        <Loader2 className="animate-spin" size={14} />
                        <span>Waiting for booking confirmation...</span>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    {/* Confirmed booking actions */}
                    {appointmentDetails.scheduling_link && (
                      <a
                        href={appointmentDetails.scheduling_link}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors bg-green-600 hover:bg-green-700 text-white"
                      >
                        <span>View Appointment</span>
                        <ExternalLink size={16} />
                      </a>
                    )}
                    
                    {/* Cancel and Reschedule buttons for confirmed bookings */}
                    {(appointmentDetails.cancel_url || appointmentDetails.reschedule_url) && (
                      <div className="flex gap-2 mt-2">
                        {appointmentDetails.reschedule_url && (
                          <a
                            href={appointmentDetails.reschedule_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-md font-medium transition-colors bg-yellow-600 hover:bg-yellow-700 text-white text-sm"
                          >
                            <span>Reschedule</span>
                            <ExternalLink size={14} />
                          </a>
                        )}
                        {appointmentDetails.cancel_url && (
                          <a
                            href={appointmentDetails.cancel_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-2 px-3 py-2 rounded-md font-medium transition-colors bg-red-600 hover:bg-red-700 text-white text-sm"
                          >
                            <span>Cancel</span>
                            <ExternalLink size={14} />
                          </a>
                        )}
                      </div>
                    )}
                    
                    {/* Show message for direct bookings (immediately confirmed) */}
                    {isConfirmed && !appointmentDetails.scheduling_link && (
                      <p className="text-xs text-green-700 mt-2">
                        ✅ Your appointment was booked directly and is confirmed!
                      </p>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

