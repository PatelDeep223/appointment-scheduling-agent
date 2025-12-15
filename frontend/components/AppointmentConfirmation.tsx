'use client'

import { CheckCircle, ExternalLink } from 'lucide-react'

interface AppointmentConfirmationProps {
  appointmentDetails: {
    booking_id?: string
    confirmation_code?: string
    date?: string
    time?: string
    appointment_type?: string
    scheduling_link?: string
    status?: string
    patient_name?: string
    patient_email?: string
    patient_phone?: string
    duration_minutes?: number
    [key: string]: any
  }
}

export default function AppointmentConfirmation({
  appointmentDetails,
}: AppointmentConfirmationProps) {
  if (!appointmentDetails || (!appointmentDetails.booking_id && !appointmentDetails.confirmation_code)) {
    return null
  }

  const isPending = appointmentDetails.status === 'pending' || appointmentDetails.booking_id?.startsWith('TEMP-')
  const title = isPending ? 'Appointment Ready to Book!' : 'Appointment Confirmed!'
  const bgColor = isPending ? 'bg-blue-50 border-blue-200' : 'bg-green-50 border-green-200'
  const textColor = isPending ? 'text-blue-900' : 'text-green-900'
  const iconColor = isPending ? 'text-blue-600' : 'text-green-600'

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
            {appointmentDetails.scheduling_link && (
              <div className="mt-3 pt-3 border-t border-gray-300">
                <a
                  href={appointmentDetails.scheduling_link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`inline-flex items-center gap-2 px-4 py-2 rounded-md font-medium transition-colors ${
                    isPending
                      ? 'bg-blue-600 hover:bg-blue-700 text-white'
                      : 'bg-green-600 hover:bg-green-700 text-white'
                  }`}
                >
                  {isPending ? 'Complete Your Booking' : 'View Appointment'}
                  <ExternalLink size={16} />
                </a>
                {isPending && (
                  <p className="text-xs mt-2 text-gray-600">
                    Your information is already pre-filled. Click the button above to finalize your appointment.
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

