'use client'

import { useEffect, useState } from 'react'
import { CheckCircle, XCircle, Loader2 } from 'lucide-react'

export default function ApiStatus() {
  const [status, setStatus] = useState<'checking' | 'connected' | 'error'>('checking')
  const [apiUrl, setApiUrl] = useState<string>('')

  useEffect(() => {
    const checkApi = async () => {
      const url = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const cleanUrl = url.replace(/\/+$/, '')
      setApiUrl(cleanUrl)

      try {
        const response = await fetch(`${cleanUrl}/`)
        if (response.ok) {
          setStatus('connected')
        } else {
          setStatus('error')
        }
      } catch (error) {
        setStatus('error')
      }
    }

    checkApi()
  }, [])

  if (status === 'checking') {
    return (
      <div className="fixed top-4 left-4 bg-white p-3 rounded-lg shadow-md border border-gray-200 flex items-center gap-2 text-sm">
        <Loader2 className="animate-spin text-gray-400" size={16} />
        <span className="text-gray-600">Checking API connection...</span>
      </div>
    )
  }

  return (
    <div
      className={`fixed top-4 left-4 p-3 rounded-lg shadow-md border flex items-center gap-2 text-sm ${
        status === 'connected'
          ? 'bg-green-50 border-green-200 text-green-800'
          : 'bg-red-50 border-red-200 text-red-800'
      }`}
    >
      {status === 'connected' ? (
        <>
          <CheckCircle size={16} />
          <span>API Connected: {apiUrl}</span>
        </>
      ) : (
        <>
          <XCircle size={16} />
          <span>API Error: Cannot reach {apiUrl}</span>
        </>
      )}
    </div>
  )
}

