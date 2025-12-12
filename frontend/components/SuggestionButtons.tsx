'use client'

interface SuggestionButtonsProps {
  onSuggestionClick: (suggestion: string) => void
  lastMessage: string
  apiSuggestions?: string[]
}

export default function SuggestionButtons({
  onSuggestionClick,
  lastMessage,
  apiSuggestions = [],
}: SuggestionButtonsProps) {
  // Extract suggestions from the last message or provide default ones
  const extractSuggestions = (message: string): string[] => {
    // Use API suggestions if available
    if (apiSuggestions.length > 0) {
      return apiSuggestions
    }
    // Look for common patterns in assistant responses
    const suggestions: string[] = []

    // Check if message contains appointment type options
    if (message.toLowerCase().includes('consultation') || message.toLowerCase().includes('appointment type')) {
      suggestions.push('General Consultation', 'Follow-up', 'Physical Exam', 'Specialist Consultation')
    }

    // Check if message asks about time preference
    if (message.toLowerCase().includes('morning') || message.toLowerCase().includes('afternoon') || message.toLowerCase().includes('time')) {
      suggestions.push('Morning', 'Afternoon', 'Evening', 'Any time')
    }

    // Check if message asks about date
    if (message.toLowerCase().includes('when') || message.toLowerCase().includes('date') || message.toLowerCase().includes('day')) {
      suggestions.push('Today', 'Tomorrow', 'This week', 'Next week')
    }

    // Default suggestions for greeting
    if (suggestions.length === 0 && message.length < 100) {
      suggestions.push('Book an appointment', 'Check availability', 'What insurance do you accept?', 'What are your hours?')
    }

    return suggestions.slice(0, 4) // Limit to 4 suggestions
  }

  const suggestions = extractSuggestions(lastMessage)

  if (suggestions.length === 0) {
    return null
  }

  return (
    <div className="px-4 pb-2 border-t border-gray-200 bg-gray-50">
      <div className="flex flex-wrap gap-2 pt-3">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            onClick={() => onSuggestionClick(suggestion)}
            className="px-3 py-1.5 text-sm bg-white border border-gray-300 rounded-full hover:bg-primary-50 hover:border-primary-300 hover:text-primary-700 transition-colors"
          >
            {suggestion}
          </button>
        ))}
      </div>
    </div>
  )
}

