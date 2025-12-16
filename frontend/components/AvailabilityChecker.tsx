'use client'

import { useState } from 'react'
import { Calendar, Clock, Search, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'
import DatePicker from './DatePicker'
import { apiService, AvailabilityResponse, AvailabilitySlot } from '@/lib/api'
import TimeSlotButtons from './TimeSlotButtons'
import { TimeSlot } from '@/lib/api'

interface AvailabilityCheckerProps {
  onSlotSelect?: (slot: TimeSlot) => void
}

const APPOINTMENT_TYPES = [
  { value: 'consultation', label: 'Consultation' },
  { value: 'followup', label: 'Follow-up' },
  { value: 'physical', label: 'Physical Exam' },
  { value: 'specialist', label: 'Specialist Visit' },
]

const TIME_PREFERENCES = [
  { value: '', label: 'Any Time' },
  { value: 'morning', label: 'Morning (6 AM - 12 PM)' },
  { value: 'afternoon', label: 'Afternoon (12 PM - 5 PM)' },
  { value: 'evening', label: 'Evening (5 PM - 9 PM)' },
]

export default function AvailabilityChecker({ onSlotSelect }: AvailabilityCheckerProps) {
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [appointmentType, setAppointmentType] = useState<string>('consultation')
  const [timePreference, setTimePreference] = useState<string>('')
  const [isLoading, setIsLoading] = useState(false)
  const [availability, setAvailability] = useState<AvailabilityResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleCheckAvailability = async () => {
    if (!selectedDate) {
      setError('Please select a date')
      return
    }

    setIsLoading(true)
    setError(null)
    setAvailability(null)

    try {
      // Try Calendly API endpoint first, fallback to regular availability endpoint
      let response: AvailabilityResponse
      
      try {
        // Use Calendly availability API (direct Calendly API call)
        const calendlyResponse = await apiService.getCalendlyAvailability(
          selectedDate,
          appointmentType
        )
        
        // Transform Calendly response to AvailabilityResponse format
        response = {
          date: calendlyResponse.date,
          appointment_type: appointmentType,
          available_slots: calendlyResponse.available_slots.map(slot => ({
            start_time: slot.start_time,
            end_time: slot.end_time,
            available: slot.available,
            raw_time: slot.start_time // Use start_time as raw_time
          }))
        }
      } catch (calendlyError: any) {
        console.warn('Calendly availability API failed, falling back to regular endpoint:', calendlyError)
        // Fallback to regular availability endpoint
        response = await apiService.getAvailability(
          selectedDate,
          appointmentType,
          timePreference || undefined
        )
      }
      
      setAvailability(response)
    } catch (err: any) {
      setError(err.message || 'Failed to check availability')
      setAvailability(null)
    } finally {
      setIsLoading(false)
    }
  }

  // Convert AvailabilitySlot to TimeSlot format for TimeSlotButtons
  const convertToTimeSlots = (slots: AvailabilitySlot[]): TimeSlot[] => {
    if (!selectedDate || !availability) return []

    return slots
      .filter(slot => slot.available)
      .map(slot => {
        const date = new Date(selectedDate)
        const [hours, minutes] = slot.raw_time
          ? slot.raw_time.split(':').map(Number)
          : slot.start_time.match(/\d{1,2}/g)?.map(Number) || [9, 0]

        const startDate = new Date(date)
        startDate.setHours(hours, minutes || 0, 0, 0)

        const endDate = new Date(startDate)
        const duration = availability.duration_minutes || 30
        endDate.setMinutes(endDate.getMinutes() + duration)

        const formatTime = (d: Date) => {
          return d.toLocaleTimeString('en-US', {
            hour: 'numeric',
            minute: '2-digit',
            hour12: true,
          })
        }

        const formatDate = (d: Date) => {
          return d.toLocaleDateString('en-US', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          })
        }

        return {
          date: selectedDate,
          full_date: formatDate(date),
          start_time: formatTime(startDate),
          end_time: formatTime(endDate),
          raw_time: slot.raw_time || `${hours.toString().padStart(2, '0')}:${(minutes || 0).toString().padStart(2, '0')}`,
          display_text: `${formatTime(startDate)} - ${formatTime(endDate)}`,
          available: slot.available,
        }
      })
  }

  const handleSlotClick = (slot: TimeSlot) => {
    if (onSlotSelect) {
      onSlotSelect(slot)
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-4">
      <div className="flex items-center gap-2 mb-4">
        <Calendar className="text-primary-600" size={20} />
        <h3 className="text-lg font-semibold text-gray-900">Check Availability</h3>
      </div>

      {/* Date Picker */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Select Date
        </label>
        <DatePicker
          selectedDate={selectedDate}
          onDateSelect={setSelectedDate}
        />
      </div>

      {/* Appointment Type */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Appointment Type
        </label>
        <select
          value={appointmentType}
          onChange={(e) => setAppointmentType(e.target.value)}
          className="w-full px-4 py-2.5 bg-white text-black border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          {APPOINTMENT_TYPES.map((type) => (
            <option key={type.value} value={type.value}>
              {type.label}
            </option>
          ))}
        </select>
      </div>

      {/* Time Preference (Optional) */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Time Preference <span className="text-gray-500 text-xs">(Optional)</span>
        </label>
        <select
          value={timePreference}
          onChange={(e) => setTimePreference(e.target.value)}
          className="w-full px-4 py-2.5 bg-white border text-black border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        >
          {TIME_PREFERENCES.map((pref) => (
            <option key={pref.value} value={pref.value}>
              {pref.label}
            </option>
          ))}
        </select>
      </div>

      {/* Check Button */}
      <button
        onClick={handleCheckAvailability}
        disabled={!selectedDate || isLoading}
        className="w-full px-4 py-3 bg-primary-600 text-white rounded-lg font-medium hover:bg-primary-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
      >
        {isLoading ? (
          <>
            <Loader2 className="animate-spin" size={18} />
            <span>Checking...</span>
          </>
        ) : (
          <>
            <Search size={18} />
            <span>Check Availability</span>
          </>
        )}
      </button>

      {/* Error Message */}
      {error && (
        <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
          <AlertCircle className="text-red-600 flex-shrink-0 mt-0.5" size={18} />
          <p className="text-sm text-red-800">{error}</p>
        </div>
      )}

      {/* Availability Results */}
      {availability && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          {availability.message && (
            <div className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 rounded-lg mb-4">
              <AlertCircle className="text-blue-600 flex-shrink-0 mt-0.5" size={18} />
              <p className="text-sm text-blue-800">{availability.message}</p>
            </div>
          )}

          {availability.available_slots && availability.available_slots.length > 0 ? (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <CheckCircle2 className="text-green-600" size={18} />
                <p className="text-sm font-medium text-gray-900">
                  {availability.available_slots.filter(s => s.available).length} available slot
                  {availability.available_slots.filter(s => s.available).length !== 1 ? 's' : ''} found
                </p>
              </div>

              <div className="space-y-2">
                {availability.available_slots
                  .filter(slot => slot.available)
                  .map((slot, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between p-3 bg-gray-50 border border-gray-200 rounded-lg"
                    >
                      <div className="flex items-center gap-2">
                        <Clock className="text-primary-600" size={16} />
                        <span className="text-sm font-medium text-gray-900">
                          {slot.start_time} - {slot.end_time}
                        </span>
                      </div>
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium">
                        Available
                      </span>
                    </div>
                  ))}
              </div>

              {/* Time Slot Buttons (if onSlotSelect is provided) */}
              {onSlotSelect && (
                <div className="mt-4">
                  <TimeSlotButtons
                    slots={convertToTimeSlots(availability.available_slots)}
                    onSlotClick={handleSlotClick}
                  />
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-start gap-2 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <AlertCircle className="text-yellow-600 flex-shrink-0 mt-0.5" size={18} />
              <p className="text-sm text-yellow-800">
                No available slots found for this date. Please try another date or appointment type.
              </p>
            </div>
          )}

          {/* Appointment Type Info */}
          {availability.appointment_type && (
            <div className="mt-3 pt-3 border-t border-gray-200">
              <p className="text-xs text-gray-500">
                Showing availability for: <span className="font-medium">{availability.appointment_type}</span>
                {availability.duration_minutes && (
                  <span> ({availability.duration_minutes} minutes)</span>
                )}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

