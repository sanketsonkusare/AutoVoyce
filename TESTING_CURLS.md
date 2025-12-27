# Testing Curl Commands for AutoVoyce API

## Phase 1: Search Videos (`/upload`)

### Basic Search Request
```bash
curl -X POST "http://localhost:8000/upload" \
  -H "Content-Type: application/json" \
  -H "Cookie: session_id=optional" \
  -d '{
    "user_query": "best value for money iphones"
  }'
```

### Expected Response
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "namespace": "session_a1b2c3d4",
  "status": "search_complete",
  "videos": [
    {
      "id": "abc123xyz",
      "title": "Best iPhones for Students 2024",
      "channel": "TechReview Channel",
      "link": "https://www.youtube.com/watch?v=abc123xyz",
      "thumbnail": "https://i.ytimg.com/vi/abc123xyz/default.jpg",
      "duration": "10:30",
      "views": "1.2M"
    },
    {
      "id": "def456uvw",
      "title": "iPhone Value Comparison",
      "channel": "MobileTech",
      "link": "https://www.youtube.com/watch?v=def456uvw",
      "thumbnail": "https://i.ytimg.com/vi/def456uvw/default.jpg",
      "duration": "8:15",
      "views": "850K"
    }
  ],
  "message": "Found 2 videos. Please select which ones to process."
}
```

### Save Session ID for Phase 2
```bash
# Save the response to a variable (bash)
RESPONSE=$(curl -X POST "http://localhost:8000/upload" \
  -H "Content-Type: application/json" \
  -d '{"user_query": "best value for money iphones"}')

# Extract session_id (requires jq)
SESSION_ID=$(echo $RESPONSE | jq -r '.session_id')
echo "Session ID: $SESSION_ID"
```

---

## Phase 2: Process Selected Videos (`/upload/process`)

### Using Session ID from Cookie (Recommended)
```bash
# First, get the cookie from Phase 1 response
# Then use it in Phase 2

curl -X POST "http://localhost:8000/upload/process" \
  -H "Content-Type: application/json" \
  -H "Cookie: session_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -d '{
    "video_ids": ["abc123xyz", "def456uvw"]
  }'
```

### Using Session ID in Request Body
```bash
curl -X POST "http://localhost:8000/upload/process" \
  -H "Content-Type: application/json" \
  -d '{
    "video_ids": ["abc123xyz", "def456uvw"],
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }'
```

### Expected Response
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "namespace": "session_a1b2c3d4",
  "status": "processing",
  "video_count": 2,
  "message": "Processing 2 selected videos. You can start querying in a few moments."
}
```

---

## Complete Test Flow

### Step 1: Search for Videos
```bash
curl -X POST "http://localhost:8000/upload" \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "best value for money iphones"
  }' \
  -c cookies.txt \
  -v
```

**Note:** The `-c cookies.txt` flag saves cookies to a file, and `-v` shows verbose output including headers.

### Step 2: Extract Video IDs from Response
From the Phase 1 response, note the video IDs you want to process. For example:
- `abc123xyz`
- `def456uvw`

### Step 3: Process Selected Videos
```bash
curl -X POST "http://localhost:8000/upload/process" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{
    "video_ids": ["abc123xyz", "def456uvw"]
  }' \
  -v
```

**Note:** The `-b cookies.txt` flag loads cookies from the file saved in Step 1.

---

## Alternative: Single Command with Session ID

### Step 1: Search and Save Session ID
```bash
RESPONSE=$(curl -s -X POST "http://localhost:8000/upload" \
  -H "Content-Type: application/json" \
  -d '{"user_query": "best value for money iphones"}')

SESSION_ID=$(echo $RESPONSE | jq -r '.session_id')
echo "Session ID: $SESSION_ID"

# Display videos
echo $RESPONSE | jq '.videos[] | {id, title, channel}'
```

### Step 2: Process Videos (replace video IDs)
```bash
curl -X POST "http://localhost:8000/upload/process" \
  -H "Content-Type: application/json" \
  -d "{
    \"video_ids\": [\"abc123xyz\", \"def456uvw\"],
    \"session_id\": \"$SESSION_ID\"
  }"
```

---

## Testing Query Endpoint (After Processing)

Once videos are processed, you can query the knowledge base:

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -H "Cookie: session_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -d '{
    "user_query": "What are the best iPhones for students?"
  }'
```

Or with session_id in body:
```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{
    "user_query": "What are the best iPhones for students?",
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }'
```

---

## Error Cases

### Missing Session ID in Phase 2
```bash
curl -X POST "http://localhost:8000/upload/process" \
  -H "Content-Type: application/json" \
  -d '{
    "video_ids": ["abc123xyz"]
  }'
```

**Expected Error:**
```json
{
  "detail": "No active session. Please search for videos first."
}
```

### Empty Video IDs
```bash
curl -X POST "http://localhost:8000/upload/process" \
  -H "Content-Type: application/json" \
  -H "Cookie: session_id=a1b2c3d4-e5f6-7890-abcd-ef1234567890" \
  -d '{
    "video_ids": []
  }'
```

**Expected Error:**
```json
{
  "detail": "No video IDs provided. Please select at least one video."
}
```

### Invalid/Expired Session
```bash
curl -X POST "http://localhost:8000/upload/process" \
  -H "Content-Type: application/json" \
  -H "Cookie: session_id=invalid-session-id" \
  -d '{
    "video_ids": ["abc123xyz"]
  }'
```

**Expected Error:**
```json
{
  "detail": "Session not found or expired. Please search for videos again."
}
```

---

## Pretty Print JSON Responses

Add `| jq` to any curl command to pretty print JSON:

```bash
curl -X POST "http://localhost:8000/upload" \
  -H "Content-Type: application/json" \
  -d '{"user_query": "best value for money iphones"}' | jq
```

---

## Health Check

Test if the API is running:

```bash
curl http://localhost:8000/
```

**Expected Response:**
```json
{
  "message": "AutoVoyce API is running"
}
```

