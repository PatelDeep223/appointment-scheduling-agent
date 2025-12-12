'use client'

import { CheckCircle } from 'lucide-react'

interface AppointmentConfirmationProps {
  appointmentDetails: {
    booking_id?: string
    confirmation_code?: string
    date?: string
    time?: string
    appointment_type?: string
    [key: string]: any
  }
}

export default function AppointmentConfirmation({
  appointmentDetails,
}: AppointmentConfirmationProps) {
  if (!appointmentDetails || !appointmentDetails.booking_id) {
    return null
  }

  return (
    <div className="bg-green-50 border border-green-200 rounded-lg p-4 my-4">
      <div className="flex items-start gap-3">
        <CheckCircle className="text-green-600 flex-shrink-0 mt-0.5" size={20} />
        <div className="flex-1">
          <h4 className="font-semibold text-green-900 mb-2">
            Appointment Confirmed!
          </h4>
          <div className="space-y-1 text-sm text-green-800">
            {appointmentDetails.confirmation_code && (
              <p>
                <strong>Confirmation Code:</strong> {appointmentDetails.confirmation_code}
              </p>
            )}
            {appointmentDetails.date && (
              <p>
                <strong>Date:</strong> {new Date(appointmentDetails.date).toLocaleDateString()}
              </p>
            )}
            {appointmentDetails.time && (
              <p>
                <strong>Time:</strong> {appointmentDetails.time}
              </p>
            )}
            {appointmentDetails.appointment_type && (
              <p>
                <strong>Type:</strong> {appointmentDetails.appointment_type}
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

