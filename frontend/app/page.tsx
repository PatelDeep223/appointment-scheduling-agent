'use client'

import FloatingChatWidget from '@/components/FloatingChatWidget'
import { Stethoscope, CalendarClock, MessageCircle  } from 'lucide-react'

export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
     
      {/* Hero Section */}
      <div className="container mx-auto px-4 py-16">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-5xl font-bold text-gray-900 mb-6">
            Welcome to HealthCare Plus Clinic
          </h1>
          <p className="text-xl text-gray-600 mb-8">
            Schedule your appointment easily with our intelligent assistant
          </p>
          <div className="grid md:grid-cols-3 gap-6 mt-12">
            <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="flex items-center justify-center">
            <Stethoscope size={40} className="text-primary-600" />
            </div>
              <h3 className="text-lg font-semibold mb-2 center">Expert Care</h3>
              <p className="text-gray-600">
                Experienced medical professionals ready to help
              </p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="flex items-center justify-center">
            <CalendarClock size={40} className="text-green-600" />
            </div>
            <h3 className="text-lg font-semibold mb-2">Flexible Scheduling</h3>
              <p className="text-gray-600">
                Book appointments at your convenience
              </p>
            </div>
            <div className="bg-white p-6 rounded-lg shadow-md">
            <div className="flex items-center justify-center">
            <MessageCircle size={40} className="text-blue-600" />
            </div>
              <h3 className="text-lg font-semibold mb-2">24/7 Assistant</h3>
              <p className="text-gray-600">
                Get answers and schedule anytime
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Floating Chat Widget */}
      <FloatingChatWidget />
    </main>
  )
}

