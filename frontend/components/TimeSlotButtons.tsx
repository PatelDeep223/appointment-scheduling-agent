'use client'

import { Calendar, Clock } from 'lucide-react'
import { TimeSlot } from '@/lib/api'

interface TimeSlotButtonsProps {
  slots: TimeSlot[]
  onSlotClick: (slot: TimeSlot) => void
}

export default function TimeSlotButtons({ slots, onSlotClick }: TimeSlotButtonsProps) {
  if (!slots || slots.length === 0) {
    return null
  }

  return (
    <div className="px-4 pb-2 border-t border-gray-200 bg-gray-50">
      <div className="pt-3">
        <p className="text-xs text-gray-600 mb-2 font-medium">Available Time Slots:</p>
        <div className="grid grid-cols-1 gap-2">
          {slots.map((slot, index) => (
            <button
              key={index}
              onClick={() => onSlotClick(slot)}
              className="flex items-center gap-3 px-4 py-3 bg-white text-left border border-gray-300 rounded-lg hover:bg-primary-50 hover:border-primary-400 hover:text-primary-700 transition-all duration-200 shadow-sm hover:shadow-md"
            >
              <div className="flex-shrink-0">
                <Calendar size={18} className="text-primary-600" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-sm text-primary-600">{slot.display_text}</span>
                </div>
                {slot.date && slot.start_time && (
                  <p className="text-xs text-gray-500 mt-0.5">
                    {slot.date} • {slot.start_time}
                  </p>
                )}
              </div>
              <div className="flex-shrink-0">
                <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full font-medium">
                  Available
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

