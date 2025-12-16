# Medical Appointment Scheduling Agent

An intelligent conversational AI agent that helps patients schedule medical appointments through Calendly integration. The agent understands available time slots, asks relevant questions, answers FAQs using RAG (Retrieval-Augmented Generation), and handles scheduling intelligently.

## 🚀 Features

- **Intelligent Conversation Flow**: Natural, empathetic conversation that understands patient needs
- **Calendly Integration**: Fetches available time slots and creates appointments dynamically
- **RAG-based FAQ System**: Answers frequently asked questions using vector search
- **Context Switching**: Seamlessly switches between scheduling and FAQ answering
- **Smart Slot Recommendations**: Suggests optimal appointment times based on preferences
- **Multiple Appointment Types**: Handles consultations, follow-ups, physical exams, and specialist visits
- **Edge Case Handling**: Gracefully handles no available slots, API failures, and ambiguous inputs

## 📋 Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **LLM**: OpenAI GPT-4 Turbo (configurable - supports OpenAI, Anthropic, Llama, Mistral)
- **Vector Database**: ChromaDB (configurable - supports Pinecone, Weaviate, Qdrant)
- **Calendar API**: Calendly API (with mock implementation for development)
- **Frontend**: React with chat interface (optional)

## 🛠️ Setup Instructions

### Prerequisites

- Python 3.10 or higher
- pip package manager
- (Optional) Node.js and npm for frontend

### 1. Clone the Repository

```bash
git clone <repository-url>
cd appointment-scheduling-agent
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` and configure:

```env
# LLM Configuration (Required)
OPENAI_API_KEY=your_openai_api_key_here

# Calendly (Optional - leave empty to use mock)
CALENDLY_API_KEY=your_calendly_api_key
CALENDLY_USER_URL=https://calendly.com/your-username

# Vector Database (Optional - defaults to ChromaDB)
VECTOR_DB_PATH=./data/vectordb

# Clinic Configuration
CLINIC_NAME=HealthCare Plus Clinic
CLINIC_PHONE=+1-555-123-4567
TIMEZONE=America/New_York
```

### 5. Calendly API Setup (Optional)

If using the real Calendly API:

1. Sign up for a free Calendly account at https://calendly.com
2. Go to Integrations → API & Webhooks
3. Generate a Personal Access Token
4. Add the token to `.env` as `CALENDLY_API_KEY`
5. Set your Calendly user URL in `CALENDLY_USER_URL`

**Note**: The system works with a mock Calendly implementation by default. No API key is required for basic functionality.

### 6. Initialize Vector Database

The vector database will be automatically initialized on first run. The FAQ knowledge base is built from `data/clinic_info.json`.

### 7. Run the Application

```bash
cd backend
python main.py
```

Or using uvicorn directly:

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### 8. API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📁 Project Structure

```
appointment-scheduling-agent/
├── README.md 
├── requirements.txt 
├── architecture_diagram.pdf 
├── backend/
│   ├── main.py 
│   ├── agent/
│   │   ├── scheduling_agent.py 
│   │   ├── prompts.py 
│   │   └── llm_service.py 
│   ├── rag/
│   │   ├── faq_rag.py 
│   │   ├── embeddings.py
│   │   └── vector_store.py 
│   ├── api/
│   │   ├── chat.py 
│   │   └── calendly_integration.py 
│   ├── tools/
│   │   ├── availability_tool.py 
│   │   └── booking_tool.py 
│   ├── models/
│   │   └── schemas.py 
│   ├── services/ 
│   ├── database.py 
│   └── scripts/ 
├── data/
│   ├── clinic_info.json 
│   └── doctor_schedule.json 
├── frontend/ 
└── tests/ 
```

## 🎯 System Design

### Agent Conversation Flow

The scheduling agent follows a structured conversation flow:

1. **Greeting Phase**: Welcomes patient and identifies intent
2. **Understanding Needs**: Determines reason for visit and appointment type
3. **Time Preference**: Collects preferred date/time preferences
4. **Slot Recommendation**: Shows 3-5 available slots based on preferences
5. **Patient Information**: Collects name, email, phone, and reason
6. **Confirmation**: Books appointment and provides confirmation details

The agent can seamlessly switch to FAQ answering at any point and return to scheduling context.

### Calendly Integration Approach

The system supports both real Calendly API and mock implementation:

- **Mock Mode** (Default): No API key required, generates realistic availability
- **Real API Mode**: Full Calendly integration for production use

The `CalendlyClient` class automatically detects which mode to use based on environment variables.

### RAG Pipeline for FAQs

1. **Knowledge Base Building**: FAQ data from `clinic_info.json` is chunked and embedded
2. **Vector Storage**: Embeddings stored in ChromaDB for fast similarity search
3. **Query Processing**: User questions are embedded and searched against knowledge base
4. **Answer Generation**: Most relevant chunks are retrieved and formatted as answers

### Tool Calling Strategy

The agent uses specialized tools:

- **AvailabilityTool**: Checks and filters available appointment slots
- **BookingTool**: Creates, cancels, and validates bookings
- **FAQRetriever**: Searches and retrieves FAQ answers

