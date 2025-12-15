'use client'

import { useState, useEffect } from 'react'
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react'

interface DatePickerProps {
  selectedDate: string | null
  onDateSelect: (date: string) => void
  minDate?: string // YYYY-MM-DD format
  maxDate?: string // YYYY-MM-DD format
}

export default function DatePicker({
  selectedDate,
  onDateSelect,
  minDate,
  maxDate,
}: DatePickerProps) {
  const [currentMonth, setCurrentMonth] = useState(new Date())
  const [isOpen, setIsOpen] = useState(false)

  // Get today's date in YYYY-MM-DD format
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const todayStr = today.toISOString().split('T')[0]

  // Default min date to today if not provided
  const minDateStr = minDate || todayStr
  const maxDateStr = maxDate || (() => {
    const max = new Date()
    max.setMonth(max.getMonth() + 3) // 3 months ahead
    return max.toISOString().split('T')[0]
  })()

  // Get first day of current month and number of days
  const firstDayOfMonth = new Date(
    currentMonth.getFullYear(),
    currentMonth.getMonth(),
    1
  )
  const lastDayOfMonth = new Date(
    currentMonth.getFullYear(),
    currentMonth.getMonth() + 1,
    0
  )
  const daysInMonth = lastDayOfMonth.getDate()
  const startingDayOfWeek = firstDayOfMonth.getDay()

  // Generate calendar days
  const days: (number | null)[] = []
  
  // Add empty cells for days before month starts
  for (let i = 0; i < startingDayOfWeek; i++) {
    days.push(null)
  }
  
  // Add days of the month
  for (let day = 1; day <= daysInMonth; day++) {
    days.push(day)
  }

  const formatDate = (date: Date): string => {
    return date.toISOString().split('T')[0]
  }

  const formatDisplayDate = (dateStr: string): string => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }

  const isDateDisabled = (day: number): boolean => {
    const date = new Date(
      currentMonth.getFullYear(),
      currentMonth.getMonth(),
      day
    )
    const dateStr = formatDate(date)
    return dateStr < minDateStr || dateStr > maxDateStr
  }

  const isDateSelected = (day: number): boolean => {
    if (!selectedDate) return false
    const date = new Date(
      currentMonth.getFullYear(),
      currentMonth.getMonth(),
      day
    )
    return formatDate(date) === selectedDate
  }

  const handleDateClick = (day: number) => {
    const date = new Date(
      currentMonth.getFullYear(),
      currentMonth.getMonth(),
      day
    )
    const dateStr = formatDate(date)
    if (!isDateDisabled(day)) {
      onDateSelect(dateStr)
      setIsOpen(false)
    }
  }

  const goToPreviousMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1))
  }

  const goToNextMonth = () => {
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1))
  }

  const monthName = currentMonth.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })

  return (
    <div className="relative">
      {/* Date Input Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-2.5 bg-white border border-gray-300 rounded-lg text-left flex items-center justify-between hover:border-primary-400 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
      >
        <div className="flex items-center gap-2">
          <Calendar size={18} className="text-gray-500" />
          <span className={selectedDate ? 'text-gray-900' : 'text-gray-500'}>
            {selectedDate ? formatDisplayDate(selectedDate) : 'Select a date'}
          </span>
        </div>
        <ChevronRight
          size={18}
          className={`text-gray-400 transition-transform ${isOpen ? 'rotate-90' : ''}`}
        />
      </button>

      {/* Calendar Dropdown */}
      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute top-full left-0 mt-2 bg-white border border-gray-200 rounded-lg shadow-lg p-4 z-20 w-80">
            {/* Calendar Header */}
            <div className="flex items-center justify-between mb-4">
              <button
                type="button"
                onClick={goToPreviousMonth}
                className="p-1 hover:bg-gray-100 rounded transition-colors"
                aria-label="Previous month"
              >
                <ChevronLeft size={20} className="text-gray-600" />
              </button>
              <h3 className="text-lg font-semibold text-gray-900">{monthName}</h3>
              <button
                type="button"
                onClick={goToNextMonth}
                className="p-1 hover:bg-gray-100 rounded transition-colors"
                aria-label="Next month"
              >
                <ChevronRight size={20} className="text-gray-600" />
              </button>
            </div>

            {/* Day Names */}
            <div className="grid grid-cols-7 gap-1 mb-2">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) => (
                <div
                  key={day}
                  className="text-center text-xs font-medium text-gray-500 py-1"
                >
                  {day}
                </div>
              ))}
            </div>

            {/* Calendar Days */}
            <div className="grid grid-cols-7 gap-1">
              {days.map((day, index) => {
                if (day === null) {
                  return <div key={index} />
                }

                const isDisabled = isDateDisabled(day)
                const isSelected = isDateSelected(day)
                const isToday = (() => {
                  const date = new Date(
                    currentMonth.getFullYear(),
                    currentMonth.getMonth(),
                    day
                  )
                  return formatDate(date) === todayStr
                })()

                return (
                  <button
                    key={index}
                    type="button"
                    onClick={() => handleDateClick(day)}
                    disabled={isDisabled}
                    className={`
                      aspect-square flex items-center justify-center text-sm rounded transition-colors
                      ${isDisabled
                        ? 'text-gray-300 cursor-not-allowed'
                        : isSelected
                        ? 'bg-primary-600 text-white font-semibold hover:bg-primary-700'
                        : isToday
                        ? 'bg-primary-100 text-primary-700 font-medium hover:bg-primary-200'
                        : 'text-gray-700 hover:bg-gray-100'
                      }
                    `}
                  >
                    {day}
                  </button>
                )
              })}
            </div>

            {/* Quick Actions */}
            <div className="mt-4 pt-4 border-t border-gray-200 flex gap-2">
              <button
                type="button"
                onClick={() => {
                  onDateSelect(todayStr)
                  setIsOpen(false)
                }}
                className="flex-1 px-3 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 rounded text-gray-700 transition-colors"
              >
                Today
              </button>
              <button
                type="button"
                onClick={() => {
                  const tomorrow = new Date(today)
                  tomorrow.setDate(tomorrow.getDate() + 1)
                  onDateSelect(tomorrow.toISOString().split('T')[0])
                  setIsOpen(false)
                }}
                className="flex-1 px-3 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 rounded text-gray-700 transition-colors"
              >
                Tomorrow
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

