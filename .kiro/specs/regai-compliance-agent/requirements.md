# Requirements Document

## Introduction

RegAI is an AI-powered compliance agent that helps organizations navigate regulatory requirements. It uses Gemini AI to analyze documents, answer compliance questions, and surface relevant regulatory obligations. The system is built with a Next.js frontend, FastAPI backend, MongoDB Atlas for persistence, and Arize Phoenix for AI observability. It is designed to be deployed on Google Cloud Run and structured to support future agents and tools.

## Glossary

- **RegAI**: The AI compliance agent system described in this document
- **Compliance_Agent**: The core AI agent that processes regulatory queries and documents
- **Document_Processor**: The component responsible for ingesting and parsing uploaded compliance documents
- **Query_Engine**: The component that routes user questions to the Compliance_Agent and returns answers
- **Observability_Service**: The Arize Phoenix + OpenInference integration that traces and monitors AI calls
- **Auth_Service**: The component responsible for user authentication and session management
- **Storage_Service**: The MongoDB Atlas integration for persisting sessions, documents, and results
- **Frontend**: The Next.js + Tailwind web application
- **Backend**: The FastAPI application serving the REST API
- **User**: A person interacting with RegAI through the Frontend

## Requirements

### Requirement 1: Compliance Query Processing

**User Story:** As a compliance officer, I want to ask natural language questions about regulations, so that I can quickly get accurate answers without manually searching through documents.

#### Acceptance Criteria

1. WHEN a User submits a compliance query, THE Query_Engine SHALL forward the query to the Compliance_Agent and return a response within 30 seconds.
2. WHEN the Compliance_Agent generates a response, THE Observability_Service SHALL record a trace including the input, output, and latency of the AI call.
3. IF the Gemini API returns an error, THEN THE Query_Engine SHALL return a structured error response with an HTTP 502 status code and a descriptive message.
4. THE Query_Engine SHALL support queries of up to 4000 characters in length.
5. WHEN a response is generated, THE Storage_Service SHALL persist the query and response to MongoDB Atlas with a timestamp and session identifier.

---

### Requirement 2: Document Ingestion and Analysis

**User Story:** As a compliance officer, I want to upload regulatory documents, so that the agent can analyze them and answer questions based on their content.

#### Acceptance Criteria

1. WHEN a User uploads a document, THE Document_Processor SHALL accept PDF and plain text files up to 10 MB in size.
2. WHEN a document is successfully parsed, THE Document_Processor SHALL extract the text content and store it in the Storage_Service linked to the User's session.
3. IF a document exceeds 10 MB or is an unsupported file type, THEN THE Document_Processor SHALL return an HTTP 422 error with a descriptive validation message.
4. WHEN a document is stored, THE Compliance_Agent SHALL be able to reference its content when answering subsequent queries in the same session.
5. THE Document_Processor SHALL support concurrent uploads from multiple sessions without data cross-contamination.

---

### Requirement 3: Session Management

**User Story:** As a User, I want my conversation history to persist across page refreshes, so that I can continue a compliance review session without losing context.

#### Acceptance Criteria

1. WHEN a User starts a new session, THE Auth_Service SHALL generate a unique session token and return it to the Frontend.
2. WHILE a session is active, THE Storage_Service SHALL retain all queries, responses, and uploaded document references associated with that session.
3. WHEN a User returns with a valid session token, THE Frontend SHALL restore the conversation history from the Storage_Service.
4. IF a session token is invalid or expired, THEN THE Auth_Service SHALL return an HTTP 401 response and prompt the User to start a new session.
5. THE Storage_Service SHALL expire inactive sessions after 24 hours.

---

### Requirement 4: AI Observability and Tracing

**User Story:** As a developer, I want full traceability of every AI call, so that I can debug issues, monitor quality, and optimize the agent's performance.

#### Acceptance Criteria

1. THE Observability_Service SHALL instrument every call to the Gemini API using OpenInference trace attributes.
2. WHEN a trace is recorded, THE Observability_Service SHALL capture the model name, prompt tokens, completion tokens, latency, and status.
3. WHILE the Backend is running, THE Observability_Service SHALL expose a Phoenix UI endpoint for viewing traces.
4. IF an AI call exceeds 20 seconds, THEN THE Observability_Service SHALL log a warning with the trace ID and elapsed time.
5. THE Observability_Service SHALL support exporting traces to an OTLP-compatible collector for production use.

---

### Requirement 5: Frontend Compliance Chat Interface

**User Story:** As a User, I want a clean chat interface to interact with the compliance agent, so that I can ask questions and review answers in a familiar conversational format.

#### Acceptance Criteria

1. THE Frontend SHALL render a chat interface with an input field, send button, and scrollable message history.
2. WHEN a User submits a query, THE Frontend SHALL display a loading indicator until the Backend returns a response.
3. WHEN a response is received, THE Frontend SHALL render the agent's answer with markdown formatting support.
4. THE Frontend SHALL provide a file upload control that allows Users to attach documents to the current session.
5. IF the Backend returns an error response, THEN THE Frontend SHALL display a human-readable error message inline in the chat.
6. THE Frontend SHALL be responsive and render correctly on viewports from 375px to 1440px wide.

---

### Requirement 6: Modular Agent and Tool Architecture

**User Story:** As a developer, I want the backend structured to support multiple agents and tools, so that new compliance capabilities can be added without refactoring the core system.

#### Acceptance Criteria

1. THE Backend SHALL organize agents under a dedicated `agents/` module where each agent is an independent class or function.
2. THE Backend SHALL organize tools under a dedicated `tools/` module where each tool exposes a consistent interface callable by any agent.
3. WHEN a new agent is added to the `agents/` module, THE Backend SHALL register it without requiring changes to existing agent code.
4. THE Backend SHALL define a shared schema module for request and response models used across agents and tools.
5. THE Backend SHALL expose agent capabilities through versioned API routes under `/api/v1/`.

---

### Requirement 7: Deployment and Environment Configuration

**User Story:** As a developer, I want the project to be deployable to Google Cloud Run with minimal configuration, so that the team can ship quickly during the hackathon.

#### Acceptance Criteria

1. THE Backend SHALL include a `Dockerfile` that builds a production-ready container image.
2. THE Frontend SHALL include a `Dockerfile` that builds and serves the Next.js application.
3. THE Backend SHALL read all secrets and configuration from environment variables defined in `.env.example`.
4. THE Frontend SHALL read all public configuration from environment variables prefixed with `NEXT_PUBLIC_`.
5. IF a required environment variable is missing at startup, THEN THE Backend SHALL log a descriptive error and exit with a non-zero status code.
6. THE Backend SHALL include a `/health` endpoint that returns HTTP 200 when the service is ready to accept requests.