### Context Switching Mechanism

The agent maintains conversation context and can:

- Answer FAQ questions mid-booking and return to scheduling
- Handle multiple FAQs while preserving booking state
- Transition from FAQ to scheduling seamlessly

## 📅 Scheduling Logic

### How Available Slots are Determined

1. **Business Hours**: Respects clinic working hours from `doctor_schedule.json`
2. **Existing Appointments**: Excludes already-booked time slots
3. **Appointment Duration**: Matches slot duration to appointment type
   - General Consultation: 30 minutes
   - Follow-up: 15 minutes
   - Physical Exam: 45 minutes
   - Specialist Consultation: 60 minutes
4. **Time Preferences**: Filters by morning/afternoon preferences
5. **Buffer Time**: Accounts for travel and preparation time

### Appointment Type Handling

The system automatically maps patient descriptions to appointment types:

- Headaches, symptoms → General Consultation
- Follow-up, checkup → Follow-up
- Physical, exam → Physical Exam
- Specialist, cardio, derm → Specialist Consultation

### Conflict Prevention

- Real-time availability checking before booking
- Validation of date/time constraints
- Prevents double-booking through mock storage or Calendly API

## 🧪 Testing

### Example Conversations

#### Successful Booking

```
User: I need to see the doctor
Agent: I'd be happy to help you schedule an appointment! What's the main reason for your visit today?

User: I've been having headaches
Agent: I understand. For persistent headaches, I'd recommend a general consultation (30 minutes)...

User: General consultation is fine
Agent: Perfect. When would you like to come in? Do you have a preference for morning or afternoon appointments?

[... continues to booking confirmation]
```

#### FAQ During Booking

```
User: I want to book an appointment
Agent: I'd be happy to help! What brings you in today?

User: Actually, first - what insurance do you accept?
Agent: Great question! We accept most major insurance providers including Blue Cross Blue Shield...

User: Yes, I have Blue Cross. Okay, I'd like to schedule a checkup
Agent: Perfect, we accept Blue Cross Blue Shield. Now for your checkup...
```

#### No Available Slots

```
User: Can I see the doctor today?
Agent: I understand you'd like to be seen today. Unfortunately, we don't have any available appointments for today. However, I have several options for tomorrow...
```

### Edge Cases Covered

- ✅ No available slots → Offers alternatives
- ✅ API failures → Graceful error handling
- ✅ Ambiguous time references → Clarification questions
- ✅ Invalid dates/times → Validation and correction
- ✅ User changes mind → Graceful restart
- ✅ Missing patient info → Progressive collection

## 📡 API Endpoints

### POST `/api/chat`
Main chat endpoint for conversational interaction.

**Request:**
```json
{
  "message": "I need an appointment",
  "session_id": "user-123"
}
```

**Response:**
```json
{
  "message": "I'd be happy to help you schedule an appointment!...",
  "context": "collecting_reason",
  "suggestions": ["I have a headache", "Annual checkup"],
  "appointment_details": null
}
```

### GET `/api/availability`
Get available time slots for a date.

**Query Parameters:**
- `date`: YYYY-MM-DD format
- `appointment_type`: consultation, followup, physical, specialist

### POST `/api/book`
Book an appointment directly.

**Request:**
```json
{
  "appointment_type": "consultation",
  "date": "2024-01-15",
  "start_time": "10:00",
  "patient_name": "John Doe",
  "patient_email": "john@example.com",
  "patient_phone": "+1-555-0100",
  "reason": "Annual checkup"
}
```

### GET `/api/faq/search`
Search FAQ knowledge base.

**Query Parameters:**
- `query`: Search query string

### DELETE `/api/appointments/{booking_id}`
Cancel an appointment.

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings | Yes* | - |
| `CALENDLY_API_KEY` | Calendly API token | No | Mock mode |
| `CALENDLY_USER_URL` | Calendly user URL | No | - |
| `VECTOR_DB_PATH` | Path to vector database | No | `./data/vectordb` |
| `CLINIC_NAME` | Clinic name | No | HealthCare Plus Clinic |
| `CLINIC_PHONE` | Clinic phone number | No | +1-555-123-4567 |
| `TIMEZONE` | Timezone for scheduling | No | America/New_York |

*Required if using OpenAI embeddings. Can use sentence-transformers as fallback.

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed: `pip install -r requirements.txt`
2. **Vector DB Errors**: Delete `./data/vectordb` and restart to rebuild
3. **OpenAI API Errors**: Check API key is valid and has credits
4. **Port Already in Use**: Change `BACKEND_PORT` in `.env` or kill existing process

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🚧 Future Enhancements

- [ ] Support for multiple doctors/locations
- [ ] Appointment rescheduling flow
- [ ] SMS/Email notifications
- [ ] Integration with EHR systems
- [ ] Multi-language support
- [ ] Voice interface
- [ ] Analytics and reporting

## 📝 License

[Specify your license here]

## 👥 Contributors

[Add contributors here]

## 📧 Contact

For questions or support, please contact: [your-email@example.com]

